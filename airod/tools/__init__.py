"""Tools the agents and orchestrator can call to test claims against reality."""

from .backtest import (
    BacktestResult,
    BacktestTool,
    StrategySpec,
    synthetic_prices,
)
from .event_backtest import (
    Event,
    EventBacktestTool,
    EventStrategy,
    load_catalyst_csv,
)

__all__ = [
    "BacktestResult",
    "BacktestTool",
    "StrategySpec",
    "synthetic_prices",
    "Event",
    "EventBacktestTool",
    "EventStrategy",
    "load_catalyst_csv",
]
