# Patterns

## Draft-Review for Generated Code
**When to use**: any AI-proposed code entering a financial workflow.
**How**: skim structure → check assumptions (columns, timezones, frequency) → scan numerics (day counts, compounding) → check error handling (fail loudly).
**Trade-offs**: cheap insurance against silent mispricing; doesn't replace domain review.

## Precise Prompting
**When to use**: asking GenAI for code.
**How**: context + constraints + typed interface (`summarize_prices(data: pd.DataFrame) -> dict[str, float]`).
**Trade-offs**: better fitting code; requires you to know the interface.

## Validation Triangle
**When to use**: any new computation.
**How**: toy example by hand → invariants as tests (probabilities sum 1, constant-price returns 0) → baseline comparison (known formula).
**Trade-offs**: small setup cost; catches most subtle errors.

## Vectorize → JIT → Parallel Ladder
**When to use**: slow numerical code.
**How**: NumPy vectorization first; `@nb.njit` for loop-structured code; multiprocessing for embarrassingly parallel (large chunks); Cython for manual control.
**Trade-offs**: vectorization allocates intermediates; JIT avoids them; parallelism adds process overhead.

## Walk-Forward Evaluation
**When to use**: any signal/forecast claim.
**How**: refit on rolling training window (2y), predict next block (1m), roll forward; report out-of-sample metrics + costs.
**Trade-offs**: honest but slower than single split; the minimum bar for financial ML.

## Vectorized vs Event-Based Parity
**When to use**: building backtests.
**How**: implement the same rule both ways; they must agree.
**Trade-offs**: event-based is slower but rehearses execution (orders/fills); parity catches structural bugs.

## Input Shrinkage
**When to use**: portfolio optimization inputs.
**How**: μ toward benchmark mean; Σ toward diagonal (λ weight).
**Trade-offs**: bias toward prior vs instability from noise.

## Signal → Rank → Weight
**When to use**: turning research signals into portfolios.
**How**: raw score → cross-sectional rank → weights under mandate caps.
**Trade-offs**: rank robustness vs score information.

## Bump-and-Revalue Greeks
**When to use**: portfolio-level sensitivity without analytical derivatives.
**How**: (V(spot+bump) − V(spot−bump)) / 2bump, re-pricing everything.
**Trade-offs**: model-agnostic; costs a full re-price per bump.

## Horizon-Split Calibration
**When to use**: fitting option models to a surface.
**How**: short horizon → Merton JD on one expiry; long horizon → Heston global + per-expiry local refinement.
**Trade-offs**: better fit across maturities; more moving parts than single-model.

## LSM Continuation Regression
**When to use**: pricing American options by simulation.
**How**: regress discounted future value on basis functions of spot (ITM paths only) → compare with intrinsic → walk back.
**Trade-offs**: tractable early exercise; regression basis choice matters.

## Environment Injection
**When to use**: valuation code that must swap rates/curves/models.
**How**: MarketEnvironment container with add/get; deterministic defaults, injectable alternatives.
**Trade-offs**: explicit wiring vs quick hardcodes.

## Simulation Contract
**When to use**: any Monte Carlo layer.
**How**: year-fraction grid from 0, (paths, steps+1) shapes, PathSimulator protocol, centralized RNG (seed/antithetic/moment-matching).
**Trade-offs**: small convention cost; eliminates downstream fragility.

## Friction Budget
**When to use**: judging strategy viability.
**How**: net = gross − tx − slippage − infra; break-even hit rate = eff_loss/(eff_gain+eff_loss).
**Trade-offs**: arithmetic only; frictions vary by venue/order size.

## Missing-Data Strategy Matrix
**When to use**: cleaning time series.
**How**: dropna (missing excludes observation) / ffill (sticky quantities) / interpolate (charting only).
**Trade-offs**: drop is conservative; ffill assumes stickiness; interpolate fabricates.
