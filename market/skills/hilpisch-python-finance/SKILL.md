---
name: hilpisch-python-finance
description: "Knowledge base from \"Python for Finance: Python Fluency in the Era of GenAI (3rd ed)\" by Yves Hilpisch. Use when applying Hilpisch's frameworks for Python fluency/GenAI collaboration, numerical computing (NumPy/pandas), financial time series, asset management (portfolio construction, signals, mandates), algorithmic trading (backtesting, market/broker engines, deployment), or derivatives valuation (Monte Carlo, LSM, calibration)."
---

<!-- argument-hint: [topic, framework name, or chapter number] -->

# Python for Finance (3rd Edition)
**Author**: Yves Hilpisch | **Chapters**: 31 + 3 appendices | **Generated**: 2026-08-07

## How to Use This Skill

- **Without arguments** — load core frameworks for reference
- **With a topic** — ask about `portfolio construction`, `backtesting`, `LSM`, `implied volatility`, or another indexed topic; I find and read the relevant chapter
- **With chapter** — ask for `ch18`; I load that specific chapter
- **Browse** — ask "what chapters do you have?" to see the full index

When you ask about a topic not covered in Core Frameworks below, I will read the relevant chapter file before answering.

---

## Core Frameworks & Mental Models

### The Grand Architecture: Valuation as Contracts (Part VI)
Risk-neutral valuation V₀ = E^ℚ(DF·payoff) is an **architecture statement**: four orthogonal, swappable blocks — time grids (ACT/365.25 year fractions), discounting (curve objects, deterministic by default), simulation (PathSimulator protocol), payoff evaluation. Use MarketEnvironment for dependency injection; bump-and-revalue for model-agnostic portfolio Greeks; horizon-split calibration (JD short / Heston long) to respect the smile surface.

### The Discipline Ladder for Strategies (Parts IV–V)
1. **EMH as null** — simple public rules shouldn't beat costs persistently; test predictability statistically (effect size, power, multiple testing, walk-forward). (ch22)
2. **Walk-forward evaluation** — refit on rolling 2y window, predict 1m block; never in-sample. (ch22-23)
3. **Backtest parity** — vectorized and event-based implementations of the same rule must agree; event-based rehearses execution (orders/fills/account). (ch23-24)
4. **Friction budget** — net alpha = gross − tx − slippage − infra; break-even hit rate = eff_loss/(eff_gain+eff_loss). Alpha claims need a benchmark. (ch26)

### Asset Management as Mandate-Driven Workflow (Part IV)
Mandate (written contract) → portfolio → processes → reports. Separate **research (signals/forecasts) / portfolio (weights/trades) / execution (orders)** layers. Signals = aligned, leakage-free time series used for selection, sizing, timing; map score → rank → weight under constraints. Regularize portfolio inputs (shrink μ toward benchmark, Σ toward diagonal) before optimizing.

### Python Fluency × GenAI (Part I)
LLMs raise, not lower, the fluency bar: 4-pass draft review of generated code (structure → assumptions → numerics → error handling), precise prompting (context + constraints + typed interfaces), validation triangle (toy data → invariants as tests → baseline comparison).

### Numerical Foundations (Part II)
Vectorize with NumPy first (biggest win), `@nb.njit` for loops, multiprocessing last. pandas: DatetimeIndex early, `.loc` labels / `.iloc` positions, groupby-agg, missing-data matrix (dropna/ffill/interpolate). Money → Decimal; copies: slices are views.

### Market Realities (Part V)
Implementation frictions, model decay, and crowding erode most apparent edges; scale/sophistication ≠ outperformance — verify against simple benchmarks with capture ratios and calendar-year returns.

