"""The orchestrator — deterministic code that runs the collaboration loop.

It owns the round state machine, the budget, and every write to memory. Agents
are stateless functions it calls. This is deliberate: keeping the "manager" as
code, not a model, is what makes the system converge and stay within budget.

Round protocol:  propose -> ground -> attack -> score -> resolve -> checkpoint
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .agents import Agent
from .knowledge import KnowledgeSector
from .llm import LLMClient
from .memory import Memory
from .models import (
    Claim,
    ClaimStatus,
    Critique,
    Evidence,
    Hypothesis,
    HypothesisStatus,
    Mission,
)
from .tools.backtest import BacktestTool  # any oracle with .evaluate() works

# Keywords used to attach the backtest result to the claim it measures.
_ORACLE_KEYS = {"sharpe", "sample", "edge", "return", "backtest", "cost", "costs", "drawdown"}


@dataclass
class RoundResult:
    round_index: int
    hypothesis: Hypothesis
    new_supported_claims: int
    cost_so_far: float


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _best_status(claim_text: str, claim_scores: list[dict]) -> ClaimStatus:
    """Match a claim to the Judge's scores by token overlap."""
    ct = _tokens(claim_text)
    best, best_overlap = None, 0
    for score in claim_scores:
        overlap = len(ct & _tokens(score.get("claim", "")))
        if overlap > best_overlap:
            best, best_overlap = score, overlap
    if best is None:
        return ClaimStatus.UNSUPPORTED
    try:
        return ClaimStatus(best.get("status", "unsupported"))
    except ValueError:
        return ClaimStatus.UNSUPPORTED


