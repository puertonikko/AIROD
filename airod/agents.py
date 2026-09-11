"""Agents — one specialist per job.

An agent bundles a role, a model, a system prompt, and (optionally) a knowledge
sector it retrieves from. Each role has a fixed JSON output contract so the
orchestrator can route on structured results instead of parsing prose.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from .knowledge import KnowledgeSector
from .llm import LLMClient, Usage

# JSON schemas per role. Kept permissive (additionalProperties allowed) so a
# real model has room, while the fields the orchestrator reads are required.
_SCHEMAS: dict[str, dict] = {
    "proposer": {
        "type": "object",
        "properties": {
            "statement": {"type": "string"},
            "prediction": {"type": "string"},
            "claims": {"type": "array", "items": {"type": "string"}},
            # Optional: a machine-runnable strategy the oracle can backtest.
            # Only trading missions fill this in.
            "strategy": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "required": ["statement", "prediction", "claims"],
    },
    "researcher": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "quote": {"type": "string"},
                                    "relevance": {"type": "string"},
                                },
                                "required": ["source", "quote"],
                            },
                        },
                    },
                    "required": ["claim", "evidence"],
                },
            }
        },
        "required": ["findings"],
    },
    "critic": {
        "type": "object",
        "properties": {
            "critiques": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "leverage": {"type": "integer"},
                    },
                    "required": ["text", "leverage"],
                },
            }
        },
        "required": ["critiques"],
    },
    "skeptic": {
        "type": "object",
        "properties": {
            "failure_modes": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["failure_modes"],
    },
    "risk": {
        "type": "object",
        "properties": {
            "risks": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["risks"],
    },
    "ideator": {
        "type": "object",
        "properties": {
            "angles": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["angles"],
    },
    "judge": {
        "type": "object",
        "properties": {
            "claim_scores": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["supported", "contested", "unsupported"],
                        },
                    },
                    "required": ["claim", "status"],
                },
            },
            "confidence": {"type": "number"},
            "rationale": {"type": "string"},
        },
        "required": ["claim_scores", "confidence"],
    },
}


@dataclass
class Agent:
    name: str
    role: str
    model: str
    system_prompt: str
    sector: KnowledgeSector | None = None
    web: bool = False  # if True, the agent pulls outside info via web search

    def schema(self) -> dict:
        return _SCHEMAS.get(self.role, {"type": "object"})

    def run(self, llm: LLMClient, task: str) -> tuple[dict, Usage]:
        """Call the model for this agent's task and return (result, usage).

        Grounding sources, in order of preference:
          * web research (if ``web`` is set) — outside information the agent finds
          * a local knowledge sector — documents the user provided
        Both are injected into the prompt so the agent grounds its output.
        """
        user = task
        extra_usage = Usage()

        if self.web:
            notes, wusage = llm.research(task, model=self.model)
            extra_usage = wusage
            if notes:
                user = f"{user}\n\n--- Web research notes (cite these) ---\n{notes}"

        if self.sector is not None and not self.sector.is_empty:
            passages = self.sector.retrieve(task, k=4)
            if passages:
                block = "\n\n".join(f"[{p.source}] {p.text}" for p in passages)
                user = (
                    f"{user}\n\n--- Retrieved source passages (quote from these) ---\n{block}"
                )

        result, usage = llm.complete_json(
            system=self.system_prompt,
            user=user,
            model=self.model,
            agent_role=self.role,
            schema=self.schema(),
        )
        usage.input_tokens += extra_usage.input_tokens
        usage.output_tokens += extra_usage.output_tokens
        usage.cost_usd += extra_usage.cost_usd
        return result, usage


def load_agents(config_path: str) -> dict[str, Agent]:
    """Build the agent roster from a YAML config file."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    agents: dict[str, Agent] = {}
    for entry in cfg.get("agents", []):
        sector = None
        if entry.get("sector"):
            sector = KnowledgeSector(entry["sector"])
        agent = Agent(
            name=entry["name"],
            role=entry["role"],
            model=entry["model"],
            system_prompt=entry["system_prompt"].strip(),
            sector=sector,
            web=bool(entry.get("web", False)),
        )
        agents[agent.role] = agent
    return agents
