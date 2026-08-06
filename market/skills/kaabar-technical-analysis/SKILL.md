---
name: kaabar-technical-analysis
description: "Knowledge base from \"Mastering Financial Markets with Python - New Horizons in Technical Analysis\" by Sofien Kaabar. Use when applying Kaabar's frameworks for modern technical analysis, exotic moving averages, Fibonacci trading, pattern recognition (candlestick/harmonic/timing/price), K's indicators, volatility analysis, or backtesting/performance evaluation in Python."
---

# Mastering Financial Markets with Python
**Author**: Sofien Kaabar | **Pages**: ~204 | **Chapters**: 12 | **Generated**: 2026-08-06

## How to Use This Skill

- **Without arguments** — load core frameworks for reference
- **With a topic** — ask about `fibonacci`, `harmonic patterns`, `K's indicators`, `volatility`, or another indexed topic; I find and read the relevant chapter
- **With chapter** — ask for `ch05`; I load that specific chapter
- **Browse** — ask "what chapters do you have?" to see the full index

When you ask about a topic not covered in Core Frameworks below, I will read the relevant chapter file before answering.

---

## Core Frameworks & Mental Models

### Modern vs Classic Technical Analysis (Ch1)
- **Use "modern" TA when** classic indicators fail: classic TA suffers from *subjectivity* (unbacktestable rules), *fitting paradox* (Elliott wave hindsight), *rusty indicators* (decades-old formulas on evolved markets), *self-fulfilling prophecy* (crowded patterns), and *high intraclass correlation* (RSI/MACD/etc. signal together).
- **Modern TA rule**: every signal must be *rules-based and backtestable* — no discretionary interpretation.
- **Marginal predictability principle**: adding an indicator to your toolkit only helps if it is (a) uncorrelated with what you already use AND (b) better-than-random (>50% accuracy). Two correlated >50% indicators add nothing.
- **Regime-weighted signals**: in an uptrend, bullish signals outweigh bearish ones; in a downtrend, bearish signals outweigh bullish ones; in a sideways regime both weigh equally. Apply your indicator signals *conditional on regime*, not raw.
- **Modern toolkit**: modern indicators (raw or structured fusions), modern patterns (double trouble, Fibonacci timing), modern techniques (V technique on RSI — new uses of classic indicators).
- **Bridge to other analysis**: apply modern indicators on sentiment inputs (e.g., put-call ratio) or feed indicator values into ML models.

### Market Structure (Ch1)
- Three TA assumptions: (1) history *rhymes* (not repeats), (2) market discounts everything, (3) movement occurs in waves.
- Three regimes: bullish / bearish / ranging. Classify regime before choosing signals.
- Support/resistance are **self-fulfilling** levels formed by repeated tests; round/psychological levels (e.g., 100, 200 on JPY pairs) act as natural barriers. Broken resistance becomes support, and vice versa.

### Exotic Moving Averages (Ch3)
- **WMA** (weighted): weights increase with recency — more responsive than SMA, but outliers hit harder.
- **IWMA** (inverse weighted): weights favor older data — smooth, laggy, useful for comparing current price to long-term trend.
- **WMA/IWMA cross**: use *one* lookback parameter for both (WMA = short, IWMA = long) — removes the second MA parameter from crossover strategies. Bullish when WMA crosses above IWMA.
- **HMA** (Hull): `WMA(sqrt(n)) of (2×WMA(n/2) − WMA(n))` — reduces lag while staying smooth; the best of both responsiveness and noise filtering.
- **KAMA** (Kaufman adaptive): smoothing factor adapts to volatility via *efficiency ratio* (|net change| / Σ|period changes|). Responsive in trends, calm in chop.
- **ALMA** (Arnaud Legoux), **LSMA** (least-squares fit line): see ch03.

### Bollinger & RSI Techniques (Ch3)
- **Bollinger aggressive**: sell close above upper band, buy close below lower band (default).
- **Bollinger conservative**: wait for price to *re-cross the middle band* after touching outer band — fewer false signals.
- **Trend-friendly**: take only the conservative signal aligned with trend.
- **Bollinger–RSI overlay**: combine band touch with RSI confirmation.
- **RSI aggressive** (classic 30/70), **RSI V technique** (RSI spikes into extreme then reverses — early signal), **DCC (double conservative confirmation)**: require two consecutive confirmations — personal favorite of the author.

### Fibonacci (Ch5)
- Core ratios: **23.6%**, **38.2%**, **50%**, **61.8%**, **78.6%**, **161.8%** (golden ratio ϕ≈1.618; 61.8% = 1/1.618).
- Use retracements for support/resistance entries; projections for targets; **23.6% reintegration technique** for re-entries after shallow pullbacks. Combine multiple ratios for confluence.

### Pattern Recognition (Ch7–10)
- **Candlestick (Ch7)**: classic Doji (open≈close — indecision, reversal watch); modern patterns incl. **double trouble** and **extreme euphoria** — code them as objective rules, don't eyeball.
- **Harmonic (Ch8)**: fractal XABCD structures with Fibonacci ratios — Gartley, Bat, Crab, Butterfly, ABCD. Apply across timeframes because markets are fractal.
- **Timing (Ch9)**: patterns with a *time condition* — e.g., **TD setup** (DeMark), Fibonacci timing pattern. TD setup **thrives in ranging markets**, underperforms in trends.
- **Price (Ch10)**: double top/bottom, head & shoulders — reversal patterns needing confirmation.

