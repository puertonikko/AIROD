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
    ctx_lower = context.lower()
    # Distinctive phrases only in the catalyst mission's own text — avoids matching
    # the generic word "catalysts" that appears in the trading knowledge docs.
    catalyst = "catalyst filter" in ctx_lower or "catalyst event" in ctx_lower
    # Finance terms that appear in trading/catalyst hypotheses (for the attacker
    # roles, whose only context is the hypothesis text), but not battery ones.
    trading = catalyst or any(
        w in ctx_lower
        for w in (
            "strateg", "trading", "backtest", "sharpe", "crossover",
            "momentum", "catalyst", "expectancy", "out-of-sample", "drawdown", "edge",
        )
    )

    if role == "proposer" and catalyst:
        return {
            "statement": "Confirmed catalysts with a high confidence score carry a "
            "positive same-day edge; trading only that subset filters out the noise.",
            "prediction": "Out-of-sample expectancy is positive after costs when "
            "filtering to confirmed catalysts with confidence >= 60.",
            "claims": [
                "Filtering to confirmed, high-confidence catalysts has positive "
                "out-of-sample expectancy after costs.",
                "The filter keeps enough signals to be tradable.",
            ],
            "strategy": {
                "strategy": "catalyst_filter",
                "params": {
                    "direction": "long",
                    "require_confirmed": True,
                    "min_score": 60,
                    "outcome_field": "outcome_pct",
                },
            },
        }
    if role == "proposer" and trading:
        return {
            "statement": "A simple moving-average crossover captures momentum with "
            "controlled turnover, giving a positive risk-adjusted return net of costs.",
            "prediction": "Out-of-sample Sharpe stays above 0.5 after 5bps costs, with "
            "max drawdown under 20%.",
            "claims": [
                "The crossover strategy has a positive out-of-sample Sharpe after costs.",
                "Turnover is low enough that transaction costs do not erase the edge.",
            ],
            "strategy": {"strategy": "sma_crossover", "params": {"fast": 10, "slow": 50}},
        }
    if role == "risk":
        return {
            "risks": [
                "Position sizing must cap per-trade risk; a crossover can whipsaw in "
                "choppy regimes and stack losses.",
                "Max drawdown budget should force de-risking before capital is impaired.",
                "Edge measured on one synthetic/limited history may not survive regime change.",
            ]
        }
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
    if role == "researcher" and trading:
        # The backtest oracle is the grounding here; don't attach unrelated quotes.
        return {"findings": []}
    if role == "critic" and trading:
        return {
            "critiques": [
                {
                    "text": "In-sample Sharpe far exceeds out-of-sample — a classic "
                    "overfitting signature the backtest split should expose.",
                    "leverage": 8,
                },
                {
                    "text": "The edge claim rests on one price history; parameters may be "
                    "curve-fit to it.",
                    "leverage": 6,
                },
            ]
        }
    if role == "skeptic" and trading:
        return {
            "failure_modes": [
                "Edge evaporates once realistic slippage and spread are modeled.",
                "Momentum crossovers whipsaw and bleed in range-bound regimes.",
                "Survivorship or lookahead bias in the data would inflate returns.",
            ]
        }
    if role == "judge" and trading:
        return {
            "claim_scores": [
                {"claim": "positive out-of-sample Sharpe after costs", "status": "supported"},
                {"claim": "turnover low enough that costs do not erase edge", "status": "contested"},
            ],
            "confidence": 0.55,
            "rationale": "The backtest oracle supports positive OOS Sharpe after costs; "
            "turnover is borderline and regime dependence remains a real risk.",
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
