# Chapter 2: Python Fluency and GenAI

## Core Idea
You can outsource thinking, not understanding: Python fluency is the leverage point for using GenAI responsibly in finance — treat AI output as a draft that must be reviewed, validated, and adapted.

## Frameworks Introduced
- **Draft-Review Workflow for Generated Code**: four-pass review of any AI-proposed code.
  1. *Skim structure* — function/class boundaries, imports, dependencies, shape of the solution.
  2. *Check assumptions* — data format, column names, time zones, data frequency.
  3. *Scan numerical/financial correctness* — discount factors, compounding, day-count conventions, time indexing explicit.
  4. *Check error handling* — fail loudly on invalid input, never silently produce wrong numbers.
- **Precise Prompting**: specify context (data source, historical vs streaming), constraints (runtime, missing data, rounding, output format), and interface (function signature with typed inputs/outputs, e.g. `summarize_prices(data: pd.DataFrame) -> dict[str, float]`).
- **Validation Triangle**: (1) toy synthetic example you can reason by hand → (2) invariants (probabilities sum to 1, row counts match, returns from constant price = 0) codified as unittest/pytest → (3) baseline comparison (known formula or trusted implementation).

## Key Concepts
- **Fail fast**: validate required columns/inputs with clear user-facing errors before computing.
- **ddof=1**: pandas default sample standard deviation; explicit for intent.
- **Contract-first docstrings**: state the contract for readers and tools.
- **Role-based collaboration**: students run everything themselves; lecturers generate variations/scaffolding; professionals use GenAI as pair-programmer for glue code while owning correctness and risk.

## Mental Models
- Think of generated code as *a strong junior developer's draft*: read it before running it.
- Use X when Y: *specify type hints and signatures when prompting* so code fits your project without unrequested finance assumptions.
- Ask one model to propose checks, another to critique whether those checks are strong enough.

## Anti-patterns
- **Generic prompts** ("write a program that analyzes prices") → unusable, assumption-laden output.
- **Trusting output without validation**: assume the snippet contains mistakes until proven otherwise.
- **Ignoring hidden conventions**: time zones, day counts, and column names silently baked into code.

## Code Examples
```python
import pandas as pd

def summarize_prices(data: pd.DataFrame) -> dict[str, float]:
    """Summarize close prices with validation."""
    if "close" not in data.columns:
        raise ValueError("expected a 'close' column in the input DataFrame")
    close = pd.to_numeric(data["close"], errors="coerce").dropna()
    return {
        "mean": float(close.mean()),
        "median": float(close.median()),
        "std": float(close.std(ddof=1)),
    }

sample = pd.DataFrame({"close": [100.4, 101.1, 101.1, 102.3]})
summarize_prices(sample)
# {'mean': 101.225, 'median': 101.1, 'std': 0.7889866919029723}
```
- **What it demonstrates**: contract-first function, fail-fast validation, explicit ddof, typed return.

## Worked Example
Minimal pipeline workflow: (1) download daily prices for one asset → (2) compute log returns + rolling volatility → (3) plot and save. With GenAI: ask for the full script draft with clear function boundaries → review imports/error handling/naming → run on a limited date range and inspect outputs → factor reusable pieces into modules. Scales to larger data and models.

## Key Takeaways
1. Treat AI-proposed code as a draft requiring a 4-pass review (structure → assumptions → numerics → errors).
2. Prompt with context + constraints + typed interfaces, not vague requests.
3. Validate on toy data, codify invariants as tests, compare against baselines.
4. The human stays responsible for connecting code to real data, risk limits, and production constraints.

## Connects To
- **Ch 1**: AI-first finance framing
- **Ch 3-8**: the fluency (types, pandas, numpy) needed to run these patterns
