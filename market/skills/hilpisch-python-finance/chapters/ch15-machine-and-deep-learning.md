# Chapter 15: Machine and Deep Learning

## Core Idea
Supervised learning with scikit-learn (classification/regression baselines), unsupervised PCA/K-means, and small neural nets in PyTorch — on synthetic datasets first (known structure), then sequence models (LSTM) for financial time series with explicit **caution about time-series predictability**.

## Frameworks Introduced
- **Baseline-first ML**: logistic regression (linear baseline) → RBF SVM (nonlinear) → MLP (flexible) — compare test accuracy on the same split (two-moons: 0.89 → 0.97 → …). `train_test_split(..., stratify=y)`.
- **Model selection by structure**: LinearRegression vs RandomForestRegressor (max_depth, n_estimators) with MSE comparison.
- **Unsupervised**: PCA (dimensionality reduction) + K-means clustering on synthetic blobs.
- **PyTorch thinking**: tensors, autograd gradients, optimizers; small MLP classifier.
- **Sequence models for finance**: convert prices → lagged-return windows; LSTM classification (multi-day up/down) and LSTM regression (next-day return).
- **Time-series predictability caution**: markets are noisy; evaluate with out-of-sample discipline, don't overclaim.

## Key Concepts
- **make_moons / make_regression**: synthetic datasets with known ground truth.
- **RBF kernel SVM**: `SVC(kernel="rbf", gamma="scale", C=1.0)` — curved boundaries in low-dim feature space.
- **Accuracy vs grounded truth**: synthetic data lets you see whether the model learned the right structure.
- **Lagged windows**: reshape return series into (n_windows, seq_len, features) for LSTMs.

## Mental Models
- Use X when Y: *logistic when* linear baseline needed; *SVM-RBF when* nonlinear boundary, small data; *LSTM when* temporal structure matters (with heavy skepticism).
- Think of synthetic datasets as *ground truth tests*: if the model can't learn structure you control, it won't learn market noise.

## Anti-patterns
- **Overclaiming predictability on markets** — the chapter's central caution.
- **Leaking future info** — lagged windows must not include the target period.
- **Judging models without a test split** — always hold out data.
- **Defaulting to complex models** when linear/tree baselines suffice.

## Code Examples
```python
from sklearn.datasets import make_moons
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score

X, y = make_moons(n_samples=500, noise=0.25, random_state=2027)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3,
                                                    random_state=2027, stratify=y)
acc_lin = accuracy_score(y_test, LogisticRegression(solver="lbfgs").fit(X_train, y_train).predict(X_test))   # ≈0.89
acc_svm = accuracy_score(y_test, SVC(kernel="rbf", gamma="scale", C=1.0).fit(X_train, y_train).predict(X_test))  # ≈0.97

# LSTM windows from returns
X = np.column_stack([rets.shift(i) for i in range(1, seq_len+1)])  # lagged features
```
- **What it demonstrates**: baseline vs nonlinear classifier; lagged-return feature building.

## Worked Example
Two-moons: logistic decision boundary ≈ linear (0.893) vs RBF SVM curved boundary (0.973) — visualize probability color map + test points. Time series: SPY daily returns → 20-day lagged windows → LSTM classifies next-day up/down; report out-of-sample accuracy and compare against a naive baseline (predict "up" always) to check real edge.

## Key Takeaways
1. Start with simple baselines; add complexity only when it wins out-of-sample.
2. Synthetic datasets verify models learn controllable structure.
3. Financial time series: lagged windows + LSTM, but evaluate with discipline.
4. PCA/K-means for unsupervised structure discovery.

## Connects To
- **Ch 14**: statistics foundation for ML
- **Ch 16**: text models (NLP/LLM) build on these patterns
- **Ch 19**: signals and forecasts applied
