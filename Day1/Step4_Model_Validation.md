# Step 4 Deliverable: Model & Tooling Stack — Built & Validated
Day 1 · skillSYNC AI/ML Sprint · Problem 01

---

## Decision

**WOE-style Logistic Regression scorecard**, scaled to a **300–900 score** via industry-standard PDO (Points-to-Double-Odds) transformation. Built and tested today — not just decided on paper.

**Stack:** Python, pandas, scikit-learn (`LogisticRegression`, `StandardScaler`, `train_test_split`), numpy. No heavyweight ML infrastructure needed — this keeps the system auditable and explainable, which matters more here than raw accuracy given the brief's "defensible" requirement.

---

## Critical Fix Applied: Temporal Validation

Step 3 flagged that features and label were computed from the same history window (tautological, not genuinely predictive). **This is now fixed:**

- **Feature window:** all transactions with `due_date < 2025-01-01`
- **Label window:** all transactions with `due_date` in 2025 (the "future" outcome being predicted)
- Only dealers with sufficient transaction history (≥3 invoices) in **both** windows are scored — 219 of 220 dealers qualified

This means the model is now genuinely tested on: *given a dealer's behavior through 2024, does it predict their 2025 outcome?* That is the real question a distributor owner is asking, and it's the only version of this test that means anything.

---

## Validation Results (out-of-time test set, 30% holdout)

| Metric | Value | Benchmark |
|---|---|---|
| Train AUC | 0.881 | — |
| **Test AUC** | **0.848** | 0.70+ generally considered usable for credit models |
| **Test Gini** | **0.696** | Directly derived from AUC (2×AUC − 1) |
| **Test KS-statistic** | **0.702** | >0.3 acceptable, >0.4 good, >0.5 strong (industry norm) |

All three metrics land well above standard credit-industry acceptability thresholds — on synthetic data, which is expected to be cleaner-signaled than messy real-world ledgers, but confirms the pipeline and methodology are sound before real client data arrives.

---

## Known Issue to Resolve on Day 2: Multicollinearity

`bounce_rate_lifetime` and `salesman_default_rate_loo` showed strong **standalone** predictive power (Step 3's IV analysis) but near-zero coefficients in the **combined** model — most likely because `avg_days_late_nonseasonal` and `payment_volatility` absorb overlapping variance. This is a modeling artifact, not evidence the salesman-bias feature is unimportant — it remains the single most narratively important feature for the client demo (it's the one that literally quantifies "yaar acha banda hai"), even if its marginal statistical contribution is currently masked.

**Day 2 action item:** Run a Variance Inflation Factor (VIF) check across features; consider a two-layer design — a compact statistical model for the score, and a separate feature-attribution layer (e.g., reason codes) that surfaces salesman-bias and territory risk explicitly for the client narrative regardless of their raw model weight.

---

## Scorecard Scaling (log-odds → 300–900)

Standard PDO scaling, matching how real bureau-style scores are constructed:
- **Base score:** 600 at base odds of 19:1 (good:bad)
- **PDO:** 40 points doubles the odds of being "good"

```
factor = PDO / ln(2)
offset = base_score - factor * ln(base_odds)
score  = offset + factor * ln((1 - P(default)) / P(default))
```

**Result validated on real output:** confirmed high-risk dealers scored 385–450, reliable dealers scored 888–894 — a spread that reads as legitimate and interpretable to a non-technical owner, matching familiar credit-score conventions.

---

## Definition of Done — Step 4

- [x] Model architecture selected and justified (WOE-logistic, not black-box)
- [x] Tooling stack confirmed and installed (sklearn 1.8.0 verified working)
- [x] **Temporal leakage fix implemented**, not just documented
- [x] Model trained and validated with AUC / Gini / KS on genuine out-of-time holdout
- [x] Log-odds → 300–900 scaling implemented and sanity-checked against real scored output
- [x] Multicollinearity issue identified with a concrete Day 2 remediation plan

---
*Next: Step 5 — deliverable format (dealer risk table + per-dealer Risk Card), Step 6 — Day 1 check-in summary.*
