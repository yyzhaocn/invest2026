# Chapter 6: Practical Trading Templates

## Core Idea
Every trade type gets a written playbook — entry trigger, initial stop, target, management — decided BEFORE the trade, then executed mechanically.

## Frameworks Introduced

### The Template Structure
Per trade type:
- **Entry trigger**: precise price-action condition (pullback to level + confirmation candle).
- **Initial stop**: structural (below swing low / above swing high), volatility-scaled.
- **Price target**: measured move / volatility projection (past volatility ≈ future range).
- **Management**: scale-out points, trailing rules.

### Volatility-Based Target
- "Swing out of consolidation ≈ past volatility projected forward": if the market's recent average true range is R, a breakout/continuation leg often runs ~R-2R. Target = entry + k×ATR, not an arbitrary round number.

## Key Concepts
- **Playbook**: pre-written rules per trade type.
- **Measured move**: structure-derived target.

## Key Takeaways
1. Write the template before entry; execution is then mechanical.
2. Targets from volatility/structure beat round numbers.
3. If the setup doesn't match a template, it's not a trade.

## Connects To
- **Ch 8-9**: management and sizing plug into the template.
- **Repo**: position-size computes volatility targets; trade-journal records the plan.
