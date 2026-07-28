# Unified Scoring Pipeline: Cold-Start Wired In, Silent-Drop Bug Fixed
Day 2 · skillSYNC AI/ML Sprint · Problem 01

---

## What This Was Supposed To Fix

Cold-start scoring (`cold_start.py`) existed and worked, but as a standalone script — nothing in the actual scoring pipeline routed a real dealer to it. This closes that gap.

---

## What Was Actually Found While Fixing It

While wiring the routing logic, testing surfaced a **real, previously undetected bug**: every scored output produced so far — `scored_dealers.csv`, `dealer_scores_calibrated.csv`, `dealer_risk_table.csv` — was built via an inner join between feature data and label data. That inner join was doing double duty: it correctly restricted *training* to dealers with a known future outcome, but it also accidentally restricted *scoring* to that same group.

**Concretely:** dealer D0055 has 40+ historical invoices — plenty of feature history — but only 2 invoices fell in the 2025 label-evaluation window, so they got silently dropped from every prior output. Not flagged, not erroring, just absent. **A real distributor would have opened the risk table and one of their dealers simply wouldn't be there**, with nothing to indicate why.

This is architecturally the same class of bug as the pandas NaN-detection issue caught during the messy-data stress test: a correct-looking pipeline silently losing data because two different concerns (training eligibility vs. scoring eligibility) got conflated into one filter.

---

## The Fix: Three Correctly Separated Concerns

1. **Training/validation pool** — dealers with sufficient history in *both* the feature window and the label window (219 dealers). Used only to fit and validate the model.
2. **Scoring pool** — every dealer with sufficient *feature* history gets scored by the trained model, regardless of whether they had enough label-window data to be part of training. In this dataset, that's 220 dealers (219 + D0055).
3. **Cold-start pool** — dealers with insufficient feature history entirely get routed to the rule-based provisional scorer instead of being silently dropped or forced through a statistical model that has no real signal to work with.

Every scored dealer is now tagged with exactly which path produced their score:
- `Statistical (validated in training)` — 219 dealers
- `Statistical (scored, not used in training — thin recent activity)` — 1 dealer (D0055)
- `Provisional (Cold-Start — insufficient history)` — 0 dealers in this dataset (expected; the synthetic generator always gives every dealer 15–60 invoices, so no dealer is genuinely "new" here — this path exists and is tested via `cold_start.py`'s simulation, ready for when a real new dealer appears)

---

## Also Applied: VIF-Remediated Feature Set

This pipeline uses the 6-feature, VIF-clean set (`payment_delay_severity` composite replacing the two collinear features) rather than the original 7 — consistent with the multicollinearity fix. Validation AUC: 0.847, matching the earlier remediation result.

---

## Coverage Proof

| | Before | After |
|---|---|---|
| Dealers in master list | 220 | 220 |
| Dealers appearing in scored output | **219** | **220** |
| D0055 present? | ❌ No — silently absent | ✅ Yes — score 767, GREEN, correctly labeled as unvalidated |

---

## Definition of Done

- [x] Cold-start routing actually wired into the scoring pipeline, not just a standalone script
- [x] Root cause found for a real silent-drop bug affecting every prior scored output
- [x] Training eligibility and scoring eligibility correctly separated as distinct concerns
- [x] Every scored dealer transparently tagged with which method produced their score
- [x] Full 220/220 dealer coverage confirmed
- [x] VIF-remediated feature set carried forward consistently
