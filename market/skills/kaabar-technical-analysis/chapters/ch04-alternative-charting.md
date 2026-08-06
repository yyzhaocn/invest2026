# Chapter 4: Alternative Charting Systems

## Core Idea
Charts are the first line of offense in technical analysis — alternative constructions (volume candlesticks, Heikin-Ashi, K's candlesticks) filter noise and reveal trend/volume truth that regular candlesticks hide.

## Frameworks Introduced

### Volume Candlesticks Charting System
- Candles encode **volume context**, not just OHLC: a bullish-looking candle on a regular chart may be weak when volume is low.
- Use when: you have quality volume data. A strong up-move on rising volume is trustworthy; the same move on shrinking volume is suspect.
- Main advantage: exposes whether price moves are volume-backed.

### Heikin-Ashi System
- Purpose: **filter market noise**, give a clearer picture of the trend.
- Construction (modified candles):
  - `HA close = (O + H + L + C) / 4`
  - `HA open = (prev HA open + prev HA close) / 2`
  - HA high/low = extremes of HA values and true ranges.
- Consequences: smoother candles, no/low wicks in strong trends, multi-candle sequences that are easier to read for trend strength.
- Pattern-recognition tools can be applied to Heikin-Ashi candles too (Ch7-10 techniques port over).

### K's Candlestick Charting System
- Author's alternative OHLC construction; see ch11 for the philosophy of K's collection.

## Key Concepts
- **Volume-backed move**: price change accompanied by proportionally high volume.
- **HA close**: average of the four OHLC prices.
- **HA open**: average of previous HA open and close — creates the smoothing.

## Code Example
```python
def heikin_ashi(df):
    ha = df.copy()
    ha['HA_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_open = [(df['open'].iloc[0] + df['close'].iloc[0]) / 2]
    for i in range(1, len(df)):
        ha_open.append((ha_open[-1] + ha['HA_close'].iloc[i-1]) / 2)
    ha['HA_open'] = ha_open
    return ha
```
- **What it demonstrates**: HA open/close recursion — the core of noise-filtered candles.

## Reference Table
| Chart system | Filters | Main signal value |
|--------------|---------|-------------------|
| Regular candlesticks | nothing | raw OHLC detail |
| Volume candlesticks | price×volume | volume confirmation |
| Heikin-Ashi | noise | clear trend reading |
| K's candlesticks | varies | author's alternative construction |

## Key Takeaways
1. Always ask: is this move volume-backed? Volume candles answer directly.
2. Heikin-Ashi turns choppy trends into readable one-directional candle sequences.
3. Alternative charts don't replace analysis — they change what's visible; apply the same pattern/indicator logic on top.

## Connects To
- **Ch 7-10**: pattern recognition can run on Heikin-Ashi candles.
- **Ch 11**: K's candlestick system shares the K's collection design philosophy.
