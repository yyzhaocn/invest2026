---
name: chan-quantitative-trading
description: "Knowledge base from \"Quantitative Trading: How to Build Your Own Algorithmic Trading Business\" by Ernest P. Chan (2nd ed, 2021). Use when applying Chan's frameworks for strategy idea screening (6 questions), backtesting rigor (survivorship bias, transaction costs, Sharpe), Kelly capital allocation, mean-reversion/momentum & cointegration strategies, execution systems, or money & risk management."
---

# Quantitative Trading
**Author**: Ernest P. Chan | **Pages**: ~256 | **Chapters**: 8 | **Generated**: 2026-08-06

## How to Use This Skill

- **Without arguments** — load core frameworks for reference
- **With a topic** — ask about `kelly`, `cointegration`, `survivorship bias`, `backtesting`, `mean reversion`; I read the relevant chapter
- **With chapter** — ask for `ch03` (backtesting) etc.
- **Browse** — ask "what chapters do you have?"

---

## Core Frameworks & Mental Models

### The 6 Questions Before You Trade Any Strategy (Ch2)
Before committing capital, answer all six:
1. **Benchmark & consistency** — does it beat a benchmark (e.g., SPY) and is the edge consistent over time?
2. **Drawdown depth & length** — how deep and how long? Can you survive it psychologically and financially?
3. **Transaction costs** — what does the strategy earn *after* realistic costs? (See ES example below — costs can flip Sharpe from +3 to −3.)
4. **Survivorship bias** — is your data full of "survivors" (no delisted/bankrupt stocks)? Biased data inflates backtests.
5. **Performance over the years** — does the edge hold across different market regimes, not just one golden period?
6. **Data-snooping bias** — did you try many variations and report only the best? Then live Sharpe will be lower.
Plus: **"fly under the radar"** — can retail capital still exploit it, or is it crowded by institutions?

### The Transaction-Cost Lesson (Ch3, canonical example)
A 5-minute Bollinger strategy on ES: **Sharpe ≈ +3 without costs → −3 with 1 basis point per side**. Intraday/high-frequency edges die on costs. Always model costs in the backtest; if gross profit ≈ cost, the strategy is dead.

### Backtesting Rigor (Ch3)
- **Adjust data for splits & dividends** (adjusted close, not raw).
- **Survivorship-bias-free data is expensive but essential**; same for news coverage.
- **Sharpe ratio** is the headline metric, but look at the whole equity curve (drawdowns, regime sensitivity).
- **Optimization danger**: more parameters + more trials = data-snooping. Prefer robust, few-parameter strategies.
- **Strategy refinement**: diligent variation (holding period, entry/exit timing) can turn a mediocre published idea into a profit center — iterate, don't abandon.

### Kelly & Capital Allocation (Ch6, following Thorp)
- **Kelly formula** (continuous finance): optimal leverage `F* = μ / σ²` (expected return / variance) — maximizes long-term compounded growth.
- **Fractional Kelly**: use a fraction of full Kelly (conservative), because model estimates of μ/σ are themselves uncertain.
- **Allocation across strategies**: with several strategies (each with μ, σ, and correlations), maximize portfolio compounded growth — allocation & leverage are one optimization, not separate.
- **Model risk**: the strategy may be right but the *parameters* wrong — this is why fractional Kelly and robustness testing matter.

### Mean Reversion vs Momentum (Ch7)
- **Mean reversion**: prices revert to a mean — profit from overreaction; works on **stationary** series.
- **Momentum**: trends persist — profit from underreaction; works on non-stationary series.
- **Stationarity & cointegration**: a linear combination of non-stationary series (e.g., GLD/GDX) can be stationary — the **spread** is mean-reverting. Use ADF test + half-life of mean reversion to size the lookback.
- **Optimization**: conditional (regime-dependent) vs unconditional parameter selection.

### Execution & Business (Ch4-5, Ch8)
- Semi-automated (manual orders + automated signals) → fully automated (data feed → engine → broker API).
- Minimize transaction costs (slippage, commissions, market impact); paper-trade first.
- **Live ≠ backtest**: divergence comes from costs, latency, fills, model drift — expect it and plan for it.
- Capital, working hours, programming skills, and goal determine which strategy suits you (Ch2 "identify a strategy that suits you").

---

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-whats-whos-whys.md) | The Whats, Whos, Whys | business case, scalability, who can trade |
| [ch02](chapters/ch02-fishing-for-ideas.md) | Fishing for Ideas | 6 questions, strategy fit, pitfalls |
| [ch03](chapters/ch03-backtesting.md) | Backtesting | data adjustment, survivorship, Sharpe, costs |
| [ch04](chapters/ch04-setting-up-business.md) | Setting Up Your Business | brokerage, infrastructure, investor protection |
| [ch05](chapters/ch05-execution-systems.md) | Execution Systems | semi/full automation, paper trading, divergence |
| [ch06](chapters/ch06-money-risk-management.md) | Money & Risk Management | Kelly, capital allocation, model risk |
| [ch07](chapters/ch07-special-topics.md) | Special Topics | mean reversion vs momentum, cointegration |
| [ch08](chapters/ch08-conclusion.md) | Conclusion | next steps, live trading |

## Topic Index

- **ADF test / half-life** → ch07
- **Backtesting platforms** → ch03
- **Capital allocation across strategies** → ch06
- **Cointegration / spread** → ch07
- **Data-snooping bias** → ch02, ch03
- **Drawdown** → ch02, ch06
- **Execution systems** → ch05
- **Fractional Kelly** → ch06
- **Kelly formula / optimal leverage** → ch06
- **Mean reversion vs momentum** → ch07
- **Model risk** → ch06
- **Optimization** → ch03, ch07
- **Paper trading** → ch05
- **Sharpe ratio** → ch03
- **Stationarity** → ch07
- **Survivorship bias** → ch02, ch03
- **Transaction costs** → ch02, ch03, ch05

## Supporting Files

- [glossary.md](glossary.md) — key terms
- [patterns.md](patterns.md) — techniques
- [cheatsheet.md](cheatsheet.md) — decision guides (6 questions, backtest checklist, Kelly)

---

## Scope & Limits

Book content only. Complements the kaabar-technical-analysis skill (indicators/patterns) with the **strategy → backtest → risk → execution** layer. For hands-on use, combine with the repo's backtest / position-size / scan / portfolio skills.
