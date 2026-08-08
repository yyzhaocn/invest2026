# Chapter 29: Derivatives Valuation

## Core Idea
From paths to values with **orthogonal pricing blocks**: time axis + discounting + simulation + payoff — `EuropeanMCPricer` for terminal payoffs (needs only S_T), and Least-Squares Monte Carlo (`AmericanPutLSM`) for American puts (needs all intermediate S_t and the Longstaff-Schwartz regression).

## Frameworks Introduced
- **Valuation blocks**: `DiscountingModel` protocol (`.discount_factor(ttm)`), `FlatDiscounting`, `discount_factors()` (vectorized over grid), `TerminalPayoff` protocol, `EuropeanCall/EuropeanPut` callable payoffs, `AmericanPut` (terminal payoff + pathwise `.intrinsic_value()`).
- **EuropeanMCPricer**: prices any terminal payoff from any PathSimulator — process, payoff, discounting, maturity, steps, paths.
- **LSM (Longstaff-Schwartz)**: at each exercise date, regress discounted continuation values on basis functions of spot (basis_degree, min_itm filter) → compare with intrinsic value → walk back optimal exercise; `AmericanPutLSM` simulates internally; `lsm_american_put_from_paths()` applies to externally simulated paths (Heston etc.).
- **Monte Carlo diagnostics**: visualize price vs path count, early-exercise boundary behavior.

## Key Concepts
- **European = terminal only**: V₀ = DF(T)·E^ℚ[h(S_T)].
- **American ≠ European**: early exercise option → needs continuation values at every step; LSM makes it tractable.
- **Why American options are different**: exercise decision at each date = optimal stopping problem.

## Mental Models
- Use X when Y: *EuropeanMCPricer when* terminal payoffs; *LSM when* American/early exercise; *external-path LSM when* models like Heston supply the paths.
- Think of LSM as *regressing future value onto current state* to approximate the optimal stopping rule.

## Anti-patterns
- **Pricing American as European** — ignores early exercise premium.
- **Regression on all paths** — use ITM paths (`min_itm`) for stability.
- **Mixed responsibilities** — keep discounting/dynamics/payoff separate.

## Code Examples
```python
from dxlib.valuation import EuropeanMCPricer, FlatDiscounting
from dxlib.payoffs import EuropeanCall, AmericanPut
from dxlib.lsm import AmericanPutLSM
from dxlib.processes import GeometricBrownianMotion

pricer = EuropeanMCPricer(process=GeometricBrownianMotion(0.02, 0.2),
                          payoff=EuropeanCall(strike=105.0),
                          discounting=FlatDiscounting(rate=0.02),
                          maturity=1.0, steps=12, paths=100_000)
call_price = pricer.price(spot=100.0)     # ≈ Black-Scholes

am_put = AmericanPutLSM(basis_degree=3, min_itm=0.1)
put_price = am_put.price(spot=100.0, strike=105.0, maturity=1.0,
                         process=GeometricBrownianMotion(0.02, 0.2),
                         discounting=FlatDiscounting(0.02), paths=100_000)
```
- **What it demonstrates**: European MC pricing and LSM American pricing.

## Worked Example
Pricing session: European put via EuropeanMCPricer ≈ BS reference; American put via LSM on an equity index — American price > European price (early-exercise premium); diagnostics: price convergence with paths, exercise boundary visualization, LSM regression fit.

## Key Takeaways
1. Four orthogonal blocks price anything: grid, discounting, simulation, payoff.
2. European pricer needs terminal spot only; American needs the whole path.
3. LSM = regress continuation value → compare with intrinsic → optimal exercise.
4. Diagnostics (convergence, boundaries) validate MC noise and behavior.

## Connects To
- **Ch 27-28**: architecture + simulation contracts
- **Ch 30**: portfolios of these prices
- **Ch 31**: market-calibrated models price real options
