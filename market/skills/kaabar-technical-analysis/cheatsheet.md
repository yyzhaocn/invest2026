# Cheatsheet — Decision Guides

## Adding an Indicator (Ch1)
```
New indicator worth adding?
├─ Uncorrelated with current set?  → NO → skip
├─ Better than random (>50%)?      → NO → skip
└─ YES → add (uncorrelated pair > any two correlated classics)
```

## Signal Weighting by Regime (Ch1)
| Regime | Bullish signals | Bearish signals |
|--------|----------------|-----------------|
| Uptrend | high weight | low weight |
| Downtrend | low weight | high weight |
| Ranging | equal | equal |

## Fibonacci Ratios (Ch5) — memorize
`23.6% | 38.2% | 50% | 61.8% | 78.6% | 161.8%` (ϕ = 1.618; 61.8% = 1/ϕ)

## Bollinger / RSI Technique Choice (Ch3)
| Situation | Technique |
|-----------|-----------|
| Fast entries, more noise OK | aggressive |
| Fewer false signals | conservative (middle-band re-cross) |
| Align with trend | trend-friendly |
| Early reversals from extremes | RSI V technique |
| Maximum conviction | DCC (double confirmation) |

## Harmonic Pattern D-Extremes (Ch8)
| Pattern | D vs XA | Bias |
|---------|---------|------|
| Gartley | 78.6% | reversal in trend |
| Bat | 88.6% | deeper reversal |
| Butterfly | 127.2% | medium reversal |
| Crab | 161.8% | extreme reversal |

## Timing Pattern Regime Rule (Ch9)
- **TD setup**: trust in ranging markets, distrust in trends.
- **Fibonacci timing**: pair with price levels for confluence.

## Volatility-Scaled Risk (Ch6)
```
Stop distance = k × ATR(14)          (k=2 typical)
Position size = risk budget / stop distance
Squeeze (low vol) → breakout watch; high vol → caution
```

## Performance Metrics — Thresholds (Ch12)
| Metric | Good | Notes |
|--------|------|-------|
| Hit ratio | >50% | read WITH risk-reward |
| Risk-reward | >1.5 | low hit ratio OK if R:R high |
| Profit factor | >1.5 | >1 = profitable |
| Sharpe | >1 good, >2 very good | total risk |
| Sortino | higher better | downside only |
| Max drawdown | small | sizes your capital |

## Backtest Checklist (Ch12)
- [ ] Costs modeled (spreads + commissions)
- [ ] Out-of-sample / walk-forward pass
- [ ] Net return normalized (%, not $)
- [ ] Hit ratio + risk-reward read as a pair
- [ ] Max drawdown survivable at planned sizing

## Pattern Confirmation Rules (Ch7–10)
- Every pattern needs **confirmation** (next-bar close / neckline break) — never trade the pattern alone.
- Location + trend context decides meaning (a doji means opposite things in rally vs decline).
- Use **measured moves** for targets (pattern height from neckline).

## K's Indicators (Ch11)
- K's Reversal II = price + time + MA (3D) → decorrelated by construction.
- Pair **one K's + one classic** indicator — never K's-on-K's-on-K's.
- Prefer modern/less-crowded patterns to avoid self-fulfilling erosion.

## Tells & Smells
- **"Obvious" pattern after the fact** → hindsight bias; code it or skip it.
- **All indicators agree** → they're probably correlated; trust the uncorrelated one.
- **Backtest great, live terrible** → costs not modeled, or overfit; walk-forward next time.
- **Low volume move** → suspect; check volume candles.
