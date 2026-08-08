# Chapter 26: Algorithmic Trading in the Real World

## Core Idea
Research edge ≠ economic edge: frictions (transaction costs, slippage, infrastructure/data, model decay, crowding, operational complexity) erode gross alpha — quantify with implementation-shortfall budgets, break-even hit rates, and honest hedge-fund comparisons. Scale and sophistication do not guarantee outperformance.

## Frameworks Introduced
- **Implementation-shortfall budget**: net_alpha = gross_alpha − transaction_costs − slippage − infrastructure; retention ratio = net/gross. Example: 8% gross → 5% net (62.5% retention) — noisy edges may not survive.
- **Break-even hit-rate arithmetic**: effective gain = avg_gain − cost; effective loss = avg_loss + cost; break-even p = eff_loss/(eff_gain + eff_loss). Example: 1.2%/1.0% avg win/loss, 0.1% cost → p = 0.5 just to break even.
- **Benchmark-relative hedge-fund evidence**: compare fund returns vs simple benchmarks (Sharpe, capture ratios, calendar-year perspective) — most funds struggle to beat passive benchmarks net of fees; interpret carefully (survivorship, look-ahead, fees).
- **When algo trading still makes sense**: high-frequency/operational edges, risk control, cost reduction, capacity-efficient strategies — not magic alpha.

## Key Concepts
- **Erosion layers**: transaction costs → spreads/slippage → infrastructure/data → model decay/crowding → capital constraints.
- **EMH relevance**: liquid markets efficient → modest edges → especially vulnerable to shortfall.
- **Capture ratios / benchmark sensitivity**: how much of benchmark move the strategy captures up vs down.

## Mental Models
- Use X when Y: *shortfall budget when* evaluating any strategy's viability; *break-even hit rate when* judging win-rate claims.
- Think of alpha as *gross research edge minus the friction tax* — retention is what matters.

## Anti-patterns
- **Notebook alpha without implementation costs** — the core mistake.
- **Believing sophistication/scale ⇒ outperformance** — evidence says otherwise.
- **Ignoring benchmark** — alpha claims need a benchmark (Lab: "Alpha Is Rare").

## Code Examples
```python
def implementation_shortfall(gross, tx, slip, infra):
    net = gross - tx - slip - infra
    return pd.Series({"gross": gross, "tx": tx, "slip": slip,
                      "infra": infra, "net": net,
                      "retention": net/gross if gross else np.nan})

implementation_shortfall(0.08, 0.015, 0.010, 0.005)  # net 0.05, retention 0.625

def break_even_hit_rate(gain, loss, cost):
    eg, el = gain - cost, loss + cost
    return el / (eg + el)
break_even_hit_rate(0.012, 0.010, 0.001)  # 0.5
```
- **What it demonstrates**: friction budget and break-even arithmetic.

## Worked Example
Hedge-fund comparison: load `data/hf_data.csv` → compute fund vs benchmark Sharpe, capture ratios (up/down), calendar-year returns → test whether the fund's net-of-fee performance beats buy-and-hold SPY; conclusion typically: some years yes, long-run net outperformance rare.

## Key Takeaways
1. Net edge after frictions is the only edge that matters.
2. Break-even hit rates rise quickly with per-trade costs.
3. Scale and sophistication don't guarantee outperformance — check benchmark-relative evidence.
4. Algo trading still wins on operational, risk, and cost dimensions.

## Connects To
- **Ch 22**: EMH baseline — why edges are small to begin with
- **Ch 23-25**: backtest → engine → deployment chain
- **Ch 17-21**: benchmark-relative mandate perspective
