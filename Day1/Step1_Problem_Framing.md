# Problem 01: Distributor Credit Risk — Step 1 Deliverable
**Problem Framing & ML Approach Definition**
Day 1 · skillSYNC AI/ML Sprint

---

## 1. Problem Statement (ML framing)

Distributors across Pakistan extend trade credit to hundreds of retailers/dealers based on a salesman's personal judgment, with no structured scoring at any stage. This project replaces that judgment with a **defensible, dealer-level credit risk score** derived from the distributor's own historical payment behavior — surfacing risk the owner currently cannot see, including in dealers they personally trust.

The system must work on the kind of data Pakistani mid-tier distributors actually keep: scattered Excel sheets or ledger exports, not clean ERP records.

---

## 2. Target Variable

**`is_high_risk`** (binary, dealer-level)

A dealer is flagged `1` if, over their trailing payment history:
- **(a)** Any cheque/payment bounce occurred in the trailing 6 months, **OR**
- **(b)** Average days-late across their last N invoices exceeds a defined threshold (default: 15 days)

**Why binary first:** Keeps Day 2–3 build tractable. A continuous **300–900 scorecard score** (mirroring familiar credit-score ranges) will be layered on top of the underlying model probability once the classifier is running — giving both a simple flag for quick triage and a graded score for nuanced credit-limit decisions.

---

## 3. Unit of Analysis

**One row per dealer** — not per transaction.

Raw data lives at invoice/transaction grain (individual payments, cheques, due dates). The model must aggregate this up to dealer grain, since business owners think in terms of "is this dealer risky," not individual transactions. This aggregation logic (transaction-level → dealer-level features) is the core data engineering task for Step 2.

---

## 4. Business KPI Mapping

This table is the direct link between the brief's stated cost-of-inaction and what the model delivers — it is the backbone of the Day 4 client narrative.

| Brief's Stated Cost | How the Model Moves It |
|---|---|
| **3–7% bad debt rate** | Flagging high-risk dealers before credit is extended (or renewed) reduces the proportion of total exposure that eventually defaults |
| **PKR 1M+ annual write-offs** | Capping or reducing credit limits on flagged dealers shrinks the PKR amount at risk per bad account |
| **100 hrs/month chase calls** | Smaller credit extended to risky dealers means smaller overdue balances to chase; reason codes tell staff *which* dealers need proactive follow-up instead of blanket chasing every account |

---

## 5. Differentiation Principle (carried from planning discussion)

The model must be **defensible** (brief's own word) and **Pakistan-specific**, not a generic scoring demo. This is achieved via:
- A **Weight-of-Evidence (WOE) logistic scorecard** methodology (transparent, point-based, industry-standard for credit — not a black-box classifier)
- Locally-grounded features: post-dated cheque (PDC) bounce behavior, Eid/Ramzan seasonal payment adjustment, salesman-vouch bias tracking, territory risk clustering, inflation-adjusted real exposure, business continuity proxy

Full feature/bin definitions are the subject of Step 3.

---

## 6. Definition of Done — Step 1

- [x] Target variable defined and justified
- [x] Unit of analysis defined
- [x] Business KPI mapping completed
- [x] Differentiation principle stated
- [ ] **Open decision for lead check-in:** confirm binary-first approach vs. building the 300–900 scorecard range directly in Day 1

---
*Next: Step 2 — Synthetic dealer payment history dataset schema, including Eid seasonality and salesman-bias simulation.*
