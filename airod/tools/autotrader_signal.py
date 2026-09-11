"""Adapter that turns autotrader's /predict service into a backtest signal.

This is the concrete wiring between AIROD's backtester and the autotrader AI
layer. The backtester's ``signal_threshold`` strategy calls this to get a
probability per day; if the probability clears the threshold, it goes long.

Backtesting on this signal finally answers the question autotrader's own README
poses — "is the model adding real edge?" — by measuring, out-of-sample and net
of costs, whether trading on its score makes money.

Contract (autotrader/AI/server.py):  POST /predict {symbol, features} -> {ai_score}
The service neutral-defaults any feature we omit and falls back to a rule-based
score when the model is untrained, so a price-only feature subset is valid input.

Uses stdlib urllib so AIROD gains no new dependency. Any error → neutral 0.5.
"""

from __future__ import annotations

import json
import urllib.request


def _ema(series: list[float], n: int) -> float:
    k = 2 / (n + 1)
    ema = series[0]
    for p in series[1:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rsi(prices: list[float], n: int = 14) -> float:
    if len(prices) <= n:
        return 50.0
    gains = losses = 0.0
    for i in range(len(prices) - n, len(prices)):
        change = prices[i] - prices[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def features_from_prices(prices: list[float]) -> dict:
    """Compute the price-derived subset of autotrader's feature vector.

    Catalyst/options/float features (earnings, sweeps, short interest) aren't
    derivable from closes, so they're left out and the service defaults them —
    which is the honest state of a pure-price backtest.
    """
    price = prices[-1]
    prev_close = prices[-2] if len(prices) >= 2 else price
    ema9 = _ema(prices[-30:], 9) if len(prices) >= 9 else price
    ema20 = _ema(prices[-60:], 20) if len(prices) >= 20 else price
    ema50 = _ema(prices[-120:], 50) if len(prices) >= 50 else price
    window = prices[-20:]
    return {
        "price": price,
        "prev_close": prev_close,
        "gap_pct": (price / prev_close - 1) * 100 if prev_close else 0.0,
        "rsi": _rsi(prices),
        "ema9_above_ema20": ema9 > ema20,
        "ema20_above_ema50": ema20 > ema50,
        "daily_above_ema20": price > ema20,
        "daily_above_ema50": price > ema50,
        "daily_higher_highs": price >= max(window),
        "spy_regime": True,
    }


class AutotraderSignal:
    """Callable signal provider backed by the autotrader /predict endpoint."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.url = base_url.rstrip("/") + "/predict"
        self.timeout = timeout

    def __call__(self, symbol: str, prices: list[float]) -> float:
        try:
            payload = json.dumps(
                {"symbol": symbol, "features": features_from_prices(prices)}
            ).encode()
            req = urllib.request.Request(
                self.url, data=payload, headers={"content-type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
            return float(data.get("ai_score", 0.5))
        except Exception:
            return 0.5  # neutral on any failure — never crash the backtest
