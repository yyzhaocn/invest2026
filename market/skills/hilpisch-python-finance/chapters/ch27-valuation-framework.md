# Chapter 27: Valuation Framework

## Core Idea
Risk-neutral valuation is an **architecture statement**, not just a formula: V₀ = E^ℚ(e^{−∫r dt}·h(S_T)) maps to software modules — time handling, discounting, simulation of risk factors, payoff evaluation — kept orthogonal with small public interfaces. Implemented as `dxlib` (time, curves, env) with dependency injection via a market environment.

## Frameworks Introduced
- **Orthogonal module design (dxlib)**: `dxlib.time` (year fractions, time-to-maturity), `.curves` (discount curve objects), `.env` (MarketEnvironment container), `.processes` (Ch 28), `.payoffs`, `.valuation`, `.lsm` (Ch 29), `.portfolio` (Ch 30) — each single-responsibility, replaceable/extendable.
- **Deterministic by default, interchangeable by design**: flat rate default; InterpolatedZeroCurve for term structure; curves and rates injected via MarketEnvironment (`.add_*()` / `.get_*()`), so models swap without rewriting callers.
- **Time conventions**: ACT/365.25 year fractions (`year_fractions()`, `time_to_maturity()`); `ensure_datetime_array()` normalizes date inputs; day_count parameterized.

## Key Concepts
- **Discount curve objects**: `ConstantShortRateCurve` (flat, continuously compounded), `InterpolatedZeroCurve` (zero rates between dated nodes, `extrapolate` option).
- **MarketEnvironment**: bundles constants, lists, curves — reproducible valuation runs; the dependency-injection container.
- **Four pricing requirements from the formula**: consistent time axis, discounting model, risk-neutral dynamics, payoff function.

## Mental Models
- Use X when Y: *flat curve when* prototyping; *interpolated curve when* term structure matters; *MarketEnvironment when* passing market inputs explicitly.
- Think of valuation as *a pipeline of swappable contracts*: time → discount → simulate → payoff.

## Anti-patterns
- **Hardcoding rates in pricing functions** — breaks testability.
- **Date arithmetic without day-count conventions** — ambiguous maturities.
- **Fat modules mixing responsibilities** — violates the orthogonality goal.

## Code Examples
```python
import numpy as np
from dxlib.time import year_fractions, time_to_maturity
from dxlib.curves import ConstantShortRateCurve
from dxlib.env import MarketEnvironment

t0 = "2027-01-04"
grid = year_fractions(t0, ["2027-01-04", "2027-07-04", "2028-01-04"])  # ACT/365
curve = ConstantShortRateCurve(name="flat", reference_date=t0, rate=0.02)
curve.discount_factor(1.0)              # exp(-0.02) ≈ 0.9802

env = MarketEnvironment()
env.add_constant("initial_value", 100.0)
env.add_curve("discount_curve", curve)
env.get_curve("discount_curve")         # explicit market inputs
```
- **What it demonstrates**: time grid, discount curve, environment injection.

## Worked Example
Sanity check: price a 1y European call by hand — grid 0→1y, flat 2% curve discount factor e^{−0.02}, simulated S_T (Ch 28), payoff max(S_T−K,0), expectation → present value. Swap the flat curve for an interpolated zero curve and re-price to see the architecture pay off.

## Key Takeaways
1. Valuation = V₀ = E^ℚ(DF·payoff) — each term is a swappable module.
2. dxlib keeps time/curves/env orthogonal with small public APIs.
3. Deterministic defaults, injectable alternatives.
4. Explicit day-count conventions avoid maturity ambiguity.

## Connects To
- **Ch 28**: simulation fills the risk-factor contract
- **Ch 29**: valuation + LSM build on this
- **Ch 30**: portfolio aggregation
