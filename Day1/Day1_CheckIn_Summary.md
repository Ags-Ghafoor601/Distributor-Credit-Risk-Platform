# Day 1 Check-In Summary
Problem 01: Distributor Credit Risk on Gut Feel · skillSYNC AI/ML Sprint

---

## One-Paragraph Summary

Built and validated a working credit-risk scoring pipeline for Pakistani FMCG/Pharma/Textile distributors, from synthetic data generation through a trained, tested model to client-facing output — not just a plan. The system replaces salesman gut-feel with a transparent WOE-logistic scorecard (score range 300–900), embedding Pakistan-specific behavioral signals (post-dated cheque bounces, Eid/Ramzan seasonality, salesman-vouch bias, territory risk, PKR-adjusted exposure). Validated out-of-time (temporally correct, not leaked) with Test AUC 0.848 and KS-statistic 0.702 — both well above credit-industry acceptability thresholds. A real demo scenario is confirmed: 5 dealers are simultaneously salesman-favorites and flagged high-risk, including the single worst-scored dealer in the portfolio.

---

## What Was Built (all 6 steps completed)

| Step | Deliverable | Status |
|---|---|---|
| 1 | Problem framing — target variable, unit of analysis, KPI mapping | ✅ Complete |
| 2 | Synthetic data generator — 220 dealers, 8 salesmen, 8,230 transactions, seeded/reproducible | ✅ Complete, validated |
| 3 | Feature engineering + WOE/IV analysis — 7 candidate features scored | ✅ Complete; caught and documented a label-leakage risk |
| 4 | Model build — logistic scorecard with corrected temporal split | ✅ Complete; AUC 0.848, KS 0.702 |
| 5 | Deliverable format — ranked risk table + verified sample Risk Card (.docx) | ✅ Complete, rendered and visually checked |
| 6 | This check-in summary | ✅ Complete |

---

## Key Technical Decisions

- **Model:** WOE-style logistic regression scorecard, not a black-box classifier — chosen specifically because the brief requires a "defensible" score an owner can trust over gut feel. Scores decompose additively into plain-language reason codes as a mathematical property of the model, not a bolted-on explanation.
- **Differentiation:** Every feature beyond raw payment history is Pakistan-specific — post-dated cheque bounce behavior (not generic "late payment"), Eid/Ramzan seasonally-adjusted lateness, salesman-vouch bias quantified as a leave-one-out feature, and territory risk clustering. This is deliberately not a generic scoring template.
- **Methodological rigor:** Initial feature/label design had same-window leakage (caught via suspiciously high IV scores on two features). Fixed before modeling began — final validation is genuinely out-of-time (features from pre-2025 history predicting 2025 outcomes), which is the only version of this test that means anything to a client.

---

## Known Limitations / Open Items for Day 2

1. **Multicollinearity** between `avg_days_late_nonseasonal`, `payment_volatility`, and other features masks some individual feature coefficients in the combined model despite strong standalone signal (esp. salesman-vouch-bias). Needs a VIF check and possibly a two-layer design (compact statistical model + separate feature-attribution layer for the client narrative).
2. **Synthetic data ceiling:** current AUC/KS reflect clean synthetic generation; real client data (messy Excel exports) will likely show more noise. Day 2–3 should stress-test the pipeline against deliberately messier synthetic data (missing fields, inconsistent formats) before assuming these numbers hold.
3. **Dealers with insufficient history** (< 3 invoices in either window) currently can't be scored — only 1 of 220 dealers hit this in synthetic data, but real new-dealer onboarding may hit this more often. Needs a fallback approach (e.g., a simpler onboarding-stage rule set) for Day 3.

---

## Files Delivered Today

- `Step1_Problem_Framing.md`
- `Step2_Data_Schema.md`, `generate_data.py`, `salesmen.csv`, `dealers.csv`, `transactions.csv`
- `Step3_Features_WOE_IV.md`, `feature_engineering.py`, `dealer_features.csv`, `iv_summary.csv`
- `Step4_Model_Validation.md`, `model_build.py`, `scored_dealers.csv`
- `Step5_Deliverable_Format.md`, `reason_codes.py`, `generate_risk_card.js`, `dealer_risk_table.csv`, `dealer_scores_with_reasons.csv`, `D0080_Risk_Card.docx`
- This summary

---

## Requesting Lead Sign-Off On

1. Confirm the binary-label-with-300–900-score approach (vs. simplifying to flag-only) — currently proceeding with both.
2. Confirm scope for Day 2: should multicollinearity/VIF cleanup happen before or after building out the messy-data stress test?
3. Any real client data available yet, or should Day 2–3 continue on enhanced synthetic data?
