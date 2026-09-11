"""Event-study backtester for catalyst data (autotrader's catalyst_training).

Your catalyst log is *event* data, not a price time series: each row is
"a catalyst fired for SYMBOL at time T with these metrics → it moved eod_pct by
end of day." The right way to test it is an event study, not a moving average.

This tool takes a strategy = a **filter + direction** over catalyst events
(e.g. "long every CONFIRMED earnings catalyst with confidence ≥ 60"), applies it
to the events in chronological order, and reports — separately for in-sample and
out-of-sample — the hit rate, expectancy per trade, an equity curve, and max
drawdown, all net of costs. The out-of-sample numbers are the honest verdict.

Because catalysts were logged whether or not they were traded, expectancy here
is the *true* base rate of the signal, free of the usual selection bias.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Any


def _num(x: Any) -> float | None:
    try:
        v = float(x)
        return v if v == v else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _truthy(x: Any) -> bool:
    return str(x).strip().lower() in ("true", "t", "1", "yes")


# Default column mapping matches the catalyst_training export. Override per field
# if your export differs.
DEFAULT_MAP = {
    "symbol": "symbol",
    "timestamp": "created_at",
    "catalyst_type": "catalyst_type",
    "score": "confidence",
    "positive": "positive",
    "confirmed": "confirmed",
    "outcome_pct": "eod_pct",
    "premarket_gap_pct": "premarket_gap_pct",
    "midday_pct": "midday_pct",
    "features": "features",
    "trade_result": "trade_result",
}


@dataclass
class Event:
    symbol: str
    timestamp: str
    catalyst_type: str
    score: float
    positive: bool
    confirmed: bool
    outcome_pct: float | None
    premarket_gap_pct: float | None
    midday_pct: float | None
    features: dict[str, Any]


def load_catalyst_csv(path: str, mapping: dict[str, str] | None = None) -> list[Event]:
    m = {**DEFAULT_MAP, **(mapping or {})}
    events: list[Event] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            feats: dict[str, Any] = {}
            raw = row.get(m["features"], "") or ""
            if raw.strip():
                try:
                    feats = json.loads(raw)
                except json.JSONDecodeError:
                    feats = {}
            events.append(
                Event(
                    symbol=row.get(m["symbol"], "") or "",
                    timestamp=row.get(m["timestamp"], "") or "",
                    catalyst_type=(row.get(m["catalyst_type"], "") or "").upper(),
                    score=_num(row.get(m["score"])) or 0.0,
                    positive=_truthy(row.get(m["positive"])),
                    confirmed=_truthy(row.get(m["confirmed"])),
                    outcome_pct=_num(row.get(m["outcome_pct"])),
                    premarket_gap_pct=_num(row.get(m["premarket_gap_pct"])),
                    midday_pct=_num(row.get(m["midday_pct"])),
                    features=feats,
                )
            )
    return events


@dataclass
class EventStrategy:
    """A filter + direction over catalyst events, backtested as trades."""

    direction: str = "long"                 # "long" | "short"
    min_score: float = 0.0
    require_positive: bool = False
    require_confirmed: bool = False
    catalyst_types: list[str] = field(default_factory=list)  # empty = all
    min_premarket_gap: float | None = None
    outcome_field: str = "outcome_pct"      # or "midday_pct"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "EventStrategy | None":
        if not d:
            return None
        p = d.get("params", d)
        return cls(
            direction=str(p.get("direction", "long")),
            min_score=float(p.get("min_score", p.get("min_confidence", 0.0))),
            require_positive=bool(p.get("require_positive", False)),
            require_confirmed=bool(p.get("require_confirmed", False)),
            catalyst_types=[str(t).upper() for t in p.get("catalyst_types", [])],
            min_premarket_gap=(
                float(p["min_premarket_gap"]) if p.get("min_premarket_gap") is not None else None
            ),
            outcome_field=str(p.get("outcome_field", "outcome_pct")),
        )

    def selects(self, e: Event) -> bool:
        if self.require_positive and not e.positive:
            return False
        if self.require_confirmed and not e.confirmed:
            return False
        if e.score < self.min_score:
            return False
        if self.catalyst_types and e.catalyst_type not in self.catalyst_types:
            return False
        if self.min_premarket_gap is not None:
            g = e.premarket_gap_pct
            if g is None or g < self.min_premarket_gap:
                return False
        return getattr(e, self.outcome_field) is not None


@dataclass
class PeriodStats:
    n_signals: int
    hit_rate: float
    expectancy_pct: float   # mean per-trade return after costs, in %
    avg_win_pct: float
    avg_loss_pct: float
    total_return: float
    max_drawdown: float
    per_trade_sharpe: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class EventBacktestResult:
    strategy: str
    params: dict[str, Any]
    in_sample: PeriodStats
    out_sample: PeriodStats
    passed: bool
    reason: str

    def evidence_quote(self) -> str:
        o = self.out_sample
        return (
            f"Out-of-sample: {o.n_signals} catalysts, hit rate {o.hit_rate * 100:.0f}%, "
            f"expectancy {o.expectancy_pct:+.2f}%/trade after costs, "
            f"total {o.total_return * 100:+.1f}%, max drawdown {o.max_drawdown * 100:.1f}%. "
            f"In-sample expectancy {self.in_sample.expectancy_pct:+.2f}%."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "params": self.params,
            "inSample": self.in_sample.to_dict(),
            "outSample": self.out_sample.to_dict(),
            "passed": self.passed,
            "reason": self.reason,
        }


def _stats(returns: list[float]) -> PeriodStats:
    """returns: per-trade fractional returns (after costs), in chronological order."""
    n = len(returns)
    if n == 0:
        return PeriodStats(0, 0, 0, 0, 0, 0, 0, 0)
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / n
    std = math.sqrt(var)
    return PeriodStats(
        n_signals=n,
        hit_rate=len(wins) / n,
        expectancy_pct=mean * 100,
        avg_win_pct=(sum(wins) / len(wins) * 100) if wins else 0.0,
        avg_loss_pct=(sum(losses) / len(losses) * 100) if losses else 0.0,
        total_return=equity - 1,
        max_drawdown=max_dd,
        per_trade_sharpe=(mean / std) if std > 0 else 0.0,
    )


class EventBacktestTool:
    """Backtests an EventStrategy over catalyst events with a time-based split."""

    def __init__(
        self,
        events: list[Event],
        train_frac: float = 0.6,
        cost_bps: float = 10.0,
        min_oos_expectancy_pct: float = 0.0,
        max_dd_limit: float = 0.25,
        min_signals: int = 10,
    ) -> None:
        # Chronological order is essential for an honest out-of-sample split.
        self.events = sorted(events, key=lambda e: e.timestamp)
        self.train_frac = train_frac
        self.cost = cost_bps / 10_000.0
        self.min_oos_expectancy_pct = min_oos_expectancy_pct
        self.max_dd_limit = max_dd_limit
        self.min_signals = min_signals

    def _returns(self, strat: EventStrategy, events: list[Event]) -> list[float]:
        sign = -1.0 if strat.direction == "short" else 1.0
        out: list[float] = []
        for e in events:
            if not strat.selects(e):
                continue
            pct = getattr(e, strat.outcome_field)
            out.append(sign * (pct / 100.0) - self.cost)
        return out

    def run(self, strat: EventStrategy) -> EventBacktestResult:
        split = int(len(self.events) * self.train_frac)
        train_ev, test_ev = self.events[:split], self.events[split:]
        in_s = _stats(self._returns(strat, train_ev))
        out_s = _stats(self._returns(strat, test_ev))

        reasons = []
        if out_s.n_signals < self.min_signals:
            reasons.append(
                f"only {out_s.n_signals} out-of-sample signals (< {self.min_signals})"
            )
        if out_s.expectancy_pct < self.min_oos_expectancy_pct:
            reasons.append(
                f"OOS expectancy {out_s.expectancy_pct:+.2f}% < "
                f"{self.min_oos_expectancy_pct:.2f}%"
            )
        if out_s.max_drawdown > self.max_dd_limit:
            reasons.append(
                f"OOS drawdown {out_s.max_drawdown * 100:.1f}% > "
                f"{self.max_dd_limit * 100:.0f}% limit"
            )
        passed = not reasons
        params = {
            "direction": strat.direction,
            "min_score": strat.min_score,
            "require_positive": strat.require_positive,
            "require_confirmed": strat.require_confirmed,
            "catalyst_types": strat.catalyst_types,
            "min_premarket_gap": strat.min_premarket_gap,
            "outcome_field": strat.outcome_field,
        }
        return EventBacktestResult(
            strategy="catalyst_filter",
            params=params,
            in_sample=in_s,
            out_sample=out_s,
            passed=passed,
            reason="Passed out-of-sample gate." if passed else "; ".join(reasons),
        )

    # Unified oracle interface used by the orchestrator.
    def evaluate(self, strategy_dict: dict | None):
        # Only act on catalyst filters; ignore price-strategy specs.
        if strategy_dict and strategy_dict.get("strategy") not in (None, "catalyst_filter"):
            return None
        strat = EventStrategy.from_dict(strategy_dict)
        if strat is None:
            return None
        r = self.run(strat)
        return _OracleResult(r.passed, r.evidence_quote(), r.to_dict())


@dataclass
class _OracleResult:
    passed: bool
    quote: str
    payload: dict
