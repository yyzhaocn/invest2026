# Patterns & Techniques

## Exotic Moving Averages (Ch 3)
**WMA** — When to use: trend following needing recency emphasis. How: weights 1..n ascending, Σ(w·v)/Σ(w). Trade-offs: more responsive than SMA; outliers hit harder.
**IWMA** — When to use: compare current price to long-term norm. How: weights descending. Trade-offs: smooth but slow to react.
**WMA/IWMA cross** — When to use: crossover strategy with one parameter. How: WMA(n) crosses IWMA(n). Trade-offs: removes the short/long parameter pair.
**HMA** — When to use: need both low lag and smoothness. How: WMA(√n) of (2·WMA(n/2) − WMA(n)). Trade-offs: best responsiveness/smoothness balance; window choice matters.
**KAMA** — When to use: regime-switching markets. How: smoothing adapts via efficiency ratio. Trade-offs: one MA for all conditions; no fixed lookback meaning.
**ALMA / LSMA** — ALMA for noise filtering; LSMA for slope/regression reading.

## Bollinger Band Techniques (Ch 3)
**Aggressive** — buy close below lower band / sell above upper band. Fast, more false signals.
**Conservative** — after band touch, wait for middle-band re-cross. Fewer false signals, delayed entries.
**Trend-friendly** — take only conservative signals aligned with trend.
**Bollinger–RSI overlay** — confirm band touches with RSI extremes.

## RSI Techniques (Ch 3)
**Aggressive** — classic 30/70. Baseline.
**V technique** — buy/sell the sharp reversal out of an extreme, not the extreme itself.
**DCC (Double Conservative Confirmation)** — two consecutive conservative confirmations; high conviction, low frequency.

## Fibonacci Trading (Ch 5)
**Retracement entry** — from swing A→B, buy/sell at 38.2/50/61.8% zones with confluence.
**Projection target** — extend 161.8% for exits; objective risk:reward math.
**23.6% reintegration** — re-enter strong trends on shallow 23.6% pullbacks with tight stops.

## Pattern Detection (Ch 7–10)
**Doji detection** — |close−open|/range < tol; context (trend + location) decides meaning; confirm next bar.
**Double bottom/top** — two similar pivots + neckline break; measured move = pattern height from neckline.
**Head and shoulders** — three peaks, neckline through troughs; breakdown confirms; width → target.
**Harmonic detection** — verify XABCD leg ratios within tolerance (Gartley/Bat/Crab/Butterfly tables); entry at D, stop beyond D.
**TD setup** — count 9 consecutive closes vs close 4 bars back; exhaustion watch in ranges only.

## Alternative Charting (Ch 4)
**Heikin-Ashi** — HA close = (O+H+L+C)/4, HA open = (prev HA O + prev HA C)/2; smoother trend reading.
**Volume candlesticks** — weight price moves by volume confirmation.

## Backtesting & Evaluation (Ch 12)
**Cost-aware backtest** — model spreads + commissions in every fill.
**Walk-forward validation** — rolling fit→out-of-sample test before trust.
**Metrics bundle** — net return, hit ratio + risk-reward (read as pair), profit factor, Sharpe/Sortino, max drawdown, CAGR.
