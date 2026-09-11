# Factors and signals (reference notes)

## Momentum

Cross-sectional and time-series momentum — the tendency of recent winners to
keep outperforming over horizons of weeks to months — is one of the most
robustly documented market anomalies across asset classes and decades. Simple
implementations use moving-average crossovers or trailing returns. Momentum
suffers sharp crashes during sharp reversals, so drawdown control matters.

## Mean reversion

Over short horizons (days), prices often mean-revert: oversold instruments
bounce and overbought ones pull back. RSI and z-score-of-price signals are
common triggers. Mean reversion tends to work in range-bound regimes and lose
badly in strong trends, so it is roughly the opposite exposure to momentum.

## Combining signals with a model

A machine-learning model can combine many weak signals (price, volume, options
flow, catalysts) into a single probability. The value of such a model is only
real if trading on its output produces edge out-of-sample — a high in-sample AUC
proves nothing. A useful test is to treat the model's probability as a signal and
backtest a threshold rule on it, out-of-sample, net of costs. If the edge is not
there after costs, the model is not adding value regardless of its AUC.

## Regime dependence

Almost every signal's performance depends on regime (trending vs range-bound,
high vs low volatility, risk-on vs risk-off). A strategy that ignores regime can
show a strong average while hiding long stretches of losses. Naming the regimes
where a strategy fails is part of validating it.
