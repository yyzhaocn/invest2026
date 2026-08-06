---
name: grimes-technical-analysis
description: "Knowledge base from \"The Art and Science of Technical Analysis\" by Adam Grimes (2012). Use when applying Grimes' frameworks for the execution layer: market structure (trend/range/transitions), the four trades, trade management (initial stop, volatility-based targets, active management), risk & position sizing (fixed fractional), expectancy & the vig, trading psychology and decision biases."
---

# The Art and Science of Technical Analysis
**Author**: Adam Grimes | **Pages**: ~234 | **Chapters**: 12 | **Generated**: 2026-08-06

## How to Use This Skill

- **Without arguments** — load core frameworks
- **With a topic** — ask about `fixed fractional`, `four trades`, `initial stop`, `expectancy`, `active management`, `market cycle`
- **With chapter** — ask for `ch08` (trade management) or `ch09` (risk)
- **Browse** — ask "what chapters do you have?"

---

## Core Frameworks & Mental Models

### The Trader's Edge (Ch1)
- **Edge = positive expectancy**, but you still pay "the vig" (costs) on every trade — a positive-expectancy system can still lose money to the vig. Edge must exceed costs.
- Edge comes from **market structure understanding + price action + disciplined execution**, not prediction.
- Being wrong is normal (most trades lose); the edge is in the asymmetry (winners >> losers).

### Market Cycle & The Four Trades (Ch2)
- Markets alternate: **trend → range → trend**, with **transitions** (the riskiest zone).
- The four trades (what you can actually trade):
  1. **Trend continuation** (buy pullbacks in uptrends)
  2. **Trend termination** (sell exhaustion at climaxes)
  3. **Range trading** (fade range extremes)
  4. **Range breakout** (trade the transition into a new trend)
- Know which trade you're in; each has different edge, stop, and failure mode.

### Trends vs Ranges (Ch3-5)
- **Trends**: persistence, pullbacks = entry; use volatility-based stops.
- **Ranges**: mean reversion, fade extremes; range structure is measurable (width, time).
- **Interfaces/transitions** are where most money is lost and made — respect them, trade them deliberately.

### Practical Trading Templates (Ch6)
- Template per trade type: entry trigger, initial stop placement, target, management rules — written BEFORE the trade.
- **Initial stop**: place based on market structure (below swing low / above swing high), not arbitrary %.
- **Price target**: volatility-based — "swing out of consolidation ≈ past volatility projected forward".

### Confirmation (Ch7)
- Multiple timeframe + price-action confirmation; avoid **confirmation bias** (seeking evidence for your position) — structure the trade so you act on rules, not on what you want to see.

### Trade Management (Ch8)
- **Placing the initial stop**: structural (under swing), sized to volatility.
- **Price targets**: measured moves / volatility projection.
- **Active management**: scale out, trail stops, let winners run — pre-planned, not emotional.
- **Portfolio considerations**: don't overload correlated trades.

### Risk & Position Sizing (Ch9)
- **Fixed fractional**: risk a consistent fraction of equity per trade (the standard) — position size = risk $ / stop distance.
- Theoretical risk vs **misunderstood risk** (leverage, correlated bets, tail events).
- Practical risks: slippage, gap risk, liquidity — size so a worst-case loss is survivable.

### The Trader's Mind (Ch11)
- **Emotions unbalance the brain chemically** — stress overweights recent losses, fear/euphoria drive overtrading.
- **Cognitive biases**: confirmation bias, hindsight, loss aversion, recency — recognize them in your journal.
- The counter: pre-committed rules + trade journaling + process over outcome.

### Becoming a Trader (Ch12)
- Development path: screen time, small size, journal every trade, iterate on process not results.
- Mastery = thousands of reps of disciplined execution; the process is the edge.

---

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-traders-edge.md) | The Trader's Edge | expectancy, vig, edge sources |
| [ch02](chapters/ch02-market-cycle-four-trades.md) | Market Cycle & Four Trades | cycle, 4 trade types |
| [ch03](chapters/ch03-on-trends.md) | On Trends | trend structure, pullbacks |
| [ch04](chapters/ch04-on-ranges.md) | On Trading Ranges | range dynamics, fading |
| [ch05](chapters/ch05-trend-range-interfaces.md) | Interfaces | transitions, breakout risk |
| [ch06](chapters/ch06-practical-templates.md) | Practical Templates | per-trade playbooks |
| [ch07](chapters/ch07-confirmation.md) | Confirmation | multi-TF, bias |
| [ch08](chapters/ch08-trade-management.md) | Trade Management | initial stop, targets, active mgmt |
| [ch09](chapters/ch09-risk-management.md) | Risk & Position Sizing | fixed fractional, misunderstood risk |
| [ch10](chapters/ch10-trade-examples.md) | Trade Examples | worked cases |
| [ch11](chapters/ch11-traders-mind.md) | The Trader's Mind | emotions, biases |
| [ch12](chapters/ch12-becoming-a-trader.md) | Becoming a Trader | development path |

## Topic Index

- **Active management** → ch08
- **Confirmation bias** → ch07, ch11
- **Expectancy / the vig** → ch01
- **Fixed fractional sizing** → ch09
- **Four trades** → ch02
- **Initial stop** → ch08
- **Loss aversion / biases** → ch11
- **Market cycle** → ch02
- **Portfolio considerations** → ch08
- **Price targets (volatility-based)** → ch06, ch08
- **Pullback entry** → ch03
- **Range breakout / transition** → ch05
- **Range fading** → ch04
- **Trend continuation / termination** → ch02, ch03

## Supporting Files

- [glossary.md](glossary.md) — terms
- [patterns.md](patterns.md) — templates/techniques
- [cheatsheet.md](cheatsheet.md) — trade plan template, sizing, bias checklist

---

## Scope & Limits

Execution-layer complement to kaabar (indicators) and Chan (strategy/backtest). For hands-on use, the repo's portfolio (trade plan), position-size (fixed fractional/Kelly), trade-journal (bias checklist), performance (expectancy/Sharpe) skills operationalize this book.
