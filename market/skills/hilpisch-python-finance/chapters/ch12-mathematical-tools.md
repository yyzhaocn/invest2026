# Chapter 12: Mathematical Tools

## Core Idea
The four workhorse math toolkits for quant finance: **least-squares regression with basis functions** (NumPy), **interpolation/splines** (SciPy), **root finding & convex optimization** (scipy.optimize), and **symbolic math** (SymPy) — applied to yield curves, option pricing, and portfolio problems.

## Frameworks Introduced
- **Basis-function regression**: build design matrix `X` (intercept, x, x², sin(x), …) and solve `np.linalg.lstsq(X, y)` — encodes domain knowledge (e.g. sinusoidal term for term structure) and recovers true coefficients under noise. Central for yield curves, vol surfaces, factor models.
- **Regression vs interpolation choice**: regression when data noisy → best fit; spline when you trust the knots (actively quoted rates) → passes through exactly. Smoothness is an *assumption* imposed on data.
- **Root finding**: `scipy.optimize.root_scalar(f, bracket=(a,b), method="brentq")` — needs continuous function + sign change. Invert price→yield/vol/rate.
- **Convex optimization**: scipy.optimize for mean-variance and other convex objectives; global vs local optimizers for 2D problems.
- **Symbolic → numeric bridge**: SymPy solves equations symbolically, differentiates (Greeks), then lambdify to numerical functions.

## Key Concepts
- **OLS**: minimize ‖y - Xβ‖²; `lstsq` returns β, residuals, rank, singular values.
- **Noisy/unsorted data robustness**: regression cares about rows, not order — permuting inputs gives `allclose` identical coefficients.
- **CubicSpline**: piecewise polynomial, continuous 1st+2nd derivatives; evaluate like a function on fine grids.
- **Numerical integration**: integrate standard normal density and option pricing as integrals (quad).
- **Zero-coupon yield inversion**: `P₀ = F·exp(-yT)` → root_scalar over pricing error.

## Mental Models
- Use X when Y: *lstsq when* fitting noisy market data; *spline when* respecting quoted points exactly; *root_scalar when* inverting a pricing function; *SymPy when* deriving Greeks then lambdify.
- Think of basis functions as *encoding prior knowledge* into linear regression.

## Anti-patterns
- **Exact interpolation on noisy data** — overfits the noise.
- **Unbracketed root finding** — brentq needs a sign-changing interval.
- **Symbolic-only workflows** — lambdify to get fast numerics.

## Code Examples
```python
import numpy as np
from scipy import optimize
from scipy.interpolate import CubicSpline

# basis-function regression (term structure)
X = np.column_stack([np.ones_like(x), x, x**2, np.sin(x)])
beta, *_ = np.linalg.lstsq(X, y_obs, rcond=None)   # recovers [~0, ~0.1, ~0, ~0.5]

# cubic spline
spl = CubicSpline(x_grid, y_clean)
y_fine = spl(np.linspace(0, 10, 201))

# invert bond price -> yield
def bond_err(y): return face*np.exp(-y*T) - price_0
res = optimize.root_scalar(bond_err, bracket=(0.0, 0.2), method="brentq")
res.root  # 0.025566674301997327
```
- **What it demonstrates**: lstsq with basis, spline, root_scalar.

## Worked Example
Mean-variance portfolio: minimize variance subject to expected return target and weights-sum constraint via scipy.optimize (convex); compare with global optimization on a 2D grid for a two-asset problem. Greeks: SymPy `diff()` on the Black-Scholes formula → lambdify → numeric deltas/gammas.

## Key Takeaways
1. lstsq + basis functions = flexible curve fitting for yields/vols/factors.
2. Splines when knots are trusted; regression when data is noisy.
3. root_scalar(brentq) inverts any pricing function given a bracket.
4. SymPy → lambdify bridges symbolic derivations to fast numerics.

## Connects To
- **Ch 13**: stochastics simulation uses these tools
- **Ch 27-29**: valuation framework, derivatives pricing
- **Ch 18**: portfolio optimization (mean-variance)
