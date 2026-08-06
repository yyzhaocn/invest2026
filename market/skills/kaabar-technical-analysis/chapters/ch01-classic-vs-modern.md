# Chapter 1: Classic Technical Analysis Versus Modern Technical Analysis

## Core Idea
Technical analysis forecasts markets from historical price patterns, but classic techniques are plagued by subjectivity, correlation, and self-fulfilling behavior — modern technical analysis fixes this with rules-based, backtestable, decorrelated signals.

## Frameworks Introduced

### The Three Assumptions of Technical Analysis
- **History rhymes, not repeats**: patterns recur with comparable (never guaranteed) outcomes. Trading assumes non-random probability over the long term.
- **Market discounts everything**: all fundamental/technical/quant info is already in the price.
- **Market movement occurs in waves**: varied frequencies/timeframes create patterns rather than straight lines.

### Market Regimes
- **Bullish** (ascending trend), **Bearish** (descending), **Ranging** (sideways).
- Modern TA **weights signals by regime**: bullish signals matter more in uptrends, bearish signals more in downtrends, equal weight in ranging markets.

### Classic vs Modern TA Diagnostic
Classic TA fails on six counts; modern TA answers each:
| Classic problem | Modern answer |
|---|---|
| Subjective signals | Always rules-based, no discretion |
| Hard to backtest | Strict conditions → easy backtesting |
| Fitting paradox (Elliott wave hindsight) | Eliminate fitting-based techniques |
| Rusty indicators | New indicators with evolving calculation methods (e.g., K's Reversal II: price+time+MA) |
| Self-fulfilling prophecy (crowded patterns) | Modern indicators are unknown → immune |
| High intraclass correlation | Uncorrelated indicators with different math |

### Marginal Predictability Principle
Adding an indicator is only worthwhile if it is **uncorrelated** with current tools **and** better-than-random (>50% accuracy). Two highly correlated >50% indicators add no value; two uncorrelated ones compound conviction.

## Key Concepts
- **OHLC**: open, high, low, close — the four building blocks of financial time series; candlesticks are box-shaped OHLC per time step.
- **Support**: price floor where demand overcomes selling; forms via repeated bounces.
- **Resistance**: price ceiling where selling overcomes demand; repeated rejections.
- **Round/psychological levels**: clean numbers (100, 200 on USDJPY) act as natural barriers and self-fulfilling reference points.
- **EMH**: efficient market hypothesis — technical analysis's "greatest nemesis"; assumes no excess returns from active trading.
- **Regime**: the present and past directional state of the market.
- **Time series**: sequence of data points measured at successive times.

## Mental Models
- **Self-fulfilling barrier**: the more often price reacts at a level, the more traders expect it — the level works for expectation, not just supply/demand.
- **Role reversal**: broken resistance becomes support; broken support becomes resistance.
- **Think "rhymes, not repeats"** when a pattern looks obvious — hindsight bias is the trap.
- **Use X when Y**: use trend lines/pivots for inflection levels; indicators for objective signals; patterns for event-based expectations.

## Anti-patterns
- **Elliott wave in its classic form**: forces every market into a wave count — hindsight-fitting, subjective, unbacktestable. Only acceptable if rendered objective via algorithms.
- **Stacking correlated indicators**: RSI + MACD + Stochastic often fire together — diversification illusion.
- **Trading the same crowded pattern**: once everyone sees it, it works for the wrong reasons (luck), invalidating the hypothesis.

## Key Takeaways
1. Classify the regime (bull/bear/range) before choosing how much weight to give a signal.
2. Only add an indicator if it's uncorrelated with your current set AND better than random.
3. Prefer rules-based, backtestable signals over discretionary chart reading.
4. Watch psychological round numbers as support/resistance.
5. Incorporate sentiment (e.g., put-call ratio) or ML as bridges to other analysis styles.

## Connects To
- **Ch 3**: modern indicators (exotic MAs, Rainbow) are the practical application of decorrelation.
- **Ch 11**: K's Reversal II exemplifies the price+time+MA "3D" decorrelation idea.
- **Ch 12**: rules-based signals are what make backtesting meaningful.
