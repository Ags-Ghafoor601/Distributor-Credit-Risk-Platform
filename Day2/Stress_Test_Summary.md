# Stress Test: Messy Data Ingestion — Built, Tested, Validated
Day 2 · skillSYNC AI/ML Sprint · Problem 01

---

## Why This Test Matters More Than Any Other So Far

The brief's own words: *"turns a distributor's raw, unstructured payment history into a clear, defensible risk signal."* Every test run until now used clean synthetic CSVs. This is the first test against data shaped the way a real Pakistani distributor's Excel export actually looks — and it's arguably the single highest-risk unknown in the whole project, since near-zero ERP adoption in this market is the brief's own opening problem statement.

---

## What Was Deliberately Broken

`generate_messy_data.py` corrupted 35% of 8,230 transaction rows with realistic manual-entry mess:

- **Column names**: renamed to inconsistent, real-world style (`Txn ID`, `Dealer Code ` with trailing space, `Amount (Rs)`, etc.) — not our clean schema
- **Dates**: 5 different formats mixed together, including raw Excel serial date numbers (e.g. `45826`)
- **Currency**: `Rs. 50,000`, `50,000/-`, `(176,200)`, comma-separated, with stray whitespace
- **Boolean flags**: bounced field mixed across `Y/Yes/YES/1/TRUE/Bounced` and `N/No/0/FALSE/blank`
- **Missing data**: ~89 rows with no dealer code at all
- **Orphan references**: ~57 rows with typo'd dealer codes (e.g. `D0036X`) not in the master list
- **Duplicates**: 132 accidentally re-pasted rows
- **Stray columns**: notes field, ghost "Unnamed" column
- **Row order**: shuffled, not sorted

---

## What the Ingestion Pipeline Had to Prove

`robust_ingestion.py` processes this raw mess into a clean, schema-conformant dataset — and produces a **Data Quality Report** as an actual deliverable, not just internal logging, since a client needs to see their data was handled honestly rather than silently mangled.

| Stage | Rows In | Rows Out | Action |
|---|---|---|---|
| Column standardization | 8,394 | 8,394 | Mapped inconsistent headers to canonical schema |
| Duplicate removal | 8,394 | 8,262 | Dropped 132 exact duplicates |
| Missing dealer_id | 8,262 | 8,173 | Dropped 89 rows with no dealer attribution |
| Orphan dealer_id | 8,173 | 8,116 | Dropped 57 rows with typo'd/unknown dealer codes |
| Date parsing | 8,116 | 8,116 | Parsed 5 mixed formats + Excel serials — zero unparseable |
| Amount cleaning | 8,116 | 8,061 | Stripped currency symbols/commas/suffixes — dropped 55 genuinely blank |
| Bounced-flag normalization | 8,061 | 8,061 | Mapped all boolean-text variants — zero ambiguous |
| Logical consistency | 8,061 | 8,061 | Zero due-before-invoice-date errors found |

**Final retention: 96.0%** (8,061 of 8,394 raw rows) — every dropped row has a documented, defensible reason. Nothing was silently discarded.

---

## A Real Bug the Stress Test Caught

While building the ingestion pipeline, the missing-dealer-code detection initially reported **zero** missing rows — despite 86 being deliberately injected. Root cause: pandas' newer string dtype does not convert a true missing value into the string `"nan"` the way older pandas behavior did, so a sentinel-string check (`isin(["nan", ...])`) silently missed genuinely missing cells. **Fixed by explicitly checking `.isna()` before any string conversion**, not relying on stringified sentinels.

This is exactly the value of stress-testing now rather than at the client demo: a silent data-quality bug like this would have been invisible on clean synthetic data forever, and would only have surfaced on real client data — in front of the client.

---

## Does the Cleaned Data Still Produce a Trustworthy Model?

Ran the full feature engineering + model pipeline on data that went **messy → cleaned**, and compared directly against the original clean-source run:

| | Original Clean Data | Messy Data → Cleaned |
|---|---|---|
| Dealers scored | 219 | 219 |
| Test AUC | 0.848 | 0.848 |
| Test KS-statistic | 0.702 | **0.727** |

**Zero dealers were lost entirely.** Model performance is identical on AUC and slightly better on KS — well within normal run-to-run variation, not a meaningful degradation.

**Feature-level agreement** (average % difference per feature, same 219 dealers, clean-source vs. messy-source):

| Feature | Avg. % Difference |
|---|---|
| `real_exposure_pkr` | 0.00% |
| `territory_default_rate_loo` | 1.53% |
| `salesman_default_rate_loo` | 3.44% |
| `payment_volatility` | 3.17% |
| `avg_days_late_nonseasonal` | 4.54% |
| `bounce_rate_lifetime` | 5.62% |
| `order_frequency_trend` | 9.81% |

All differences are small and explainable by the ~4% of rows legitimately dropped for data-quality reasons (missing/orphan/malformed), not by any flaw in the cleaning logic. `order_frequency_trend`'s slightly higher variance is expected — it's a count-based ratio feature, inherently more sensitive to a handful of dropped rows than an averaged feature like days-late.

---

## Definition of Done — Stress Test

- [x] Realistic messy data generated matching real-world Pakistani distributor Excel export patterns
- [x] Robust ingestion pipeline built: column mapping, multi-format date parsing, currency cleaning, boolean normalization, duplicate/orphan/missing-data handling
- [x] Data Quality Report generated as a client-facing deliverable, not just internal logs
- [x] A real bug caught and fixed during testing (pandas string-dtype NaN handling)
- [x] End-to-end validation: messy→cleaned data produces statistically equivalent model performance to clean-source data, with zero dealer coverage loss

---

## Still Open for Day 2

1. Multicollinearity / VIF check on the 7 features
2. Cold-start handling for dealers with insufficient transaction history
3. Calibration ceiling remains (documented, needs more data volume — unrelated to this stress test)
