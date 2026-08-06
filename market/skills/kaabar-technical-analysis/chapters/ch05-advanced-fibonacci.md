# Chapter 5: Advanced Fibonacci Analysis in Python

## Core Idea
Fibonacci ratios derived from the golden ratio (ϕ ≈ 1.618) generate objective support/resistance levels — retracements for entries, projections for targets, and the author's 23.6% reintegration technique for re-entries.

## Frameworks Introduced

### Fibonacci Ratios (must memorize)
| Ratio | Derivation |
|-------|-----------|
| 23.6% | cube of 61.8% (conjugate) |
| 38.2% | 1 − 61.8% |
| 50% | midpoint (convention) |
| 61.8% | 1 / ϕ (reciprocal of golden ratio) |
| 78.6% | √61.8% |
| 161.8% | ϕ itself (projection ratio) |

### Fibonacci Retracements & Projections
- **Retracement**: from a swing low (A) to swing high (B), draw levels at 23.6/38.2/50/61.8/78.6% — support candidates in uptrends (resistance in downtrends).
- **Projection**: extend from C (after the retrace) applying ratios forward — target/exit zones (e.g., 161.8%).
- Use multiple ratios at once → **confluence zones** where several levels cluster = higher-probability reaction points.

### The 23.6% Reintegration Technique
- After a strong impulse, price often retraces only ~23.6% before resuming — a shallow pullback entry.
- Use when: trend is strong and you missed the initial move; the shallow retracement is the re-entry.
- Keep the stop tight (below the retracement low) because the pullback is shallow by construction.

## Key Concepts
- **Golden ratio ϕ**: ≈1.618; ratio of successive Fibonacci numbers as the sequence grows.
- **Confluence**: multiple Fibonacci levels (and/or other S/R) near the same price.
- **Reintegration**: re-entering after a shallow 23.6% pullback in a strong trend.

## Code Example
```python
def fibonacci_levels(swing_low, swing_high, ratios=[0.236, 0.382, 0.5, 0.618, 0.786]):
    diff = swing_high - swing_low
    return {f"{r*100:.1f}%": swing_high - diff * r for r in ratios}
```
- **What it demonstrates**: converting a swing to objective levels; projection adds `swing_high + diff * ratio` for 161.8% targets.

## Worked Example
Swing A=100 → B=150 in an uptrend. Retracement support levels: 138.2 (23.6%), 130.9 (38.2%), 125 (50%), 119.1 (61.8%). Price pulls to 138 and holds → the 23.6% reintegration entry; stop below 130; target the 161.8% projection at 180.9.

## Key Takeaways
1. Anchor Fibonacci levels to clean swing points (A/B), not arbitrary ranges.
2. Prefer confluence — the 61.8% level alone is weaker than 61.8% + round number + prior support.
3. Use the 23.6% reintegration technique for low-risk re-entries in strong trends.
4. Projections (161.8%) give objective exit/target zones for risk:reward math.
5. Ratios are percentages of the golden ratio — memorize the six, derive the rest.

## Connects To
- **Ch 8**: harmonic patterns are Fibonacci-ratio structures (Gartley/Bat/Crab).
- **Ch 9**: the Fibonacci timing pattern applies ratios to *time*.
- **Ch 1**: levels are support/resistance in the classic sense, now objectively defined.
