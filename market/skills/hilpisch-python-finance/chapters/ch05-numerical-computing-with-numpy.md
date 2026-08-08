# Chapter 5: Numerical Computing with NumPy

## Core Idea
The `ndarray` — a single-dtype, contiguous-memory array — is the workhorse of quant finance: vectorized C-speed operations with explicit shape/axis control, used by pandas, simulation, and ML libraries underneath.

## Frameworks Introduced
- **Vectorization over Loops**: express operations on whole arrays instead of element loops — 10-100x faster via C implementation.
- **Broadcasting Rules**: align array shapes by (1) trailing dimensions match, (2) size-1 dims stretch, (3) dimensions missing stretch — enables outer-product style ops without explicit loops.
- **Boolean Masks + np.where**: vectorized filtering (`prices[mask]`) and vectorized if-else (`np.where(cond, a, b)`).
- **Random via Generator**: use `np.random.default_rng(seed)` — the modern interface; `np.random.seed` legacy.

## Key Concepts
- **dtype / ndim / shape / size / itemsize**: metainfo governing memory and operations.
- **Views vs copies**: slices are views — mutating a slice mutates the original; use `.copy()` for independence.
- **axis argument**: `mean(axis=0)` aggregates across rows (per column); `axis=1` per row. Be explicit for time series/panels.
- **Creation routines**: `np.zeros/np.ones/np.eye/np.linspace/arange` — specify shapes directly.
- **np.insert preserves dtype, np.append may upcast** — check output dtype.
- **Structured arrays**: named-field dtypes (`[("symbol","U6"),("price","f8")]`) for low-level tabular control — but pandas is the primary tool.
- **C (row-major) vs F (column-major) order**: memory layout interacts with axis choice for performance.

## Mental Models
- Think of arrays as *values with shape*: index `arr[axis0, axis1]`, slice `arr[:, 1]`.
- Use X when Y: *NumPy when* operations are over arrays of numbers at scale; *pandas when* labels and mixed types matter.
- Design shapes so innermost algorithm loops follow contiguous memory.

## Anti-patterns
- **Mutating a slice unintentionally**: `window = spot[1:3]; window[0] = 999` silently changes `spot`.
- **Python-level loops over arrays** where vectorized ops exist.
- **Trusting single %timeit ranking** for layout microbenchmarks — varies by CPU/version/architecture.
- **Using legacy random API** when `default_rng` gives reproducible Generator-based draws.

## Code Examples
```python
import numpy as np
prices = np.array([100.0, 101.5, 103.2, 102.8])     # create
prices.dtype, prices.shape, prices.ndim             # float64 (4,) 1

# 2D: 2 assets × 3 days returns, axis semantics
returns = np.array([[0.01, 0.02, -0.005], [-0.01, 0.015, 0.0]])
returns.mean()            # 0.005  (all)
returns.mean(axis=0)      # per-day mean across assets
returns.mean(axis=1)      # per-asset mean across days

# Boolean mask
mask = prices > 100.0
prices[mask]              # filter

# Random walk one-step Monte Carlo
rng = np.random.default_rng(100)
S0, mu, sigma, T, M = 100.0, 0.05, 0.2, 1.0, 100_000
S_T = S0 * np.exp((mu - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * rng.standard_normal(M))
S_T.mean()                # ≈ S0 * exp(mu*T) via GBM expectation

# structured arrays
dtype = np.dtype([("symbol", "U6"), ("price", "f8"), ("volume", "i8")])
quotes = np.array([("AAPL", 180.0, 1_000)], dtype=dtype)
quotes["price"]           # field access
```
- **What it demonstrates**: creation, axis aggregation, masks, Generator RNG, structured dtype.

## Worked Example
Monte Carlo European call: `S0=100, K=105, r=0.05, sigma=0.2, T=1, M=100k` — draw `standard_normal(M)` paths, payoff `max(S_T-K, 0)`, discount `exp(-r*T)`, mean → price ≈ Black-Scholes. Shows vectorized simulation in ~3 lines.

## Key Takeaways
1. ndarray = single dtype + contiguous memory + vectorized C ops.
2. Slices are views — call `.copy()` when independence matters.
3. Be explicit with `axis` — it's the #1 source of aggregation errors.
4. Use `default_rng(seed)` for reproducible simulations.
5. Memory layout (C vs F) and axis choice interact for performance.

## Connects To
- **Ch 4**: Python containers → arrays conversion
- **Ch 6**: pandas wraps ndarray with labels
- **Ch 28**: simulation builds directly on Generator + broadcasting
