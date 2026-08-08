# Chapter 9: Financial Time Series

## Core Idea
Clean, correctly-indexed time series are the foundation of everything that follows: load with `parse_dates`/`index_col`, make missingness explicit, derive returns/log returns, resample to decision frequencies, and compute rolling/correlation analytics on a proper DatetimeIndex.

## Frameworks Introduced
- **Local/Remote fallback loader**: prefer local CSV under `data/`, fall back to remote URL if missing — always return a DataFrame with proper DatetimeIndex.
- **Import-time correctness**: `pd.read_csv(source, parse_dates=["Date"], index_col="Date")` — get the datetime index right at load; post-hoc fix is `pd.to_datetime` + `set_index` + `sort_index`.
- **Systematic structure inspection**: `shape`, `columns`, `index.min()/max()`, `.info()` (dtypes/memory); reindex to full business-day range (`freq="B"`) and count `isna().any(axis=1).sum()` to reveal gaps.
- **Missing-data strategy matrix**: dropna (missing ⇒ exclude), ffill (sticky quantities), interpolate(method="time") (charting only — use with care in risk/PnL).
- **Returns normalization**: `pct_change()` simple returns; `np.log(prices/prices.shift(1))` log returns (additive over time); `df.div(base)` normalize to 1.0 for relative performance comparison.

## Key Concepts
- **DatetimeIndex unlocks .loc date slicing**: `df.loc["2016-01-04"]` single day, `df.loc["2016-01"]` partial-string month, `df.loc["2016-01", ["AAPL","SPY"]]` day+columns.
- **RangeIndex pitfall**: reading CSV without index_col makes `.loc["2016-01-04"]` raise KeyError — the classic "doesn't behave like a time series" symptom.
- **Resample anchors**: `"ME"` month-end (last obs), `"W-FRI"` weekly anchored Friday; then `.pct_change()` for monthly/weekly returns.
- **Rolling stats**: `.rolling(window).mean()` for SMA — the base indicator primitive.
- **Correlation**: `.corr()` across asset return columns.

## Mental Models
- Use X when Y: *ffill when* quantity is sticky (balances, last traded price); *dropna when* missingness should exclude the observation; *interpolate when* only charting.
- Think of index correctness as *the contract*: date-aware operations (resample, partial-index, alignment) silently fail on RangeIndex.

## Anti-patterns
- **Forgetting parse_dates/index_col** at import — fixable but a recurring source of KeyError confusion.
- **Silent NaN propagation** in returns — check first row after `pct_change()`.
- **Interpolating risk/PnL series** — fabricates observations.
- **Resampling before returns** — decide level (daily/monthly) before computing return series.

## Code Examples
```python
import pandas as pd, numpy as np
from pathlib import Path

LOCAL, REMOTE = Path("data/eod_data.csv"), "https://hilpisch.com/eod_data.csv"
df = pd.read_csv(LOCAL if LOCAL.exists() else REMOTE,
                 parse_dates=["Date"], index_col="Date")
# df: 2514 days × 8 assets (AAPL NVDA JPM SPY GLD TLT EURUSD BTC-USD) 2016-2025

# structure checks
df.loc["2016-01", ["AAPL", "SPY"]].head()        # partial-string month slice
gaps = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="B"))
gaps.isna().any(axis=1).sum()                    # business days with any NaN

# returns & log returns
rets = df[["AAPL","SPY"]].pct_change()
log_rets = np.log(df / df.shift(1))
norm = df[["AAPL","SPY","GLD","TLT"]].div(df.loc["2016-01-04", ["AAPL","SPY","GLD","TLT"]])

# resample
spy_monthly = df["SPY"].resample("ME").last()
spy_monthly.pct_change().describe()[["mean","std"]]

# rolling
df["SPY"].rolling(20).mean()                     # 20-day SMA

# correlation
df.pct_change().corr()
```
- **What it demonstrates**: canonical load, date slicing, gap detection, returns, resample, rolling, corr.

## Worked Example
EOD workflow: load `eod_data.csv` (2016-01-04 → 2025-12-31, 2514 rows) with DatetimeIndex → inspect → create a 5%-random-missing sub-sample of AAPL → apply dropna vs ffill vs interpolate and compare → compute SPY monthly returns via `resample("ME").last().pct_change()` → 20-day SMA → cross-asset correlation matrix.

## Key Takeaways
1. Configure `parse_dates`/`index_col` at import; verify with shape/index/info.
2. Check the calendar: reindex to full business days and count gaps.
3. Returns (not prices) are the analysis unit; log returns aggregate over time.
4. Resample to the decision frequency; rolling windows for indicators; corr for relationships.

## Connects To
- **Ch 6**: pandas foundations
- **Ch 10**: I/O for other data formats
- **Ch 17-19**: asset management uses these series directly
