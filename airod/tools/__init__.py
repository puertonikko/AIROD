"""Tools the agents and orchestrator can call to test claims against reality."""

from .backtest import (
    BacktestResult,
    BacktestTool,
    StrategySpec,
    synthetic_prices,
)

__all__ = ["BacktestResult", "BacktestTool", "StrategySpec", "synthetic_prices"]
