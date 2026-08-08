# Chapter 30: Portfolio Valuation

## Core Idea
Portfolios need structure: a **minimal pricing contract** so positions aggregate and risk metrics derive mechanically — positions with market values, standard errors for MC-based books, and bump-and-revalue deltas (Greeks by re-pricing).

## Frameworks Introduced
- **Minimal pricing contract**: each position exposes what's needed to value (instrument, quantity, price/market value) — aggregation becomes a sum.
- **Positions and aggregation**: book = collection of positions; total value, per-instrument contributions; diagnostic figures show which positions drive value/risk.
- **Standard errors in portfolios**: when position values come from Monte Carlo, aggregate SE propagates — report values with uncertainty.
- **Bump-and-revalue delta**: perturb the underlying (spot bump) → re-price the book → delta = (V_after − V_before)/bump. Model-agnostic Greeks at portfolio level.

## Key Concepts
- **Book-level risk**: sum of deltas from bump-and-revalue captures net exposure including correlation via re-pricing.
- **Contribution diagnostics**: per-position P&L/value contributions — where does portfolio value/risk come from?

## Mental Models
- Use X when Y: *bump-and-revalue when* you need Greeks without analytical derivatives; *contribution analysis when* explaining a book's value/risk.
- Think of a portfolio as *a vector of positions aggregated by a contract*, not ad-hoc sums.

## Anti-patterns
- **Ad-hoc portfolio sums** without a pricing contract — breaks when positions change type.
- **Ignoring MC standard errors** — presenting noisy values as exact.
- **Analytical Greeks only** — bump-and-revalue works for any model/payoff.

## Code Examples
```python
# (structure per chapter)
book = Portfolio()
book.add(Position(instrument=call, quantity=100))
book.add(Position(instrument=put, quantity=-50))

total_value = book.total_value()            # aggregation
se = book.standard_error()                  # MC uncertainty

delta = book.bump_and_revalue_delta(bump=0.01)   # (V(+bump) - V(-bump)) / 2bump
contrib = book.contributions()              # per-position value/risk share
```
- **What it demonstrates**: aggregation, SE, bump-and-revalue delta, contributions.

## Worked Example
Build a small book (European call + American put on index) → value each via MC → aggregate with SE → compute book delta by bumping spot ±1% and re-pricing (captures netting) → contribution plot shows call vs put share of value and delta.

## Key Takeaways
1. A minimal pricing contract makes portfolios aggregate cleanly.
2. MC values carry standard errors — report them.
3. Bump-and-revalue delivers model-agnostic portfolio Greeks.
4. Contribution diagnostics explain value and risk composition.

## Connects To
- **Ch 29**: individual valuations aggregate here
- **Ch 31**: market-calibrated models feed the book
- **Ch 18**: portfolio-level risk thinking (AM part)
