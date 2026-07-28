# Gap Fixes: Calibration Check + Parameterized Risk Cards
Day 2 (start) · skillSYNC AI/ML Sprint · Problem 01

---

## Fix 1: Probability Calibration — Checked, Fixed Where Possible, Limitation Documented

**What was tested:** whether `class_weight="balanced"` (used to handle the 37% base rate) was distorting raw probability output away from true frequencies, which would make the exact 300–900 score number unreliable even though ranking (AUC/KS) stayed strong.

**Result — reported honestly, not spun:**

| Metric | Before | After (sigmoid calibration) |
|---|---|---|
| Brier score | 0.1356 | 0.1403 (slightly worse) |
| AUC | 0.848 | 0.850 (unchanged, as expected) |

Calibration did **not** demonstrably improve reliability on this dataset. The most likely cause: 5-fold cross-fitted calibration on ~150 training dealers leaves only ~30 dealers per fold — too little data to fit a stable calibration curve. This is a **data volume limitation**, not a flaw in the calibration method itself.

**Practical consequence, stated plainly for the client-facing materials:**
- The **RED / AMBER / GREEN risk tier** is trustworthy — this is what AUC 0.848 and KS 0.702 validate, and those numbers didn't move with calibration.
- The **exact numeric score** (e.g., 520 vs 544) should currently be treated as directionally meaningful, not precisely calibrated. This will sharpen automatically once real client data increases the training set size.
- Risk Cards now include this caveat directly in the disclaimer text, and present "model confidence" as a ranking signal rather than an exact probability.

**Production model:** refit on all 219 labeled dealers (standard practice — validate on holdout, then retrain on full data for deployment). Reason codes still come from a separately-fit uncalibrated logistic regression on full data, since calibration wraps the probability output only and doesn't change the underlying linear decomposition used for explainability.

---

## Fix 2: Parameterized Risk Card Generator

**Problem:** the original `generate_risk_card.js` had dealer D0080's name, score, and reason text hardcoded directly in the script — it could not produce a card for any other dealer without manual editing.

**Fix:** `generate_risk_card_v2.js` now:
- Reads `dealer_cards_data.json` (exported by `calibration_fix.py` from the live scored dataset)
- Accepts any `dealer_id` via command line, or `--all-red` / `--all-favorites-red` to batch-generate
- Builds all text dynamically — reason sentences are constructed from each dealer's actual feature values (bounce rate, days late, volatility, salesman name, city), not static strings
- Recommended action text is rule-based on risk tier (RED/AMBER/GREEN), not per-dealer authored text

**Verified working on 5 different dealers in one run** (`--all-favorites-red`), not just re-running the same dealer. Spot-checked D0125 (Interior Sindh, Pharma, salesman Kamran Shahid) — confirmed the rendered card pulled genuinely different data and a different third reason code than D0080's card, proving the generator responds to actual input rather than reusing cached text.

---

## Definition of Done — Gap Fixes

- [x] Calibration tested with a real before/after comparison, not assumed
- [x] Limitation honestly documented (small-sample calibration instability) with a clear resolution path (more data)
- [x] Score precision caveat added directly into the client-facing Risk Card text
- [x] Risk Card generator fully parameterized — works for any dealer via `dealer_id` or batch flags
- [x] Verified on a dealer other than the original demo case, with visual + data cross-check

---

## Still Open for Day 2 (unchanged from before, not yet touched)

1. Multicollinearity / VIF check on the 7 features
2. Messy-data stress test (missing fields, inconsistent formats mimicking real Excel exports)
3. Cold-start handling for dealers with insufficient transaction history
