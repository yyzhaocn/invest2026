# Chapter 21: A Small Asset Management Library in Python

## Core Idea
`assetlib` — a compact teaching library that makes Chapters 17-20 concrete: core domain objects (Instruments/Universes/Positions/Portfolios), MarketData, SignalEngine, portfolio construction, backtesting, and reporting — one module per responsibility, small public interfaces, single-line analytics.

## Frameworks Introduced
- **Library layout (single responsibility)**: `assetlib.core` (domain objects), `.data` (MarketData), `.signals` (signal engine + forecast targets), `.portfolio` (weights from risk/return inputs), `.backtest` (rebalancing, trades, value history), `.reporting` (performance/risk/exposure reports). Internal helpers prefixed `_`.
- **Domain objects**: `Instrument` (symbol, asset_class, sector, region, currency), `Universe`, `Position` (qty × price → market_value), `Portfolio` (cross-sectional snapshot; weights sum to 1; `sector_weights()`, `top_concentrations(n)`).
- **MarketData centralization**: load eod_data.csv once, cache; `.select(symbols+benchmark)`, `.returns(freq)`, `.window(n_days)`, wide↔long conversion — components assume clean aligned data.
- **End-to-end toy mandate**: instruments → universe → signals → weights → backtest → report in one workflow.

## Key Concepts
- **Portfolio.from_holdings_dataframe**: holdings table (symbol, quantity, price, metadata) → Portfolio with derived market_value/weight columns.
- **Single-line analytics**: `portfolio.sector_weights()` — aggregation by sector; concentration via top holdings.
- **Wide vs long**: wide (Date index, symbols columns) for analytics; long (Date, symbol MultiIndex) for groupby-style ops.

## Mental Models
- Use X when Y: *MarketData when* you need consistent prices across components; *Portfolio when* you need weights/exposures/concentration; *SignalEngine when* features/targets repeat.
- Think of the library as *the mandate in code*: each module implements one piece of the workflow.

## Anti-patterns
- **Each script loading/re-cleaning data** — centralize in MarketData.
- **Fat modules with multiple responsibilities** — keep single-purpose modules.
- **Exposing internal helpers** — underscore prefix signals private API.

## Code Examples
```python
from assetlib.core import Instrument, Universe, Position, Portfolio
from assetlib.data import MarketData

instruments = [Instrument(symbol="AAPL", sector="Technology", region="US"),
               Instrument(symbol="SPY", asset_class="Equity Index", region="Global")]
universe = Universe(instruments)
pos = Position(symbol="AAPL", quantity=120, price=180.25)
pos.market_value                       # 21630.0

portfolio = Portfolio.from_holdings_dataframe(holdings_df)
portfolio.sector_weights()              # aggregate weights by sector
portfolio.top_concentrations(n=3)       # largest holdings

md = MarketData.load()
prices = md.select(universe.symbols + ["SPY"])
rets = md.returns(["AAPL", "JPM", "TLT"])
recent = md.window(2 * 252)
prices_long = recent.to_long(symbols=universe.symbols)
```
- **What it demonstrates**: domain objects, portfolio analytics, MarketData workflow.

## Worked Example
Toy mandate end-to-end: build universe (AAPL, NVDA, JPM + SPY benchmark) → MarketData returns → SignalEngine momentum scores → portfolio construction (rank→weights under caps) → backtest monthly rebalancing with costs → reporting module produces performance + risk + exposure tables → present as stakeholder report. Lab: "Hidden Costs of Portfolio Constraints" — measure how caps/turnover drag performance.

## Key Takeaways
1. One module per responsibility + small public API = readable, extendable AM code.
2. Portfolio objects make analytics (sector weights, concentration) one-liners.
3. Centralized MarketData keeps all components on clean aligned data.
4. End-to-end workflow proves the Chapter 17-20 concepts in code.

## Connects To
- **Ch 7**: OOP patterns underpin the library
- **Ch 17-20**: mandate → portfolio → system → reporting implemented
- **Ch 23**: backtesting machinery generalizes assetlib.backtest
