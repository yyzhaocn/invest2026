# Chapter 11: A New Breed of Technical Indicators

## Core Idea
K's collection — the author's proprietary indicators — fuses price, time, and moving averages to create signals decorrelated from classic tools; designed to survive the self-fulfilling-prophecy and correlation problems of mainstream indicators.

## Frameworks Introduced

### K's Reversal Indicator I
- Composed around the **MACD** oscillator (classic trend/momentum component).
- Converts MACD behavior into reversal signals with defined rules.
- Useful as a trend-following/reversal hybrid; see book for exact signal conditions.

### K's Reversal Indicator II (author's favorite)
- **No relation** to K's Reversal I — different construction entirely.
- **3-dimensional**: takes into account **price + time + moving averages** to find directional signals.
- Why it matters (Ch1 link): the price+time+MA fusion **decorrelates** its signals from other indicators → adds genuine marginal predictability when combined with classic tools.
- The chapter's argument: this is what "a new breed" means — not a tweaked classic, but a different dimension of input.

### K's RSI²
- Builds on the **slope-divergence technique** first introduced with the Yellow indicator (Ch3).
- Compares RSI behavior at two levels/periods (squared relationship) to sharpen divergence detection.

## Key Concepts
- **Decorrelation**: the design goal — signals independent of classic indicator behavior.
- **Slope divergence**: comparing the slope of price vs slope of an indicator.
- **3D signal**: price + time + MA combined — the defining trait of K's Reversal II.
- **Structured indicator**: a fusion of multiple indicators (vs raw indicators built from scratch).

## Code Example
```python
def k_reversal_II(df, ma_window=20):
    # price dimension: close relative to MA
    ma = df['close'].rolling(ma_window).mean()
    # time dimension: consecutive bars spent in a state
    state = (df['close'] > ma).astype(int)
    time_count = state.groupby((state != state.shift()).cumsum()).cumsum()
    # signal: price crosses MA after an extended time in the opposite state
    return (state.diff() != 0) & (time_count.shift(1) >= 3)
```
- **What it demonstrates**: fusing price (vs MA) and time (bar counts) into one signal — illustrative of the 3D idea; the book's exact construction differs.

## Key Takeaways
1. K's Reversal II's value = decorrelation via price+time+MA fusion.
2. Pair one K's indicator with one classic indicator — the combination adds more than any two classics.
3. Modern/unknown indicators are immune to crowding (self-fulfilling prophecy).
4. Slope-divergence (from Ch3's Yellow) is a reusable technique across indicators.

## Connects To
- **Ch 1**: marginal predictability principle — K's indicators are the exemplar.
- **Ch 3**: Rainbow indicators set up the slope-divergence technique reused here.
- **Ch 12**: evaluate whether any indicator actually beats >50% before adding it.
