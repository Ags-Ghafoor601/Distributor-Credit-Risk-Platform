"""
Stress Test Validation: Does the pipeline survive messy data?
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2, Stress Test

Runs the SAME feature engineering + model logic on cleaned_transactions.csv
(derived from deliberately messy raw data) and compares dealer-level scores
against the original clean-data run. If scores stay close, the ingestion
pipeline is proven to preserve signal despite real-world messiness.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

CUTOFF_DATE = pd.Timestamp("2025-01-01")
LABEL_WINDOW_END = pd.Timestamp("2025-12-31")
LATE_LABEL_THRESHOLD_DAYS = 15
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES_PER_WINDOW = 3

pd.options.mode.chained_assignment = None

dealers = pd.read_csv("dealers.csv", parse_dates=["onboarding_date"])

def build_dataset(txn_path, parse_dates_cols):
    txns = pd.read_csv(txn_path, parse_dates=parse_dates_cols)
    feature_window = txns[txns["due_date"] < CUTOFF_DATE]
    label_window = txns[(txns["due_date"] >= CUTOFF_DATE) & (txns["due_date"] <= LABEL_WINDOW_END)]

    rows = []
    for dealer_id, dgrp in feature_window.groupby("dealer_id"):
        if len(dgrp) < MIN_INVOICES_PER_WINDOW:
            continue
        dealer_row = dealers[dealers["dealer_id"] == dealer_id]
        if len(dealer_row) == 0:
            continue
        dealer_row = dealer_row.iloc[0]
        non_bounced = dgrp[dgrp["cheque_bounced"] == False]
        bounce_rate_lifetime = dgrp["cheque_bounced"].mean()
        avg_days_late = non_bounced["days_late"].mean() if len(non_bounced) else 0
        nonseasonal = non_bounced[non_bounced["is_eid_ramzan_period"] == False]
        avg_days_late_nonseasonal = nonseasonal["days_late"].mean() if len(nonseasonal) else avg_days_late
        payment_volatility = non_bounced["days_late"].std() if len(non_bounced) > 1 else 0
        years_active = max((CUTOFF_DATE.date() - dealer_row["onboarding_date"].date()).days / 365.25, 0)
        real_exposure_pkr = dealer_row["credit_limit_pkr"] * ((1 - ANNUAL_PKR_EROSION) ** years_active)
        mid = feature_window["invoice_date"].median()
        early = dgrp[dgrp["invoice_date"] < mid]
        late = dgrp[dgrp["invoice_date"] >= mid]
        order_frequency_trend = (len(late) - len(early)) / max(len(early), 1)
        rows.append({
            "dealer_id": dealer_id, "salesman_id": dealer_row["salesman_id"],
            "territory_risk_tier": dealer_row["territory_risk_tier"],
            "bounce_rate_lifetime": bounce_rate_lifetime,
            "avg_days_late_nonseasonal": avg_days_late_nonseasonal,
            "payment_volatility": payment_volatility,
            "real_exposure_pkr": real_exposure_pkr,
            "order_frequency_trend": order_frequency_trend,
        })
    feat_df = pd.DataFrame(rows)

    def loo_group_rate(df, group_col, rate_col):
        s = df.groupby(group_col)[rate_col].transform("sum")
        c = df.groupby(group_col)[rate_col].transform("count")
        return ((s - df[rate_col]) / (c - 1).replace(0, np.nan)).fillna(df[rate_col].mean())

    feat_df["salesman_default_rate_loo"] = loo_group_rate(feat_df, "salesman_id", "bounce_rate_lifetime")
    feat_df["territory_default_rate_loo"] = loo_group_rate(feat_df, "territory_risk_tier", "bounce_rate_lifetime")

    label_rows = []
    for dealer_id, dgrp in label_window.groupby("dealer_id"):
        if len(dgrp) < MIN_INVOICES_PER_WINDOW:
            continue
        non_bounced = dgrp[dgrp["cheque_bounced"] == False]
        avg_late = non_bounced["days_late"].mean() if len(non_bounced) else 0
        bounced_any = dgrp["cheque_bounced"].any()
        is_high_risk = int(bounced_any or (avg_late > LATE_LABEL_THRESHOLD_DAYS))
        label_rows.append({"dealer_id": dealer_id, "is_high_risk": is_high_risk})
    label_df = pd.DataFrame(label_rows)

    return feat_df.merge(label_df, on="dealer_id", how="inner")

feature_cols = [
    "bounce_rate_lifetime", "avg_days_late_nonseasonal", "payment_volatility",
    "real_exposure_pkr", "order_frequency_trend",
    "salesman_default_rate_loo", "territory_default_rate_loo",
]

def train_eval(dataset, label):
    X, y = dataset[feature_cols], dataset["is_high_risk"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_train_s, y_train)
    test_probs = model.predict_proba(X_test_s)[:, 1]
    auc = roc_auc_score(y_test, test_probs)

    def ks_stat(y_true, y_prob):
        d = pd.DataFrame({"y": y_true, "p": y_prob}).sort_values("p")
        d["cum_bad"] = (d["y"] == 1).cumsum() / (d["y"] == 1).sum()
        d["cum_good"] = (d["y"] == 0).cumsum() / (d["y"] == 0).sum()
        return np.max(np.abs(d["cum_bad"] - d["cum_good"]))

    ks = ks_stat(y_test.values, test_probs)
    print(f"[{label}] Dealers: {len(dataset)} | Test AUC: {auc:.3f} | Test KS: {ks:.3f}")
    return dataset, model, scaler

print("=" * 70)
print("COMPARISON: Clean-source data vs Messy-source data (post-cleaning)")
print("=" * 70)

clean_dataset = build_dataset(
    "transactions.csv",
    ["invoice_date", "due_date", "payment_date"]
)
_, _, _ = train_eval(clean_dataset, "ORIGINAL CLEAN DATA")

messy_dataset = build_dataset(
    "cleaned_transactions.csv",
    ["invoice_date", "due_date", "payment_date"]
)
_, _, _ = train_eval(messy_dataset, "MESSY DATA -> CLEANED VIA PIPELINE")

# ---------------------------------------------------------------------------
# Dealer-level coverage comparison: did we lose any dealers entirely?
# ---------------------------------------------------------------------------
clean_dealers = set(clean_dataset["dealer_id"])
messy_dealers = set(messy_dataset["dealer_id"])

print()
print(f"Dealers scored from original clean data: {len(clean_dealers)}")
print(f"Dealers scored from messy->cleaned data: {len(messy_dealers)}")
print(f"Dealers present in both: {len(clean_dealers & messy_dealers)}")
print(f"Dealers lost (in clean, missing from messy pipeline): {len(clean_dealers - messy_dealers)}")
print(f"Lost dealer IDs: {sorted(clean_dealers - messy_dealers)}")

# ---------------------------------------------------------------------------
# Feature-level agreement check on dealers present in both
# ---------------------------------------------------------------------------
common = sorted(clean_dealers & messy_dealers)
comp = clean_dataset[clean_dataset["dealer_id"].isin(common)].set_index("dealer_id")[feature_cols]
comp_messy = messy_dataset[messy_dataset["dealer_id"].isin(common)].set_index("dealer_id")[feature_cols]
comp_messy = comp_messy.reindex(comp.index)

diff_pct = ((comp_messy - comp).abs() / comp.abs().replace(0, np.nan)).mean() * 100
print()
print("Average % difference per feature (clean-source vs messy-source, same dealers):")
print(diff_pct.round(2).to_string())
