# Chapter 6: Advanced Volatility Indicators

## Core Idea
Volatility is the risk currency of trading — measure it properly and it drives position sizing, stop-loss placement, diversification, and entry/exit timing.

## Frameworks Introduced

### Why Volatility Matters (utility map)
- **Position sizing**: higher volatility → smaller position for the same risk budget.
- **Stop-loss placement**: volatility-based stops (e.g., multiples of ATR) survive normal noise; fixed-percent stops get whipsawed in volatile assets.
- **Diversification**: comparing volatility across assets informs allocation.
- **Entry/exit timing**: low volatility often precedes breakouts; high volatility signals caution.

### Volatility Measurement Toolkit
- **Standard deviation** (rolling): baseline dispersion of returns/price.
- **Bollinger bands** (Ch3 link): mean ± k·σ — expand/contract with volatility; squeezes precede breakouts.
- **ATR (Average True Range)**: `TR = max(H−L, |H−prevC|, |L−prevC|)`; ATR = rolling mean of TR — the go-to stop-distance measure.
- **Channels**: volatility-scaled envelopes around price.

## Key Concepts
- **True Range (TR)**: captures gaps — the maximum of the day's range and the gaps to the previous close.
- **Volatility squeeze**: bands/channels compressing to historical lows → breakout watch.
- **Risk currency**: think of volatility as the unit you price risk in (X × ATR = stop distance).

## Code Example
```python
def true_range(df):
    prev_close = df['close'].shift(1)
    return pd.concat([
        df['high'] - df['low'],
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs()
    ], axis=1).max(axis=1)

def atr(df, window=14):
    return true_range(df).rolling(window).mean()
```
- **What it demonstrates**: TR handles overnight gaps; ATR smooths it — the basis for volatility-scaled stops and position size.

## Worked Example
ATR(14) = 2.0 on a 100-price asset. A 2×ATR stop = 4 (4% away). Risking 2% of a 100k account (2,000): position size = 2,000 / 4 = 500 shares. This is exactly how volatility feeds the position-size decision (see the repo's position-size skill for an implementation).

## Key Takeaways
1. Size positions and set stops in volatility units (ATR multiples), not fixed percentages.
2. Squeezes (low vol) are the setup; expansions (high vol) are the follow-through.
3. Different assets need different volatility treatments — don't reuse one stop % everywhere.
4. True Range, not just daily range, because gaps matter.

## Connects To
- **Ch 3**: Bollinger bands techniques assume volatility bands.
- **Ch 12**: Sharpe/Sortino measure return per unit of volatility — the same risk lens.
- **Repo skills**: `position-size` implements ATR-based sizing/stop logic.
