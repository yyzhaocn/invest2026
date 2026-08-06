# Chapter 5: Execution Systems

## Core Idea
Move from signals to fills deliberately: semi-automated first, then fully automated; minimize transaction costs; paper-trade before live; expect live performance to diverge from backtest.

## Frameworks Introduced

### Semi-Automated System
- Strategy engine generates signals/orders; a human reviews and sends to broker.
- Pros: human oversight; cons: slower, less scalable.

### Fully Automated System
- Real-time data feed → strategy engine → broker API → fills → position tracking.
- Requires reliability: monitoring, failovers, kill switches.

### Minimizing Transaction Costs
- Commissions, slippage, market impact, financing costs — optimize order type (limit vs market), execution timing.

### Paper Trading Before Live
- Test the full pipeline (data → signal → order) with simulated fills; catch integration bugs without losing money.

### Why Actual Performance Diverges From Backtest
- Costs & slippage (unmodeled), latency, partial fills, model drift, data differences — plan a "reality gap" budget and compare forward vs backtest Sharpe.

## Key Concepts
- **Slippage**: difference between expected and actual fill price.
- **Market impact**: your own order moving the price.
- **Paper trading**: dry-run with simulated execution.
- **Reality gap**: backtest Sharpe → live Sharpe degradation.

## Key Takeaways
1. Automate in stages: signals → semi-auto → full auto, testing each layer.
2. Costs (especially impact/latency) are an execution problem, not just a backtest number.
3. Paper trade the whole pipeline before risking capital.
4. Expect live ≠ backtest; monitor forward Sharpe and investigate divergence.

## Connects To
- **Ch 3**: backtest costs vs execution costs are the same enemy.
- **Repo**: portfolio skill is a manual paper-trading layer; flow-chart/multi-lens give the monitoring loop.
