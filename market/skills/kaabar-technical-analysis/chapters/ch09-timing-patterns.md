# Chapter 9: Pattern Recognition in Python III — Timing Patterns

## Core Idea
Timing patterns add a **time condition** to price structure — unlike candlestick patterns (price only), they count bars/sessions to identify trend exhaustion or continuation points.

## Frameworks Introduced

### TD Setup (DeMark)
- Foundational DeMark pattern for identifying a trend and its **potential exhaustion point**.
- Counts consecutive closes in the same direction (e.g., 9 closes higher than the close 4 bars earlier = a setup count).
- **Thrives in ranging markets** (perfected or unperfected); underperforms during strong trends — regime matters.
- Completion of the setup count marks a potential reversal zone.

### Fibonacci Timing Pattern
- Applies Fibonacci ratios to **time** instead of price: projected turning points at ratios (e.g., 38.2%, 61.8%) of a prior swing's duration.
- Pairs with Fibonacci price levels (Ch5) for price×time confluence.

### Session/Bar Counting Logic
- Patterns that require a time condition — count-based detection (N bars up/down, N-day highs/lows, etc.).

## Key Concepts
- **Exhaustion point**: where the current directional move is likely to stall/reverse.
- **Setup count**: sequential close count (TD 9-style).
- **Time projection**: ratio-scaled durations between swings.

## Code Example
```python
def td_setup_count(df, lookback=4, target=9):
    # count consecutive closes > close[lookback] bars ago
    up = (df['close'] > df['close'].shift(lookback))
    count = 0; counts = []
    for u in up:
        count = count + 1 if u else 0
        counts.append(count)
    df['TD_count'] = counts
    return df[df['TD_count'] >= target]  # setup complete → exhaustion watch
```
- **What it demonstrates**: converting a time condition into a countable, rules-based signal.

## Worked Example
In a ranging market, price prints 9 consecutive higher closes (TD setup complete) at the top of the range → exhaustion watch; the reversal signal is the setup completion plus a bearish confirmation (e.g., close below the setup's last low).

## Key Takeaways
1. Timing patterns are the "when" layer — pair them with price levels.
2. TD setup is regime-sensitive: trust it in ranges, distrust it in trends.
3. Time ratios (Fibonacci timing) + price ratios = strong confluence.
4. Code counts explicitly; never hand-count bars in analysis.

## Connects To
- **Ch 5**: Fibonacci timing pairs with price retracements.
- **Ch 1**: regime weighting decides how much to trust timing signals.
- **Ch 10**: price patterns give the confirmation structure.
