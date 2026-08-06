# Chapter 3: Modern Technical Analysis Techniques and Indicators

## Core Idea
Beyond the SMA: exotic moving averages (WMA, IWMA, HMA, KAMA, ALMA, LSMA), smarter ways to use Bollinger bands and RSI, and the author's seven "Rainbow" indicators — all chosen to be less correlated with classic tools.

## Frameworks Introduced

### Exotic Moving Averages
- **WMA (weighted)**: weights grow with recency → responds faster to trend changes than SMA; more sensitive to outliers.
- **IWMA (inverse weighted)**: weights favor older data → smooth, slow; use to compare current price against the long-term norm.
- **WMA/IWMA cross**: ONE lookback parameter replaces two — WMA is the short MA, IWMA the long MA. Bullish when WMA crosses above IWMA.
- **HMA (Hull)**: `WMA(√n) of (2·WMA(n/2) − WMA(n))` — reduces lag while staying smooth; use when you need both responsiveness and noise filtering.
- **KAMA (Kaufman Adaptive)**: smoothing constant adapts via **efficiency ratio** ER = |net change| / Σ|per-period changes|. Responsive in trends, calm in chop — one MA for all regimes.
- **ALMA (Arnaud Legoux)**: Gaussian-windowed MA with offset/shift control.
- **LSMA (least squares)**: fits a regression line over the window; the indicator value is the fitted value — good for trend slope.

### Bollinger Band Techniques
- **Aggressive (default)**: buy close below lower band, sell close above upper band.
- **Conservative**: after a band touch, wait for price to **re-cross the middle band** — fewer false signals, delayed entry.
- **Trend-friendly**: take only the conservative signal aligned with the trend direction.
- **Bollinger–RSI overlay**: confirm band-touch signals with RSI.

### RSI Techniques
- **Aggressive**: classic 30/70 extremes.
- **V technique**: RSI pierces an extreme then reverses sharply (V-shape) — earlier reversal signal than the extreme itself.
- **DCC (Double Conservative Confirmation)**: require two consecutive conservative confirmations — author's personal favorite; high conviction, fewer trades.

### The Rainbow Collection (7 proprietary indicators)
- **Red, Orange, Yellow, Green, Blue, Indigo, Violet**: seven indicators using different math (price/time/MA fusions, slope divergence, etc.).
- **Yellow indicator** introduces the **slope-divergence technique** (reused later in K's RSI², Ch11).
- Purpose: **decorrelation** — mixing Rainbow indicators with classic ones beats stacking correlated classics.

## Key Concepts
- **Weighted average**: Σ(weight × value) / Σ(weights).
- **Efficiency ratio (ER)**: trendiness measure feeding KAMA's smoothing.
- **Middle-band re-cross**: the conservative Bollinger confirmation event.
- **Slope divergence**: comparing the slope of price vs slope of an indicator.

## Code Example
```python
def wma(my_time_series, source='close', ma_lookback=50):
    weights = np.arange(1, ma_lookback + 1)
    my_time_series['WMA'] = 0
    for i in range(ma_lookback - 1, len(my_time_series)):
        window = my_time_series[source].iloc[i - ma_lookback + 1:i + 1]
        weighted_sum = np.dot(window, weights)
        my_time_series['WMA'].iloc[i] = weighted_sum / weights.sum()
    return my_time_series['WMA'].dropna()
```
- **What it demonstrates**: WMA core; `iwma()` is identical with `weights[::-1]`; `hma()` combines two WMAs and re-smooths.

## Reference Table
| MA | Responsiveness | Smoothness | Best for |
|----|---------------|------------|----------|
| SMA | low | low | baseline |
| WMA | medium | medium | recent-weighted trend |
| IWMA | very low | high | long-term comparison |
| HMA | high | high | lag-free trend |
| KAMA | adaptive | adaptive | regime-switching |
| ALMA | tunable | high | noise filtering |
| LSMA | high | low | slope/regression |

## Worked Example
WMA/IWMA cross with a single window (e.g., 50) on an index: buy when WMA(50) crosses above IWMA(50), exit when it crosses below — no second parameter to optimize, unlike SMA crosses.

## Key Takeaways
1. HMA and KAMA are the workhorse modern MAs — one reduces lag, one adapts to regime.
2. The WMA/IWMA cross removes a free parameter from crossover strategies.
3. Prefer conservative Bollinger/RSI confirmations over aggressive in choppy markets.
4. Use the V technique and DCC to catch reversals earlier or with more conviction.
5. Decorrelation (Rainbow + classics) beats piling on correlated classics.

## Connects To
- **Ch 1**: these indicators answer the "rusty indicators" and "correlation" critiques.
- **Ch 6**: volatility indicators build on the same windowed-math patterns.
- **Ch 11**: K's RSI² reuses the slope-divergence technique from the Yellow indicator.
