# Chapter 2: Exploring Time Series Analysis with Python

## Core Idea
A practical Python refresher: importing/visualizing OHLC data with pandas and matplotlib is the foundation for every later chapter — master dataframes, control flow, functions, and plotting first.

## Frameworks Introduced

### Time Series Decomposition
Any time series decomposes into:
- **Trend** (bullish/bearish/sideways regime)
- **Seasonality** (regular repeating cycles)
- **Cycles** (irregular, economy-driven)
- **Noise** (unpredictable random component — markets can't always be predicted)

### OHLC Data Generation & Visualization
- `generate_ohlc_data(length_data=1000)`: simulates a random-walk OHLC series in a pandas dataframe.
- `ohlc_plot(series, window, plot_type)`: three views —
  - `bars` — thin black bars (long-term visual)
  - `candlesticks` — green up / red down bodies (interpretation)
  - `line` — close-only (simplicity)

## Key Concepts
- **Variable**: dynamic-typed named storage; `=` assigns, `==` compares.
- **Dataframe**: 2-D tabular structure (spreadsheet/SQL-like); `iloc` = positional access, `loc` = label access.
- **Filtering**: `df[df["close"] > 30]`; condition columns `df["flag"] = df["close"] > 30`.
- **Rolling ops**: `df["close"].rolling(window=5).mean()` (SMA), `.std()` (rolling deviation).
- **Control flow**: `if/elif/else`; `for` loops; `continue` (skip iteration), `break` (exit loop).
- **Functions**: `def name(params): return value` — local scope, modularity, abstraction.
- **Libraries**: numpy (numeric), pandas (dataframes), matplotlib (plots); install via `pip`, import via `import x as y`.

## Code Example
```python
def generate_ohlc_data(length_data=1000):
    data = {'open': np.zeros(length_data), 'high': np.zeros(length_data),
            'low': np.zeros(length_data), 'close': np.zeros(length_data)}
    data['open'][0] = np.random.uniform(100, 200)
    data['close'][0] = data['open'][0] + np.random.uniform(-5, 5)
    data['high'][0] = max(data['open'][0], data['close'][0]) + np.random.uniform(0, 5)
    data['low'][0] = min(data['open'][0], data['close'][0]) - np.random.uniform(0, 5)
    for i in range(1, length_data):
        data['open'][i] = data['close'][i-1] + np.random.uniform(-3, 3)
        data['close'][i] = data['open'][i] + np.random.uniform(-5, 5)
        data['high'][i] = max(data['open'][i], data['close'][i]) + np.random.uniform(0, 5)
        data['low'][i] = min(data['open'][i], data['close'][i]) - np.random.uniform(0, 5)
    return pd.DataFrame(data)
```
- **What it demonstrates**: simulating a realistic OHLC path with drift — the base data pattern used across the book.

## Reference Table
| Access | Meaning |
|--------|---------|
| `df.iloc[0]` / `df.iloc[-1]` | first / last row |
| `df.iloc[0:3]` | first three rows |
| `df.iloc[:, 0]` / `df.iloc[:, -1]` | first / last column |
| `df.loc[0, "close"]` | cell by label |

## Worked Example
Import CSV from the same path as the working directory, filter closes above 30, add a 5-period SMA column, plot candlesticks:
```python
my_data_frame = pd.read_csv("data.csv")
filtered = my_data_frame[my_data_frame["close"] > 30]
my_data_frame["SMA5"] = my_data_frame["close"].rolling(window=5).mean()
ohlc_plot(my_data_frame, window=250, plot_type="candlesticks")
```

## Key Takeaways
1. OHLC dataframes are the universal input — keep data in pandas, not lists.
2. Use `rolling()` for any windowed calculation (SMA, std, later indicators).
3. `iloc` by position vs `loc` by label — pick deliberately.
4. Functions + libraries (numpy/pandas/matplotlib) make indicator code reusable.
5. All book code is available at `github.com/sofienkaabar/mastering-financial-markets-in-python`.

## Connects To
- **Ch 3**: rolling windows become WMA/HMA/KAMA.
- **Ch 7-10**: pattern detection functions operate on the same OHLC frames.
- **Ch 12**: backtesting loops reuse the dataframe patterns here.
