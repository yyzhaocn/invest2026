# Chapter 17: Asset Management Foundations

## Core Idea
Asset management = a repeatedly executed workflow driven by **mandates** (the written contract between asset owners and managers): read current data → apply consistent rules → write updated portfolios and reports. The mandate is the north star — models/code matter only insofar as they implement it in a disciplined, explainable way.

## Frameworks Introduced
- **Mandate → Portfolio → Process → Report mapping**: each mandate gives rise to a portfolio (holdings), processes (how it's updated), and a reporting schedule — this structure maps directly to Python workflows.
- **Absolute vs benchmark-relative mandates**: absolute-return ("CPI+3%") vs benchmark-relative ("outperform MSCI World by 1%") — most book examples are benchmark-relative, long-only, multi-year.
- **Three mandate questions**: What are we trying to achieve? Over which horizon? How much risk is acceptable (volatility, drawdown, tracking error, VaR)?
- **Data structures for AM**: cross-sectional snapshots (assets × attributes at a date), panel data (returns/holdings over time), identifiers/metadata/reference data.

## Key Concepts
- **Actors**: asset owners (pension funds, endowments, sovereign funds — define goals), asset managers (design/run portfolios under mandate), mandates/IPS (written contract: universe, instruments, leverage, benchmarks, constraints, reporting).
- **Asset classes**: equities, fixed income, cash/equivalents, alternatives; direct positions vs pooled vehicles (ETFs).
- **Benchmarks & tracking error**: performance relative to a specified index; tracking error measures deviation.
- **Constraints & risk limits**: position/sector/asset-class limits; liquidity, turnover, capacity; regulatory, ESG, client-specific constraints.
- **Investable universe**: the set of instruments a mandate permits.

## Mental Models
- Think of the mandate as *the specification*: models and data are implementation details.
- Use X when Y: *cross-sectional snapshot when* looking at asset attributes at one date; *panel data when* returns/holdings evolve over time.
- Horizons decide volatility tolerance: decades (endowment) vs quarters (cash management).

## Anti-patterns
- **Building models detached from mandates** — code without mandate alignment is ungrounded.
- **Ignoring constraints/limits** — risk limits are part of the problem definition.
- **Conflating asset classes / forgetting pooled vehicles** — instrument taxonomy matters.

## Code Examples
*(Chapter 17 is framework-heavy; data-structure patterns follow in later chapters.)*

## Reference Tables
| Mandate axis | Absolute-return | Benchmark-relative |
|---|---|---|
| Goal | "CPI + 3% annualized" | "MSCI World + 1% annualized" |
| Judged against | return target / inflation | specified index |
| Key risk metric | drawdown, volatility | tracking error |

## Worked Example
Map an IPS to code: take a benchmark-relative mandate (long-only equities, MSCI World +1%, TE ≤ 3%, position ≤ 5%, no ESG-excluded sectors) → define universe from index constituents → panel of returns/holdings → portfolio construction rules (Ch 18) → daily workflow: data → rebalance → report.

## Key Takeaways
1. Mandates encode objectives, constraints, and reporting — start there.
2. Absolute vs benchmark-relative changes how success and risk are measured.
3. Cross-sectional + panel data structures support systematic workflows.
4. The workflow loop: read data → apply rules → write portfolio/report.

## Connects To
- **Ch 18**: portfolio construction and risk (executes mandates)
- **Ch 19**: signals and forecasts into portfolio implementation
- **Ch 20-21**: systems, reporting, and the small AM library
