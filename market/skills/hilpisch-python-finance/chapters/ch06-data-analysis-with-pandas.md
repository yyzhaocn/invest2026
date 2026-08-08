# Chapter 6: Data Analysis with pandas

## Core Idea
pandas wraps NumPy arrays with labels: `Series` (1D labeled) and `DataFrame` (2D labeled table) make time-indexed, multi-instrument financial data natural to explore, clean, and aggregate.

## Frameworks Introduced
- **Label vs Position Indexing**: `.loc[label]` for calendar-aware selection (dates, partial strings like `df.loc["2027-01"]`); `.iloc[pos]` for positional/rolling-window logic. Never rely on ambiguous legacy indexing.
- **Resample-Report Loop**: resample higher-frequency to decision frequency (`df["price"].resample("W").last()`, monthly/quarterly for reporting and risk).
- **Missing-Data Policy**: `.isna()/.notna()` to make missingness explicit; `.dropna()` when missingness excludes the observation, `.ffill()` for sticky quantities (last traded price, balances); never silently propagate NaN.
- **groupby-agg pattern**: `df.groupby("symbol")["price"].agg(["mean","min","max"])` — one pass for multi-instrument summaries.

## Key Concepts
- **DatetimeIndex unlocks everything**: convert string index via `pd.to_datetime`; partial-string indexing and resampling require it.
- **Single-column select returns Series; list select returns DataFrame**; single-row `.loc` may upcast ints to float — use `.loc[["row"]]` to preserve dtypes.
- **NaN**: the missing-value sentinel; `isna()` returns boolean DataFrame.
- **Interoperability**: `df["price"].to_numpy()` for speed/third-party libs; `DataFrame(dict_of_arrays, index=dates)` from NumPy.
- **Long format** (date, symbol, price rows) is the natural input for groupby.

## Mental Models
- Think of DataFrame as *a dict of aligned Series sharing an index*; rows = observations, columns = named fields.
- Use X when Y: *.loc when* selection is calendar-based; *.iloc when* you mean relative positions (previous 20 rows).
- Use X when Y: *dropna when* missing ⇒ exclude; *ffill when* the quantity is sticky between observations.

## Anti-patterns
- **Ambiguous chained indexing** (`df["price"][mask]`) — prefer `.loc`.
- **Working with string date indices** — convert to DatetimeIndex early.
- **Silent NaN propagation** — decide drop vs fill explicitly.
- **Manual loops for per-symbol stats** — groupby does it in one pass.

## Code Examples
```python
import pandas as pd
import numpy as np

df = pd.DataFrame({"price": [100.0, 101.5, 103.2], "volume": [1_000, 1_500, 800]},
                  index=pd.to_datetime(["2027-01-08", "2027-01-11", "2027-01-12"]))

# time-indexed selection + resample
df.loc["2027-01"]                       # partial-string: all of January
df["price"].resample("W").last()        # weekly close

# missing data
df.loc["2027-01-11", "price"] = np.nan
df.dropna(subset=["price"])             # drop missing
df["price"].ffill()                     # forward-fill sticky values
df["price"].notna()                     # boolean mask

# groupby multi-agg
quotes = pd.DataFrame({"date": ["2027-01-08","2027-01-08","2027-01-11","2027-01-11"],
                       "symbol": ["AAPL","MSFT","AAPL","MSFT"],
                       "price": [180.0, 350.0, 182.0, 355.0]})
quotes.groupby("symbol")["price"].agg(["mean", "min", "max"])

# simple returns
df["ret"] = df["price"].pct_change()    # or .diff()/df["price"].shift()
```
- **What it demonstrates**: DatetimeIndex, resample, missing handling, groupby, returns.

## Worked Example
Daily price → weekly report: read CSV → `to_datetime` index → drop/fill NaN policy → `resample("W").last()` for weekly closes → `groupby("symbol")` mean/min/max for a multi-symbol report table — the exact pipeline pattern used in later asset-management chapters.

## Key Takeaways
1. Series = labeled 1D; DataFrame = labeled 2D; always know index vs columns.
2. Convert to DatetimeIndex early — it unlocks resample, partial indexing, alignment.
3. `.loc` for labels, `.iloc` for positions — keep them separate.
4. groupby + agg answers per-symbol/per-day questions in one expression.

## Connects To
- **Ch 5**: NumPy underneath; `to_numpy()` for performance
- **Ch 9**: financial time series in depth
- **Ch 17-21**: asset management pipelines on DataFrame foundations
