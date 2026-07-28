# Step 5 Deliverable: Output Format — Built & Verified
Day 1 · skillSYNC AI/ML Sprint · Problem 01

---

## Decision

Two-layer deliverable format, matching how a non-technical distributor owner actually consumes information:

1. **Ranked Dealer Risk Table** — the triage view (dashboard-style), sorted worst-to-best
2. **Per-Dealer Risk Card** — a one-page plain-language explainer for any individual dealer, generated on demand

Both are built and verified today, not just specified.

---

## Layer 1: Ranked Dealer Risk Table

Generated from the validated model (Step 4). Every dealer gets: score (300–900), color flag (RED/AMBER/GREEN), and whether they're currently a salesman favorite — so risky-but-trusted dealers are immediately visible without extra filtering.

**Confirmed working — 5 dealers are simultaneously "salesman favorite" AND flagged RED**, including the worst-scored dealer in the entire portfolio (score 385). This is the exact contradiction the brief describes, now reproducible from real (synthetic) data rather than hypothetical.

Full ranked table: `dealer_risk_table.csv`

---

## Layer 2: Per-Dealer Risk Card (sample generated: `D0080_Risk_Card.docx`)

Built for the highest-risk salesman-favorite dealer in the portfolio — Rizwan Malik's trusted account, "Ph-Rawalpindi-0080 Traders" — and rendered/verified as an actual Word document, not just a mockup description.

**Contents:**
- Credit score (385/900) and RED flag, prominently displayed
- Explicit callout that this dealer is currently marked as trusted by the salesman — the contradiction is stated up front, not buried
- **Top 3 plain-language reasons**, derived directly from the model's additive log-odds decomposition (Step 4's coefficient × feature contribution), translated out of statistical language:
  1. Late payment pattern (37.6 days late on average, seasonally adjusted)
  2. Inconsistent/unpredictable payment timing
  3. Elevated territory-wide risk
- A recommended action (no credit increase, consider COD terms, flag for salesman conversation)
- A disclaimer that the score supports — not replaces — human judgment

**Why this reasoning method is defensible:** because the underlying model is a logistic scorecard (not a black box), each dealer's score decomposes additively into per-feature contributions. This is a mathematical property of the model, not a post-hoc explanation bolted on afterward — the reason codes are *exactly* what drove the score, which is what "defensible" requires.

---

## Verification Performed

- Docx rendered to PDF and visually inspected page-by-page (per skill requirement) — confirmed clean layout, correct data, no rendering artifacts
- Reason codes cross-checked against the actual trained model's coefficients — not hardcoded text
- Demo dealer (D0080) confirmed via the ground-truth `true_risk_profile` field to genuinely be "Risky" — so the demo isn't cherry-picked noise, it's the model correctly catching a real bad account gut-feel is protecting

---

## Definition of Done — Step 5

- [x] Ranked dealer risk table generated from live model output
- [x] Per-dealer Risk Card designed and generated as a real, rendered .docx
- [x] Reason codes sourced directly from model internals (additive decomposition), not authored manually
- [x] Demo dealer selected and confirmed against ground truth — ready for Day 4 client walkthrough
- [x] Output visually verified before delivery

---
*Next: Step 6 — Day 1 check-in summary for the project lead.*
