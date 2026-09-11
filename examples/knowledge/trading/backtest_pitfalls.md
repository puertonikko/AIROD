# Backtesting pitfalls (reference notes)

## Overfitting and in-sample vs out-of-sample

The single most common failure in strategy research is overfitting: tuning
parameters until a strategy looks great on the data it was fit to, then watching
it fail on new data. The defense is an out-of-sample (OOS) split — reserve a
portion of history the strategy never sees during design, and judge it only on
that portion. A large gap between in-sample and out-of-sample Sharpe is a red
flag that the "edge" is curve-fit noise.

## Costs erase paper edges

Backtests that ignore commissions, bid-ask spread, and slippage routinely show
edges that vanish in live trading. High-turnover strategies are especially
vulnerable: a signal that trades daily pays costs daily. Always model realistic
per-trade costs (commission plus slippage of several basis points), and prefer
strategies whose edge survives them with margin.

## Lookahead and survivorship bias

Lookahead bias uses information not available at decision time (e.g. acting on a
day's close before it happens). Survivorship bias tests only on instruments that
still exist, hiding the losers that were delisted. Both inflate backtested
returns and are invisible unless deliberately controlled for.

## Data snooping

Testing many strategies on the same data guarantees some will look good by
chance. The more variants tried, the higher the bar the winner must clear to be
believable. Out-of-sample validation and honest accounting of how many ideas
were tried both help.
