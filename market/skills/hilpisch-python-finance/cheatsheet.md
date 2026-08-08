# Cheatsheet — Python for Finance (Hilpisch 3rd ed)

## Decision Rules

- **Any AI-generated code** → 4-pass review (structure → assumptions → numerics → errors) before running. (ch2)
- **Money math** → `Decimal` with explicit context precision; floats lie (0.1+0.2≠0.3). (ch4)
- **Container choice** → append/mutate → list; fixed record → tuple; keyed lookup → dict; uniqueness → set. (ch4)
- **Slices are views** → `.copy()` when independence matters. (ch5)
- **pandas selection** → `.loc` for labels/dates, `.iloc` for positions; convert to DatetimeIndex early. (ch6)
- **Missing data** → dropna when missing excludes; ffill for sticky values; interpolate only for charts. (ch9)
- **Performance** → vectorize first, Numba second, multiprocessing third (large chunks). (ch11)
- **Returns vs prices** → analysis on returns; log returns add over time. (ch9)
- **Portfolio inputs** → always shrink μ (→benchmark) and Σ (→diagonal) before optimizing. (ch18)
- **Signal claims** → walk-forward + costs + multiple-testing awareness or no claim. (ch22)
- **Backtests** → vectorized and event-based implementations must agree on the same rule. (ch23)
- **Strategy viability** → net = gross − tx − slippage − infra; check retention ratio. (ch26)
- **American options** → LSM, never European-style pricing. (ch29)
- **Volatility** → options trade on a surface; calibrate JD short-horizon, Heston long-horizon. (ch31)
- **Simulation** → one seeded Generator; antithetic + moment matching; contract shapes. (ch13, 28)

## Thresholds & Defaults

| Item | Value | Where |
|---|---|---|
| Book Python baseline | ≥ 3.10/3.11 | ch3 |
| Default EOD universe | AAPL NVDA JPM SPY GLD TLT EURUSD BTC-USD | ch9 |
| Year fraction day count | ACT/365.25 | ch27 |
| Annualization | ×252 for variance, (1+μ)^252−1 for mean | ch18 |
| Walk-forward windows | train 2×252, test 21 | ch23 |
| Antithetic requirement | even path count | ch28 |
| Min-ITM filter (LSM) | ~0.1 (10% ITM) | ch29 |
| Break-even hit rate | eff_loss/(eff_gain+eff_loss) | ch26 |
| Covariance shrink | λ≈0.2 toward diagonal | ch18 |
| Return normalization | div by base date price (start=1.0) | ch9 |
| MC error | ∝ 1/√M | ch13 |

## Tells & Smells

- **`.loc["2026-01-04"]` raises KeyError** → RangeIndex, dates not parsed: fix parse_dates/index_col. (ch9)
- **Weights look crazy (huge shorts/extremes)** → noisy covariance; shrink. (ch18)
- **Normality p-value ≈ 0** → expected; use tails-aware risk (VaR/ES). (ch14)
- **Vectorized vs event-based curves diverge** → structural bug in the rule. (ch23)
- **Apparent alpha that dies with 0.1% costs** → break-even arithmetic says no edge. (ch26)
- **Single flat vol "calibration"** → ignoring the smile surface. (ch31)
- **In-line `np.random.standard_normal()`** → unseeded, no variance reduction. (ch28)
- **Backtest "accuracy" without walk-forward** → in-sample overfit. (ch22)

## Trade-off Matrix

| Task | Tool | Trade-off |
|---|---|---|
| Fit noisy data | lstsq + basis fns | smoothness vs overfit |
| Respect trusted knots | CubicSpline | exact fit = assumption |
| Invert pricing | root_scalar brentq | needs bracket |
| Greeks | bump-and-revalue | model-agnostic, costly |
| Text baseline | TF-IDF + linear | fast/interpretable, no semantics |
| Text semantics | dense embeddings/LLM | costly, needs eval |
| Storage | CSV → npz → SQLite → HDF5 | size/queries vs complexity |
| RNG | Generator (antithetic/MM) | noise down, not bias |
| Early exercise | LSM | basis choice matters |
| AM mandates | benchmark-relative long-only | burden of proof on active |
