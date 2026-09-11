# Position sizing and risk (reference notes)

## Risk per trade

A common rule is to risk a small fixed fraction of capital per trade (often
0.5–2%), defined by the distance to a stop. This bounds the damage of any single
loss and keeps a losing streak from impairing capital. Sizing by a fixed dollar
amount instead of a fixed risk fraction leads to inconsistent exposure.

## Drawdown control

Maximum drawdown — the largest peak-to-trough equity decline — is often a better
survival metric than return. A strategy that returns 30% annually but can draw
down 50% may be un-tradeable in practice because the operator abandons it at the
bottom. A drawdown budget that forces de-risking (cutting size as equity falls)
protects against ruin.

## The Kelly criterion and fractional Kelly

The Kelly criterion gives the position size that maximizes long-run growth given
an edge, but full Kelly is famously volatile; practitioners typically use a
fraction (e.g. half-Kelly) to cut drawdown at a small cost to growth. Kelly
sizing requires an accurate estimate of edge — overestimating it leads to
over-betting and eventual ruin.

## Capacity and crowding

An edge that works on small size can disappear at scale as the strategy's own
orders move the market, or as other participants crowd the same trade. Backtests
assume infinite liquidity at the quoted price; real capacity is finite.
