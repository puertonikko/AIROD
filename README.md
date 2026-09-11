# AIROD — an R&D group made of AIs

AIROD is a small **research-institution-as-software**: a team of specialized AI
agents that collaborate on a central mission, argue with each other, ground their
claims in curated knowledge, and remember everything they learn across runs.

It is the same architecture that a Claude Code session uses to run — an
*orchestrator* that coordinates *specialist agents* — rebuilt as a standalone
system you own and steer.

## What it is (and isn't)

- **It is** a way to build one agent per job (Proposer, Critic, Researcher,
  Skeptic, Judge, …), point each at an *information sector* it learns from,
  and have them collaborate on a mission you assign.
- **It is not** training new foundation models from scratch. Each "AI" is a
  model + a role + its own tools + its own curated knowledge. An agent "learns"
  a sector by **retrieving** from it (RAG), not by retraining.

## The collaboration loop

Every research round runs a structured debate — not an open-ended chat, which
is how multi-agent systems burn money without converging:

```
propose ──▶ ground ──▶ attack ──▶ score ──▶ resolve ──▶ (checkpoint to memory)
   │           │          │          │          │
Proposer   Researcher  Critic +    Judge     Orchestrator
           (retrieves  Skeptic   (scores    (advances / demotes /
           evidence)             evidence)   spawns sub-tasks)
```

The **orchestrator is plain code, not a model** — it owns the loop, the budget,
and every write to project memory. Agents are stateless functions it calls. That
is what stops the "$50k congratulating each other" failure mode.

## Quick start

```bash
pip install -r requirements.txt

# Watch the whole loop run with NO API key and NO cost:
python -m airod run --mission config/mission.example.yaml --rounds 2 --mock

# When you're ready to use real models, set your key and drop --mock:
export ANTHROPIC_API_KEY=sk-ant-...      # or: ant auth login
python -m airod run --mission config/mission.example.yaml --rounds 3
```

Everything the agents produce is written to a local SQLite project memory
(`airod_memory.db` by default). Inspect it any time:

```bash
python -m airod status --mission-id 1
```

## Open questions in any domain (thinking outside the box)

The team is domain-general. Point it at anything — not just the built-in
battery/trading examples — using the general team, which **thinks outside the
box** two ways:

- An **Ideator** runs first each round, generating bold, cross-domain, contrarian
  angles *before* the Proposer commits — so you don't just get incremental ideas.
- The **Researcher pulls outside information via web search** (live mode), so the
  team learns from the world, not only from documents you provided.

```bash
# e.g. "reach a target horsepower by re-tuning a vehicle via OBD-II feedback"
python -m airod run --mission config/mission.vehicle.yaml \
    --agents config/agents.general.yaml --rounds 3          # add ANTHROPIC_API_KEY for real web research
```

Write your own `config/mission.*.yaml` (a title + goal) and run it with
`--agents config/agents.general.yaml`. That's the whole interface: give it a
mission, read the debate, steer, repeat.

## Concepts

| Piece | File | What it does |
|---|---|---|
| **Mission** | `config/mission.*.yaml` | The central task + success criteria |
| **Agents** | `config/agents.yaml` | One entry per specialist (role, model, sector, prompt) |
| **Knowledge sectors** | `airod/knowledge.py` | Curated docs an agent retrieves from (`examples/knowledge/`) |
| **Orchestrator** | `airod/orchestrator.py` | Runs the debate protocol, enforces budget & stop conditions |
| **Project memory** | `airod/memory.py` | Persists hypotheses, evidence, critiques, rejections |

## Adding your own agent

Add an entry to `config/agents.yaml`:

```yaml
- name: economics
  role: economist
  model: claude-sonnet-5
  sector: examples/knowledge/economics    # optional: a folder of .md/.txt files
  system_prompt: |
    You are the Economics agent. Estimate cost, scalability, and unit economics
    of each proposal. Every number you give must cite its assumption.
```

Drop reference documents into the sector folder and the agent will retrieve from
them automatically. That's how you "target an information sector."

## Status

This is a V1 skeleton — the loop, memory, retrieval, and agent framework are
real and runnable. See `docs/ROADMAP.md` for what's stubbed and what's next.
