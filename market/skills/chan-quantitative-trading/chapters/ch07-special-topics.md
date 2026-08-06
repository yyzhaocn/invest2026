# Chapter 7: Special Topics in Quantitative Trading

## Core Idea
The two great strategy families — mean reversion and momentum — differ in their statistical premise (stationarity vs trend persistence); cointegration is the tool that turns non-stationary pairs into mean-reverting spreads.

## Frameworks Introduced

### Mean-Reverting vs Momentum
- **Mean reversion**: overreaction → price returns to mean; profit by fading extremes. Requires **stationary** series.
- **Momentum**: underreaction → trends persist; profit by riding. Works on **non-stationary** series.
- Each market/instrument has a natural regime — match strategy to it (and to the strategy's own timeframe).

### Stationarity & Cointegration
- A series is stationary if its statistical properties are time-invariant; a single price is usually non-stationary, its **returns** are.
- **Cointegration**: two non-stationary series (e.g., GLD/GDX) can have a stationary linear combination — the **spread**.
- **Test**: ADF (Augmented Dickey-Fuller) test for stationarity of the spread.
- **Half-life of mean reversion**: how fast the spread reverts — a first-order autoregression coefficient gives `half-life = −ln(2)/ln(β)`; it sizes the lookback and holding period.
- Example: long GLD / short GDX spread backtested for mean reversion (cointegration package in R/Python).

### Optimization
- **Unconditional**: fixed parameters across regimes.
- **Conditional**: regime-dependent parameters (train per regime) — more powerful but higher overfit risk; validate out-of-sample.

## Key Concepts
- **Stationarity**: time-invariant statistical properties.
- **Cointegration**: stationary combination of non-stationary series.
- **Spread**: the (β-weighted) difference used for mean reversion.
- **ADF test**: unit-root test for stationarity.
- **Half-life**: mean-reversion speed → lookback sizing.

## Worked Example
GLD vs GDX: both non-stationary; regress GLD on GDX → residual spread; ADF confirms spread stationary; half-life ≈ 20 days → use ~20-day lookback for entry/exit; trade spread mean reversion (buy when spread z-score < −2, exit at 0).

## Key Takeaways
1. Know which family you're in: mean reversion needs stationarity, momentum needs persistence.
2. Cointegration (ADF + half-life) is the principled way to find mean-reverting spreads.
3. Half-life sets the lookback — don't guess it.
4. Conditional optimization risks overfitting; always out-of-sample validate.

## Connects To
- **Ch 3**: backtest the spread with costs before trusting it.
- **kaabar ch06**: volatility/ATR apply to the spread's z-score too.
- **Repo**: scan/backtest could host a cointegration screener.
