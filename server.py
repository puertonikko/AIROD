"""FastAPI HTTP wrapper around the AIROD core — the backend deployed on Railway.

Exposes the orchestration loop over HTTP so the Vercel dashboard can drive real
model runs (no serverless time limit, persistent memory on a Railway volume).

Endpoints:
    GET  /health   liveness probe
    POST /run      run a mission and return the full transcript

The /run response is serialized in the camelCase shape the Next.js UI expects
(see web/lib/types.ts), so the same UI renders mock and live runs identically.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from airod.agents import load_agents
from airod.cli import build_backtest_tool
from airod.llm import LLMClient
from airod.memory import Memory
from airod.models import Hypothesis, Mission
from airod.orchestrator import Orchestrator, RoundResult

AGENTS_PATH = os.environ.get("AIROD_AGENTS", "config/agents.yaml")
DB_PATH = os.environ.get("AIROD_DB", "airod_memory.db")

app = FastAPI(title="AIROD backend", version="0.1.0")

# The browser never calls this directly (the Vercel route proxies server-side),
# but allow it so the API is usable standalone too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    title: str = "Untitled mission"
    goal: str = ""
    rounds: int = 3
    budget_usd: float = 5.0
    mock: bool | None = None  # force mock; None = auto (mock if no API key)
    # Optional: run a different team and turn on the backtest oracle (trading).
    agents_path: str = AGENTS_PATH
    oracle: str | None = None            # "backtest" enables the oracle
    backtest: dict = {}                  # oracle config (see mission.trading.yaml)


def _blurb(system_prompt: str) -> str:
    """First sentence of the agent's system prompt, for the UI card."""
    text = " ".join(system_prompt.split())
    for end in (". ", ".\n"):
        if end in text:
            return text.split(end)[0].strip() + "."
    return text[:120]


def _serialize_round(r: RoundResult) -> dict:
    h: Hypothesis = r.hypothesis
    return {
        "roundIndex": r.round_index,
        "newSupportedClaims": r.new_supported_claims,
        "hypothesis": {
            "statement": h.statement,
            "prediction": h.prediction,
            "confidence": h.confidence,
            "status": h.status.value,
            "roundIndex": h.round_index,
            "claims": [
                {
                    "text": c.text,
                    "status": c.status.value,
                    "evidence": [
                        {"source": e.source, "quote": e.quote, "relevance": e.relevance}
                        for e in c.evidence
                    ],
                }
                for c in h.claims
            ],
            "critiques": [
                {"authorRole": cr.author_role, "text": cr.text, "leverage": cr.leverage}
                for cr in h.critiques
            ],
            "strategy": h.strategy,
            "backtest": h.backtest,
        },
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "hasKey": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/run")
def run(req: RunRequest) -> dict:
    use_mock = req.mock if req.mock is not None else not os.environ.get("ANTHROPIC_API_KEY")

    mission = Mission(
        title=req.title,
        goal=req.goal,
        budget_usd=req.budget_usd,
    )
    memory = Memory(DB_PATH)
    mission.id = memory.create_mission(mission)

    agents = load_agents(req.agents_path)
    llm = LLMClient(mock=use_mock)
    tool = build_backtest_tool({"oracle": req.oracle, "backtest": req.backtest})
    orch = Orchestrator(mission, agents, llm, memory, verbose=False, backtest_tool=tool)
    results = orch.run(max_rounds=req.rounds)

    payload = {
        "mode": "mock" if use_mock else "live",
        "mission": {"title": mission.title, "goal": mission.goal, "rounds": req.rounds},
        "agents": [
            {
                "name": a.name,
                "role": a.role,
                "model": a.model,
                "blurb": _blurb(a.system_prompt),
            }
            for a in agents.values()
        ],
        "rounds": [_serialize_round(r) for r in results],
        "costUsd": memory.total_cost(mission.id),
    }
    memory.close()
    return payload
