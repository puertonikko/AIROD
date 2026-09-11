# The trading arm — funding the R&D

The idea: the trading team is a *tool the R&D group uses*. Its job is not to
"make $1M" on command — no system can honestly promise that — but to **find
strategies whose edge survives out-of-sample testing**, so you can paper-trade
the survivors and let real returns fund the harder research.

## Why it's honest

Markets are adversarial and near-efficient, so an agent can describe a beautiful
strategy that's pure hindsight. The defense is an **oracle**: a real backtester
with an out-of-sample split and realistic costs. A strategy's edge claim is
settled by numbers the agents can't argue with — a failed out-of-sample backtest
is authoritative over any amount of optimism.

## Run it

```bash
# Offline demo (real backtest on synthetic data, no API key):
python -m airod run \
  --mission config/mission.trading.yaml \
  --agents  config/agents.trading.yaml \
  --rounds 3 --mock

python -m airod status --mission-id 1
```

Drop `--mock` and set `ANTHROPIC_API_KEY` for real model reasoning. The backtest
runs for real in both modes — it's code, not an LLM.

## The team (`config/agents.trading.yaml`)

Proposer (emits a runnable strategy), Researcher, Critic (hunts overfitting),
Skeptic (live-trading failure modes), **Risk** (sizing + drawdown rules), Judge.

## The oracle (`config/mission.trading.yaml` → `backtest:`)

- **Strategies:** `sma_crossover`, `rsi_reversion`, `signal_threshold`.
- **Gates:** out-of-sample Sharpe ≥ `min_oos_sharpe`, drawdown ≤ `max_dd_limit`,
  at least `min_trades` trades — all after `cost_bps` costs.
- **Data:** deterministic synthetic by default; point `data.csv` at a
  `date,SYM1,SYM2,...` file of real closes for real research.

## Wiring in autotrader's model

`autotrader/AI` is a next-day-move *predictor*, not a backtester. Wire it in as a
**signal** and the backtester answers its README's open question — "is the model
adding real edge?" — out-of-sample and net of costs:

```yaml
backtest:
  signal:
    type: autotrader
    url: https://your-autotrader-ai.up.railway.app
```

The Proposer then uses `signal_threshold`, and the backtester calls
`/predict` per day (price-derived features; catalyst/options features default
off). If the edge isn't there after costs, the model isn't adding value — which
is exactly what you want to know before trading real money.

## Event-study backtesting your catalyst data

Your `catalyst_training` log is **event** data (a catalyst fired → it moved
`eod_pct` by end of day), not a price series — so it uses a different oracle,
the **event-study backtester**. A strategy here is a *filter* over catalysts
(confidence, confirmation, catalyst type, premarket gap), and the oracle reports
hit rate, expectancy per trade, and an equity curve — split out-of-sample by
time, net of costs.

Because you logged catalysts **whether or not you traded them**, expectancy is
the *true* base rate of the signal, free of selection bias.

```bash
# Runs on a committed SYNTHETIC sample out of the box:
python -m airod run --mission config/mission.catalyst.yaml \
    --agents config/agents.catalyst.yaml --rounds 3 --mock
python -m airod status --mission-id 1
```

**Using your real export:** export `catalyst_training` from Supabase to CSV,
drop it at `data/catalyst_training.csv` (this path is git-ignored — real data is
never committed to the public repo), and point the mission at it:

```yaml
# config/mission.catalyst.yaml
event:
  data: data/catalyst_training.csv
  min_signals: 20        # raise the bar so tiny, noisy subsets can't "pass"
```

If your column names differ from the default export, set `event.mapping` (see
`airod/tools/event_backtest.py` → `DEFAULT_MAP`).

**A caution the oracle enforces for you:** a filter that shows +2.7% on 5
out-of-sample trades is noise, not edge. The `min_signals` gate rejects it — keep
it strict on small datasets, and trust filters that hold up across many signals.

## The workflow (how you "work with them")

1. Run the mission; read the round transcript.
2. **Steer** with a constraint and re-run:
   *"Max drawdown ≤ 15%. Assume $2/trade + 5bps slippage. Focus on the momentum variant."*
3. Take strategies that **pass out-of-sample**, backtest them on your own real
   data, then **paper trade** before a single real dollar.
4. The survivors — sized by the Risk agent's rules — are what you trade to fund
   the rest of the R&D.

No step promises profit. The system's value is killing bad strategies fast and
handing you a short list of falsifiable, risk-bounded candidates.
