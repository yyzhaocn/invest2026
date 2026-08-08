# Glossary

**American option** — option exercisable at any time before expiry; priced via LSM because of early-exercise optionality (Ch 29)

**Antithetic sampling** — variance reduction pairing z with −z draws (requires even path count) (Ch 28)

**Baseline-first ML** — try linear models before nonlinear; synthetic datasets verify learned structure (Ch 15)

**Benchmark-relative mandate** — performance judged vs a specified index (tracking error, capture) (Ch 17, 26)

**Bump-and-revalue delta** — portfolio Greek by perturbing spot and re-pricing the book (Ch 30)

**Code-first workflows** — version-controlled, rerunnable scripts replacing spreadsheet logic (Ch 1)

**Cross-sectional snapshot** — assets × attributes at a single date (Ch 17)

**Dataclass** — `@dataclass` auto-generating `__init__`/`__repr__` from annotations (Ch 7)

**DatetimeIndex** — pandas datetime row index enabling date slicing, resampling, alignment (Ch 6, 9)

**Decimal** — exact decimal arithmetic for money-like quantities (Ch 4)

**Deep copy** — duplicates container and nested objects; vs shallow copy sharing nested (Ch 4)

**Discount curve** — object mapping year-fraction maturities to discount factors (Ch 27)

**EMH (Efficient Market Hypothesis)** — null baseline: simple public rules shouldn't beat costs persistently; weak/semi-strong/strong forms (Ch 22)

**Efficient frontier** — envelope of random portfolios in risk-return space (Ch 14)

**Expected Shortfall** — mean loss beyond VaR; tail measure beyond quantile (Ch 13)

**Fail fast** — validate inputs with clear errors before computing (Ch 2)

**GBM (Geometric Brownian Motion)** — log-normal equity model: dS = μS dt + σS dW (Ch 13, 28)

**Generator (numpy)** — `np.random.default_rng(seed)` modern RNG interface (Ch 5, 13)

**Global minimum-variance portfolio** — lowest variance under full investment; closed form Σ⁻¹1/(1ᵀΣ⁻¹1) (Ch 18)

**groupby-agg** — pandas grouped aggregation for per-symbol/day summaries (Ch 6)

**Heston model** — stochastic-volatility model (κ, θ, vol-of-vol, ρ) for smile dynamics (Ch 28, 31)

**Implementation shortfall** — gross alpha minus transaction/slippage/infrastructure costs (Ch 26)

**Implied volatility** — volatility inverted from market option price via Black-76 (Ch 31)

**Jump diffusion (Merton)** — log-normal jumps + diffusion for short-horizon smile (Ch 28, 31)

**Log returns** — ln(P_t/P_{t−1}); additive over time (Ch 9)

**LSM (Longstaff-Schwartz)** — least-squares Monte Carlo for American options via continuation-value regression (Ch 29)

**Mandate / IPS** — written contract between asset owner and manager: universe, benchmarks, constraints, reporting (Ch 17)

**MarketEnvironment** — dependency-injection container for valuation inputs (Ch 27)

**Moment matching** — variance reduction shifting/scaling draws to sample mean 0, std 1 (Ch 28)

**Monte Carlo valuation** — V₀ = E^ℚ(DF·payoff) via simulated paths (Ch 13, 29)

**Multiple testing** — inflated false discoveries when testing many hypotheses (Ch 22)

**Numba** — `@nb.njit` JIT compiles Python loops via LLVM (Ch 11)

**Panel data** — returns/holdings over time for many instruments (Ch 17)

**PathSimulator** — simulation protocol: `.simulate_paths(spot, time_grid, paths)` (Ch 28)

**Put-call parity** — C − P = F·DF − K·DF; used to infer forwards (Ch 31)

**RAG (Retrieval-Augmented Generation)** — retrieve chunks → ground LLM answers (Ch 16)

**Resampling** — pandas frequency conversion (e.g. daily → weekly `resample("W").last()`) (Ch 6, 9)

**Risk-neutral measure ℚ** — measure under which discounted prices are martingales (Ch 27)

**Self-attention** — token weighting by query×key scores (Ch 16)

**Shrinkage** — regularizing noisy μ/Σ estimates toward priors (Ch 18)

**Signal** — time series aligned to instruments/dates; used for selection/sizing/timing (Ch 19)

**TF-IDF** — term frequency × inverse document frequency text features (Ch 16)

**Tracking error** — deviation of portfolio returns from benchmark (Ch 17)

**VaR (Value-at-Risk)** — quantile of PnL distribution (Ch 13)

**Vectorization** — whole-array NumPy ops moving loops to C (Ch 5, 11)

**Walk-forward** — rolling refit/predict evaluation for financial time series (Ch 22, 23)

**Year fraction** — ACT/365.25 time measure for discounting (Ch 27)
