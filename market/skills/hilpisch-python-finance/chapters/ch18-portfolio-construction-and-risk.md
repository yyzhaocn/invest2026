# Chapter 18: Portfolio Construction and Risk

## Core Idea
Portfolio construction turns mandate-level language into arrays and matrices: weights w, expected returns μ, covariance Σ, benchmark weights — then solves optimization problems (minimum-variance, target-return, utility, risk-budgeted) under constraints (long-only, leverage, position/sector caps, turnover), regularizing inputs so the optimizer stays stable.

## Frameworks Introduced
- **Input regularization** (critical): expected returns are noisy → shrink toward benchmark mean (`mu_shrunk = λ·μ + (1-λ)·μ_bench`); covariance unstable when assets >> sample → shrink toward diagonal (`Σ_shrunk = λ·Σ + (1-λ)·diag(Σ)`). Same principle: regularize so optimization remains stable/interpretable.
- **Minimum-variance closed form**: `w_GMV = Σ⁻¹1 / (1ᵀΣ⁻¹1)` via `np.linalg.solve`.
- **Mean-variance family**: minimum-variance, target-return, utility-maximizing, risk-budgeted portfolios — solved with a convex optimizer (cvxpy).
- **Constraints → implementability**: long-only, leverage, position limits, turnover caps, transaction costs, rebalancing; risk budgets and concentration controls; factor exposures and risk decomposition.

## Key Concepts
- **Annualization**: μ_annual = (1+μ_daily)^252 - 1; Σ_annual = Σ_daily × 252.
- **Risk decomposition**: factor model → decompose portfolio risk into factor vs idiosyncratic contributions.
- **Estimation error**: noisy μ/Σ → unstable, unintuitive weights — the core motivation for shrinkage.
- **Sample covariance**: `rets[universe].cov()` — natural start, numerically fragile on inversion.

## Mental Models
- Use X when Y: *shrink returns when* sample short/noisy; *shrink covariance when* assets > sample length; *cvxpy when* constraints multiply.
- Think of constraints as *part of the problem definition*, not afterthoughts.

## Anti-patterns
- **Raw sample covariance inversion** — unstable for wide universes.
- **Unconstrained portfolios** — ignore mandate limits → unimplementable weights.
- **Ignoring turnover/costs** — optimal-but-churned portfolios lose to costs.
- **Point estimates without robustness** — no shrinkage, no sensitivity.

## Code Examples
```python
import numpy as np, pandas as pd

rets = sub.pct_change().dropna().iloc[-2*252:]           # 2y daily
mu_daily = rets[universe].mean()
cov_daily = rets[universe].cov()
mu_annual = (1 + mu_daily)**252 - 1
cov_annual = cov_daily * 252

# shrink returns toward benchmark
mu_shrunk = 0.5*mu_annual + 0.5*mu_bench_annual

# shrink covariance toward diagonal
lam = 0.2
Sigma = lam*cov_annual.values + (1-lam)*np.diag(np.diag(cov_annual.values))

# global minimum-variance
ones = np.ones(len(universe))
inv = np.linalg.solve(Sigma, ones)
w_gmv = inv / (ones @ inv)     # e.g. [0.131, 0.197, 0.672]
```
- **What it demonstrates**: estimation, shrinkage, GMV closed form.

## Worked Example
3-asset universe (AAPL, JPM, TLT) + SPY benchmark, 2y daily returns: annualize μ/Σ → shrink both → GMV weights via closed form → target-return portfolio via cvxpy (min variance s.t. Σwᵢ=1, μᵀw = target, w ≥ 0) → add position cap (≤50%) and turnover constraint → compare weight vectors and their risk contributions. Lab: "The Hidden Costs of Portfolio Constraints" — constraints raise risk/lower return vs unconstrained.

## Key Takeaways
1. Regularize μ and Σ before optimizing — estimation error dominates.
2. GMV has a closed form; constrained problems need a convex solver.
3. Constraints (long-only, caps, turnover) define implementability.
4. Decompose risk into factor + idiosyncratic parts to explain exposures.

## Connects To
- **Ch 17**: mandate inputs (constraints, universe, benchmark)
- **Ch 19**: signals → weights bridge
- **Ch 21**: assetlib.portfolio implements these in code
