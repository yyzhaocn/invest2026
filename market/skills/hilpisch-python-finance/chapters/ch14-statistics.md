# Chapter 14: Statistics

## Core Idea
A finance-focused statistics toolkit: normality diagnostics (GBM benchmark vs real data), portfolio mean-variance stats, random portfolios / efficient frontier / Sharpe ratios / CML, and Bayesian updating — because real returns have heavy tails and skew, later chapters favor simulation and robust risk measures.

## Frameworks Introduced
- **Normality diagnostics**: benchmark against simulated GBM (log prices ~ N), then test real returns — histograms, QQ plots vs fitted normal, plus formal tests: `scipy.stats.skewtest`, `kurtosistest`, `normaltest` (omnibus). Real data: negative skew + excess kurtosis (SPY kurtosis 15.1 vs normal 3) → normality p-values ~0.
- **Random portfolios / efficient frontier**: draw random weight vectors → compute mean, std, Sharpe; scatter on risk-return plane → frontier emerges as envelope; approximate efficient frontier from the best points.
- **Bayesian updating**: boxes/hypotheses + Bayes' Rule — posterior ∝ prior × likelihood; a simple worked example updating beliefs from evidence.

## Key Concepts
- **GBM benchmark**: terminal log price mean = ln S₀ + (r-½σ²)T, std = σ√T — the clean reference before noisy data.
- **Sharpe ratio**: (mean excess return)/std — the standard risk-adjusted performance measure.
- **Capital Market Line**: risk-free + tangency portfolio; the efficient frontier's linear envelope.
- **print_statistics()**: `scs.describe` table (size/min/max/mean/std/skew/kurtosis) + normality p-values.

## Mental Models
- Use X when Y: *GBM benchmark when* establishing "clean" reference behavior; *QQ plot when* judging tail deviations visually; *skewtest/kurtosistest when* quantifying non-normality.
- Think of the normality assumption as *useful approximation, poor tail description*.

## Anti-patterns
- **Assuming normality for risk** — heavy tails + skew are the norm in real returns.
- **Relying on one normality test** — combine visual (QQ) + moment tests.
- **Ignoring sample moments** — report skew/kurtosis alongside mean/std.

## Code Examples
```python
import numpy as np, pandas as pd, scipy.stats as scs

rng = np.random.default_rng(seed=2027)
s_T = 100.0 * np.exp((0.02 - 0.5*0.2**2) + 0.2*rng.standard_normal(250_000))
log_s_T = np.log(s_T)
log_s_T.mean(), log_s_T.std(ddof=1)      # ≈ 4.605, 0.200 (theory match)

log_returns = np.log(prices / prices.shift(1))    # real data
sta = scs.describe(log_returns["SPY"].dropna(), nan_policy="omit")
# skew ≈ -0.60, kurtosis ≈ 15.1 → normaltest p ≈ 0

# efficient frontier: random weights
w = rng.random((n_portf, n_assets)); w /= w.sum(axis=1, keepdims=True)
rets_p = (rets.mean() * w).sum(axis=1)            # portfolio means
std_p  = np.sqrt((w @ cov_matrix * w).sum(axis=1)) # portfolio stds
sharpe = rets_p / std_p
```
- **What it demonstrates**: GBM benchmark moments, normality tests, random-portfolio frontier.

## Worked Example
Efficient frontier: 8 assets from eod_data → 100k random weight vectors → plot (std, mean) scatter → frontier envelope; Sharpe-max portfolio ≈ tangency point; CML from risk-free rate. Bayesian update: prior P(downturn) updated by one day's return evidence via Bayes' Rule → posterior belief.

## Key Takeaways
1. Real returns: negative skew + heavy tails — normality is an approximation.
2. Random portfolios reveal the efficient frontier as an envelope.
3. Sharpe ratio + CML standardize risk-adjusted comparisons.
4. Bayes' Rule = posterior ∝ prior × likelihood — simple, powerful updating.

## Connects To
- **Ch 9/13**: return series + simulation benchmarks
- **Ch 18**: portfolio construction and risk formalizes this
- **Ch 22**: efficient markets and hypothesis testing
