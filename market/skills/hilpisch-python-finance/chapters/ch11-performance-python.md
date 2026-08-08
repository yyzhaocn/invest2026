# Chapter 11: Performance Python

## Core Idea
Speed hierarchy for numerical code: **vectorize with NumPy first** (biggest single win, ~2 orders of magnitude), then **JIT with Numba** (`@nb.njit` on existing loops, no large intermediate arrays), then multiprocessing/Cython for specific cases — measure everything with `%timeit`.

## Frameworks Introduced
- **Vectorize → JIT → Parallel ladder**: (1) NumPy vectorization moves loops to C; (2) Numba compiles Python-structured loops via LLVM — often beats vectorized versions and avoids allocation; (3) multiprocessing for embarrassingly parallel Monte Carlo (large chunks per worker); (4) Cython for manual C-level control.
- **%timeit discipline**: compare alternative implementations; relative orders of magnitude matter, absolute numbers don't (hardware-dependent).

## Key Concepts
- **Pure Python loop overhead**: `average_py(1M)` ≈ 155ms vs NumPy ≈ 3.7ms (42x) on 2026 hardware.
- **Numba**: add `@nb.njit` to existing function; trigger compilation with a small call before timing. Random numbers inside compiled loops use Numba's own generator — treat JIT reproducibility as a separate concern (test seeding explicitly).
- **Multiprocessing**: `fork` on POSIX interactive (compact), `spawn` in production macOS; worker functions in importable module + `if __name__ == "__main__":` guard; chunk size must be large to amortize process overhead.
- **Cython**: `%%cython -a` magic; `cdef` typed vars; C-level `rand()` from libc for max speed.
- **lru_cache**: `@lru_cache(maxsize=None)` turns exponential recursion (fib(30)=52ms) into linear (fib(200)≈19ns).
- **Iterative beats cached recursion** even in pure Python.

## Mental Models
- Use X when Y: *vectorize when* the op maps to arrays; *Numba when* you keep loop structure + no big intermediates; *multiprocessing when* scenarios are independent (embarrassingly parallel); *Cython when* you need manual type/loop control.
- Think of multiprocessing as *complementary, not a replacement*: make each worker fast first, then parallelize.

## Anti-patterns
- **"Python is slow" from Python-level loops** — vectorize first.
- **Microbenchmark overinterpretation** — single %timeit ranking varies by CPU/version.
- **Uncontrolled seeds in JIT/parallel code** — reproducibility must be explicit.
- **Forking interactive sessions in production** — use spawn + module-level workers.

## Code Examples
```python
import numpy as np, numba as nb

def average_np(n):
    rng = np.random.default_rng(seed=42)
    return float(rng.standard_normal(n).mean())          # ~3.7ms/1M

@nb.njit
def average_nb(n):
    acc = 0.0
    for i in range(n):
        acc += np.random.standard_normal()               # compiled RNG
    return acc / n                                       # ~12ms w/o big array
# average_nb(10)  # trigger compilation first

# multiprocessing (production: spawn + module worker)
import multiprocessing as mp
def average_chunk(n, seed):
    return float(np.random.default_rng(seed).standard_normal(n).mean())
with mp.get_context("spawn").Pool(processes=4) as pool:
    means = pool.starmap(average_chunk, [(1_000_000, s) for s in range(4)])
    result = float(np.mean(means))

# caching
from functools import lru_cache
@lru_cache(maxsize=None)
def fib_rec_cached(n):
    return n if n < 2 else fib_rec_cached(n-1) + fib_rec_cached(n-2)
```
- **What it demonstrates**: vectorization, njit, multiprocessing, caching.

## Worked Example
Monte Carlo option pricing speed ladder: pure Python loops (~seconds) → NumPy vectorized (fast) → Numba njit (~vectorized speed, no big arrays) → Cython (manual C loop). Binomial option pricing: pure Python vs numba vs cython — same logic, 10-100x spread. Use `%timeit` to justify each step.

## Key Takeaways
1. NumPy vectorization is the first and biggest win.
2. Numba JITs existing loop code with one decorator.
3. Multiprocessing scales embarrassingly parallel workloads; large chunks per worker.
4. lru_cache converts exponential recursion to linear.
5. Measure with %timeit; trust relative orders of magnitude.

## Connects To
- **Ch 5**: NumPy vectorization foundations
- **Ch 13/28**: Monte Carlo simulation speedups
- **Ch 23**: backtesting performance
