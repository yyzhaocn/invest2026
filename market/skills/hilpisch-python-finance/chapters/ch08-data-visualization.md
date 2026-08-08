# Chapter 8: Data Visualization

## Core Idea
Static Matplotlib figures with the **object-oriented fig/axes API** (style `seaborn-v0_8`) — a reusable grammar for time series, distributions, multi-panel comparisons, and 3D views; read plots as *shape* (center, spread, asymmetry, tails), not bars.

## Frameworks Introduced
- **Figure/Axes grammar**: `fig, ax = plt.subplots()`; draw on `ax`, save `fig.savefig()`; pandas `.plot()` returns an Axes you can customize. Use reusable scripts for report figures (style, fonts, DPI, paths) vs short snippets for exploration.
- **Multi-panel comparison**: `plt.subplots(2,1, sharex=True)` stacks prices over returns; link spike → move; `fig.tight_layout()`.
- **Distribution reading**: histograms of returns (30 bins, `pct_change().dropna()`) to see skew/kurtosis/tails before any parametric modeling.
- **Dual scale / axes**: separate `ax2 = ax.twinx()` when series have different units/scales.

## Key Concepts
- **pandas-native plotting**: `prices.plot(figsize=(6,3))` with DatetimeIndex x-axis.
- **Style baseline**: `plt.style.use("seaborn-v0_8")` for consistent look.
- **Line semantics**: once >1 series, linestyle/marker/legend carry analytical weight — disambiguation matters.
- **Bar/axhline**: returns bars + `ax.axhline(0.0)` zero line.
- **3D**: `ax.plot_surface` / `ax.scatter` for surfaces (e.g. vol surfaces) and scatter relationships.

## Mental Models
- Use X when Y: *subplots when* comparing related series; *histogram when* judging return distribution shape; *scatter when* testing relationships; *twinx when* scales differ.
- Think of a figure as *a claim with axes*: title states it, labels define units, grid aids reading.

## Anti-patterns
- **Plotting prices without considering returns** — levels mislead; returns reveal distribution.
- **Ignoring legend/line-style when series overlap** — ambiguity destroys analytical value.
- **Notebook-only figures** — report figures should be reproducible scripts.
- **3D for 2D data** — use 3D only for genuine surfaces.

## Code Examples
```python
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
plt.style.use("seaborn-v0_8")

rng = np.random.default_rng(seed=42)
dates = pd.date_range("2027-01-06", periods=200, freq="B")
prices = pd.Series(100 * (1 + rng.normal(0, 0.01, 200)).cumprod(), index=dates, name="price")
rets = prices.pct_change().dropna()

# stacked: prices over returns
fig, (ax_price, ax_ret) = plt.subplots(2, 1, figsize=(6, 4), sharex=True)
ax_price.plot(prices, color="tab:blue")
ax_price.set_title("Prices and Returns"); ax_price.set_ylabel("Price")
ax_ret.bar(rets.index, rets, color="tab:orange", width=0.8)
ax_ret.axhline(0.0, color="black", linewidth=0.8)
ax_ret.set_ylabel("Return")
fig.tight_layout()
fig.savefig("prices_and_returns.png", dpi=150)

# histogram
fig, ax = plt.subplots(figsize=(6, 3))
ax.hist(rets, bins=30, color="tab:gray", edgecolor="black", alpha=0.7)
ax.set_title("Daily Returns Histogram")
```
- **What it demonstrates**: fig/axes API, subplots+sharex, pandas plot integration, histogram.

## Worked Example
Lab: "The Importance of Return Tails for Investing and Trading" — plot daily return histogram of a real index vs a normal distribution overlay; heavy tails show up as excess observations beyond ±3σ. This motivates non-normal risk measures (VaR/CVaR) used in later chapters.

## Key Takeaways
1. Use the object-oriented fig/axes API — works in notebooks and scripts.
2. Histograms of returns reveal skew/kurtosis — read shape, not bars.
3. Multi-panel + sharex connects returns to price moves.
4. Disambiguation (line style, legend) is analytical, not cosmetic.

## Connects To
- **Ch 6**: pandas Series/DataFrame plotting
- **Ch 14**: statistics of returns (tails, moments)
- **Ch 18**: portfolio risk visualizations
