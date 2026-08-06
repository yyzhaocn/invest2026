# Cheatsheet — Decision Guides

## The 6-Question Gate (Ch2) — run EVERY idea through this
```
[ ] Beats benchmark (SPY/000300) AND consistent (not one lucky year)?
[ ] Worst drawdown known: depth + length survivable?
[ ] Profitable AFTER realistic transaction costs?
[ ] Data survivorship-bias-free?
[ ] Edge holds across regimes (bull/bear/crash)?
[ ] Not data-snooped (few params, walk-forward validated)?
[ ] Bonus: flies under institutional radar?
→ 6×YES = rare, valuable. Any NO = fix or drop.
```

## Cost Reality Check (Ch3) — the ES example
| Cost assumption | Sharpe |
|----------------|--------|
| 0 | +3 |
| 1 bp/side | −3 |
→ If gross profit ≈ cost, strategy is dead. Always model costs.

## Kelly Sizing (Ch6)
```
Full Kelly (continuous):  F* = μ / σ²
Full Kelly (discrete):    F* = W − (1−W)/R
Use: ½–¾ Kelly  (estimates are wrong, survive first)
Leverage cap: F* = portfolio / equity
```

## Mean-Reversion Setup (Ch7)
```
1. Find pair (e.g., GLD/GDX) — economically linked
2. Spread = y − β·x (linear regression)
3. ADF test p < 0.05 → spread stationary?
4. half-life = −ln(2)/ln(β₁)   (β₁ from spread ~ AR(1))
5. Lookback ≈ half-life
6. Entry: z-score(spread) < −2 (buy) / > +2 (short)
7. Exit: z-score ≈ 0; stop: cointegration breaks
```

## Backtest Checklist (Ch3)
- [ ] Adjusted prices (splits/dividends)
- [ ] Survivorship-free universe
- [ ] Costs modeled per side
- [ ] Out-of-sample / walk-forward
- [ ] Report Sharpe + full equity curve (drawdown!)
- [ ] Parameters few & jitter-robust

## Live vs Backtest Reality Gap (Ch5)
| Source of divergence | Budget for |
|---------------------|-----------|
| Transaction costs/slippage | model in backtest |
| Latency/fills | paper trade first |
| Model drift | re-estimate μ/σ quarterly |
| Alpha decay | keep research pipeline running |

## Tells & Smells
- **"Sharpe 3!"** with zero costs → costs will kill it (ES lesson).
- **Great backtest, one golden period** → regime luck; check per-year.
- **Many parameters tuned to data** → data-snooping; walk-forward it.
- **"Full Kelly"** → you're one bad estimate from ruin; go fractional.
- **Spread that used to revert, now trends** → cointegration broke; stop trading it.
