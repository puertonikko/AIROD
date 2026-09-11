"""Command-line entry point for AIROD."""

from __future__ import annotations

import argparse

import yaml

from .agents import load_agents
from .llm import LLMClient
from .memory import Memory
from .models import Mission
from .orchestrator import Orchestrator


def _load_mission(path: str) -> Mission:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return Mission(
        title=cfg["title"],
        goal=cfg["goal"],
        success_criteria=cfg.get("success_criteria", []),
        budget_usd=float(cfg.get("budget_usd", 5.0)),
        stall_rounds=int(cfg.get("stall_rounds", 2)),
    )


def cmd_run(args: argparse.Namespace) -> None:
    mission = _load_mission(args.mission)
    memory = Memory(args.db)
    mission.id = memory.create_mission(mission)

    agents = load_agents(args.agents)
    llm = LLMClient(mock=args.mock)

    mode = "MOCK (offline, no cost)" if args.mock else "LIVE (real API calls)"
    print(f"Mission #{mission.id}: {mission.title}")
    print(f"Mode: {mode}   Budget: ${mission.budget_usd:.2f}   Max rounds: {args.rounds}")

    orch = Orchestrator(mission, agents, llm, memory)
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
