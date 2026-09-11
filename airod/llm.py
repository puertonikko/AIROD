"""The model layer — one wrapper the agents call to talk to Claude.

Responsibilities:
  * Send a structured request and return parsed JSON.
  * Track token cost against the mission budget.
  * Provide a ``--mock`` mode so the whole loop runs offline, with no API key
    and no spend, producing role-appropriate structured output.

Defaults follow current guidance: adaptive thinking, and per-agent model choice
(strong models for synthesis/judging, cheaper models for high-volume work).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# USD per 1M tokens (input, output). Cached rates; adjust as pricing changes.
_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5-1": (10.0, 50.0),
}
_DEFAULT_PRICE = (5.0, 25.0)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = _PRICES.get(model, _DEFAULT_PRICE)
    return input_tokens / 1_000_000 * pin + output_tokens / 1_000_000 * pout


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the first balanced {...} span.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class BudgetExceeded(RuntimeError):
    """Raised before a call that would push a mission over its budget."""


class LLMClient:
    def __init__(self, mock: bool = False) -> None:
        self.mock = mock
        self._client = None  # lazy — mock mode needs no SDK

    def _anthropic(self):
        if self._client is None:
            import anthropic  # imported lazily so mock mode has no hard dep

            self._client = anthropic.Anthropic()
        return self._client

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str,
        agent_role: str,
        schema: dict,
    ) -> tuple[dict, Usage]:
        """Return (parsed_json, usage). Raises on unparseable real responses."""
        if self.mock:
            return _mock_response(agent_role, user), Usage(
                input_tokens=len(user) // 4,
                output_tokens=120,
                cost_usd=0.0,
            )

        client = self._anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=system,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        data = _extract_json(text)
        usage = Usage(
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cost_usd=estimate_cost(model, resp.usage.input_tokens, resp.usage.output_tokens),
        )
        return data, usage


# --------------------------------------------------------------------------
# Mock responses — deterministic, role-appropriate output so the loop runs
# end-to-end offline. These are intentionally generic; they demonstrate the
# SHAPE of collaboration, not real research.
# --------------------------------------------------------------------------
def _mock_response(role: str, context: str) -> dict:
    snippet = " ".join(context.split()[:12])
    if role == "proposer":
        return {
            "statement": "A sulfide-based solid electrolyte with a thin protective "
            "interlayer is the most promising path to the target energy density.",
            "prediction": "At 25 C, interface resistance stays below 30 ohm-cm^2 "
            "over 1000 cycles.",
            "claims": [
                "Sulfide electrolytes reach ionic conductivity comparable to liquid electrolytes.",
                "A protective interlayer suppresses lithium dendrite formation at high rates.",
            ],
        }
    if role == "researcher":
        return {
            "findings": [
                {
                    "claim": "Sulfide electrolytes reach high ionic conductivity.",
                    "evidence": [
                        {
                            "source": "mock_source.md",
                            "quote": "Argyrodite sulfide electrolytes exhibit room-temperature "
                            "ionic conductivities on the order of 10 mS/cm.",
                            "relevance": "Supports the conductivity claim.",
                        }
                    ],
                },
                {
                    "claim": "Interlayers suppress dendrites.",
                    "evidence": [],
                },
            ]
        }
    if role == "critic":
        return {
            "critiques": [
                {
                    "text": "The dendrite-suppression claim has no cited evidence and is the "
                    "load-bearing assumption for cycle life.",
                    "leverage": 9,
                },
                {
                    "text": "Interface resistance below 30 ohm-cm^2 at 25 C is optimistic "
                    "versus reported values.",
                    "leverage": 6,
                },
            ]
        }
    if role == "skeptic":
        return {
            "failure_modes": [
                "Dendrites still nucleate at grain boundaries above 4C charging.",
                "Sulfide electrolytes react with moisture, complicating manufacturing.",
                "Thin interlayers may not survive volume changes over 1000 cycles.",
            ]
        }
    if role == "judge":
        return {
            "claim_scores": [
                {"claim": "high ionic conductivity", "status": "supported"},
                {"claim": "interlayer suppresses dendrites", "status": "unsupported"},
            ],
            "confidence": 0.45,
            "rationale": "Conductivity is supported by a quoted source; the dendrite "
            "claim has no evidence and is heavily contested. Advance with the "
            "dendrite claim demoted to an open question.",
        }
    return {"note": f"mock output for role={role}: {snippet}"}
