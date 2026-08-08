# Chapter 24: Building a Market and Broker for Trading

## Core Idea
Build a separate **engine layer** (market + broker simulation) instead of connecting directly to a real broker API during development: historical replay or GBM simulation feeds, market orders with return objects, position/account state, stop-loss triggers, and session callbacks — so strategies can be developed, tested, and replayed exactly like production.

## Frameworks Introduced
- **Engine architecture**: models module (instruments, orders, trades, positions), data module (feeds: historical replay from CSV or GBM simulation), engine (market matching + broker accounting).
- **Feed choice**: historical replay (real data) vs GBM simulation (stylized stress) — pick by test purpose.
- **Market orders**: place order → get typed return objects (fill details, slippage, fees) → inspect positions and account state.
- **Stop-loss orders**: register conditional orders; engine triggers on price crosses.
- **Session with strategy callback**: run a trading session where the engine calls your strategy per bar/event — the deployment-style loop.

## Key Concepts
- **Why an engine?**: real broker APIs are for production; an engine lets you iterate, replay, and stress-test without capital/connectivity risk.
- **Design boundaries**: engine is market/broker; strategy is the user's; separation keeps both testable.
- **Return objects**: order outcomes as typed results (filled / rejected / partial) — not raw printouts.

## Mental Models
- Use X when Y: *historical replay when* testing against real market behavior; *GBM feed when* testing robustness under stylized scenarios.
- Think of the engine as *a rehearsal stage*: the same code path later runs against live data.

## Anti-patterns
- **Trading real APIs during development** — use the engine first.
- **Strategy logic mixed into engine internals** — keep layers separate.
- **Ignoring order-state semantics** — fills, rejects, and partials must be first-class.

## Code Examples
```python
# (pseudo-structure per chapter)
from engine import Engine, Feed, Order

feed = Feed.historical("data/eod_data.csv")   # or Feed.gbm(S0, mu, sigma, seed)
engine = Engine(feed, cash=100_000)
order = Order.market(symbol="EURUSD", qty=1_000)
result = engine.place(order)                   # typed return object
engine.positions, engine.account.cash          # state inspection
engine.register_stop_loss(symbol="EURUSD", qty=-1_000, trigger=1.08)

def strategy(ctx):
    # decision per event; ctx provides bar, account, positions
    ...
engine.run_session(strategy)                   # event loop with callback
```
- **What it demonstrates**: feed selection, market order lifecycle, stop-loss, session loop.

## Worked Example
Run a session: GBM feed for EURUSD → strategy places market orders on momentum signal → stop-loss registered at 1% below entry → observe positions/account evolve → replay same strategy on historical feed → compare behavior; verify stop-loss triggered at the correct price level.

## Key Takeaways
1. Engine = market + broker simulation; strategy code stays separate.
2. Historical replay vs GBM feed serve different test purposes.
3. Orders are typed objects with fills/rejects/partials; state is inspectable.
4. Session callbacks rehearse the production event loop.

## Connects To
- **Ch 23**: event-based backtesting groundwork
- **Ch 25**: deployment reuses the engine for live simulation
- **Ch 26**: real-world algorithmic trading details
