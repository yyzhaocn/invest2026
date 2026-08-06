# Chapter 6: Money and Risk Management

## Core Idea
Maximize long-term compounded growth — the math is capital allocation across strategies plus leverage, and the Kelly framework (after Thorp) is the optimal answer, tempered by fractional Kelly and model risk.

## Frameworks Introduced

### Kelly Formula (continuous finance)
- For a strategy with expected return μ and variance σ², optimal leverage **F* = μ / σ²**.
- Maximizes long-run compounded growth rate g.
- Discrete-outcome version: F* = W − (1−W)/R (win prob, payoff ratio).

### Fractional Kelly
- Use a fraction (e.g., half) of full Kelly — because μ and σ² are *estimated*, full Kelly over-leverages on bad estimates and can gut the account.
- Conservative sizing trades growth for survival.

### Allocation Across Strategies (Thorp-style)
- With multiple strategies (μ_i, σ_i, correlation matrix): the optimal allocation + overall leverage is ONE optimization maximizing portfolio growth — don't size strategies in isolation.
- Leverage = portfolio size / equity; Kelly gives the cap.

### Model Risk
- The strategy's *parameters* may be wrong even if the concept is right — this is why fractional Kelly and robustness (walk-forward) matter; a correct strategy with wrong sizing is still ruinous.

## Key Concepts
- **Compound growth rate g**: the objective.
- **Optimal leverage F***: Kelly's answer.
- **Fractional Kelly**: survival-first sizing.
- **Model risk**: parameter/estimate uncertainty.

## Worked Example
Strategy: μ = 10%/yr, σ = 20%/yr → full Kelly F* = 0.10/0.04 = 2.5× leverage. Half-Kelly = 1.25×. If estimates are off (true σ 25%), full Kelly still over-risks; fractional Kelly stays survivable. (This maps directly to the repo's position-size risk-budget method.)

## Key Takeaways
1. Kelly F* = μ/σ² is the theoretical optimum — then go fractional.
2. Size strategies jointly (correlations matter), not one at a time.
3. Model risk is managed by conservatism (fractional Kelly, walk-forward), not by smarter prediction.
4. Maximize growth, but only on the side of survival.

## Connects To
- **Ch 3**: backtest μ/σ are Kelly's inputs.
- **Repo**: position-size (risk-budget/Kelly methods), performance (drawdown/Sharpe).
