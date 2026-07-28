"""
Feature Engineering + WOE Binning + Information Value Validation
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 1, Step 3

Aggregates transaction-level data to dealer-level features (per Step 1's
unit-of-analysis decision), computes the binary label, then bins each
feature and computes Weight-of-Evidence (WOE) + Information Value (IV)
to PROVE predictive power before committing features to the model.

IV interpretation (industry-standard credit scoring convention):
  < 0.02            -> not predictive, drop
  0.02 - 0.10        -> weak
  0.10 - 0.30        -> medium, useful
  0.30 - 0.50        -> strong
  > 0.50             -> suspiciously strong, check for leakage
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta

REFERENCE_DATE = date(2025, 12, 31)   # simulated "as-of" scoring date
LATE_LABEL_THRESHOLD_DAYS = 15        # from Step 1 target definition
BOUNCE_WINDOW_MONTHS = 6
ANNUAL_PKR_EROSION = 0.18

pd.options.mode.chained_assignment = None

# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------
dealers = pd.read_csv("dealers.csv", parse_dates=["onboarding_date"])
txns = pd.read_csv(
    "transactions.csv",
    parse_dates=["invoice_date", "due_date", "payment_date"]
)

# ---------------------------------------------------------------------------
# DEALER-LEVEL FEATURE AGGREGATION (transaction grain -> dealer grain)
# ---------------------------------------------------------------------------
features = []

six_months_ago = pd.Timestamp(REFERENCE_DATE) - pd.DateOffset(months=BOUNCE_WINDOW_MONTHS)

for dealer_id, dgrp in txns.groupby("dealer_id"):
    dealer_row = dealers[dealers["dealer_id"] == dealer_id].iloc[0]

    n_invoices = len(dgrp)
    bounced = dgrp["cheque_bounced"]
    bounce_rate_lifetime = bounced.mean()

    recent = dgrp[dgrp["due_date"] >= six_months_ago]
    bounce_count_6m = recent["cheque_bounced"].sum()

    non_bounced = dgrp[dgrp["cheque_bounced"] == False]
    avg_days_late = non_bounced["days_late"].mean() if len(non_bounced) else 0

    nonseasonal = non_bounced[non_bounced["is_eid_ramzan_period"] == False]
    avg_days_late_nonseasonal = nonseasonal["days_late"].mean() if len(nonseasonal) else avg_days_late

    payment_volatility = non_bounced["days_late"].std() if len(non_bounced) > 1 else 0

    # Real exposure: erode nominal credit limit by years since onboarding
    years_active = max((REFERENCE_DATE - dealer_row["onboarding_date"].date()).days / 365.25, 0)
    real_exposure_pkr = dealer_row["credit_limit_pkr"] * ((1 - ANNUAL_PKR_EROSION) ** years_active)

    # Order frequency trend: invoice count in most recent 6 months vs prior 6 months
    last_6m = dgrp[dgrp["invoice_date"] >= six_months_ago]
    prev_6m_start = six_months_ago - pd.DateOffset(months=6)
    prev_6m = dgrp[(dgrp["invoice_date"] >= prev_6m_start) & (dgrp["invoice_date"] < six_months_ago)]
    order_frequency_trend = (len(last_6m) - len(prev_6m)) / max(len(prev_6m), 1)

    # Label (Step 1 definition): bounce in trailing 6mo OR avg days late > threshold
    is_high_risk = int((bounce_count_6m > 0) or (avg_days_late > LATE_LABEL_THRESHOLD_DAYS))

    features.append({
        "dealer_id": dealer_id,
        "salesman_id": dealer_row["salesman_id"],
        "territory_risk_tier": dealer_row["territory_risk_tier"],
        "is_salesman_favorite": dealer_row["is_salesman_favorite"],
        "n_invoices": n_invoices,
        "bounce_rate_lifetime": bounce_rate_lifetime,
        "bounce_count_6m": bounce_count_6m,
        "avg_days_late": avg_days_late,
        "avg_days_late_nonseasonal": avg_days_late_nonseasonal,
        "payment_volatility": payment_volatility,
        "real_exposure_pkr": real_exposure_pkr,
        "order_frequency_trend": order_frequency_trend,
        "true_risk_profile": dealer_row["true_risk_profile"],  # held out, validation only
        "is_high_risk": is_high_risk,
    })

dealer_features = pd.DataFrame(features)

# ---------------------------------------------------------------------------
# LEAVE-ONE-OUT GROUP FEATURES (must exclude self to avoid label leakage)
# ---------------------------------------------------------------------------
# Salesman-favorite default rate: for each dealer, the default rate among
# OTHER dealers their salesman manages (not including this dealer itself)
def loo_group_rate(df, group_col, label_col):
    group_sum = df.groupby(group_col)[label_col].transform("sum")
    group_count = df.groupby(group_col)[label_col].transform("count")
    loo_rate = (group_sum - df[label_col]) / (group_count - 1).replace(0, np.nan)
    return loo_rate.fillna(df[label_col].mean())  # fallback to global mean if group size 1

dealer_features["salesman_default_rate_loo"] = loo_group_rate(
    dealer_features, "salesman_id", "is_high_risk"
)
dealer_features["territory_default_rate_loo"] = loo_group_rate(
    dealer_features, "territory_risk_tier", "is_high_risk"
)

dealer_features.to_csv("dealer_features.csv", index=False)

# ---------------------------------------------------------------------------
# WOE BINNING + INFORMATION VALUE
# ---------------------------------------------------------------------------
def woe_iv_table(df, feature, label, bins=4):
    d = df[[feature, label]].copy()
    try:
        d["bin"] = pd.qcut(d[feature], q=bins, duplicates="drop")
    except ValueError:
        d["bin"] = pd.cut(d[feature], bins=bins, duplicates="drop")

    grouped = d.groupby("bin", observed=True)[label].agg(["count", "sum"])
    grouped.columns = ["total", "bad"]
    grouped["good"] = grouped["total"] - grouped["bad"]

    total_good = grouped["good"].sum()
    total_bad = grouped["bad"].sum()

    # Laplace smoothing to avoid div-by-zero on empty bins
    grouped["pct_good"] = (grouped["good"] + 0.5) / (total_good + 0.5 * len(grouped))
    grouped["pct_bad"] = (grouped["bad"] + 0.5) / (total_bad + 0.5 * len(grouped))
    grouped["woe"] = np.log(grouped["pct_good"] / grouped["pct_bad"])
    grouped["iv_contribution"] = (grouped["pct_good"] - grouped["pct_bad"]) * grouped["woe"]

    iv_total = grouped["iv_contribution"].sum()
    return grouped, iv_total


candidate_features = [
    "bounce_rate_lifetime",
    "avg_days_late_nonseasonal",
    "payment_volatility",
    "real_exposure_pkr",
    "order_frequency_trend",
    "salesman_default_rate_loo",
    "territory_default_rate_loo",
]

print("=" * 70)
print("INFORMATION VALUE SUMMARY (feature predictive strength)")
print("=" * 70)

iv_results = []
woe_tables = {}
for feat in candidate_features:
    table, iv = woe_iv_table(dealer_features, feat, "is_high_risk")
    woe_tables[feat] = table
    iv_results.append({"feature": feat, "information_value": round(iv, 4)})
    print(f"\n--- {feat} (IV = {iv:.4f}) ---")
    print(table[["total", "bad", "good", "woe"]].round(3))

iv_summary = pd.DataFrame(iv_results).sort_values("information_value", ascending=False)
iv_summary.to_csv("iv_summary.csv", index=False)

print("\n" + "=" * 70)
print("FINAL RANKED FEATURE LIST BY INFORMATION VALUE")
print("=" * 70)
print(iv_summary.to_string(index=False))
