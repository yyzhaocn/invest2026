# Chapter 10: Pattern Recognition in Python IV — Price Patterns

## Core Idea
Classic price patterns — double tops/bottoms, head and shoulders — mark potential trend reversals; detect them with code on pivot swings and require confirmation before trading.

## Frameworks Introduced

### Double Top / Double Bottom
- **Double bottom**: bullish reversal — price makes a low (1), rallies, makes a second similar low (2) near the same level, then breaks above the intervening high (neckline).
- **Double top**: mirror image — two similar highs, then a break below the neckline.
- Confirmation = close beyond the neckline; the measured move approximates the height of the pattern.

### Head and Shoulders
- **Head and shoulders** (top): three peaks — lower left shoulder, higher head, lower right shoulder; neckline through the two troughs; breakdown confirms.
- **Inverse head and shoulders**: bullish mirror.
- Width/depth of the pattern gives the measured target.

### Detection Machinery
- Find swings via local extrema (pivot highs/lows), group them into the pattern's shape, validate with tolerance (similarity of the two lows/highs, neckline slope).

## Key Concepts
- **Neckline**: the level whose break confirms the reversal.
- **Measured move**: pattern height projected from the neckline → target.
- **Similarity tolerance**: the two bottoms/tops must be within a tolerance to count as the pattern.

## Code Example
```python
def double_bottom(df, tol=0.03):
    lows = local_minima(df['low'])          # pivot lows
    if len(lows) < 2:
        return False
    l1, l2 = lows[-2], lows[-1]
    if abs(l1.low - l2.low) / l1.low > tol:
        return False                        # bottoms not similar enough
    neckline = max(df['high'].iloc[l1.idx:l2.idx])   # intervening high
    return df['close'].iloc[-1] > neckline           # confirmation
```
- **What it demonstrates**: similarity tolerance + neckline confirmation = the objective pattern test.

## Worked Example
Downtrend makes low 1 at 80, rallies to 86, dips to 79.5 (within 3% of 80 ✓), closes above 86 → confirmed double bottom. Measured target = 86 + (86 − 80) = 92.

## Key Takeaways
1. Patterns only count with similarity tolerance and neckline confirmation.
2. Measured move gives an objective target for risk:reward.
3. Code pivot detection — visual "obvious" patterns are hindsight bias.
4. Reversal patterns work best after established trends (Ch1 context rule).

## Connects To
- **Ch 7**: same detection/confirmation philosophy as candlestick patterns.
- **Ch 8**: shares pivot/swing machinery with harmonics.
- **Ch 12**: measured moves feed the reward side of hit-ratio/risk-reward evaluation.
