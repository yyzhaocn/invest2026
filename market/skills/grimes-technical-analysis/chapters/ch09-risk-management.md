# Chapter 9: Risk Management

## Core Idea
Risk one consistent fraction of equity per trade (fixed fractional) — the foundation of survival; respect the risks everyone misunderstands.

## Frameworks Introduced

### Fixed Fractional Position Sizing
- Always risk a **consistent fraction of equity** per trade.
- Position size = (equity × risk %) / stop distance.
- Survives losing streaks; grows with the account.

### Theoretical vs Misunderstood Risk
- **Misunderstood risks**: leverage, correlated bets, tail/gap events, liquidity — the ones that gut accounts aren't the ones in the model.
- Leverage amplifies the tail; correlations make "diversified" books behave as one bet.

### Practical Risks
- Slippage, gap risk (stop not filled at stop price), liquidity — size so a worst-case (not average-case) loss is survivable.

## Key Concepts
- **Fixed fractional**: constant risk fraction per trade.
- **Misunderstood risk**: leverage/correlation/tail that models miss.
- **Gap risk**: stop becomes market order at open.

## Key Takeaways
1. Fixed fractional is the baseline: risk% × equity ÷ stop distance.
2. Stress-test leverage and correlation, not just σ.
3. Plan for worst-case fills (gaps), not average slippage.

## Connects To
- **Chan ch06**: Kelly is the theoretical cap; fixed fractional the practical rule.
- **Repo**: position-size (risk-budget = fixed fractional) implements this directly.
