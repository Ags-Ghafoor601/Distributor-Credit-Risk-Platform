# Cold-Start Handling: New/Low-History Dealers
Day 2 · skillSYNC AI/ML Sprint · Problem 01

---

## The Gap Being Closed

The statistical model needs ≥3 invoices of trailing history to compute payment-behavior features. In synthetic data this affected only 1 of 220 dealers — invisible. In a real distributor actively onboarding new dealers every month, this will be a routine, recurring situation, not an edge case. Without a defined fallback, every newly onboarded dealer would simply be unscoreable, which defeats the point of the system for exactly the moment a credit decision is riskiest (a brand-new relationship, no track record).

---

## The Approach: Provisional Rule-Based Score, No Payment History Required

Uses only information available **at the moment of onboarding**:

1. **Salesman track record** — the assigned salesman's average bounce rate across their *entire existing portfolio* (excludes the new dealer, since they have no history yet). This is the one meaningful signal available on day one — literally "does this salesman have a track record of vouching for people who default."
2. **Territory baseline risk** — average bounce rate across all dealers in the same geographic risk tier.
3. **Sector baseline risk** — average bounce rate across all dealers in the same sector (FMCG/Pharma/Textile).

Blended: `0.5 × salesman_rate + 0.3 × territory_rate + 0.2 × sector_rate` — salesman weighted highest since it's the most direct available proxy for who's vouching for this specific dealer.

**Deliberately compressed score range (480–680, not the full 300–900):** this is intentional, not a bug. A provisional score built from zero dealer-specific data should never claim the same confidence as the full statistical model — no cold-start dealer should ever show as GREEN (Reliable) or deep RED, because that certainty hasn't been earned yet. Every cold-start dealer is tagged **AMBER (Provisional)**, split into "Standard" or "Elevated Caution" — never a full RED/GREEN verdict.

**Starter credit limit:** flat conservative cap (PKR 100,000) regardless of what's requested, until the dealer graduates.

---

## Graduation Path

A dealer moves from provisional scoring to the full statistical model once **either**:
- 3 invoices of trailing history accumulate (matches the statistical model's minimum), **or**
- 3 months have passed since onboarding

whichever comes first. This should be an automatic transition in the actual system, not a manual review trigger.

---

## Test Results — Honest Read

Simulated 15 dealers as if they were brand-new (using only their onboarding-time attributes, ignoring their actual transaction history), and checked whether the provisional score's direction matched their (hidden) true risk profile:

- Scores properly spread across the full 519–680 provisional band once the scaling was corrected (an initial version clustered everyone in a useless 633–655 band — caught and fixed before shipping)
- **Correlation between provisional score and true risk: -0.579** (correctly signed — lower score for higher risk)

**What this number honestly means:** directionally useful at the *portfolio* level (a batch of new dealers assigned to a risky salesman in a risky territory will, on average, score lower and deserve more caution) — but **not** a reliable predictor of any *individual* dealer's specific behavior, since none of their own payment history exists yet. This mirrors exactly how real credit bureaus handle thin-file/new customers: start conservative using demographic/proxy signals, then update fast once real behavior data arrives. The system should not oversell what a zero-history dealer's provisional score can promise — and the client-facing framing should say this explicitly, not imply the provisional score is as trustworthy as a fully-scored dealer's.

---

## Definition of Done

- [x] Rule-based provisional scoring built using only onboarding-time information
- [x] Deliberately compressed score range and forced AMBER-only tier (no false RED/GREEN confidence)
- [x] Conservative starter credit limit cap defined
- [x] Explicit graduation criteria to the full statistical model
- [x] Tested against 15 simulated new dealers, scaling bug caught and fixed
- [x] Honest documentation of what the provisional score can and cannot promise
