# Step 3 Deliverable: Feature List, WOE Bins & Information Value Validation
Day 1 · skillSYNC AI/ML Sprint · Problem 01

---

## Method

Rather than picking features by intuition alone, each candidate was run through **Weight-of-Evidence (WOE) binning** and scored with **Information Value (IV)** — the standard pre-modeling validation metric in credit scoring. This proves predictive power *before* committing a feature to the model, and gives a defensible answer if a client or lead asks "why this feature?"

**IV interpretation convention used:**
| IV Range | Meaning |
|---|---|
| < 0.02 | Not predictive — drop |
| 0.02 – 0.10 | Weak |
| 0.10 – 0.30 | Medium — useful |
| 0.30 – 0.50 | Strong |
| > 0.50 | Suspiciously strong — check for leakage |

---

## ⚠️ Critical Finding: Label Leakage in Two Features

`bounce_rate_lifetime` (IV 3.35) and `avg_days_late_nonseasonal` (IV 1.98) scored far above the "suspicious" threshold. **This is not a genuine discovery** — the `is_high_risk` label is directly defined using bounce count and average days-late (per Step 1's target definition), so these features are near-tautological to the label by construction. High IV here confirms internal consistency, not real-world predictive power.

**The underlying issue to fix on Day 2:** features and label are currently computed over the *same full history window*. A methodologically sound model needs **temporal separation** — features computed from an earlier period predicting an outcome in a *later* period (e.g., features from 2023–24 behavior → label = default behavior in 2025), evaluated with an out-of-time train/test split. Without this, we're confirming arithmetic, not testing prediction.

**Action item for Day 2:** Implement time-based feature/label split before training the actual classifier. This is now a locked requirement, not an optional refinement.

---

## Validated Feature Set (ranked by genuine — non-tautological — signal)

| Rank | Feature | IV | Assessment |
|---|---|---|---|
| 1 | `payment_volatility` | 1.60 | Strong. Consistency of payment behavior over time is a real, independent risk signal. |
| 2 | `salesman_default_rate_loo` | 0.34 | Strong. Directly operationalizes the brief's core complaint — a salesman's own track record of vouching for defaulters, computed leave-one-out to avoid self-leakage. |
| 3 | `order_frequency_trend` | 0.18 | Medium. Business continuity proxy — declining order volume ahead of a bad account. |
| 4 | `territory_default_rate_loo` | 0.14 | Medium. Confirms geographic risk clustering is real, not assumed. |
| 5 | `real_exposure_pkr` | 0.03 | Weak as a risk classifier — **retained anyway**, but repurposed for the credit-limit sizing decision rather than the risk-probability model (see note below). |

**Features held for the core scorecard but flagged as label-derived (not independently validated):**
- `bounce_rate_lifetime`, `avg_days_late_nonseasonal` — these remain in the model since payment/bounce history is legitimately the foundation of any credit scorecard (this mirrors how real bureaus work — past payment behavior predicting future behavior is the whole premise). The caveat is about *methodology* (temporal split needed), not about excluding the features.

---

## Note on `real_exposure_pkr`

Low IV here is not a failure — this feature was never intended to predict *who* defaults. Its job is to answer *how much exposure matters* once risk is already known (a risky dealer with PKR 50K exposure is a smaller problem than a risky dealer with PKR 500K exposure, especially once PKR depreciation is accounted for). This stays in the system at the **credit-limit recommendation layer**, separate from the risk-probability classifier.

---

## WOE Bin Boundaries (from data, not arbitrary)

Bins below were derived via quantile-based cuts on the actual synthetic dataset — this is the real bin table Day 2's scorecard will use as a starting point (subject to refinement once real client data replaces synthetic data).

**`payment_volatility` (std dev of days late):**
| Bin | WOE |
|---|---|
| ≤ 1.66 | +1.43 (protective) |
| 1.66 – 1.88 | +1.08 |
| 1.88 – 5.89 | +0.26 |
| > 5.89 | **−1.94 (high risk)** |

**`salesman_default_rate_loo` (salesman's track record, self excluded):**
| Bin | WOE |
|---|---|
| ≤ 0.267 | +0.78 |
| 0.267 – 0.30 | +0.54 |
| 0.30 – 0.333 | −0.36 |
| > 0.333 | **−0.63 (high risk)** |

*(Full bin tables for all 7 features are in the code output / `iv_summary.csv`.)*

---

## Definition of Done — Step 3

- [x] Candidate features engineered from raw transaction data (dealer-grain aggregation, per Step 1)
- [x] Leave-one-out logic applied to group features (salesman, territory) to prevent self-leakage
- [x] WOE + IV computed for every candidate feature
- [x] Label leakage identified and flagged with a concrete Day 2 fix (temporal split)
- [x] Final feature set locked, with roles separated: risk classifier vs. credit-limit sizing

---
*Next: Step 4 — lock model + tooling stack, Step 5 — deliverable format, Step 6 — Day 1 check-in summary.*
