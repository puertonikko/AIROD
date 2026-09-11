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

    def schema(self) -> dict:
        return _SCHEMAS.get(self.role, {"type": "object"})

    def run(self, llm: LLMClient, task: str) -> tuple[dict, Usage]:
        """Call the model for this agent's task and return (result, usage).

        If the agent has a knowledge sector, relevant passages are retrieved and
        injected so the agent grounds its output in real quoted text.
        """
        user = task
        if self.sector is not None and not self.sector.is_empty:
            passages = self.sector.retrieve(task, k=4)
            if passages:
                block = "\n\n".join(
                    f"[{p.source}] {p.text}" for p in passages
                )
                user = (
                    f"{task}\n\n--- Retrieved source passages (quote from these) ---\n{block}"
                )
        return llm.complete_json(
            system=self.system_prompt,
            user=user,
            model=self.model,
            agent_role=self.role,
            schema=self.schema(),
        )


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
        )
        agents[agent.role] = agent
    return agents
