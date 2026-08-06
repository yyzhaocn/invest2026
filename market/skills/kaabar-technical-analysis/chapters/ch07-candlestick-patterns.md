# Chapter 7: Pattern Recognition in Python I — Candlestick Patterns

## Core Idea
Patterns are recurring configurations with empirically expected outcomes; candlestick patterns must be detected with objective rules in code — including modern patterns absent from classic literature (double trouble, extreme euphoria).

## Frameworks Introduced

### Pattern Definition
- A pattern is a **recurring sequence of events** with a specific expected outcome based on empirical observation — not a guarantee.
- Code them as explicit conditions on OHLC, never eyeball them.

### Classic Example: The Doji Pattern
- **Doji**: open ≈ close (tiny body) — indecision between buyers and sellers.
- Context matters:
  - **Bullish Doji** (after decline / composed of a prior bearish candle): hints at a possible recovery — watch for confirmation.
  - In a mature bullish market, a run of Dojis hints at a correction/reversal.
- Detection rule: `abs(close − open) <= tolerance` (e.g., small fraction of the range).

### Modern Candlestick Patterns
- **Double trouble pattern**: not in classic literature — a specific multi-candle configuration with defined detection conditions (see book for exact rules).
- **Extreme euphoria pattern**: overextended bullish configuration signaling exhaustion (pp. 113-114 of the book).
- Principle: modern patterns are less crowded → less eroded by self-fulfilling trading.

## Key Concepts
- **Pattern**: event with empirically expected outcome.
- **Doji**: open≈close indecision candle.
- **Confirmation**: the next candle/bar validating the pattern's implication.
- **Context**: the same candle means different things in a rally vs a decline.

## Code Example
```python
def detect_doji(df, tol=0.05):
    body = (df['close'] - df['open']).abs()
    rng = (df['high'] - df['low']).replace(0, 1e-9)
    return body / rng < tol  # True where a doji forms
```
- **What it demonstrates**: turning a visual pattern into a boolean detection rule — the template for all pattern functions in the book.

## Worked Example
After a 5-day decline, a doji appears at a prior support level. Detection fires (doji ∧ prior downtrend ∧ at support). The rule-based system flags "bullish doji watch" — entry only on next-bar confirmation (e.g., close above doji high).

## Key Takeaways
1. Every pattern = explicit OHLC conditions; no discretion.
2. Context (trend + location) matters as much as the candle itself.
3. Prefer modern, less-crowded patterns — classic ones erode via self-fulfilling prophecy.
4. Always demand confirmation before acting on a pattern.

## Connects To
- **Ch 1**: self-fulfilling prophecy critique → modern patterns.
- **Ch 4**: apply the same detection to Heikin-Ashi candles.
- **Ch 8-10**: harmonic/timing/price patterns extend the same detection philosophy.