class Orchestrator:
    def __init__(
        self,
        mission: Mission,
        agents: dict[str, Agent],
        llm: LLMClient,
        memory: Memory,
        verbose: bool = True,
        backtest_tool: BacktestTool | None = None,
    ) -> None:
        self.mission = mission
        self.agents = agents
        self.llm = llm
        self.memory = memory
        self.verbose = verbose
        self.backtest_tool = backtest_tool
        self._require_roles(["proposer", "researcher", "critic", "skeptic", "judge"])

    def _require_roles(self, roles: list[str]) -> None:
        missing = [r for r in roles if r not in self.agents]
        if missing:
            raise ValueError(f"Missing required agents for roles: {missing}")

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _call(self, agent: Agent, task: str, round_index: int) -> dict:
        cost = self.memory.total_cost(self.mission.id)
        if cost >= self.mission.budget_usd:
            raise RuntimeError(
                f"Budget of ${self.mission.budget_usd:.2f} reached (spent ${cost:.2f})."
            )
        result, usage = agent.run(self.llm, task)
        self.memory.record_call(
            self.mission.id,
            round_index,
            agent.name,
            agent.model,
            usage.input_tokens,
            usage.output_tokens,
            usage.cost_usd,
        )
        return result

    def _mission_context(self) -> str:
        prior = self.memory.hypotheses_for(self.mission.id)
        lines = [f"MISSION: {self.mission.title}", f"GOAL: {self.mission.goal}"]
        if prior:
            lines.append("\nPrior hypotheses (do not repeat rejected ones):")
            for h in prior[-5:]:
                lines.append(f"  - [{h.status.value}] {h.statement}")
        return "\n".join(lines)

    # -- one round --------------------------------------------------------
    def run_round(self, round_index: int) -> RoundResult:
        self._log(f"\n=== Round {round_index} ===")
        ctx = self._mission_context()

        # 1. PROPOSE
        prop = self._call(self.agents["proposer"], ctx, round_index)
        hyp = Hypothesis(
            statement=prop["statement"],
            prediction=prop.get("prediction", ""),
            claims=[Claim(text=c) for c in prop.get("claims", [])],
            round_index=round_index,
        )
        self._log(f"  proposer: {hyp.statement}")

        # 1b. MEASURE — if a strategy was proposed and we have an oracle, backtest it.
        # The oracle result is authoritative for the claim it measures.
        oracle_claim, oracle_passed = self._measure(hyp, prop.get("strategy"), round_index)

        # 2. GROUND — attach quoted evidence to claims
        ground_task = (
            f"Hypothesis: {hyp.statement}\nClaims:\n"
            + "\n".join(f"- {c.text}" for c in hyp.claims)
        )
        research = self._call(self.agents["researcher"], ground_task, round_index)
        for finding in research.get("findings", []):
            claim = self._match_claim(hyp, finding.get("claim", ""))
            if claim is not None:
                for ev in finding.get("evidence", []):
                    claim.evidence.append(
                        Evidence(
                            source=ev.get("source", "?"),
                            quote=ev.get("quote", ""),
                            relevance=ev.get("relevance", ""),
                        )
                    )
        grounded = sum(1 for c in hyp.claims if c.evidence)
        self._log(f"  researcher: {grounded}/{len(hyp.claims)} claims have evidence")

        # 3. ATTACK — critic + skeptic (authorship hidden from the judge)
        attack_task = f"Hypothesis: {hyp.statement}\nPrediction: {hyp.prediction}"
        critic = self._call(self.agents["critic"], attack_task, round_index)
        for c in critic.get("critiques", []):
            hyp.critiques.append(
                Critique(author_role="critic", text=c["text"], leverage=c.get("leverage", 0))
            )
        skeptic = self._call(self.agents["skeptic"], attack_task, round_index)
        for fm in skeptic.get("failure_modes", []):
            hyp.critiques.append(Critique(author_role="skeptic", text=fm, leverage=0))
        # Optional Risk agent (trading missions): sizing and drawdown concerns.
        if "risk" in self.agents:
            risk = self._call(self.agents["risk"], attack_task, round_index)
            for rk in risk.get("risks", []):
                hyp.critiques.append(Critique(author_role="risk", text=rk, leverage=0))
        self._log(f"  attackers: {len(hyp.critiques)} objections raised")

        # 4. SCORE — judge sees claims, evidence, and objections; NOT who wrote them
        judge_task = self._judge_view(hyp)
        verdict = self._call(self.agents["judge"], judge_task, round_index)
        scores = verdict.get("claim_scores", [])
        for claim in hyp.claims:
            claim.status = _best_status(claim.text, scores)
        hyp.confidence = float(verdict.get("confidence", 0.0))

        # The backtest oracle overrides the Judge for the claim it measured:
        # a real out-of-sample result beats an opinion.
        if oracle_claim is not None and oracle_passed is not None:
            oracle_claim.status = (
                ClaimStatus.SUPPORTED if oracle_passed else ClaimStatus.UNSUPPORTED
            )

        # 5. RESOLVE — apply the orchestrator's advancement rules
        supported = hyp.supported_claims()
        if supported:
            hyp.status = HypothesisStatus.ADVANCED
        elif hyp.confidence < 0.2:
            hyp.status = HypothesisStatus.REJECTED
        else:
            hyp.status = HypothesisStatus.OPEN_QUESTION
        self._log(
            f"  judge: confidence={hyp.confidence:.2f}, "
            f"{len(supported)} supported claim(s) -> {hyp.status.value}"
        )

        # 6. CHECKPOINT
        self.memory.save_hypothesis(self.mission.id, hyp)
        return RoundResult(
            round_index=round_index,
            hypothesis=hyp,
            new_supported_claims=len(supported),
            cost_so_far=self.memory.total_cost(self.mission.id),
        )

    def _judge_view(self, hyp: Hypothesis) -> str:
        lines = [f"Hypothesis: {hyp.statement}", "Claims and their evidence:"]
        for c in hyp.claims:
            lines.append(f"- Claim: {c.text}")
            if c.evidence:
                for ev in c.evidence:
                    lines.append(f"    evidence [{ev.source}]: \"{ev.quote}\"")
            else:
                lines.append("    evidence: (none)")
        lines.append("Objections:")
        for cr in hyp.critiques:
            lines.append(f"- {cr.text}")
        return "\n".join(lines)

    @staticmethod
    def _match_claim(hyp: Hypothesis, text: str) -> Claim | None:
        ct = _tokens(text)
        best, best_overlap = None, 0
        for claim in hyp.claims:
            overlap = len(ct & _tokens(claim.text))
            if overlap > best_overlap:
                best, best_overlap = claim, overlap
        return best

    @staticmethod
    def _match_oracle_claim(hyp: Hypothesis) -> Claim | None:
        """The claim the backtest speaks to (about edge/Sharpe/returns)."""
        best, best_overlap = None, 0
        for claim in hyp.claims:
            overlap = len(_tokens(claim.text) & _ORACLE_KEYS)
            if overlap > best_overlap:
                best, best_overlap = claim, overlap
        if best is not None:
            return best
        return hyp.claims[0] if hyp.claims else None

    def _measure(
        self, hyp: Hypothesis, strategy_dict: dict | None, round_index: int
    ) -> tuple[Claim | None, bool | None]:
        """Run the oracle on a proposed strategy, if an oracle and spec exist.

        Works with any oracle exposing ``.evaluate(spec) -> result`` with
        ``.passed``, ``.quote``, and ``.payload`` (price or event backtester).
        """
        if self.backtest_tool is None:
            return None, None
        res = self.backtest_tool.evaluate(strategy_dict)
        if res is None:
            return None, None
        hyp.strategy = {
            "strategy": res.payload.get("strategy"),
            "params": res.payload.get("params", {}),
        }
        hyp.backtest = res.payload
        claim = self._match_oracle_claim(hyp)
        if claim is not None:
            claim.evidence.append(
                Evidence(
                    source="backtest",
                    quote=res.quote,
                    relevance="Out-of-sample backtest oracle.",
                )
            )
        self._log(
            f"  oracle: {res.payload.get('strategy')} -> "
            f"{'PASS' if res.passed else 'FAIL'} ({res.payload.get('reason')})"
        )
        return claim, res.passed

    # -- full mission -----------------------------------------------------
    def run(self, max_rounds: int) -> list[RoundResult]:
        results: list[RoundResult] = []
        stall = 0
        for i in range(1, max_rounds + 1):
            try:
                result = self.run_round(i)
            except RuntimeError as exc:
                self._log(f"\nStopping: {exc}")
                break
            results.append(result)
            if result.new_supported_claims == 0:
                stall += 1
                if stall >= self.mission.stall_rounds:
                    self._log(
                        f"\nStopping: no new supported claims for {stall} rounds (stall)."
                    )
                    break
            else:
                stall = 0
        self._log(f"\nDone. {len(results)} round(s), spent ${self.memory.total_cost(self.mission.id):.4f}.")
        return results
