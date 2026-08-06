# Chapter 8: Pattern Recognition in Python II — Harmonic Patterns

## Core Idea
Harmonic patterns are precise Fibonacci-ratio price structures (XABCD legs) that exploit the fractal, cyclic nature of markets — the same shapes recur across timeframes, so a pattern is tradable wherever it forms.

## Frameworks Introduced

### Harmonic Pattern Basis
- Markets exhibit **fractal behavior**: patterns in small timeframes reappear in larger ones, in more complex form.
- A harmonic pattern = specific price configuration relying on Fibonacci ratios between legs (X→A→B→C→D).
- Detection = objective ratio checks per leg, coded in Python.

### Pattern Family
- **ABCD**: the base 4-point structure; a measured move — C retraces a defined portion of AB, D completes at a defined ratio of BC.
- **Gartley**: bullish/bearish 5-point structure (XABCD) with defined retracements (typically B at 61.8% of XA, D at 78.6% of XA).
- **Bat**: D retraces 88.6% of XA — deeper extreme.
- **Crab**: D extends beyond X (161.8% of XA) — extreme reversal.
- **Butterfly**: D at 127.2% of XA.
- Each has strict ratio definitions → rules-based, backtestable detection.

## Key Concepts
- **XABCD legs**: the five swing points defining harmonic structures.
- **Fractal markets**: self-similarity across timeframes — the theoretical basis.
- **Ratio tolerance**: detection needs a tolerance band around exact ratios (real markets rarely hit perfect ratios).

## Code Example
```python
def abcd_ratio(df):
    # XABD swings from pivots; return ratios between legs
    AB = B - A; BC = C - B; CD = D - C
    return {'BC/AB': BC / AB, 'CD/BC': CD / BC}
# then check: 0.382 <= BC/AB <= 0.886 and 1.272 <= CD/BC <= 1.618, etc.
```
- **What it demonstrates**: ratio-checking is the core of harmonic detection; each pattern is a different ratio table.

## Reference Table
| Pattern | D relative to XA | Typical use |
|---------|-----------------|-------------|
| ABCD | varied | measured move |
| Gartley | 0.786 | reversal in trend |
| Bat | 0.886 | deeper reversal |
| Crab | 1.618 | extreme reversal |
| Butterfly | 1.272 | medium reversal |

## Worked Example
Uptrend: X=100, A=120, B=105 (61.8% retrace of XA ✓), C=115, D=110 (78.6% of XA ✓) → bullish Gartley candidate. Entry at D with stop below D; target = A-level retest or beyond.

## Key Takeaways
1. Harmonic patterns are Fibonacci-ratio structures — always verify ratios with tolerance, in code.
2. Fractal nature means they apply across timeframes and markets.
3. Different patterns = different D-extremes (Gartley shallow → Crab deep); pick by market context.
4. Combine with trend direction for higher-probability setups.

## Connects To
- **Ch 5**: harmonic ratios come straight from the Fibonacci toolkit.
- **Ch 10**: price patterns share the pivot/swing detection machinery.
- **Ch 1**: rules-based detection keeps harmonics backtestable.
