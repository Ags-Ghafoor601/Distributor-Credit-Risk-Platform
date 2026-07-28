# CHANGELOG
Problem 01: Distributor Credit Risk on Gut Feel · skillSYNC AI/ML Sprint

This documents what changed at each stage, so the Day1/Day2/Day3 folder
split reflects a real version history rather than duplicated files. Written
against the actual code, not from memory — see "Verification" note at the
bottom of each entry where relevant.

---

## Day 1 — Foundation

**Steps 1–6 completed:** problem framing, synthetic data generator (`generate_data.py`
→ 220 dealers, 8,230 transactions), feature engineering + WOE/IV validation
(`feature_engineering.py`), first model with temporal-leakage fix (`model_build.py`
→ AUC 0.848, KS 0.702), reason-code generation (`reason_codes.py`), first Risk Card
(`generate_risk_card.js` — hardcoded to a single demo dealer, D0080), and a Day 1
check-in summary.

**Known limitations at end of Day 1:** Risk Card generator not reusable; probability
calibration unverified; no test against messy/unstructured data; multicollinearity
unchecked; no cold-start handling.

---

## Day 2 — Gap Fixes, Stress Testing, Diagnostics

### Gap Fixes (`calibration_fix.py`, `generate_risk_card_v2.js` — first version)
- Tested probability calibration (sigmoid/Platt) — found it did **not** improve
  Brier score (0.1356 → 0.1403) on this dataset size; documented as a genuine,
  unresolved limitation rather than forcing a claim of success.
- Parameterized the Risk Card generator: `generate_risk_card_v2.js` reads dealer
  data from `dealer_cards_data.json` and accepts any `dealer_id` or batch flags
  (`--all-red`, `--all-favorites-red`), replacing the hardcoded single-dealer script.

### Stress Test (`generate_messy_data.py`, `robust_ingestion.py`, `stress_test_validation.py`)
- Built a realistic messy-data generator (mixed date formats, currency strings,
  boolean encodings, missing/orphan dealer codes, duplicates).
- Built an ingestion pipeline that cleaned it back to 96% retention, zero dealers
  lost, model performance held (AUC unchanged, KS improved slightly).
- **Caught a real bug:** pandas' string dtype doesn't stringify NaN to `"nan"`,
  causing a missing-value check to silently miss real gaps. Fixed by checking
  `.isna()` explicitly rather than relying on string sentinels.

### VIF Check (`vif_check.py`)
- Found severe collinearity (VIF 11.08 and 9.26, correlation 0.94) between
  `payment_volatility` and `avg_days_late_nonseasonal`.
- Remediated by combining them into a single composite feature,
  `payment_delay_severity`. All VIF dropped below 2.5; AUC/KS held (0.848→0.847,
  0.702→0.702).
- **Corrected an earlier claim:** Step 4 had blamed `salesman_default_rate_loo`'s
  weak coefficient on multicollinearity. VIF proved that wrong (VIF 1.02) —
  the true cause is weak marginal contribution under L2 regularization, not
  collinearity.

### Cold-Start (`cold_start.py`)
- Built a rule-based provisional scorer for dealers with insufficient transaction
  history, using only onboarding-time data (salesman/territory/sector averages).
- Deliberately compressed score range (480–680) and AMBER-only tier — never
  claims full RED/GREEN confidence without real payment history.
- Tested on 15 simulated new dealers; caught and fixed a scaling bug (initial
  version clustered all scores in a useless 633–655 band); final correlation
  with true risk: -0.579 (correctly directional, honestly reported as
  portfolio-level signal, not individual-level precision).

**Known limitation at end of Day 2:** cold-start logic existed only as a
standalone script — nothing in the actual scoring pipeline routed a real
dealer to it, and it wasn't connected to Risk Card generation.

---

## Day 3 — Unified Pipeline (two versions, both preserved)

### Version 1 (`Day2/unified_scoring_pipeline.py`) — Coverage fix
- Wired cold-start into the scoring flow: dealers now route automatically to
  either the statistical model or the provisional scorer based on history depth.
- **Found and fixed a real bug in the process:** every scored output produced
  before this point (`scored_dealers.csv`, `dealer_scores_calibrated.csv`,
  `dealer_risk_table.csv`) had silently excluded dealer **D0055** — not
  because they lacked feature history (they had 40+ invoices), but because
  an inner join conflated "usable for training" with "eligible to be scored."
  D0055 had two invoices in the 2025 label window — enough to disqualify them
  from training, not enough to disqualify them from being scored.
- Fixed by separating the two concerns: training pool (219 dealers, both
  windows sufficient) vs. scoring pool (all 220 with sufficient feature
  history) vs. cold-start pool (dealers with insufficient feature history
  entirely — zero in this dataset, but the path is tested and ready).
- Also switched the feature set to the VIF-remediated 6 features
  (`payment_delay_severity` composite) from the original collinear 7.
