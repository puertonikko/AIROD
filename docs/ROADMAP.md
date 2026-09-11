# AIROD roadmap

## V1 — what works now

- **Agent framework** — declarative agents (role, model, sector, prompt) in `config/agents.yaml`.
- **Debate protocol** — propose → ground → attack → score → resolve, in code.
- **Knowledge sectors** — BM25 retrieval over folders of `.md`/`.txt` docs. No external services.
- **Project memory** — SQLite record of hypotheses, claims, evidence, critiques, and cost.
- **Budget + stop conditions** — hard USD ceiling and stall detection enforced by the orchestrator.
- **Mock mode** — the entire loop runs offline with no API key or spend.

## V2 — next

- **Real grounding quality.** BM25 → embedding-based retrieval; dedup and rank sources; store evidence rows individually with provenance hashes.
- **Human-in-the-loop steering.** A `steer` command to inject a constraint ("cost must stay under $70/kWh") between rounds, exactly like steering this session.
- **Sub-task spawning.** When a claim is `contested`, the orchestrator spins a focused sub-mission instead of dropping it.
- **Blinded judging, enforced.** Strip all authorship before the judge call at the data layer, not by convention.
- **Baseline comparison.** Run a single-model-in-a-loop baseline alongside the multi-agent run and report whether the extra cost buys better conclusions.

## V3 — the "lab OS"

- **Tool integration** per agent (web search/fetch, code execution, domain simulators) so "ground" and "score" can run real checks, not just retrieval.
- **Cross-vendor agents** (mix providers per role) to reduce correlated errors — pluggable behind the `LLMClient` contract.
- **Dashboard** over project memory (active/rejected hypotheses, evidence coverage, spend).

## Design invariants (do not break)

1. The orchestrator is code, never a model. It owns the loop, the budget, and every write to memory.
2. Every claim links to quoted evidence. A claim with no evidence is `unsupported`, never advanced.
3. Rejection is first-class — dead ends stay in memory so the team doesn't re-explore them.
4. The judge is blind to authorship and grounded only in supplied evidence.
