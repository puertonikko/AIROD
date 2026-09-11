"""A real, self-contained backtester — the oracle that grounds trading claims.

This is the piece that turns "this strategy is great" from confident text into
evidence. It runs a strategy over price history with an **out-of-sample split**
and realistic costs, then reports metrics separately for the in-sample and
out-of-sample periods. The out-of-sample numbers are what the orchestrator
scores against — that's what catches overfitting.

Pure Python (no numpy) so it runs anywhere. Prices come from a CSV of closes or
from a deterministic synthetic generator, so the whole thing works offline for
demos and tests. A strategy can also consume an external probability signal —
that is the plug for autotrader's /predict model (see SignalProvider).

Nothing here promises profit. Its job is to *falsify* strategies quickly and
report honestly, costs included.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Sequence

TRADING_DAYS = 252


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def synthetic_prices(
    symbols: Sequence[str],
    days: int = 750,
    seed: int = 7,
    ar: float = 0.08,
    daily_vol: float = 0.02,
    drift: float = 0.0002,
) -> dict[str, list[float]]:
    """Deterministic synthetic daily closes with mild return autocorrelation.

    The AR(1) term gives momentum/mean-reversion strategies something real to
    find, without baking in a guaranteed edge. Same seed → same series.
    """
    out: dict[str, list[float]] = {}
    rng = random.Random(seed)
    for s in symbols:
        prev_ret = 0.0
        price = 100.0
        series = [price]
        for _ in range(days):
            shock = rng.gauss(0, daily_vol)
            ret = drift + ar * prev_ret + shock
            price *= math.exp(ret)
            series.append(price)
            prev_ret = ret
        out[s] = series
    return out


def load_prices_csv(path: str) -> dict[str, list[float]]:
    """Load closes from a CSV. Wide format: header ``date,SYM1,SYM2,...``."""
    import csv

    cols: dict[str, list[float]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        symbols = [c for c in (reader.fieldnames or []) if c.lower() != "date"]
        for s in symbols:
            cols[s] = []
        for row in reader:
            for s in symbols:
                try:
                    cols[s].append(float(row[s]))
                except (TypeError, ValueError):
                    pass
    return cols


# A signal provider maps (symbol, price_history_up_to_t) -> probability in [0,1].
SignalProvider = Callable[[str, list[float]], float]


# --------------------------------------------------------------------------
# Specs and results
# --------------------------------------------------------------------------
@dataclass
class StrategySpec:
    """A machine-runnable strategy the Proposer emits and the tool executes."""

    strategy: str  # "sma_crossover" | "rsi_reversion" | "signal_threshold"
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "StrategySpec | None":
        if not d or not d.get("strategy"):
            return None
        return cls(strategy=str(d["strategy"]), params=dict(d.get("params", {})))


@dataclass
class PeriodMetrics:
    total_return: float
    cagr: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    n_trades: int

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class BacktestResult:
    spec: StrategySpec
    in_sample: PeriodMetrics
    out_sample: PeriodMetrics
    passed: bool
    reason: str

    def evidence_quote(self) -> str:
        o = self.out_sample
        return (
            f"Out-of-sample: Sharpe {o.sharpe:.2f}, return {o.total_return * 100:.1f}%, "
            f"max drawdown {o.max_drawdown * 100:.1f}%, {o.n_trades} trades "
            f"(after costs). In-sample Sharpe {self.in_sample.sharpe:.2f}."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.spec.strategy,
            "params": self.spec.params,
            "inSample": self.in_sample.to_dict(),
            "outSample": self.out_sample.to_dict(),
            "passed": self.passed,
            "reason": self.reason,
        }


# --------------------------------------------------------------------------
# Strategy signals: each returns a target position per day in {-1, 0, 1}
# using ONLY information available up to that day (no lookahead).
# --------------------------------------------------------------------------
def _sma(series: list[float], n: int, t: int) -> float | None:
    if t + 1 < n:
        return None
    return sum(series[t + 1 - n : t + 1]) / n


def _positions_sma_crossover(prices: list[float], params: dict) -> list[int]:
    fast = int(params.get("fast", 10))
    slow = int(params.get("slow", 50))
    pos = [0] * len(prices)
    for t in range(len(prices)):
        f, s = _sma(prices, fast, t), _sma(prices, slow, t)
        if f is None or s is None:
            continue
        pos[t] = 1 if f > s else 0
    return pos


def _rsi(prices: list[float], n: int, t: int) -> float | None:
    if t < n:
        return None
    gains = losses = 0.0
    for i in range(t - n + 1, t + 1):
        change = prices[i] - prices[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def _positions_rsi_reversion(prices: list[float], params: dict) -> list[int]:
    n = int(params.get("period", 14))
    low = float(params.get("buy_below", 30))
    high = float(params.get("exit_above", 55))
    pos = [0] * len(prices)
    holding = 0
    for t in range(len(prices)):
        r = _rsi(prices, n, t)
        if r is None:
            continue
        if holding == 0 and r < low:
            holding = 1
        elif holding == 1 and r > high:
            holding = 0
        pos[t] = holding
    return pos


def _positions_signal_threshold(
    prices: list[float], params: dict, symbol: str, signal: SignalProvider | None
) -> list[int]:
    """Go long when an external probability signal exceeds a threshold.

    This is the autotrader integration point: pass a SignalProvider that calls
    the /predict service. With no provider, a synthetic momentum proxy stands in
    so the strategy is still runnable (clearly not the real model).
    """
    threshold = float(params.get("threshold", 0.55))
    pos = [0] * len(prices)
    for t in range(len(prices)):
        if signal is not None:
            p = signal(symbol, prices[: t + 1])
        else:
            # Synthetic proxy: 5-day momentum squashed to [0,1]. Placeholder only.
            if t < 5:
                continue
            mom = prices[t] / prices[t - 5] - 1
            p = 1 / (1 + math.exp(-25 * mom))
        pos[t] = 1 if p >= threshold else 0
    return pos


def _positions(
    prices: list[float], spec: StrategySpec, symbol: str, signal: SignalProvider | None
) -> list[int]:
    if spec.strategy == "sma_crossover":
        return _positions_sma_crossover(prices, spec.params)
    if spec.strategy == "rsi_reversion":
        return _positions_rsi_reversion(prices, spec.params)
    if spec.strategy == "signal_threshold":
        return _positions_signal_threshold(prices, spec.params, symbol, signal)
    raise ValueError(f"Unknown strategy: {spec.strategy}")


# --------------------------------------------------------------------------
# The engine
# --------------------------------------------------------------------------
def _metrics(daily_returns: list[float], n_trades: int) -> PeriodMetrics:
    n = len(daily_returns)
    if n == 0:
        return PeriodMetrics(0, 0, 0, 0, 0, n_trades)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    wins = in_market = 0
    for r in daily_returns:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        if r != 0:
            in_market += 1
            if r > 0:
                wins += 1
    mean = sum(daily_returns) / n
    var = sum((r - mean) ** 2 for r in daily_returns) / n
    std = math.sqrt(var)
    sharpe = (mean / std) * math.sqrt(TRADING_DAYS) if std > 0 else 0.0
    cagr = equity ** (TRADING_DAYS / n) - 1 if equity > 0 else -1.0
    return PeriodMetrics(
        total_return=equity - 1,
        cagr=cagr,
        sharpe=sharpe,
        max_drawdown=max_dd,
        win_rate=(wins / in_market) if in_market else 0.0,
        n_trades=n_trades,
    )


class BacktestTool:
    """Runs a StrategySpec over a price panel with an out-of-sample split."""

    def __init__(
        self,
        prices: dict[str, list[float]],
        train_frac: float = 0.6,
        cost_bps: float = 5.0,
        min_oos_sharpe: float = 0.3,
        max_dd_limit: float = 0.25,
        min_trades: int = 5,
        signal: SignalProvider | None = None,
    ) -> None:
        self.prices = prices
        self.train_frac = train_frac
        self.cost = cost_bps / 10_000.0
        self.min_oos_sharpe = min_oos_sharpe
        self.max_dd_limit = max_dd_limit
        self.min_trades = min_trades
        self.signal = signal

    def _portfolio_returns(self, spec: StrategySpec) -> list[float]:
        """Equal-weight daily portfolio returns across all symbols."""
        per_symbol: list[list[float]] = []
        self._last_trades = 0
        for symbol, series in self.prices.items():
            pos = _positions(series, spec, symbol, self.signal)
            rets: list[float] = []
            trades = 0
            for t in range(1, len(series)):
                asset_ret = series[t] / series[t - 1] - 1
                held = pos[t - 1]  # act on prior day's signal (no lookahead)
                turnover = abs(pos[t - 1] - (pos[t - 2] if t >= 2 else 0))
                if turnover:
                    trades += 1
                rets.append(held * asset_ret - turnover * self.cost)
            per_symbol.append(rets)
            self._last_trades += trades
        if not per_symbol:
            return []
        length = min(len(r) for r in per_symbol)
        return [sum(r[i] for r in per_symbol) / len(per_symbol) for i in range(length)]

    def run(self, spec: StrategySpec) -> BacktestResult:
        returns = self._portfolio_returns(spec)
        split = int(len(returns) * self.train_frac)
        train, test = returns[:split], returns[split:]
        # Attribute trades proportionally to each window for reporting.
        tr_train = int(self._last_trades * self.train_frac)
        tr_test = self._last_trades - tr_train
        in_s = _metrics(train, tr_train)
        out_s = _metrics(test, tr_test)

        reasons = []
        if out_s.sharpe < self.min_oos_sharpe:
            reasons.append(
                f"OOS Sharpe {out_s.sharpe:.2f} < {self.min_oos_sharpe:.2f}"
            )
        if out_s.max_drawdown > self.max_dd_limit:
            reasons.append(
                f"OOS max drawdown {out_s.max_drawdown * 100:.1f}% > "
                f"{self.max_dd_limit * 100:.0f}% limit"
            )
        if out_s.n_trades < self.min_trades:
            reasons.append(f"only {out_s.n_trades} OOS trades (< {self.min_trades})")
        passed = not reasons
        reason = "Passed out-of-sample gate." if passed else "; ".join(reasons)
        return BacktestResult(
            spec=spec, in_sample=in_s, out_sample=out_s, passed=passed, reason=reason
        )
