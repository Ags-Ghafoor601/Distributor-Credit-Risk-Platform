# Test Portfolios D, E, F

These probe code paths Sets A/B/C never reached. Upload each set's three files
together. Mind the rate limit — 5 uploads per 10 minutes.

---

## Set D — Zamzam Enterprises

**130 dealers · 7 salesmen · ~3,850 transactions · Apr 2023 – Feb 2026**

Headers: `Dealer Code`, `Dealer Name`, `City`, `Category`, `Salesman Code`,
`Trusted`, `Credit Limit`, `Since`. Mixed date formats, `Rs.`/comma/`/-`
currency, Y/Yes/TRUE/1 booleans, 20 orphan codes, duplicate rows.

**Two firsts here:**

1. **`Trusted` is present** — the first set with a favourites column, so the
   project's signature feature can finally fire. 22 dealers are marked
   trusted, and **6 of them are genuinely risky**. Those are the demo moment:
   accounts the salesman vouches for that the model should flag anyway.
   Watch for the red pulsing callout in the summary bar, the gold ★ badges in
   the table, and the "Marked as a trusted / favorite account" line plus the
   "speak to the salesman" clause in a Risk Card.

2. **12 brand-new dealers with only 1–2 invoices** — Sets A/B/C all reported
   *cold-start 0*, meaning provisional scoring has never actually run on
   uploaded data. Here it will: expect 118 statistically scored and
   **12 cold-start**, shown as "Provisional (Cold-Start)" in the CSV's
   `scoring_method` column, with a Risk Card that says the score is based on
   portfolio averages rather than that dealer's own history.

Expect ~99% retention and a self-trained model around AUC 0.84.

---

## Set E — Al-Rehman Trading (damaged export)

**75 dealers · 4 salesmen · ~2,570 transactions**

Headers: `Account No`, `Business Name`, `Location`, `Rep Code`, `Limit`,
`Start Date`.

Deliberately broken — roughly 40% of rows are unusable, spread across every
failure mode the cleaner handles: blank dealer codes, unparseable dates
(`N/A`, `pending`, `31/02/2024`), negative and parenthesised amounts
(`(45,000)`, `-30000`), ambiguous bounce flags (`maybe`, `?`), due dates
before invoice dates, and orphan account codes.

**Expect ~58% retention** — above the 50% refusal threshold, so it should
score, but the quality report should account honestly for every dropped row
by category. This is the test of whether the app is candid about damaged
input rather than quietly scoring on scraps.

If retention had fallen below 50%, the app should refuse outright with a 422
rather than score on mostly-discarded data.

---

## Set F — Noor Traders (pristine book)

**80 dealers · 4 salesmen · ~2,600 transactions**

Canonical column names, clean formatting, 100% retention. The only unusual
thing is the behaviour: **nobody ever bounces a cheque and nobody pays
materially late.** There is no default behaviour to learn from.

**Expect training to decline** — "outcome classes too imbalanced" — because
every dealer looks identical and good. The interesting question is what the
app does next: it should fall back to the pretrained model and should *not*
manufacture a risk ranking where none exists. A large share of dealers
sitting at the ceiling with a "use ranking, not exact scores" verdict is the
honest answer here.

---

## Verified before delivery

All three were run through the pipeline end to end:

| Set | retention | scoreable | cold-start | training |
|---|---|---|---|---|
| D | 99.1% | 118 | **12** | AUC 0.844 @ 15d |
| E | 57.9% | 75 | 0 | AUC 0.818 @ 15d |
| F | 100% | 80 | 0 | **declined — no defaults to learn from** |
