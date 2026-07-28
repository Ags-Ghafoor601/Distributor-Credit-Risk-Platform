"""
Reason Codes + Ranked Dealer Risk Table
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 1, Step 5

Reproduces the exact model from model_build.py (same seed -> identical model),
then decomposes each dealer's score into per-feature contributions so every
score is explainable in plain language -- the "defensible" requirement from
the brief. This is the additive-decomposition property that makes logistic
scorecards preferable to opaque models for this use case.
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

CUTOFF_DATE = pd.Timestamp("2025-01-01")
LABEL_WINDOW_END = pd.Timestamp("2025-12-31")
LATE_LABEL_THRESHOLD_DAYS = 15
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES_PER_WINDOW = 3

pd.options.mode.chained_assignment = None

dealers = pd.read_csv("dealers.csv", parse_dates=["onboarding_date"])
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
        "dealer_id": dealer_id,
        "salesman_id": dealer_row["salesman_id"],
        "territory_risk_tier": dealer_row["territory_risk_tier"],
        "is_salesman_favorite": dealer_row["is_salesman_favorite"],
        "dealer_name": dealer_row["dealer_name"],
        "city": dealer_row["city"],
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
model = LogisticRegression(max_iter=1000, class_weight="balanced")
model.fit(X_train_s, y_train)

# ---------------------------------------------------------------------------
# PER-DEALER REASON CODES: contribution = coefficient * standardized_value
# Positive contribution = pushes toward HIGH RISK; negative = pushes toward LOW RISK
# ---------------------------------------------------------------------------
X_all_s = scaler.transform(X)
contributions = X_all_s * model.coef_[0]
contrib_df = pd.DataFrame(contributions, columns=feature_cols, index=dataset.index)

BASE_SCORE, BASE_ODDS, PDO = 600, 1 / 19, 40
factor = PDO / np.log(2)
offset = BASE_SCORE - factor * np.log(BASE_ODDS)

def prob_to_score(prob_bad):
    prob_bad = np.clip(prob_bad, 1e-6, 1 - 1e-6)
    odds_good = (1 - prob_bad) / prob_bad
    return np.clip(offset + factor * np.log(odds_good), 300, 900)

dataset["risk_probability"] = model.predict_proba(X_all_s)[:, 1]
dataset["credit_score"] = prob_to_score(dataset["risk_probability"]).round(0)
dataset["risk_flag"] = pd.cut(
    dataset["credit_score"], bins=[0, 580, 700, 900],
    labels=["RED (High Risk)", "AMBER (Moderate)", "GREEN (Reliable)"]
)

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
    row = contrib_df.loc[idx].sort_values(ascending=False)
    top = row.head(n)
    return [(REASON_LABELS[f], round(v, 3)) for f, v in top.items()]

dataset["top_reasons"] = [top_reasons(i) for i in dataset.index]

# ---------------------------------------------------------------------------
# RANKED DEALER RISK TABLE (the primary dashboard deliverable)
# ---------------------------------------------------------------------------
risk_table = dataset[[
    "dealer_id", "dealer_name", "city", "salesman_id", "is_salesman_favorite",
    "credit_score", "risk_flag", "true_risk_profile", "is_high_risk"
]].sort_values("credit_score").reset_index(drop=True)

risk_table.to_csv("dealer_risk_table.csv", index=False)
dataset.to_csv("dealer_scores_with_reasons.csv", index=False)

print("=" * 70)
print("RANKED DEALER RISK TABLE (top 10 highest risk)")
print("=" * 70)
print(risk_table.head(10).to_string(index=False))

print("\n" + "=" * 70)
print("THE DEMO MOMENT: Salesman-favorite dealers flagged RED despite trust")
print("=" * 70)
demo_candidates = risk_table[
    (risk_table["is_salesman_favorite"] == True) &
    (risk_table["risk_flag"] == "RED (High Risk)")
]
print(demo_candidates.to_string(index=False))

if len(demo_candidates) > 0:
    demo_dealer_id = demo_candidates.iloc[0]["dealer_id"]
    print(f"\n>>> Selected demo dealer for Risk Card: {demo_dealer_id}")
    demo_row = dataset[dataset["dealer_id"] == demo_dealer_id].iloc[0]
    print(f"    Score: {demo_row['credit_score']}, Flag: {demo_row['risk_flag']}")
    print(f"    Top reasons: {demo_row['top_reasons']}")
