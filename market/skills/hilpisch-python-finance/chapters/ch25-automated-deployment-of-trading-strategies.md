# Chapter 25: Automated Deployment of Trading Strategies

## Core Idea
Deploy a strategy by turning the event-based backtest into a **self-contained, deployable script**: time-frame alignment (decisions on resampled bars, not raw ticks), config + logging + deployment state, a deployable strategy class, replay through the engine, then simulated live streaming — with operational safeguards and monitoring.

## Frameworks Introduced
- **Time-frame alignment**: deployment uses **resampled bars** (e.g. 1-minute or hourly), not raw ticks — decisions happen on aligned decision intervals, matching backtest semantics.
- **Self-contained deployment script**: one script that rebuilds the baseline ML logic (walk-forward model), loads config, sets up logging and deployment state, and runs the strategy loop — deployable without notebooks.
- **Deployable strategy class**: encapsulates state (model, position, last bar), `on_bar`/`on_event` methods, logging of decisions and fills.
- **Historical replay → simulated live streaming**: first replay through engine for validation, then stream bars as they'd arrive live; resample ticks → decision interval.
- **Operational safeguards**: config-driven limits (max position, max drawdown), heartbeat/health checks, logging and monitoring, clear boundaries between strategy and infrastructure.

## Key Concepts
- **Config**: parameters (symbol, window, costs, limits) external to code — reproducible runs.
- **Deployment state**: persisted state (position, cash, last decision) so restarts are safe.
- **Monitoring**: log decisions, fills, equity; alert on anomalies/safeguard triggers.

## Mental Models
- Use X when Y: *resampled bars when* making decisions; *raw ticks only when* execution detail requires it.
- Think of deployment as *the backtest with a heartbeat*: same logic, plus state, logging, and guardrails.

## Anti-patterns
- **Tick-level decision logic** — inconsistent with backtested bar semantics.
- **Hardcoded parameters** — config-driven or untestable.
- **No state persistence** — restart loses position tracking.
- **No safeguards/limits** — deployment without kill-switches.

## Code Examples
```python
# (structure per chapter)
class DeployableStrategy:
    def __init__(self, config):
        self.model = build_walk_forward_model(config)   # ML logic rebuilt
        self.position = 0.0
        self.logger = logging.getLogger("strategy")
    def on_bar(self, bar):
        features = make_features(bar)
        direction = self.model.predict([features])[0]
        self.logger.info("decision", direction=direction, price=bar.close)
        return Order.market(symbol=bar.symbol, qty=direction * self.size)

config = load_config("deploy.yaml")        # symbol, windows, limits, costs
engine = Engine(Feed.live_or_replay(config.feed), cash=config.cash)
engine.run_session(DeployableStrategy(config), safeguards=config.limits)
```
- **What it demonstrates**: self-contained strategy class, config, logging, session.

## Worked Example
Deploy the ch23 EURUSD momentum strategy: build self-contained script → config (2y train window, 21-day predict, 0.5‰ costs, max position) → replay through engine on historical feed (must match backtest) → simulate live streaming with resampled decision bars → monitor logs and equity; test stop-loss and max-drawdown safeguard behavior.

## Key Takeaways
1. Deploy on resampled decision bars — aligned with backtest semantics.
2. Self-contained scripts: config + logging + state + strategy class.
3. Replay validates parity with backtest before live simulation.
4. Safeguards (position/drawdown limits) and monitoring are non-negotiable.

## Connects To
- **Ch 23**: backtest logic reused verbatim
- **Ch 24**: engine drives replay and live streaming
- **Ch 26**: real-world operational realities
