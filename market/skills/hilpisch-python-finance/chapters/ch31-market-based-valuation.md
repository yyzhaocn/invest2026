# Chapter 31: Market-Based Valuation

## Core Idea
Connect the valuation library to **observed option quotes**: load/clean a snapshot, infer forwards via put-call parity, compute implied vols (Black-76), build a small smile surface, then **horizon-split calibration** — Jump Diffusion for short horizons, Heston for long — and price options from the calibrated model.

## Frameworks Introduced
- **Market pipeline**: `load_spx_snapshot()` (cleans SPX options CSV, mid prices, bid-ask spreads) → `parity_table()` (merge calls/puts by expiry+strike) → `estimate_forward()` (robust forward from put-call parity, delta_band/min_price filters) → `select_small_surface()` (3 expiries × 5 strikes by moneyness, calibrate_to) → `ImpliedVolSurface` (interpolate IV over maturity+moneyness; flat/error extrapolation).
- **Black-76 machinery**: `bs_price_forward()` (forward form calls/puts), `implied_vol_forward()` (robust bisection inversion), norm_cdf/pdf helpers.
- **Horizon-split calibration**: short horizon → Merton JumpDiffusion on one expiry (captures smile skew); longer horizon → Heston global step, then per-expiry local refinement — `HestonParams`, `CalibrationBounds`, `JumpDiffusionParams`, `CalibrationDiagnostics` (records evaluations/failures/loss path).
- **Pricing with calibrated Heston**: `simulate_heston_spot_paths()` + `mc_call_prices()` (forward control variate) → European and American prices.

## Key Concepts
- **Options trade on a surface, not a vol**: term structure across maturities + smile/skew across strikes.
- **Teaching vs production calibration**: transparent pipeline with explicit steps, not a black-box optimizer.
- **Forward from parity**: F ≈ C−P + K·DF relationships per strike → robust estimate.

## Mental Models
- Use X when Y: *JD when* explaining short-dated smile; *Heston when* long-dated vol dynamics; *local step when* refining per-expiry fit.
- Think of calibration as *making the model respect the market surface* — fit quality shown in diagnostics.

## Anti-patterns
- **Single flat vol "calibration"** — ignores the surface entirely.
- **Black-box calibration** — every transformation must be explicit/auditable.
- **Ignoring calibration diagnostics** — loss paths, failures, candidate evaluations matter.

## Code Examples
```python
from dxlib.market import load_spx_snapshot, estimate_forward, select_small_surface, ImpliedVolSurface
from dxlib.calibration import calibrate_jump_diffusion, calibrate_heston

snap = load_spx_snapshot("data/spx_options_snapshot.csv")
fwd = estimate_forward(snap, expiry="2027-03-19")          # put-call parity
surface = select_small_surface(snap, expiries=3, strikes=5) # 15 quotes
iv = implied_vol_forward(price, fwd, strike, ttm, option_type)  # bisection

jd_params = calibrate_jump_diffusion(surface, horizon="short")   # one expiry
heston = calibrate_heston(surface, horizon="long")               # global + local
prices = mc_call_prices(spot, strikes, heston, control_variate=True)
```
- **What it demonstrates**: snapshot → forward → IV → calibration → MC pricing.

## Worked Example
SPX options session: load snapshot → forwards per expiry → implied vols (smile visible) → select 3×5 surface → calibrate JD on nearest expiry (short horizon, fits skew) → calibrate Heston on long expiries with local refinement → price European calls via MC (control variate) and American options; compare fitted vs market quotes (fit figure).

## Key Takeaways
1. Options trade on a surface — forwards, IVs, smiles are the market's language.
2. Put-call parity gives robust forwards; Black-76 inverts to IV.
3. Horizon-split calibration: JD short, Heston long, local refinement.
4. Calibrated Heston + MC (control variate) prices European/American options.

## Connects To
- **Ch 28-30**: simulation, valuation, portfolio blocks
- **Ch 27**: env/curves foundation
- **Ch 29**: LSM for American on calibrated paths
