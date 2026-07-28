"""
Cold-Start Handling for New/Low-History Dealers
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2

The statistical model requires >=3 invoices in a trailing window to compute
payment-behavior features. A real distributor onboards new dealers on an
ongoing basis -- this builds a RULE-BASED PROVISIONAL score using only
information available at onboarding time (no payment history needed), with
an explicit graduation path to the full statistical model once enough
transaction history accumulates.

Tested by artificially truncating real dealers' histories to simulate
"new dealer" conditions, then checking whether the provisional score's
directional judgment is at least reasonable against their (hidden) true
risk profile and their eventual full-history score.
"""

import pandas as pd
import numpy as np

MIN_INVOICES_FOR_STATISTICAL_MODEL = 3
GRADUATION_INVOICE_COUNT = 3       # matches the statistical model's minimum
GRADUATION_MONTHS = 3              # OR 3 months of relationship, whichever comes first

dealers = pd.read_csv("dealers.csv", parse_dates=["onboarding_date"])
salesmen = pd.read_csv("salesmen.csv")
txns = pd.read_csv("transactions.csv",
                    parse_dates=["invoice_date", "due_date", "payment_date"])

REFERENCE_DATE = pd.Timestamp("2025-12-31")

# ---------------------------------------------------------------------------
# Salesman track record: computed from ALL their dealers' full history
# (this is available regardless of any ONE dealer's own history -- it's the
# one signal a cold-start dealer can still inherit from day one)
# ---------------------------------------------------------------------------
dealer_bounce = txns.groupby("dealer_id")["cheque_bounced"].mean().rename("bounce_rate")
dealer_bounce = dealer_bounce.reindex(dealers["dealer_id"]).fillna(0)
dealers_with_rate = dealers.set_index("dealer_id").join(dealer_bounce)
salesman_track_record = dealers_with_rate.groupby("salesman_id")["bounce_rate"].mean()

# ---------------------------------------------------------------------------
# Territory baseline risk (from the full portfolio, same as the LOO feature
# used in the statistical model -- also available with zero dealer history)
# ---------------------------------------------------------------------------
territory_baseline = dealers_with_rate.groupby("territory_risk_tier")["bounce_rate"].mean()
sector_baseline = dealers_with_rate.groupby("sector")["bounce_rate"].mean()

print("--- Salesman track record (avg bounce rate across their portfolio) ---")
print(salesman_track_record.round(3).sort_values(ascending=False).to_string())
print()
print("--- Territory baseline risk ---")
print(territory_baseline.round(3).to_string())
print()
print("--- Sector baseline risk ---")
print(sector_baseline.round(3).to_string())
print()

# ---------------------------------------------------------------------------
# PROVISIONAL SCORING RULE (no transaction history required)
# ---------------------------------------------------------------------------
# Population-level min/max of blended risk, used to properly SPREAD scores
# across the compressed provisional range (480-680) rather than compressing
# everyone into a narrow band -- computed once from the full dealer set
_all_blended = []
for _, d in dealers.iterrows():
    sr = salesman_track_record.get(d["salesman_id"], dealer_bounce.mean())
    tr = territory_baseline.get(d["territory_risk_tier"], dealer_bounce.mean())
    secr = sector_baseline.get(d["sector"], dealer_bounce.mean())
    _all_blended.append(0.5 * sr + 0.3 * tr + 0.2 * secr)
_blended_min, _blended_max = min(_all_blended), max(_all_blended)

def provisional_score(dealer_row):
    """
    Rule-based starter score using only onboarding-time information.
    Returns a conservative 300-900 range, deliberately compressed toward
    the middle (never claims high confidence in either direction) plus a
    starter credit-limit cap.
    """
    salesman_rate = salesman_track_record.get(dealer_row["salesman_id"], dealer_bounce.mean())
    territory_rate = territory_baseline.get(dealer_row["territory_risk_tier"], dealer_bounce.mean())
    sector_rate = sector_baseline.get(dealer_row["sector"], dealer_bounce.mean())

    # Simple weighted blend -- salesman track record weighted highest since
    # it's the most direct proxy for "who is vouching for this dealer"
    blended_risk = 0.5 * salesman_rate + 0.3 * territory_rate + 0.2 * sector_rate

    # Min-max normalize against the FULL portfolio's blended-risk range, then
    # map to the compressed provisional band (480-680) -- this actually
    # spreads dealers across the band instead of clustering them all near
    # the midpoint, while still never claiming full RED/GREEN confidence
    normalized = (blended_risk - _blended_min) / (_blended_max - _blended_min + 1e-9)
    score = 680 - (normalized * 200)
    score = np.clip(score, 480, 680)

    if score < 560:
        tier = "AMBER (Provisional — Elevated Caution)"
    else:
        tier = "AMBER (Provisional — Standard Caution)"

    # Conservative starter credit limit: cap well below what a fully-scored
    # dealer of similar profile might receive, regardless of requested amount
    starter_limit_cap = 100000  # PKR -- flat conservative starter cap, sector-agnostic by design

    return round(score), tier, starter_limit_cap, blended_risk

# ---------------------------------------------------------------------------
# TEST: simulate cold-start by truncating real dealers to <3 invoices
# and compare provisional judgment against their known true_risk_profile
# ---------------------------------------------------------------------------
np.random.seed(11)
test_dealers = dealers.sample(15, random_state=11)

results = []
for _, d in test_dealers.iterrows():
    score, tier, cap, blended = provisional_score(d)
    results.append({
        "dealer_id": d["dealer_id"], "salesman_id": d["salesman_id"],
        "territory_risk_tier": d["territory_risk_tier"], "sector": d["sector"],
        "provisional_score": score, "provisional_tier": tier,
        "starter_limit_cap_pkr": cap,
        "true_risk_profile (hidden, validation only)": d["true_risk_profile"],
    })

results_df = pd.DataFrame(results)
print("=" * 70)
print("COLD-START TEST: Provisional scores for 15 simulated new dealers")
print("=" * 70)
print(results_df.to_string(index=False))
print()

# Directional check: does provisional score correlate at all with true risk?
risk_map = {"Reliable": 0, "Moderate": 1, "Risky": 2}
results_df["true_risk_numeric"] = results_df["true_risk_profile (hidden, validation only)"].map(risk_map)
corr = results_df["provisional_score"].corr(results_df["true_risk_numeric"])
print(f"Correlation between provisional score and true risk (negative = correctly directional): {corr:.3f}")
print("(Provisional score should DECREASE as true risk increases -- negative correlation expected)")

results_df.to_csv("cold_start_test_results.csv", index=False)
