# Patterns & Techniques

## Strategy Idea Vetting (Ch2)
**The 6 Questions** — When to use: before any capital. How: benchmark/consistency → drawdown → costs → survivorship → regime persistence → data-snooping (+ fly-under-radar). Trade-offs: strict vetting kills most ideas early, which is the point.

## Cost-Aware Backtest (Ch3)
**Model costs in every fill** — When: always. How: subtract commissions + slippage + impact per side; use adjusted, survivorship-free data; walk-forward or out-of-sample validation. Trade-offs: realistic but requires good cost estimates.

## Kelly Sizing (Ch6)
**F* = μ/σ², then fractional** — When: sizing any strategy. How: estimate μ/σ from backtest (conservatively), take 1/2–3/4 Kelly, allocate jointly across strategies using the correlation matrix. Trade-offs: full Kelly maximizes growth but ruins on bad estimates.

## Mean-Reversion Spread (Ch7)
**Cointegration → spread → half-life → z-score** — When: pairs/pairs-like markets. How: regress A on B, ADF-test residual, estimate half-life (≈ −ln2/ln β), trade z-score extremes, exit at mean. Trade-offs: spreads decay/break; monitor cointegration health.

## Momentum Regime (Ch7)
**Ride non-stationary trends** — When: trending regime, longer timeframe. How: trend-following entry, trailing exit; regime filter first. Trade-offs: whipsaws in ranges — pair with a regime detector.

## Staged Automation (Ch5)
**Signals → semi-auto → full auto** — When: deploying a strategy. How: paper-trade each layer (data→signal→order→fill) before live; add monitoring/kill-switch. Trade-offs: speed vs oversight.

## Robustness Testing (Ch3, 6)
**Walk-forward + parameter jitter** — When: after a good backtest. How: rolling out-of-sample; perturb parameters slightly; if Sharpe collapses, it was overfit. Trade-offs: costs time, saves capital.
