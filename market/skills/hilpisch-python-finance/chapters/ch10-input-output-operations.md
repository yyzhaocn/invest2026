# Chapter 10: Input/Output Operations

## Core Idea
Assemble a reusable I/O toolkit: standard library for text/pickle, NumPy `.npy/.npz` for arrays, pandas for CSV/JSON, SQLite/HDF5 (via PyTables) for larger panels — always with a dedicated disposable scratch folder (`_tmp/`) and reproducible read/write functions.

## Frameworks Introduced
- **Scratch-folder discipline**: all example I/O goes to a dedicated `_tmp/` dir — keeps working dir tidy, avoids overwriting real files.
- **Format-by-need matrix**: text (exchange/reports), pickle (your own short-lived objects), `.npy/.npz` (numerical arrays, near-hardware I/O speed), CSV (desk/partner interchange), JSON, SQLite (structured queries), HDF5/PyTables (large panels, compressed, out-of-memory EArray).
- **Chunked CSV reading**: for very large files, read in chunks rather than all into memory.

## Key Concepts
- **Context managers** for all file opens; `pathlib.Path` for paths.
- **pickle is unsafe**: never unpickle untrusted data — `pickle.load()` executes arbitrary code.
- **np.save/np.load**: single arrays, binary, shape+dtype preserved; `np.savez` bundles named arrays (`.npz`).
- **pandas to_csv/read_csv**: control `index=True`, `parse_dates`, `index_col` — round-trip must preserve DatetimeIndex (`reloaded.equals(prices)`).
- **SQLite**: SQL queries over stored data; **HDF5**: efficient for larger panels; **PyTables EArray**: out-of-memory computations (append-only arrays exceeding RAM).
- **TsTables**: time-series tables on HDF5.

## Mental Models
- Use X when Y: *CSV when* exchanging with desks/systems; *npz when* storing simulation results; *HDF5 when* panels exceed memory or need compression; *SQLite when* you need query semantics.
- Think of I/O as *the boundary layer*: fragile I/O corrupts otherwise-fast analytics.

## Anti-patterns
- **Unpickling untrusted files** — arbitrary code execution risk.
- **Re-parsing text repeatedly** for the same experiment — use binary `.npy`.
- **Loading huge CSVs fully into memory** — chunk or use HDF5/PyTables.
- **Mixed paths/encoding assumptions** — use pathlib + explicit `encoding="utf-8"`.

## Code Examples
```python
from pathlib import Path
import pickle, numpy as np, pandas as pd

TMP = Path("_tmp"); TMP.mkdir(exist_ok=True)

# text with context manager
p = TMP / "report.csv"
with p.open("w", encoding="utf-8") as f:
    f.write("symbol,price,quantity,value\n")
    f.writelines(["AAPL,180.25,10,1802.50\n", "SPY,520.10,5,2600.50\n"])

# numpy binary
rng = np.random.default_rng(seed=42)
rets = rng.normal(0.0003, 0.01, 252)
np.save(TMP / "daily_returns.npy", rets)
np.savez(TMP / "bundle.npz", returns=rets, prices=100*(1+rets).cumprod())
data = np.load(TMP / "bundle.npz"); data.files  # ['returns', 'prices']

# pandas CSV round-trip
prices.to_csv(TMP / "eod_prices.csv", index=True)
reloaded = pd.read_csv(TMP / "eod_prices.csv", parse_dates=["Date"], index_col="Date")
reloaded.equals(prices)   # True
```
- **What it demonstrates**: text, pickle, numpy, pandas patterns.

## Reference Tables
| Need | Tool | Notes |
|---|---|---|
| Small exchange files | CSV/text | chunk for large |
| Own objects | pickle | unsafe for untrusted input |
| Numerical arrays | np.save/npz | binary, fast |
| Structured queries | SQLite | SQL semantics |
| Large panels | HDF5/PyTables | compression, EArray out-of-memory |
| Time series tables | TsTables | HDF5-based |

## Worked Example
EOD prices pipeline: load `eod_data.csv` (local/remote fallback, parse_dates/index_col) → write to CSV with index → reload and assert `equals` → save full panel to HDF5 with compression → query a date range from SQLite for a small positions report.

## Key Takeaways
1. Dedicated scratch folder keeps I/O experiments safe.
2. Choose format by data size and query needs: CSV → npz → SQLite → HDF5/PyTables.
3. Round-trip tests (`equals`) catch index/dtype corruption.
4. Never unpickle untrusted data.

## Connects To
- **Ch 9**: EOD loading pattern reused
- **Ch 11**: I/O speed vs compute speed in performance work
- **Ch 20-21**: reporting systems persist results
