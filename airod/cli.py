"""Command-line entry point for AIROD."""

from __future__ import annotations

import argparse

import yaml

from .agents import load_agents
from .llm import LLMClient
from .memory import Memory
from .models import Mission
from .orchestrator import Orchestrator
from .tools.backtest import BacktestTool, load_prices_csv, synthetic_prices


def _load_cfg(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _mission_from_cfg(cfg: dict) -> Mission:
    return Mission(
        title=cfg["title"],
        goal=cfg["goal"],
        success_criteria=cfg.get("success_criteria", []),
        budget_usd=float(cfg.get("budget_usd", 5.0)),
        stall_rounds=int(cfg.get("stall_rounds", 2)),
    )


def build_backtest_tool(cfg: dict) -> BacktestTool | None:
    """Construct the backtest oracle from a mission's `backtest:` block."""
    if cfg.get("oracle") != "backtest":
        return None
    bt = cfg.get("backtest", {})
    data = bt.get("data", {})
    if isinstance(data, dict) and data.get("csv"):
        prices = load_prices_csv(data["csv"])
    else:
        prices = synthetic_prices(
            symbols=list(data.get("symbols", ["AAA", "BBB", "CCC"])),
            days=int(data.get("days", 750)),
            seed=int(data.get("seed", 7)),
        )
    # Optional signal provider for the signal_threshold strategy. Wiring in
    # autotrader's /predict service turns "does the model add edge?" into a
    # measurable, out-of-sample question.
    signal = None
    sig = bt.get("signal", {})
    if isinstance(sig, dict) and sig.get("type") == "autotrader" and sig.get("url"):
        from .tools.autotrader_signal import AutotraderSignal

        signal = AutotraderSignal(sig["url"])

    return BacktestTool(
        prices,
        train_frac=float(bt.get("train_frac", 0.6)),
        cost_bps=float(bt.get("cost_bps", 5.0)),
        min_oos_sharpe=float(bt.get("min_oos_sharpe", 0.3)),
        max_dd_limit=float(bt.get("max_dd_limit", 0.25)),
        min_trades=int(bt.get("min_trades", 5)),
        signal=signal,
    )


def cmd_run(args: argparse.Namespace) -> None:
    cfg = _load_cfg(args.mission)
    mission = _mission_from_cfg(cfg)
    memory = Memory(args.db)
    mission.id = memory.create_mission(mission)

    agents = load_agents(args.agents)
    llm = LLMClient(mock=args.mock)
    tool = build_backtest_tool(cfg)

    mode = "MOCK (offline, no cost)" if args.mock else "LIVE (real API calls)"
    oracle = "backtest" if tool else "none"
    print(f"Mission #{mission.id}: {mission.title}")
    print(
        f"Mode: {mode}   Oracle: {oracle}   "
        f"Budget: ${mission.budget_usd:.2f}   Max rounds: {args.rounds}"
    )

    orch = Orchestrator(mission, agents, llm, memory, backtest_tool=tool)
    orch.run(max_rounds=args.rounds)

    print(f"\nInspect results:  python -m airod status --mission-id {mission.id} --db {args.db}")
    memory.close()


def cmd_status(args: argparse.Namespace) -> None:
    memory = Memory(args.db)
    mission = memory.get_mission(args.mission_id)
    if mission is None:
        print(f"No mission #{args.mission_id} in {args.db}")
        return
    print(f"Mission #{mission.id}: {mission.title}")
    print(f"Goal: {mission.goal}")
    print(f"Total spent: ${memory.total_cost(mission.id):.4f}\n")

    hyps = memory.hypotheses_for(mission.id)
    for h in hyps:
        print(f"[{h.status.value}] (r{h.round_index}, conf {h.confidence:.2f}) {h.statement}")
        if h.backtest:
            b = h.backtest
            o = b.get("outSample", {})
            verdict = "PASS" if b.get("passed") else "FAIL"
            print(
                f"    backtest[{b.get('strategy')}] {verdict}: "
                f"OOS Sharpe {o.get('sharpe', 0):.2f}, "
                f"return {o.get('total_return', 0) * 100:.1f}%, "
                f"maxDD {o.get('max_drawdown', 0) * 100:.1f}% — {b.get('reason')}"
            )
        for c in h.claims:
            mark = {"supported": "+", "contested": "~", "unsupported": "-"}.get(
                c.status.value, "?"
            )
            print(f"    {mark} {c.text}")
            for ev in c.evidence:
                print(f"        evidence [{ev.source}]: \"{ev.quote[:80]}...\"")
    memory.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="airod", description="An R&D group made of AI agents.")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a mission through the collaboration loop.")
    run.add_argument("--mission", required=True, help="Path to a mission YAML file.")
    run.add_argument("--agents", default="config/agents.yaml", help="Path to agents YAML.")
    run.add_argument("--rounds", type=int, default=3, help="Max research rounds.")
    run.add_argument("--mock", action="store_true", help="Run offline with no API calls.")
    run.add_argument("--db", default="airod_memory.db", help="Project memory DB path.")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="Show what a mission has learned so far.")
    status.add_argument("--mission-id", type=int, required=True)
    status.add_argument("--db", default="airod_memory.db")
    status.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
