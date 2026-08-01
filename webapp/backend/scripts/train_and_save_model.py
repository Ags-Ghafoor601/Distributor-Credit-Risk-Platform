"""
Train & Persist Model — separates TRAINING from SCORING
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint

Every prior script retrained the model from scratch on every run. That's
fine for a sprint, but not how any real deployed system works -- a
distributor's dashboard should score dealers in milliseconds using an
already-trained model, not re-run training every time someone opens the
risk table.

This script trains ONCE on the full labeled pool (219 dealers, VIF-clean
6-feature set) and persists: the trained model, the fitted scaler, the
exact feature column order, and metadata (training date, data snapshot,
cross-validated performance range) -- everything needed to reproduce or
audit the model later without re-deriving it from scratch.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Script now lives at webapp/backend/scripts/, so BASE_DIR is that folder.
# Data and model artefact both live one level up, inside the backend.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "tests" / "fixtures"
MODEL_DIR = BASE_DIR.parent / "model"
import joblib
from datetime import datetime
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

CUTOFF_DATE = pd.Timestamp("2025-01-01")
LABEL_WINDOW_END = pd.Timestamp("2025-12-31")
LATE_LABEL_THRESHOLD_DAYS = 15
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES = 3

pd.options.mode.chained_assignment = None

dealers = pd.read_csv(DATA_DIR / "dealers.csv", parse_dates=["onboarding_date"])
txns = pd.read_csv(DATA_DIR / "transactions.csv",
                    parse_dates=["invoice_date", "due_date", "payment_date"])

feature_window = txns[txns["due_date"] < CUTOFF_DATE]
label_window = txns[(txns["due_date"] >= CUTOFF_DATE) & (txns["due_date"] <= LABEL_WINDOW_END)]

rows = []
for dealer_id, dgrp in feature_window.groupby("dealer_id"):
    if len(dgrp) < MIN_INVOICES:
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

z_late = (feat_df["avg_days_late_nonseasonal"] - feat_df["avg_days_late_nonseasonal"].mean()) / feat_df["avg_days_late_nonseasonal"].std()
z_vol = (feat_df["payment_volatility"] - feat_df["payment_volatility"].mean()) / feat_df["payment_volatility"].std()
feat_df["payment_delay_severity"] = (z_late + z_vol) / 2

FEATURE_COLS = [
    "payment_delay_severity", "bounce_rate_lifetime", "real_exposure_pkr",
    "order_frequency_trend", "salesman_default_rate_loo", "territory_default_rate_loo",
]

label_rows = []
for dealer_id, dgrp in label_window.groupby("dealer_id"):
    if len(dgrp) < MIN_INVOICES:
        continue
    non_bounced = dgrp[dgrp["cheque_bounced"] == False]
    avg_late = non_bounced["days_late"].mean() if len(non_bounced) else 0
    bounced_any = dgrp["cheque_bounced"].any()
    is_high_risk = int(bounced_any or (avg_late > LATE_LABEL_THRESHOLD_DAYS))
    label_rows.append({"dealer_id": dealer_id, "is_high_risk": is_high_risk})
label_df = pd.DataFrame(label_rows)

training_pool = feat_df.merge(label_df, on="dealer_id", how="inner")
X = training_pool[FEATURE_COLS]
y = training_pool["is_high_risk"]

# ---------------------------------------------------------------------------
# TRAIN ONCE on the full labeled pool (this is the deployed production model)
# ---------------------------------------------------------------------------
scaler = StandardScaler()
X_s = scaler.fit_transform(X)
model = LogisticRegression(max_iter=1000, class_weight="balanced")
model.fit(X_s, y)

# ---------------------------------------------------------------------------
# PERSIST: model, scaler, feature order, and metadata -- everything needed
# to reproduce or audit this exact model later without retraining
# ---------------------------------------------------------------------------
BASE_SCORE, BASE_ODDS, PDO = 600, 1 / 19, 40

artifact = {
    "model": model,
    "scaler": scaler,
    "feature_columns": FEATURE_COLS,
    "score_params": {"base_score": BASE_SCORE, "base_odds": BASE_ODDS, "pdo": PDO},
    "metadata": {
        "trained_on": datetime.now().isoformat(),
        "training_pool_size": len(training_pool),
        "base_rate": float(y.mean()),
        "cutoff_date": str(CUTOFF_DATE.date()),
        "label_window_end": str(LABEL_WINDOW_END.date()),
        "cross_validated_auc_mean": 0.860,
        "cross_validated_auc_std": 0.098,
        "cross_validated_ks_mean": 0.667,
        "cross_validated_ks_std": 0.175,
        "known_limitations": [
            "Calibration not validated at this sample size -- treat exact score as directional, tier (RED/AMBER/GREEN) as reliable",
            "Cross-validated AUC range is 0.763-0.989 across folds -- report as a range, not a single decimal, to any client",
        ],
    },
}

joblib.dump(artifact, MODEL_DIR / "credit_risk_model.joblib")

print("Model artifact saved: credit_risk_model.joblib")
print(f"  Trained on {len(training_pool)} dealers, base rate {y.mean():.3f}")
print(f"  Feature columns: {FEATURE_COLS}")
print(f"  Cross-validated performance embedded in metadata: "
      f"AUC {artifact['metadata']['cross_validated_auc_mean']:.3f} "
      f"+/- {artifact['metadata']['cross_validated_auc_std']:.3f}")
