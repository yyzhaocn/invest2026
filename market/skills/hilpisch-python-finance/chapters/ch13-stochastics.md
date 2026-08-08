# Chapter 13: Stochastics

## Core Idea
Simulate stochastic processes with `numpy.random.Generator`: random walks → geometric Brownian motion (GBM) → square-root (CIR) diffusion via Euler/exact schemes; Monte Carlo option valuation (European + American LSM); and risk measures (VaR, Expected Shortfall) from simulated distributions.

## Frameworks Introduced
- **Generator discipline**: one `default_rng(seed)` per notebook/module; `rng.standard_normal`, `lognormal`, `poisson`, `multivariate_normal` (correlated factor shocks).
- **GBM simulation**: log-returns `(μ - ½σ²)dt + σ√dt·z`, cumsum, exp — multiplicative growth, paths stay positive; terminal `S_T = S0·exp((r-½σ²)T + σ√T·Z)` samplable directly (lognormal).
- **CIR square-root diffusion**: `dV = κ(θ - V)dt + σ√V·dW` — Euler scheme (can go negative) vs exact discretization (non-central chi-square); for interest rates/vol.
- **Monte Carlo valuation**: European call = discounted mean payoff; American put via **Least-Squares Monte Carlo** (Longstaff-Schwartz regression on continuation value).
- **Convergence behavior**: value converges as M grows — plot MC value vs paths; standard error ∝ 1/√M.

## Key Concepts
- **Random walk**: cumsum of scaled increments — dispersion fans out over time; the visual seed of risk arguments.
- **Risk measures**: **VaR** (quantile of PnL distribution) and **Expected Shortfall** (mean beyond VaR) from simulated returns — heavier-tailed than normal in practice.
- **Distributional checks first**: mean/std of samples before driving engines.

## Mental Models
- Use X when Y: *GBM when* modeling equity underlyings (Black-Scholes); *CIR when* modeling rates/vol mean reversion; *LSM when* pricing American options.
- Think of Monte Carlo as *numerical integration over paths*: more paths → tighter estimate, ∝1/√M.

## Anti-patterns
- **Euler scheme for CIR without care** — can produce negative values; prefer exact discretization when available.
- **Ignoring convergence** — one MC estimate without path-count sensitivity is unverified.
- **Fresh rng per call** — breaks reproducibility; keep one Generator.

## Code Examples
```python
import numpy as np
rng = np.random.default_rng(seed=42)

# GBM paths (20 paths, 252 steps, 1y)
s0, mu, sigma, T, n_steps, n_paths = 100.0, 0.05, 0.2, 1.0, 252, 20
dt = T / n_steps
shocks = rng.standard_normal((n_steps, n_paths))
log_rets = (mu - 0.5*sigma**2)*dt + sigma*np.sqrt(dt)*shocks
s_paths = s0 * np.exp(np.vstack([np.zeros(n_paths), log_rets.cumsum(axis=0)]))

# terminal S_T sampling (risk-neutral)
S_T = s0 * np.exp((r - 0.5*sigma**2)*T + sigma*np.sqrt(T)*rng.standard_normal(250_000))

# European call MC
payoff = np.maximum(S_T - K, 0)
price = np.exp(-r*T) * payoff.mean()

# VaR / ES from simulated returns
VaR = np.percentile(pnl, 5)
ES = pnl[pnl <= VaR].mean()
```
- **What it demonstrates**: GBM paths, terminal distribution, MC pricing, risk measures.

## Worked Example
American put via LSM: simulate GBM paths → at each early-exercise date regress continuation value on state variables (price, price²) → compare exercise vs continuation → discount optimal payoff — value ≈ binomial tree reference. Convergence plot: price vs M (10³→10⁶) stabilizes at BS value with 1/√M error band.

## Key Takeaways
1. One seeded Generator per module; check distributions before use.
2. GBM: simulate log-price, exponentiate; terminal values are lognormal.
3. MC pricing = discounted mean payoff; convergence ∝ 1/√M.
4. VaR is a quantile; ES is the tail mean beyond VaR — report both.

## Connects To
- **Ch 5**: array ops for vectorized simulation
- **Ch 28**: full simulation of financial models
- **Ch 29**: derivatives valuation
