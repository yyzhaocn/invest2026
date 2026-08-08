# Chapter 28: Simulation of Financial Models

## Core Idea
Simulation is an **interface contract**: consistent time grids (year fractions, strictly increasing from 0), path shapes ((paths, steps+1)), the `PathSimulator` protocol (`.simulate_paths(spot, time_grid, paths)`), and centralized random numbers with variance reduction — so valuation code can rely on conventions and swap models freely.

## Frameworks Introduced
- **PathSimulator protocol**: GBM, Merton JumpDiffusion, Heston (returns tuple of arrays: spot+variance), CIRShortRate (Euler truncation, non-negative) — all implement `simulate_paths`.
- **Centralized RNG with variance reduction**: `standard_normals(shape, seed, antithetic, moment_matching)` — antithetic pairs (z, −z along last axis; requires even path count), moment matching (shift/scale to sample mean 0, std 1); seeding via `default_rng` (no legacy global state).
- **Time grids**: `build_time_grid(maturity, steps)` uniform year-fraction grid.

## Key Concepts
- **Model menu**: GBM (log-normal equity), Merton jump diffusion (intensity, mean/std of jumps), Heston stochastic vol (κ, θ, vol-of-vol, ρ, drift), CIR short rate (κ, θ, σ) — extension point for stochastic discounting.
- **Shape discipline**: (paths, steps+1) single factor; tuples for multi-state — eliminates subtle bugs at portfolio scale.
- **Variance reduction is not magic**: reduces noise for a given path count, doesn't fix model bias.

## Mental Models
- Use X when Y: *GBM when* plain equity; *Merton when* jumps matter; *Heston when* vol-of-vol/smile matters; *CIR when* rates.
- Think of simulation conventions as *the contract valuation relies on*: loose shapes → fragile everything above.

## Anti-patterns
- **In-line `np.random.standard_normal()` per model** — unseeded, no variance reduction.
- **Inconsistent shapes/time grids** across models.
- **Expecting variance reduction to fix bias** — it reduces variance only.

## Code Examples
```python
import numpy as np
from dxlib.processes import GeometricBrownianMotion, JumpDiffusion, HestonModel
from dxlib.random import standard_normals, build_time_grid

grid = build_time_grid(maturity=1.0, steps=12)          # 0..1, 13 points
z = standard_normals((paths, len(grid)-1), seed=42,
                     antithetic=True, moment_matching=True)

gbm = GeometricBrownianMotion(drift=0.02, volatility=0.2)
s_paths = gbm.simulate_paths(spot=100.0, time_grid=grid, paths=10_000)
# shape (10_000, 13)

heston = HestonModel(kappa=1.0, theta=0.04, vol_of_vol=0.3, rho=-0.6, drift=0.0)
spot_paths, var_paths = heston.simulate_paths(100.0, grid, 10_000)  # tuple
```
- **What it demonstrates**: grid, variance-reduced RNG, GBM/Heston protocols.

## Worked Example
Diagnostics: simulate GBM and Heston with same seed → plot paths + terminal distributions → verify mean ≈ S₀e^{μT}, std ≈ σ√T for GBM; antithetic+MM reduce MC standard error vs plain draws at fixed path count (compare terminal payoff estimate spread across seeds).

## Key Takeaways
1. Simulation conventions (shapes, grids, protocol) are a contract for everything above.
2. Centralize RNG: seed, antithetic, moment matching in one helper.
3. Model menu: GBM / Merton / Heston / CIR — swap via the protocol.
4. Variance reduction shrinks noise; it doesn't fix model error.

## Connects To
- **Ch 27**: time grids and env from the foundation
- **Ch 29**: valuation consumes any PathSimulator
- **Ch 31**: calibrated Heston drives market-based pricing