### K's Collection — New Breed of Indicators (Ch11)
- **K's Reversal Indicator I**: MACD-based reversal tool.
- **K's Reversal Indicator II** (author's favorite): fuses **price + time + moving averages** — 3-dimensional, hence decorrelated from other indicators. No relation to K's Reversal I.
- **K's RSI²**: builds on the slope-divergence technique (see Yellow indicator, Ch3).
- Philosophy: modern indicators are unknown → immune to self-fulfilling prophecy; combining 2 uncorrelated >50%-accuracy indicators beats any correlated pair.

### Alternative Charting (Ch4)
- **Volume candlesticks**: shows if moves are volume-backed (weak up-move on low volume = warning).
- **Heikin-Ashi**: `HA close = (O+H+L+C)/4`, `HA open = avg(prev HA open, prev HA close)` — filters noise for clearer trend reading.
- **K's candlestick charting system**: alternative OHLC construction.

### Performance Evaluation (Ch12)
- **Net return** (normalizes capital differences), **Hit ratio** (win rate; >50% good, <40% weak — but low hit ratio is fine if winners >> losers), **Risk-reward ratio**, **Profit factor**, **Sharpe** (>1 good, >2 very good), **Sortino** (downside-only deviation), **max drawdown**, CAGR/annualized return.
- Backtest discipline: include costs (spreads + commissions), then **walk-forward testing** — past backtest results are the best hope, not a guarantee.

---

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-classic-vs-modern.md) | Classic vs Modern Technical Analysis | TA assumptions, regimes, classic pitfalls, modern principles |
| [ch02](chapters/ch02-time-series-python.md) | Exploring Time Series Analysis with Python | OHLC, pandas, plotting, data importing |
| [ch03](chapters/ch03-modern-techniques-indicators.md) | Modern Techniques and Indicators | WMA/IWMA/HMA/KAMA, Bollinger & RSI techniques, Rainbow |
| [ch04](chapters/ch04-alternative-charting.md) | Alternative Charting Systems | Volume candles, Heikin-Ashi, K's candlesticks |
| [ch05](chapters/ch05-advanced-fibonacci.md) | Advanced Fibonacci Analysis | Ratios, retracements, 23.6% reintegration |
| [ch06](chapters/ch06-volatility-indicators.md) | Advanced Volatility Indicators | Volatility uses, bands, ATR, channels |
| [ch07](chapters/ch07-candlestick-patterns.md) | Pattern Recognition I — Candlestick | Doji, double trouble, extreme euphoria |
| [ch08](chapters/ch08-harmonic-patterns.md) | Pattern Recognition II — Harmonic | Gartley, Bat, Crab, Butterfly, ABCD |
| [ch09](chapters/ch09-timing-patterns.md) | Pattern Recognition III — Timing | TD setup, Fibonacci timing |
| [ch10](chapters/ch10-price-patterns.md) | Pattern Recognition IV — Price | Double top/bottom, head & shoulders |
| [ch11](chapters/ch11-new-breed-indicators.md) | A New Breed of Technical Indicators | K's Reversal I/II, K's RSI² |
| [ch12](chapters/ch12-performance-evaluation.md) | Performance Evaluation in Python | Net return, hit ratio, Sharpe/Sortino, backtesting |

## Topic Index

- **Aggressive/conservative techniques** → ch03
- **Bollinger bands** → ch03, ch06
- **Doji / candlestick patterns** → ch07
- **Double top/bottom** → ch10
- **Double trouble pattern** → ch07
- **Efficiency ratio (KAMA)** → ch03
- **Fibonacci ratios/retracements** → ch05
- **Fibonacci timing pattern** → ch09
- **Gartley/Bat/Crab/Butterfly** → ch08
- **Head & shoulders** → ch10
- **Heikin-Ashi** → ch04
- **Hit ratio / win rate** → ch12
- **HMA / Hull moving average** → ch03
- **KAMA / adaptive MA** → ch03
- **K's Reversal I/II, K's RSI²** → ch11
- **Max drawdown / Sharpe / Sortino** → ch12
- **OHLC / candlesticks / regimes** → ch01
- **Profit factor / risk-reward** → ch12
- **Put-call ratio (sentiment bridge)** → ch01
- **RSI techniques (V, DCC)** → ch03
- **Support/resistance / round levels** → ch01
- **TD setup (DeMark)** → ch09
- **Time series components** → ch02
- **Volume candlesticks** → ch04
- **Walk-forward testing** → ch12
- **WMA / IWMA cross** → ch03

## Supporting Files

- [glossary.md](glossary.md) — all key terms with definitions
- [patterns.md](patterns.md) — all techniques and design patterns
- [cheatsheet.md](cheatsheet.md) — quick reference tables and decision guides

---

## Scope & Limits

This skill covers the book content only. For hands-on implementation in your codebase, combine with project-specific tools (e.g., the market/skills suite for data fetching and backtesting). For topics beyond this book, check related skills or ask the agent directly. All code examples reference the author's open repository: `github.com/sofienkaabar/mastering-financial-markets-in-python`.
