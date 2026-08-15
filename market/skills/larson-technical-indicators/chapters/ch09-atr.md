# Ch9 — ATR (Average True Range)

**Theme**: Volatility-based stops to protect profits and limit losses.

## Core Concepts
- **ATR (Average True Range)** measures volatility — used to set **trailing stops** sized to the stock's actual movement, the strongest way to protect profits and limit losses.
- **Stop-loss habit**: once a stock drops below the **30-day moving average**, place a **stop-loss order at a select price** (sized using ATR).

## Option Traders' Key Difference
- **Sell the option based on what the STOCK does** (ATR-based stop / underlying move), NOT on a **percentage of the option cost**. Most option traders sell for a loss based on % of the option cost — that's the mistake. Larson exits on the underling's ATR-move threshold.

## How to Apply
- Use ATR to set an objective stop distance (not arbitrary %).
- Trailing stop protects open profits; adjusts as volatility changes.

## Anti-pattern
- No stop-loss at all (the Intel example — "I didn't know about stops until Cha9") → bears unlimited downside.
- Selling options on %-of-premium loss instead of the stock's technical move.
