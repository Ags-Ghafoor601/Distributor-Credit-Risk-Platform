# Step 2 Deliverable: Synthetic Dealer Payment History — Data Schema
Day 1 · skillSYNC AI/ML Sprint · Problem 01

---

## Decision Carried from Step 1
Model outputs **both**: a binary `is_high_risk` label (for training/validation) and a **continuous 300–900 score** (derived from WOE log-odds, for the client-facing scorecard). No rework needed between Day 2 and Day 4 — the scoring formula is designed for this from the start.

---

## Why Synthetic Data, and Why It Must Be Realistic

No client dataset is attached to this brief. The synthetic generator becomes the test bed for Days 2–3, so it must:
1. Mimic the **shape and messiness** of real Pakistani distributor ledgers (transaction-level, not clean).
2. Have **embedded ground truth** — dealers who are *known* good/bad in the simulation — so we can validate the model actually recovers real risk signal instead of noise.
3. Bake in a **"trusted-but-risky" dealer** deliberately vouched for by a salesman, contradicting gut feel — this is the Day 4 demo's money moment.

---

## Entity 1: `salesmen`
One row per salesman. Needed to compute the **salesman-vouch-bias feature** — quantifying the brief's core complaint ("yaar acha banda hai") as data.

| Field | Type | Description |
|---|---|---|
| `salesman_id` | string | Unique ID |
| `salesman_name` | string | Simulated name |
| `territory` | string | Primary operating area (city/zone) |
| `years_experience` | int | Tenure — used to simulate over-confidence bias in senior salesmen |

---

## Entity 2: `dealers`
One row per dealer (retailer/shop). This is the **unit of analysis** locked in Step 1.

| Field | Type | Description |
|---|---|---|
| `dealer_id` | string | Unique ID |
| `dealer_name` | string | Simulated shop name |
| `city` | string | Karachi / Lahore / Rawalpindi / Islamabad / Faisalabad / interior Sindh, etc. |
| `territory_risk_tier` | string | Low / Medium / High — geographic risk clustering |
| `sector` | string | FMCG / Pharma / Textile |
| `salesman_id` | string (FK) | Which salesman manages this dealer |
| `is_salesman_favorite` | bool | Flag: salesman personally vouches heavily for this dealer (used to test if model catches risk gut-feel misses) |
| `credit_limit_pkr` | float | Current nominal credit limit |
| `onboarding_date` | date | When credit relationship began |
| `true_risk_profile` | string (hidden/ground truth) | Reliable / Moderate / Risky — the simulation's underlying truth, used only for validation, never fed to the model |

---

## Entity 3: `transactions` (invoice/payment level — the raw, messy data layer)
One row per invoice — the actual grain a distributor's Excel sheet would have.

| Field | Type | Description |
|---|---|---|
| `transaction_id` | string | Unique ID |
| `dealer_id` | string (FK) | Links to dealer |
| `invoice_date` | date | When goods/credit issued |
| `due_date` | date | Agreed repayment date |
| `payment_date` | date or null | Actual repayment date (null if bounced/unpaid) |
| `amount_pkr` | float | Invoice amount |
| `payment_method` | string | PDC (post-dated cheque) / cash / bank_transfer — **PDC is the dominant and highest-signal method in Pakistani trade credit** |
| `cheque_bounced` | bool | True if PDC bounced — carries more weight than ordinary lateness |
| `days_late` | int | payment_date − due_date (0 if on time, null if unpaid/bounced) |
| `is_eid_ramzan_period` | bool | Whether invoice/due date falls in the seasonal window — needed for seasonally-adjusted lateness |

---

## Derived Layer: `dealer_features` (built in Day 2 from the above)

This is the aggregation Step 1 called for — transaction-grain → dealer-grain. Preview of what Day 2 will compute:

- `bounce_count_6m`, `bounce_rate_lifetime`
- `avg_days_late`, `avg_days_late_seasonally_adjusted`
- `payment_volatility` (std dev of days_late)
- `salesman_favorite_default_rate` (this salesman's historical default rate among *all* dealers they've personally vouched for)
- `territory_avg_risk`
- `real_exposure_pkr` (credit_limit adjusted for PKR inflation since onboarding_date)
- `order_frequency_trend` (business continuity proxy)
- `is_high_risk` (binary label, Step 1 definition)

---

## Embedded Ground-Truth Patterns (for validation + demo narrative)

The generator deliberately embeds:
- **~15% of dealers as "salesman favorites"**, of which a meaningful subset are secretly risky — the model must catch what gut feel missed.
- **Territory risk tiers** with different baseline default rates (not uniform across Pakistan).
- **Eid/Ramzan clustering** — a spike in due dates and a genuine (not just noisy) shift in payment timing around these windows.
- **PKR depreciation** applied to credit limits over the dealer relationship, so "real exposure" diverges from "nominal exposure" for older accounts.

---

*Next: generator script (`generate_data.py`) producing `salesmen.csv`, `dealers.csv`, `transactions.csv` with the above logic, seeded for reproducibility.*
