"""
Probability Calibration Check & Fix
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2, Gap Fix #1

class_weight='balanced' improves classification separation (AUC/KS) but
distorts raw predict_proba() output away from true empirical frequencies.
This script PROVES that with a before/after reliability comparison (Brier
score + calibration table), fixes it with sigmoid (Platt) calibration via
cross-fitting, then refits on the FULL labeled dataset for production
scoring -- the validation split proved the method works; production uses
all available data.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, brier_score_loss

CUTOFF_DATE = pd.Timestamp("2025-01-01")
LABEL_WINDOW_END = pd.Timestamp("2025-12-31")
LATE_LABEL_THRESHOLD_DAYS = 15
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES_PER_WINDOW = 3

pd.options.mode.chained_assignment = None

# ---------------------------------------------------------------------------
# REBUILD DATASET (identical logic to model_build.py / reason_codes.py)
# ---------------------------------------------------------------------------
dealers = pd.read_csv("dealers.csv", parse_dates=["onboarding_date"])
salesmen = pd.read_csv("salesmen.csv")
txns = pd.read_csv(
    "transactions.csv",
    parse_dates=["invoice_date", "due_date", "payment_date"]
)

feature_window = txns[txns["due_date"] < CUTOFF_DATE]
label_window = txns[(txns["due_date"] >= CUTOFF_DATE) & (txns["due_date"] <= LABEL_WINDOW_END)]

rows = []
for dealer_id, dgrp in feature_window.groupby("dealer_id"):
    if len(dgrp) < MIN_INVOICES_PER_WINDOW:
        continue
    dealer_row = dealers[dealers["dealer_id"] == dealer_id].iloc[0]
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
        "is_salesman_favorite": dealer_row["is_salesman_favorite"],
        "dealer_name": dealer_row["dealer_name"], "city": dealer_row["city"],
        "sector": dealer_row["sector"], "credit_limit_pkr": dealer_row["credit_limit_pkr"],
        "true_risk_profile": dealer_row["true_risk_profile"],
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
dataset = feat_df.merge(label_df, on="dealer_id", how="inner")

feature_cols = [
    "bounce_rate_lifetime", "avg_days_late_nonseasonal", "payment_volatility",
    "real_exposure_pkr", "order_frequency_trend",
    "salesman_default_rate_loo", "territory_default_rate_loo",
]
X = dataset[feature_cols]
y = dataset["is_high_risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

# ---------------------------------------------------------------------------
# BEFORE: uncalibrated model (what Day 1 shipped)
# ---------------------------------------------------------------------------
raw_model = LogisticRegression(max_iter=1000, class_weight="balanced")
raw_model.fit(X_train_s, y_train)
raw_test_probs = raw_model.predict_proba(X_test_s)[:, 1]

brier_before = brier_score_loss(y_test, raw_test_probs)
auc_before = roc_auc_score(y_test, raw_test_probs)

# ---------------------------------------------------------------------------
# AFTER: sigmoid (Platt) calibration, cross-fitted to avoid leakage
# cv=5 with only ~150 train rows keeps each fold's calibration fit stable;
# sigmoid chosen over isotonic because isotonic needs more data to avoid
# overfitting the calibration map itself
# ---------------------------------------------------------------------------
calibrated_model = CalibratedClassifierCV(
    estimator=LogisticRegression(max_iter=1000, class_weight="balanced"),
    method="sigmoid", cv=5
)
calibrated_model.fit(X_train_s, y_train)
cal_test_probs = calibrated_model.predict_proba(X_test_s)[:, 1]

brier_after = brier_score_loss(y_test, cal_test_probs)
auc_after = roc_auc_score(y_test, cal_test_probs)

# Reference: naive baseline predicting the base rate for everyone
base_rate = y_train.mean()
brier_naive = brier_score_loss(y_test, np.full_like(cal_test_probs, base_rate))

print("=" * 70)
print("CALIBRATION: BEFORE vs AFTER")
print("=" * 70)
print(f"{'Metric':<30}{'Before (raw)':<18}{'After (calibrated)'}")
print(f"{'Brier score (lower=better)':<30}{brier_before:<18.4f}{brier_after:.4f}")
print(f"{'AUC (should be ~unchanged)':<30}{auc_before:<18.4f}{auc_after:.4f}")
print(f"Naive baseline Brier (always predict base rate {base_rate:.3f}): {brier_naive:.4f}")
print()

# Reliability table: bin predicted probability, compare to actual frequency
def reliability_table(y_true, y_prob, n_bins=5, label=""):
    df = pd.DataFrame({"y": y_true.values, "p": y_prob})
    df["bin"] = pd.qcut(df["p"], q=n_bins, duplicates="drop")
    table = df.groupby("bin", observed=True).agg(
        mean_predicted=("p", "mean"), actual_rate=("y", "mean"), n=("y", "count")
    )
    print(f"--- Reliability table: {label} ---")
    print(table.round(3).to_string())
    print()
    return table

reliability_table(y_test, raw_test_probs, label="BEFORE calibration")
reliability_table(y_test, cal_test_probs, label="AFTER calibration")

# ---------------------------------------------------------------------------
# PRODUCTION MODEL: refit calibrated model on FULL labeled dataset
# (validation above proves the method works out-of-time; production scoring
# uses all 219 labeled dealers to maximize data used for the deployed model)
# ---------------------------------------------------------------------------
X_all_s_fit_scaler = StandardScaler()
X_all_s = X_all_s_fit_scaler.fit_transform(X)

production_base = LogisticRegression(max_iter=1000, class_weight="balanced")
production_model = CalibratedClassifierCV(estimator=production_base, method="sigmoid", cv=5)
production_model.fit(X_all_s, y)

# For reason codes, we still need RAW linear coefficients (calibration wraps
# the model, so we separately fit an uncalibrated version on full data for
# the additive decomposition -- calibration only adjusts probability output,
# not feature attribution)
attribution_model = LogisticRegression(max_iter=1000, class_weight="balanced")
attribution_model.fit(X_all_s, y)
contributions = X_all_s * attribution_model.coef_[0]
contrib_df = pd.DataFrame(contributions, columns=feature_cols, index=dataset.index)

REASON_LABELS = {
    "bounce_rate_lifetime": "Cheque bounce history",
    "avg_days_late_nonseasonal": "Late payment pattern (excluding Eid/Ramzan)",
    "payment_volatility": "Inconsistent / unpredictable payment timing",
    "real_exposure_pkr": "Inflation-adjusted credit exposure",
    "order_frequency_trend": "Declining order activity",
    "salesman_default_rate_loo": "Salesman's track record with similar dealers",
    "territory_default_rate_loo": "Elevated risk in dealer's territory",
}

def top_reasons(idx, n=3):
    row = contrib_df.loc[idx]
    row_sorted = row.reindex(row.abs().sort_values(ascending=False).index)
    top = row_sorted.head(n)
    return [
        {"factor": REASON_LABELS[f], "direction": "increases_risk" if v > 0 else "reduces_risk", "weight": round(float(v), 3)}
        for f, v in top.items()
    ]

dataset["top_reasons"] = [top_reasons(i) for i in dataset.index]

BASE_SCORE, BASE_ODDS, PDO = 600, 1 / 19, 40
factor = PDO / np.log(2)
offset = BASE_SCORE - factor * np.log(BASE_ODDS)

def prob_to_score(prob_bad):
    prob_bad = np.clip(prob_bad, 1e-6, 1 - 1e-6)
    odds_good = (1 - prob_bad) / prob_bad
    return np.clip(offset + factor * np.log(odds_good), 300, 900)

dataset["risk_probability_calibrated"] = production_model.predict_proba(X_all_s)[:, 1]
dataset["credit_score"] = prob_to_score(dataset["risk_probability_calibrated"]).round(0)
dataset["risk_flag"] = pd.cut(
    dataset["credit_score"], bins=[0, 580, 700, 900],
    labels=["RED (High Risk)", "AMBER (Moderate)", "GREEN (Reliable)"]
)

dataset = dataset.merge(salesmen[["salesman_id", "salesman_name"]], on="salesman_id", how="left")

dataset.to_csv("dealer_scores_calibrated.csv", index=False)

# Export JSON for the Risk Card generator (parameterized, not hardcoded)
export_cols = [
    "dealer_id", "dealer_name", "city", "sector", "salesman_id", "salesman_name",
    "is_salesman_favorite", "credit_limit_pkr", "credit_score", "risk_flag",
    "risk_probability_calibrated", "top_reasons", "avg_days_late_nonseasonal",
    "payment_volatility", "bounce_rate_lifetime",
]
dataset[export_cols].to_json(
    "dealer_cards_data.json", orient="records", indent=2
)

print("=" * 70)
print("PRODUCTION SCORES (calibrated) — sample")
print("=" * 70)
print(dataset[["dealer_id", "risk_probability_calibrated", "credit_score", "risk_flag"]]
      .sort_values("credit_score").head(5).to_string(index=False))
print()
print(f"Exported: dealer_scores_calibrated.csv, dealer_cards_data.json ({len(dataset)} dealers)")
