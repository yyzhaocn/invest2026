# Chapter 1: Why Python for Finance?

## Core Idea
Financial institutions are technology firms under regulation; Python is the strategic layer that keeps financial workflows coherent, testable, and extensible — and GenAI increases, not replaces, the need for Python fluency.

## Frameworks Introduced
- **Code-First Workflows**: replace spreadsheet logic with version-controlled, rerunnable Python scripts.
  - When to use: any logic that is edited manually, copied across versions, or audited.
  - How: codify in named variables/functions/modules → schedule or event-trigger → version control with clear diffs.
- **AI-First Finance**: treat LLMs as collaborators whose output must be verified against data and tests.
  - When to use: every GenAI-assisted coding session.
  - How: read and critique generated code → integrate into existing codebase → design tests catching subtle errors.

## Key Concepts
- **Ecosystem layers**: NumPy (vectorized arrays) → pandas (labeled Series/DataFrame) → Matplotlib (viz) → scikit-learn/PyTorch (ML) → domain packages (derivatives, backtesting, broker APIs).
- **Python's strategic properties**: open source, readable syntax (audit-friendly), multi-paradigm (procedural → functional → OOP), dynamic but introspectable, strong AI-assistant support from training-data volume.
- **Spreadsheet failure modes**: no text-based version control, hidden logic in cell formulas, no scalable diffs, silent overwrite corruption.

## Mental Models
- Think of Python as the *connective tissue* between ideas, data, models, and systems — not an isolated syntax skill.
- Use X when Y: *use code-first workflows when* logic must be audited, reproduced, or automated.
- Use X when Y: *use Python not to ban spreadsheets but* to move critical logic into tested, version-controlled code.

## Anti-patterns
- **Spreadsheet as system of record**: versioning impossible, single overwritten cell invalidates a model silently.
- **Dismissing fluency because "AI writes code"**: you remain accountable for the behavior of the system; generated code must be verified.

## Code Examples
*(Chapter 1 is non-code; motivational.)*

## Key Takeaways
1. Banks are technology firms — code is core infrastructure, not a support function.
2. Python's value = readability + ecosystem + ability to span prototype→production in one stack.
3. LLMs raise the bar for fluency: you must read, critique, and test generated code.
4. Workflows (ingestion → features → model → backtest → reporting) are the book's organizing principle.

## Connects To
- **Ch 2**: how fluency drives GenAI collaboration patterns
- **Ch 3**: the infrastructure (env, shell, notebooks) that makes workflows reproducible