- Output at this stage: `dealer_risk_table_unified.csv` covering 220/220
  dealers — but **no reason codes yet**, and no JSON export for Risk Cards.

### Version 2 (`Day3/unified_scoring_pipeline.py`) — Reason codes + Risk Card integration
- Extended the same script (in place) to add:
  - `REASON_LABELS` dictionary mapping the 6 VIF-clean features to
    plain-language factor names (line 193)
  - Per-dealer additive log-odds decomposition via `top_reasons()` (line 205),
    using `contributions = X_score_all_s * prod_model.coef_[0]` (line 202) —
    the same explainability method used since Step 5, now correctly matched
    to the 6-feature model instead of the old 7-feature one
  - Full field export (`full_cols`, line 273) including salesman names,
    credit limits, and raw feature values needed for Risk Card text
  - JSON export to `dealer_cards_data.json` (line 287) so
    `generate_risk_card_v2.js` can generate a card for **any** dealer,
    including D0055 — impossible before this version
- Updated `generate_risk_card_v2.js`'s reason-sentence mapping to match the
  new composite feature label (`"Late and inconsistent payment timing"`)
  instead of the old two-feature phrasing, plus a clean fallback for the
  cold-start explanation text style.
- **Proof this works:** generated and visually verified `D0055_Risk_Card.docx`
  — the first Risk Card ever produced for this dealer, correctly showing
  score 767 (GREEN), Interior Sindh, Textile, salesman Aamir Sohail, and
  three genuine reason codes from the retrained model.

**Verification note:** the presence of `REASON_LABELS` and `top_reasons()`
was confirmed directly against the live file content (grep on lines 193–210)
before writing this entry — not reconstructed from memory alone.

---

## Current State (end of this changelog)

| Dimension | Status |
|---|---|
| Feature coverage (6 Pakistan-specific features) | ✅ Complete |
| Temporal leakage | ✅ Fixed |
| Messy/unstructured data | ✅ Stress-tested, 96% retention |
| Multicollinearity | ✅ Fixed, re-validated |
| Cold-start | ✅ Built and wired into production scoring |
| Full dealer coverage | ✅ Fixed (220/220, was 219/220) |
| Calibration | ⚠️ Tested; genuine limitation remains, needs more data volume |

**Still open, not yet started:**
- No persisted model artifact — every script retrains from scratch
- Single train/test split — no k-fold cross-validation on the headline AUC/KS numbers
- Day 3–4 of the *original 4-day brief* (client-walkthrough polish, running
  reliably at scale without manual intervention) — not yet formally started

---

## Day 3 (continued) — Cross-Validation, Model Persistence, Pipeline Orchestration, Day 4 Prep

- Built `cross_validation.py`: 5-fold stratified CV revealed the true performance
  range (AUC 0.860 ± 0.098, range 0.763–0.989) — the single-split AUC 0.848 from
  earlier wasn't wrong, but presenting it without the range would have overstated
  precision. This range is now the number to quote, not the single decimal.
- Built `train_and_save_model.py` + `score_dealers.py`: model trains once,
  persists via joblib, and scoring loads the artifact with zero retraining —
  verified by grepping for `.fit(` calls in the scoring script (none found).
- Built `run_pipeline.py`: single-command orchestration (ingest → score → export
  → generate Risk Cards), satisfying the original brief's Day 3 requirement to
  run reliably without manual intervention. Tested against clean data, messy
  data, and two deliberate failure cases (missing file, missing model) — all
  handled with clear errors and non-zero exit codes.
- Built the Day 4 client presentation deck (`build_presentation.js`).

### Bug found and fixed: D0080 score discrepancy (425 vs 418)

While building the presentation, a manually-read figure (425) was used for
dealer D0080's score. The person cross-checked this against the actual
generated Risk Card docx and found it said 418 — catching a real inconsistency
before it reached a client.

**Investigation:** re-ran `unified_scoring_pipeline.py`, `score_dealers.py`, and
`run_pipeline.py` fresh, all three independently produced **418** with identical
underlying feature values. Conclusion: the 425 was a one-off misread when
building the slide, not a genuine divergence between pipelines at that time.

**The real risk this exposed:** three separate scripts independently
re-implementing the same feature engineering logic is inherently fragile —
they happened to agree this time, but nothing prevented future drift.
**Decision:** `train_and_save_model.py` + `score_dealers.py` + `run_pipeline.py`
(the persisted-model architecture) is now the single canonical scoring
pipeline. `unified_scoring_pipeline.py` is deprecated and kept only for
historical reference (see deprecation notice at the top of that file).

Presentation corrected: D0080 → 418 (was 425), portfolio split → 178 GREEN /
36 RED / 6 AMBER (was 179/36/5 — one dealer sits near the tier boundary,
sensitive to floating-point precision between runs).
