# Chapter 4: Setting Up Your Business

## Core Idea
The infrastructure — brokerage, data, hardware, legal form — is where quiet failures happen; choose for reliability and low cost, and protect capital with investor-protection-aware choices.

## Frameworks Introduced

### Choosing a Brokerage / Prop Firm
- Consider: commissions, data feeds, API quality, margin/leverage, account protection (SIPC/FSCS-like), shorting capability.
- Prop firms vs retail brokerages — trade off capital vs control.

### Physical Infrastructure
- Reliable internet, colocation or low-latency access if intraday; backup connectivity.
- VPS/hosted servers for 24/7 strategy engines; redundancy for the automated stack.

### Investor Protection
- Know your protections (insurance/schemes per jurisdiction); spread accounts across firms if large.

## Key Concepts
- **Prop (proprietary) trading firm**: provides capital, you trade their book.
- **API brokerage**: programmatic order entry (the automation foundation).
- **Latency**: the distance between signal and fill.

## Key Takeaways
1. Pick infrastructure for reliability first; costs second.
2. Data quality (survivorship-free, adjusted) is infrastructure, not an afterthought.
3. Automation demands redundancy — a dead server is a losing strategy.

## Connects To
- **Ch 5**: execution systems run on this infrastructure.
- **Repo**: data skills (stock/fund/block) mirror the "data quality is infrastructure" point.
