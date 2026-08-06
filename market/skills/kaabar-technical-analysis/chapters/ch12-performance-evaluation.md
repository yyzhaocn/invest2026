# Chapter 12: Performance Evaluation in Python

## Core Idea
Performance evaluation is the discipline that separates good strategies from lucky ones: normalize returns, measure risk-adjusted performance, and backtest with realistic costs and walk-forward validation.

## Frameworks Introduced

### Core Metrics
- **Net Return**: `(end/start − 1) × 100` — the normalizer that makes portfolios of different sizes comparable (portfolio A +$100k and portfolio B +$3k may both be +10%).
- **Hit Ratio (win rate)**: % of profitable trades. >50% suggests good accuracy; <40% weak — BUT a low hit ratio is fine when winners outweigh losers.
- **Risk-Reward Ratio**: average gain per winning trade / average loss per losing trade. Low hit ratio + high R:R = profitable (Trader B: 40% × $300 vs Trader A: 80% × $100).
- **Profit Factor**: gross profits / gross losses (>1 profitable; >1.5 strong).
- **Sharpe Ratio**: excess return per unit of total risk (σ). >1 good, >2 very good.
- **Sortino Ratio**: Sharpe variant using only **downside** deviation — ignores positive volatility; better for strategies targeting loss reduction.
- **Max Drawdown**: peak-to-trough decline; the "sleep at night" metric.
- **CAGR / annualized return**: per-year growth for comparability across periods.

### Backtesting Discipline
- Include **costs**: spreads + commissions in every fill — a strategy profitable gross can be dead net.
- **Walk-forward testing**: re-optimize and validate on successive out-of-sample windows; the best you can hope from a backtest is that future results resemble it.
- Expectation management: backtests are a hope, not a guarantee.

## Key Concepts
- **Normalization**: net return/% metrics so capital size doesn't distort comparisons.
- **Downside deviation**: volatility of negative returns only (Sortino's input).
- **Walk-forward**: rolling in-sample fit → out-of-sample test.

## Code Example
```python
def performance_summary(trades, equity):
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    hit_ratio = len(wins) / len(trades) * 100
    avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
    rr = abs(avg_win / avg_loss) if avg_loss else float('inf')
    return {'hit_ratio': hit_ratio, 'risk_reward': rr,
            'profit_factor': sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)) if losses else float('inf')}
```
- **What it demonstrates**: hit ratio and risk-reward must be read together — the chapter's central lesson.

## Worked Example
Backtest a simple MA-cross strategy on 3 years of data with 0.05% per-side costs: 60 trades, hit ratio 41%, avg win $320, avg loss $180 → R:R = 1.78, profit factor = 0.41×320/(0.59×180) ≈ 1.24 — profitable net of costs, then confirmed by a 12-month walk-forward window.

## Key Takeaways
1. Judge strategies by risk-adjusted metrics (Sharpe/Sortino), not gross P&L.
2. Read hit ratio and risk-reward as a pair — one without the other misleads.
3. Always model spreads + commissions; gross-profit backtests lie.
4. Walk-forward test before trusting any backtest.
5. Max drawdown sets your capital requirement — size positions so the worst drawdown is survivable.

## Connects To
- **Ch 1**: rules-based signals are what make backtesting meaningful.
- **Ch 6**: volatility feeds risk-adjusted metrics and stop sizing.
- **Repo skills**: `backtest` and `trade-journal` implement these exact metrics.
