# Messy Test Portfolios

Three synthetic distributor portfolios for stress-testing the deployed app.
None of them resemble your Day1 data — different dealers, cities, shop names,
salesmen, column headers, date formats and currency formatting.

Each set probes different code paths deliberately. Upload each set's three
files together at `https://distributor-credit-risk-platform.vercel.app`.

**Note:** your rate limit is 5 uploads per 10 minutes. Space these out or
you'll get a 429 that currently looks like a CORS error.

---

## Set A — Al-Noor Distributors (Karachi FMCG)

**Files:** `setA_alnoor_dealers.csv`, `setA_alnoor_salesmen.csv`, `setA_alnoor_transactions.csv`
**Shape:** 140 dealers, 7 salesmen, ~5,000 transactions spanning Jan 2023 – Feb 2026

A plausible real export. Column headers you have never tested — `Customer Code`,
`Shop Name`, `Area`, `Sales Officer`, `Credit Limit`, `Since`. Transaction
headers are `Invoice No`, `Net Amount`, `Cheque Returned`, `Payment Mode`.

Deliberate messiness: four date formats mixed together including raw Excel
serial numbers, currency as `Rs. 150,000` / `250,000/-` / padded whitespace,
bounce flags as `Y`/`Yes`/`TRUE`/`1`/`N`/`No`/`FALSE`/blank, 24 orphan dealer
codes, duplicate rows, a stray `Remarks` column, inconsistent casing in payment
modes. No `sector`, `territory_risk_tier` or `is_salesman_favorite` at all.

**Expect:** ~99% retention, 140 dealers scored, ~11 substitution notes, the
default 2025-01-01 cutoff (the data straddles it), and a `scores_reliable`
verdict. Payment behaviour is similar to your Day1 data.

---

## Set B — Ravi Wholesale (slow-paying market, recent data)

**Files:** `setB_ravi_dealers.csv`, `setB_ravi_salesmen.csv`, `setB_ravi_transactions.csv`
**Shape:** 90 dealers, 5 salesmen, ~3,100 transactions spanning Jan 2026 – Oct 2027

This is the interesting one. Two things differ fundamentally:

1. **All history sits after the default cutoff.** Before the dynamic-cutoff
   work, every row would have been filtered out and you'd have received
   "no dealers could be scored." The cutoff should now be *derived* as
   2027-10-23.
2. **Different payment culture.** Dealers here average ~44 days late versus
   ~13 in Set A — normal for this market, not misconduct. This is exactly the
   out-of-distribution case the reliability diagnostics exist to catch.

Headers use `Party Code`, `Station`, `Booker`, `Approved Limit`, `Opening Date`.

**Expect:** the cutoff strategy to read *"derived from uploaded data"*, and the
reliability verdict to likely drop to `scores_indicative` or `use_ranking_only`.
If it does, watch whether runtime training engages — 90 dealers over 22 months
clears the 50-dealer and 18-month gates, so it may train a portfolio-specific
model and report its own cross-validated AUC.

---

## Set C — Hilal Agency (tiny portfolio)

**Files:** `setC_hilal_dealers.csv`, `setC_hilal_salesmen.csv`, `setC_hilal_transactions.csv`
**Shape:** 9 dealers, 3 salesmen, 342 transactions

Clean formatting and canonical column names — the only stressor is size.
Before the safe-zscore fix this crashed with an opaque
`Input X contains NaN` 500, because a nine-dealer portfolio has very little
spread to standardise against.

**Expect:** it scores without crashing. Runtime training should correctly
**decline** (9 dealers is far below the 50 minimum) and say so plainly rather
than training a meaningless model on nine rows.

---

## What to check on each

- Does it score at all?
- Expand `details ▼` on the reliability banner — are the column mappings and
  substitutions listed accurately?
- Does the "payment history used" line show the cutoff you'd expect?
- Do the RED-flagged dealers look plausible against the table?
- Download a Risk Card and confirm the dealer name and salesman name are right.

---

## Verified before delivery

All three sets were run through the ingestion → normalization → feature
pipeline. Results: Set A 98.9% retention / 140 scoreable, Set B 98.9% / 90
scoreable with a derived cutoff, Set C 100% / 9 scoreable with all features
finite. Generating these surfaced two real bugs in the app, both fixed —
see the accompanying notes.
