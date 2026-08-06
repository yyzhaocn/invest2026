# Chapter 3: Backtesting

## Core Idea
A backtest is only as trustworthy as its data and cost modeling — adjust for corporate actions, remove survivorship bias, charge realistic costs, and beware optimization.

## Frameworks Introduced

### Data Foundations
- **Adjusted prices**: splits and dividends must be adjusted (adjusted close), or returns are wrong.
- **Survivorship-bias-free data**: includes delisted/bankrupt stocks; more expensive but essential for reliable equity-curve analysis.
- Daily vs intraday data: pick granularity matching the strategy's holding period.

### Backtesting Platforms
- Excel / MATLAB / **Python** (pandas) / QuantConnect / Blueshift — Python is the modern default (and this repo's ecosystem).

### The Transaction-Cost Lesson (canonical example)
- ES 5-min Bollinger mean-reversion: **Sharpe ≈ +3 without costs, −3 with 1bp/side**. If gross profit ≈ cost, the strategy is not tradable.

### Metrics & Dangers
- **Sharpe ratio** (annualized) is headline; inspect the full equity curve (drawdowns, regime stretches).
- **Optimization / data-snooping**: every extra parameter or trial raises the chance of a great-looking-but-fake backtest. Prefer robust few-parameter strategies; test on out-of-sample/walk-forward data.
- **Strategy refinement**: diligent variation of a base idea (holding period, entry/exit timing) can turn a mediocre strategy into a profit center.

## Key Concepts
- **Adjusted close**: price series adjusted for splits/dividends.
- **Survivorship bias**: missing dead securities.
- **Sharpe ratio**: (excess return)/σ, annualized.
- **Data snooping**: multiple-testing bias.
- **Transaction costs**: commissions + slippage + market impact.

## Worked Example
Mean-reverting Bollinger on ES every 5 min: enter beyond ±2σ, exit back within 1σ. Backtest shows Sharpe 3 (costs=0) → apply 1bp/side → Sharpe −3. Conclusion: intraday mean-reversion dies on costs unless latency/impact are tiny. This single example should precede any strategy decision.

## Key Takeaways
1. Model costs in every backtest; if profit ≈ cost, drop it.
2. Use adjusted, survivorship-free data — biased data lies.
3. Fewer parameters and walk-forward/out-of-sample validation beat clever overfitting.
4. Report Sharpe AND the equity curve; a great Sharpe with a 90% drawdown is a trade you can't survive.
5. Refine base ideas systematically — variations are a legitimate research channel.

## Connects To
- **Ch 2**: the 6 questions set the backtest agenda.
- **Ch 6**: the backtest's μ/σ feed Kelly sizing.
- **Repo**: backtest skill (rules + costs + walk-forward), performance skill (Sharpe/drawdown).
