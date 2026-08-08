# Chapter 19: Signals, Forecasts, and Portfolio Implementation

## Core Idea
Keep **research, portfolio, and execution layers separate**: research estimates signals/forecasts, portfolio maps them to weights/trades respecting constraints, execution turns trades into fills. Signals are time series aligned to instruments and dates — used for selection, sizing, or timing.

## Frameworks Introduced
- **Three-layer separation**: research (signals/forecasts) → portfolio (weights/trades) → execution (orders/fills). Test each component independently; compare models on the same implementation layer.
- **Signal design**: features from prices (20d momentum `rets.rolling(20).mean()`, 60d vol `rets.rolling(60).std()`), aligned with **forward-return targets** (`fwd_5d = rets.shift(-5).rolling(5).sum()`).
- **Signal uses**: selection (which assets), sizing (tilt weights by signal strength), timing (modulate risk).
- **Score → rank → weight mapping**: raw scores become ranks then portfolio weights (respecting mandate constraints).
- **Implementation quality**: rebalancing frequency, turnover, transaction costs — evaluate the *implemented* strategy, not the research signal.
- **Predictability & EMH**: signal persistence is an empirical question — test with diagnostics before trusting (deferred to Ch 22).

## Key Concepts
- **Feature engineering hygiene**: winsorise extremes, impute missing, align features/targets without leakage (`dropna()` after concat).
- **Target types**: absolute returns, benchmark-relative returns, binary outperformance labels — different evaluation criteria.
- **Backtesting & diagnostics**: signal quality measured on forward returns; IC/rank correlation and portfolio-level checks.

## Mental Models
- Use X when Y: *momentum when* exploiting persistence; *vol when* risk-adjusting; *ML scores when* combining many features (Ch 15).
- Think of the signal as *an input contract*: aligned, dated, leakage-free — portfolio layer doesn't care how it was produced.

## Anti-patterns
- **Leakage**: using future data in features/targets (shift(-k) must be handled carefully).
- **Judging research without implementation costs** — turnover/costs change results.
- **Conflating signal quality with portfolio performance** — separate the layers.
- **Overfitting signals to history** — EMH null hypothesis is the default.

## Code Examples
```python
import pandas as pd

rets = sub[universe].pct_change().dropna().iloc[-2*252:]

mom_20d = rets.rolling(20).mean()          # momentum feature
vol_60d = rets.rolling(60).std()           # vol feature
fwd_5d  = rets.shift(-5).rolling(5).sum()  # 5-day forward return target

features = pd.concat({"mom_20d": mom_20d, "vol_60d": vol_60d}, axis=1)
aligned  = pd.concat({"mom_20d": mom_20d, "fwd_5d": fwd_5d}, axis=1).dropna()
```
- **What it demonstrates**: features + leakage-free forward target alignment.

## Worked Example
Momentum signal → ranks → weights: compute 20d momentum per asset → cross-sectional rank → map to long-only weights (e.g. rank-weighted, scaled to sum 1 within mandate caps) → monthly rebalance → backtest vs equal-weight and benchmark SPY → report turnover, costs, and net outperformance. Diagnostics first: does momentum rank correlate with forward returns?

## Key Takeaways
1. Separate research/portfolio/execution layers — test and compare cleanly.
2. Signals: aligned, leakage-free time series; targets = forward returns/labels.
3. Map scores → ranks → weights under mandate constraints.
4. Implemented performance (turnover, costs) is what matters.

## Connects To
- **Ch 18**: weights construction consumes signals
- **Ch 22**: EMH and hypothesis testing about signal persistence
- **Ch 23**: vectorized/event-based backtesting machinery
