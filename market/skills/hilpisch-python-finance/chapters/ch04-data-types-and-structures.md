# Chapter 4: Data Types and Structures

## Core Idea
Choose the right built-in type early (list/tuple/dict/set, int/float/bool/str), copy deliberately (shallow vs deep), and write readable transformations — the foundation that keeps NumPy, pandas, and ML code simple.

## Frameworks Introduced
- **Container Choice Rule**: pick by ordering/mutability/access — list (ordered, mutable, append/build), tuple (ordered, immutable, fixed records/returns), dict (fast keyed lookup, insertion-ordered since 3.7, named fields), set (uniqueness, O(1) membership).
- **Money → Decimal**: for money-like quantities prefer `decimal.Decimal` with explicit context precision; `float` is binary and cannot represent decimals exactly.
- **Copy Discipline**: shallow copy duplicates the container but shares nested objects; deep copy duplicates everything. Prefer immutable tuples for fixed records to reduce deep-copy need.

## Key Concepts
- **bool is int subclass**: `True == 1`, but use bools for logic, not arithmetic.
- **float gotcha**: `0.1 + 0.2 == 0.30000000000000004`; `round()` gives a float that compares equal but doesn't fix the representation.
- **int is arbitrary precision**: no overflow in typical finance use.
- **dict.get(key, default)** avoids KeyError for optional fields.
- **zip + enumerate**: pair sequences and add counters without manual indexing.
- **any/all**: replace explicit predicate loops with clear intent.

## Mental Models
- Use X when Y: *tuple when* the record is fixed; *list when* you'll append/mutate; *set when* uniqueness or membership matters.
- Think of exceptions as *expected-condition handling*: small try blocks, `else` for success path, `finally` for cleanup.
- Prefer iterating over values (`for sym in symbols`) over index loops.

## Anti-patterns
- **Shared-reference mutation**: `shallow = positions.copy()` still mutates `positions` through nested dicts.
- **Manually counting with range(len())** when `enumerate` says intent better.
- **Catching broad exceptions** or wrapping large code regions in try.
- **break-heavy loops** when `any()`/`all()` would be clearer.

## Code Examples
```python
from decimal import Decimal, getcontext
getcontext().prec = 10
gross = Decimal("100.00")
net = gross - gross * Decimal("0.0015")   # Decimal('99.850000')

# dict with derived field + safe get
quote = {"symbol": "EURUSD", "bid": 1.0810, "ask": 1.0812}
quote["mid"] = (quote["bid"] + quote["ask"]) / 2
mid = quote.get("mid", float("nan"))

# comprehension with filter
evens = [v for v in values if v % 2 == 0]
canonical = {s.upper() for s in raw_symbols}   # normalize + dedupe

# try/except/else/finally with small body
try:
    price = Decimal(data["close"])
except (KeyError, InvalidOperation):
    price = Decimal("NaN")
else:
    price = price.quantize(Decimal("0.0001"))
finally:
    status = "done"
```
- **What it demonstrates**: Decimal money math, safe dict access, deduping comprehensions, minimal try blocks.

## Worked Example
EURUSD quote processing: `quote` dict with bid/ask → add mid → dict-comprehension `{symbol: ask - bid}` → confirm `spreads['EURUSD'] ≈ 0.0002` (float artifact visible). Spread computed via comprehension; note 0.0001999999… from binary float — use Decimal if spread must be exact.

## Key Takeaways
1. Four containers cover most needs — choose by ordering, mutability, and access pattern.
2. `0.1+0.2 ≠ 0.3`; use Decimal for money, `round()` only for display-level tolerance.
3. Shallow vs deep copy: understand sharing before mutating nested structures.
4. Comprehensions + zip/enumerate + any/all make transformations readable and fast.

## Connects To
- **Ch 5**: NumPy replaces lists for numerical arrays
- **Ch 6**: pandas builds labeled structures on these foundations