---

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-why-python-for-finance.md) | Why Python for Finance? | Code-first workflows, AI-first finance |
| [ch02](chapters/ch02-python-fluency-and-genai.md) | Python Fluency and GenAI | Draft review, precise prompting, validation triangle |
| [ch03](chapters/ch03-python-infrastructure.md) | Python Infrastructure | venv, env-outside-project, python -m pip |
| [ch04](chapters/ch04-data-types-and-structures.md) | Data Types and Structures | Container choice, Decimal, copy discipline |
| [ch05](chapters/ch05-numerical-computing-with-numpy.md) | Numerical Computing with NumPy | Vectorization, broadcasting, masks, Generator |
| [ch06](chapters/ch06-data-analysis-with-pandas.md) | Data Analysis with pandas | .loc/.iloc, DatetimeIndex, groupby-agg |
| [ch07](chapters/ch07-object-oriented-programming.md) | Object-Oriented Programming | Composition-first, dataclasses, ABC interfaces |
| [ch08](chapters/ch08-data-visualization.md) | Data Visualization | fig/axes grammar, subplots, distribution reading |
| [ch09](chapters/ch09-financial-time-series.md) | Financial Time Series | EOD loading, missing strategies, returns, resample |
| [ch10](chapters/ch10-input-output-operations.md) | Input/Output Operations | CSV/npz/SQLite/HDF5 matrix, round-trip tests |
| [ch11](chapters/ch11-performance-python.md) | Performance Python | Vectorize→JIT→Parallel ladder, lru_cache |
| [ch12](chapters/ch12-mathematical-tools.md) | Mathematical Tools | Basis-function regression, splines, root finding |
| [ch13](chapters/ch13-stochastics.md) | Stochastics | GBM/CIR simulation, MC valuation, VaR/ES |
| [ch14](chapters/ch14-statistics.md) | Statistics | Normality diagnostics, efficient frontier, Bayes |
| [ch15](chapters/ch15-machine-and-deep-learning.md) | Machine and Deep Learning | Baseline-first ML, LSTM with predictability caution |
| [ch16](chapters/ch16-nlp-and-llm-foundations.md) | NLP and LLM Foundations | Tokenization ladder, TF-IDF, embeddings, RAG |
| [ch17](chapters/ch17-asset-management-foundations.md) | Asset Management Foundations | Mandates, absolute vs benchmark-relative |
| [ch18](chapters/ch18-portfolio-construction-and-risk.md) | Portfolio Construction and Risk | Shrinkage, GMV, constraints, risk decomposition |
| [ch19](chapters/ch19-signals-forecasts-and-portfolio-implementation.md) | Signals, Forecasts, Portfolio Implementation | 3-layer separation, score→rank→weight |
| [ch20](chapters/ch20-asset-management-systems-and-reporting.md) | AM Systems and Reporting | Report suite, pipelines, attribution, governance |
| [ch21](chapters/ch21-a-small-asset-management-library-in-python.md) | A Small AM Library in Python | assetlib layout, MarketData, toy mandate |
| [ch22](chapters/ch22-efficient-markets-and-hypothesis-testing.md) | Efficient Markets and Hypothesis Testing | EMH null, statistical rigor, walk-forward |
| [ch23](chapters/ch23-vectorized-and-event-based-backtesting.md) | Vectorized and Event-Based Backtesting | Walk-forward backtest, costs, parity |
| [ch24](chapters/ch24-building-a-market-and-broker-for-trading.md) | Building a Market and Broker | Engine layer, feeds, orders, session callbacks |
| [ch25](chapters/ch25-automated-deployment-of-trading-strategies.md) | Automated Deployment | Resampled bars, config/state/logging, safeguards |
| [ch26](chapters/ch26-algorithmic-trading-in-the-real-world.md) | Algorithmic Trading in the Real World | Shortfall budget, break-even hit rates |
| [ch27](chapters/ch27-valuation-framework.md) | Valuation Framework | dxlib architecture, curves, MarketEnvironment |
| [ch28](chapters/ch28-simulation-of-financial-models.md) | Simulation of Financial Models | PathSimulator, variance reduction, GBM/Merton/Heston |
| [ch29](chapters/ch29-derivatives-valuation.md) | Derivatives Valuation | EuropeanMCPricer, LSM American puts |
| [ch30](chapters/ch30-portfolio-valuation.md) | Portfolio Valuation | Pricing contract, aggregation, bump-and-revalue |
| [ch31](chapters/ch31-market-based-valuation.md) | Market-Based Valuation | Put-call parity, implied vol, horizon-split calibration |

## Topic Index

- **American options** → ch29
- **Asset management mandates** → ch17
- **Backtesting (vectorized/event-based)** → ch23
- **Bayesian updating** → ch14
- **Break-even hit rate** → ch26
- **Bump-and-revalue delta** → ch30
- **Calibration (JD/Heston)** → ch31
- **Code-first workflows** → ch1
- **Covariance shrinkage** → ch18
- **Dataclasses / OOP** → ch7
- **Deployment** → ch25
- **Efficient frontier** → ch14
- **Efficient Market Hypothesis** → ch22
- **GenAI collaboration** → ch2
- **Geometric Brownian Motion** → ch13, ch28
- **Implied volatility** → ch31
- **Input/Output (CSV/SQLite/HDF5)** → ch10
- **Least-Squares Monte Carlo (LSM)** → ch29
- **Market/broker engine** → ch24
- **Missing data** → ch6, ch9
- **Monte Carlo valuation** → ch13, ch29
- **Multiprocessing / Numba / Cython** → ch11
- **NLP / LLMs / RAG** → ch16
- **Normality diagnostics** → ch14
- **NumPy vectorization** → ch5
- **pandas (Series/DataFrame)** → ch6
- **Performance** → ch11
- **Portfolio construction** → ch18
- **Portfolio valuation** → ch30
- **Put-call parity / forwards** → ch31
- **Resampling** → ch6, ch9
- **Risk measures (VaR/ES)** → ch13
- **Signals → ranks → weights** → ch19
- **Simulation contract** → ch28
- **Stochastics / random processes** → ch13
- **Time series** → ch9
- **Valuation framework (dxlib)** → ch27
- **Visualization** → ch8
- **Walk-forward evaluation** → ch22, ch23

## Supporting Files

- [glossary.md](glossary.md) — all key terms with definitions
- [patterns.md](patterns.md) — all techniques and design patterns
- [cheatsheet.md](cheatsheet.md) — quick reference tables and decision guides

---

## Scope & Limits

This skill covers the book content only (Python for Finance 3rd edition, O'Reilly 2027, early-release 2026-07-09). For hands-on implementation in your codebase (e.g. the invest2026 market data/backtesting stack), combine with project-specific tools and skills (stock-trend, backtest, portfolio, etc.). For topics beyond this book, check related skills or ask the agent directly.
