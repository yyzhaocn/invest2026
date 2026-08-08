# Chapter 22: Efficient Markets and Hypothesis Testing

## Core Idea
Treat EMH as a **modeling baseline / null hypothesis**, not dogma: simple publicly known rules should not generate persistent abnormal profits *after costs*. Predictability claims become actionable only as explicit statistical hypotheses — with effect sizes, power, multiple-testing awareness, and out-of-sample walk-forward evaluation.

## Frameworks Introduced
- **EMH forms as baselines**: weak (past prices only), semi-strong (+public info/fundamentals), strong (+private info — unrealistic, theoretical bound). Book assumes weak-to-semi-strong for liquid markets: predictable patterns are rare, fragile, heavily competed away.
- **Predictability as hypothesis testing**: H₀ = serially uncorrelated returns (white noise); H₁ = nonzero autocorrelation at some lag — probe with sample autocorrelation, then formal tests (Ljung-Box, regression-based, Granger causality for signal→return).
- **Statistical rigor checklist**: effect sizes (not just p<0.05), test power, multiple-testing correction, out-of-sample / walk-forward evaluation.
- **Timmermann–Granger view**: efficiency is *time-varying* — predictability can appear/disappear; EMH is a baseline that fluctuates with market conditions.
- **Decision rule**: a signal is actionable only if it survives realistic costs + out-of-sample tests + multiple-comparison scrutiny.

## Key Concepts
- **Autocorrelation**: `r_spy.autocorr(lag=1)` ≈ -0.14 for SPY daily — small vs sampling variability.
- **Benchmark-relative framing**: EMH underpins passive index trackers as default; burden of proof on active ideas.
- **Walk-forward**: refit on rolling training window (2y), predict next block (1 month), roll forward — the honest evaluation scheme.

## Mental Models
- Use X when Y: *EMH as null when* evaluating any signal; *Granger tests when* testing signal→return causation; *walk-forward when* claiming out-of-sample validity.
- Think of EMH as *the default hypothesis*: you need evidence to move off it, and costs are part of the test.

## Anti-patterns
- **In-sample overfitting presented as edge** — needs out-of-sample + costs.
- **p-value shopping** — multiple testing inflates false discoveries.
- **Ignoring effect size** — statistical ≠ economically significant.
- **Static efficiency beliefs** — efficiency varies over time (Timmermann–Granger).

## Code Examples
```python
import pandas as pd
prices = pd.read_csv("data/eod_data.csv", parse_dates=["Date"], index_col="Date")
r_spy = prices["SPY"].pct_change().dropna()

r_spy.autocorr(lag=1)   # ≈ -0.1355
r_spy.autocorr(lag=5)   # ≈ 0.038

# regression-based signal test
import statsmodels.api as sm
X = sm.add_constant(features.shift(1))   # lagged signal
mod = sm.OLS(fwd_ret, X).fit()            # H1: signal predicts forward return
mod.summary()                              # check t-stat / p-value + effect size
```
- **What it demonstrates**: autocorrelation diagnostics, regression-based predictability tests.

## Worked Example
Test momentum persistence: compute 20d momentum signal on SPY → regress 5-day forward returns on lagged momentum → walk-forward: refit monthly on 2y window, evaluate out-of-sample t-stat and IC → after costs, does the edge survive? Likely conclusion: weak/no exploitable predictability — consistent with EMH baseline.

## Key Takeaways
1. EMH = null hypothesis (with costs), not a factual claim to accept blindly.
2. Translate "predictability" claims into testable hypotheses with effect sizes and power.
3. Granger causality and regression tests connect signals to returns statistically.
4. Walk-forward out-of-sample evaluation is the minimum bar for actionable signals.

## Connects To
- **Ch 19**: signal evaluation discipline
- **Ch 23**: backtesting as the quantitative counterpart to hypothesis tests
- **Ch 14**: statistical toolkit
