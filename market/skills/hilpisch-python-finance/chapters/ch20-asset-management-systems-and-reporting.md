# Chapter 20: Asset Management Systems and Reporting

## Core Idea
Reporting is the interface to stakeholders: from raw data to narrative, with core reports (holdings/exposures, performance/risk dashboards, compliance monitoring), backed by a data pipeline (ingest → validate → analytics → store), orchestration, performance attribution, and governance/auditability.

## Frameworks Introduced
- **Stakeholder-driven reporting cadence**: different stakeholders (CIO, risk, compliance, clients) need different reports at different frequencies — map reports to needs.
- **Core report suite**: holdings & exposure reports; performance & risk dashboards; compliance & constraint monitoring (limits breached?).
- **Data pipeline architecture**: ingest (validate/clean) → run analytics → store results → schedule/orchestrate (cron, schedulers) → failure handling (retries, alerts).
- **Performance attribution**: decompose returns by asset, sector, and factor; link attribution back to research and implementation (where did performance come from?).
- **Governance/auditability**: configuration, code, and data lineage; controls, approvals, documentation — reproduce any number on demand.

## Key Concepts
- **Narrative layer**: reports should tell a story (raw numbers → insight), not just dump tables.
- **Feedback loop**: attribution results feed research/implementation improvements.
- **Lineage**: know which code+data produced each number (reproducibility contract).

## Mental Models
- Use X when Y: *dashboards when* monitoring ongoing status; *attribution when* explaining performance; *scheduled pipelines when* recurring computation.
- Think of a report as *a question answered for a stakeholder*, with a reproducible path to the answer.

## Anti-patterns
- **Dashboards without narrative** — numbers without interpretation.
- **Undocumented pipelines** — no lineage, no reproducibility, audit failure.
- **Ignoring failure handling** — scheduled jobs must retry/alert.
- **Attribution without linking to decisions** — numbers that don't inform action.

## Code Examples
*(Chapter 20 is systems-architecture heavy; concrete implementation in ch21.)*

## Reference Tables
| Report type | Audience | Cadence |
|---|---|---|
| Holdings/exposures | CIO, portfolio mgr | daily/weekly |
| Performance & risk | CIO, clients | monthly |
| Compliance monitoring | risk/compliance | continuous/daily |
| Attribution | portfolio mgr, research | monthly/quarterly |

## Worked Example
Monthly client report pipeline: ingest validated prices → run portfolio analytics (returns, risk, attribution) → store results (CSV/SQLite/HDF5) → generate report (tables + narrative) → schedule monthly; on failure, alert and retry. Every number traceable to code+data (lineage log).

## Key Takeaways
1. Reports = interface to stakeholders — cadence and content by audience.
2. Pipeline: ingest → validate → analytics → store → schedule → handle failures.
3. Attribution explains performance by asset/sector/factor and feeds decisions.
4. Governance: lineage, controls, approvals — reproducibility is a requirement.

## Connects To
- **Ch 10**: storage backends (SQLite/HDF5) for results
- **Ch 21**: assetlib.reporting implements the report suite
- **Ch 22-26**: trading systems extend these pipelines
