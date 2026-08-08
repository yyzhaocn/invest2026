# Chapter 23: Vectorized and Event-Based Backtesting

## Core Idea
Backtesting is the quantitative counterpart to EMH hypothesis tests — and the key discipline is **structural soundness**: vectorized and event-based implementations must agree when they represent the same trading rule, so backtests resemble the execution environment they stand in for.

## Frameworks Introduced
- **Feature/label design for direction prediction**: features = r_lag1, 5d rolling mean, 20d rolling mean; label = next-day direction (1 if next return > 0). Logistic regression baseline.
- **Walk-forward prediction**: refit logistic regression on rolling 2y training window → predict next 1-month block → roll forward (with `Pipeline` + `StandardScaler` per refit). No static train/test split for financial evaluation.
- **Vectorized backtest with proportional costs**: position from predicted direction (long/short); returns adjusted by cost per trade; equity curve = cumprod; compare vs buy-and-hold.
- **Minimal event-based backtester**: bars, orders, and account state (cash, positions, equity) — same signal stream replayed event-by-event; results must match vectorized version.
- **Cost awareness**: proportional transaction costs per rebalance/turnover — the difference between research and implemented performance.

## Key Concepts
- **H₀/H₁ for backtests**: H₀ = daily returns unpredictable beyond buy-and-hold; H₁ = classifier switching long/short improves equity curve.
- **Walk-forward loop**: `DEFAULT_TRAINING_WINDOW = 2*252`, `DEFAULT_TEST_WINDOW = 21`.
- **Out-of-sample diagnostics**: inspect OOS curves and metrics — not in-sample accuracy.
- **Event-based components**: bars (market data events), orders (intents), account state (fills → positions → equity).

## Mental Models
- Use X when Y: *vectorized when* fast, simple, same-rule testing; *event-based when* modeling execution detail (orders, fills, slippage).
- Think of the event-based backtester as *a rehearsal of the deployment engine* (Ch 24).

## Anti-patterns
- **In-sample evaluation** — walk-forward or nothing.
- **Cost-free backtests** — proportional costs are mandatory realism.
- **Vectorized vs event-based divergence** — if they disagree on the same rule, something is structurally wrong.
- **Unbalanced label leakage** — features/labels must use only information available at prediction time.

## Code Examples
```python
def make_features_and_labels(closes):
    rets = closes.pct_change()
    next_ret = closes.shift(-1) / closes - 1.0
    data = pd.DataFrame({
        "r_lag1": rets.shift(1),
        "mom_5": rets.rolling(5).mean(),
        "mom_20": rets.rolling(20).mean(),
        "next_ret": next_ret}).dropna()
    X = data[["r_lag1", "mom_5", "mom_20"]]
    y = (data["next_ret"] > 0.0).astype(int)
    return X, y

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
model = Pipeline([("scaler", StandardScaler()),
                  ("clf", LogisticRegression())])
# walk-forward: fit on 2y window, predict 21-day block, roll forward

# vectorized backtest with costs
position = model.predict_proba(X_oos)[:, 1].round() * 2 - 1  # ±1 exposure
trades = position.diff().abs()
strat_ret = position.shift(1) * rets_oos - costs_per_unit * trades
equity = (1 + strat_ret).cumprod()
```
- **What it demonstrates**: features/labels, walk-forward, cost-adjusted strategy returns.

## Worked Example
EURUSD daily direction: build features/labels → walk-forward logistic regression (2y train / 1m predict) → vectorized backtest with 0.5‰ proportional cost → equity curve vs buy-and-hold → same signal stream through event-based backtester (bars/orders/account) → compare curves — they must match. Analyse OOS performance: hits, costs, max drawdown.

## Key Takeaways
1. Backtests test a hypothesis: same rule must reproduce in both vectorized and event-based forms.
2. Walk-forward refitting is mandatory for honest evaluation.
3. Proportional costs separate research performance from implemented performance.
4. Event-based backtesting rehearses the execution environment.

## Connects To
- **Ch 22**: EMH hypothesis framing
- **Ch 24**: event-based engine → market/broker simulation
- **Ch 25**: deployment reuses the strategy logic
