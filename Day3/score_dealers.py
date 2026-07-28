"""
Score Dealers — loads the PERSISTED model, no retraining
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint

This is what a real production scoring run looks like: load the trained
artifact, compute features for whichever dealers need scoring, apply the
already-fitted scaler and model. No LogisticRegression.fit() call anywhere
in this file -- that's the entire point.

Still includes the cold-start routing (dealers with insufficient feature
history) since that's a genuine part of scoring, not training.
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "Day1"

CUTOFF_DATE = pd.Timestamp("2025-01-01")
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES = 3

pd.options.mode.chained_assignment = None

# ---------------------------------------------------------------------------
# LOAD PERSISTED ARTIFACT -- this replaces every training step from every
# prior script in this project
# ---------------------------------------------------------------------------
artifact = joblib.load(BASE_DIR / "credit_risk_model.joblib")
model = artifact["model"]
scaler = artifact["scaler"]
FEATURE_COLS = artifact["feature_columns"]
score_params = artifact["score_params"]
meta = artifact["metadata"]

print("=" * 70)
print("LOADED MODEL ARTIFACT (no retraining performed)")
print("=" * 70)
print(f"Trained on: {meta['trained_on']}")
print(f"Training pool size: {meta['training_pool_size']} dealers")
print(f"Cross-validated AUC: {meta['cross_validated_auc_mean']:.3f} +/- {meta['cross_validated_auc_std']:.3f}")
for lim in meta["known_limitations"]:
    print(f"  KNOWN LIMITATION: {lim}")
print()

dealers = pd.read_csv(DATA_DIR / "dealers.csv", parse_dates=["onboarding_date"])
salesmen = pd.read_csv(DATA_DIR / "salesmen.csv")
txns = pd.read_csv(DATA_DIR / "transactions.csv",
                    parse_dates=["invoice_date", "due_date", "payment_date"])
feature_window = txns[txns["due_date"] < CUTOFF_DATE]

# ---------------------------------------------------------------------------
# COMPUTE FEATURES for every dealer with sufficient history (same logic as
# training -- feature ENGINEERING is not the same as model TRAINING, this
# still needs to run per-dealer, but no model.fit() happens here)
# ---------------------------------------------------------------------------
feat_rows = []
insufficient_history = []
for dealer_id, dealer_row in dealers.set_index("dealer_id").iterrows():
    dgrp = feature_window[feature_window["dealer_id"] == dealer_id]
    if len(dgrp) < MIN_INVOICES:
        insufficient_history.append(dealer_id)
        continue
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
    feat_rows.append({
        "dealer_id": dealer_id, "dealer_name": dealer_row["dealer_name"],
        "salesman_id": dealer_row["salesman_id"],
        "territory_risk_tier": dealer_row["territory_risk_tier"],
        "bounce_rate_lifetime": bounce_rate_lifetime,
        "avg_days_late_nonseasonal": avg_days_late_nonseasonal,
        "payment_volatility": payment_volatility,
        "real_exposure_pkr": real_exposure_pkr,
        "order_frequency_trend": order_frequency_trend,
    })
feat_df = pd.DataFrame(feat_rows)

def loo_group_rate(df, group_col, rate_col):
    s = df.groupby(group_col)[rate_col].transform("sum")
    c = df.groupby(group_col)[rate_col].transform("count")
    return ((s - df[rate_col]) / (c - 1).replace(0, np.nan)).fillna(df[rate_col].mean())

feat_df["salesman_default_rate_loo"] = loo_group_rate(feat_df, "salesman_id", "bounce_rate_lifetime")
feat_df["territory_default_rate_loo"] = loo_group_rate(feat_df, "territory_risk_tier", "bounce_rate_lifetime")
z_late = (feat_df["avg_days_late_nonseasonal"] - feat_df["avg_days_late_nonseasonal"].mean()) / feat_df["avg_days_late_nonseasonal"].std()
z_vol = (feat_df["payment_volatility"] - feat_df["payment_volatility"].mean()) / feat_df["payment_volatility"].std()
feat_df["payment_delay_severity"] = (z_late + z_vol) / 2

# ---------------------------------------------------------------------------
# SCORE using the LOADED model/scaler -- zero training calls below this line
# ---------------------------------------------------------------------------
X_score = feat_df[FEATURE_COLS]
X_score_s = scaler.transform(X_score)  # transform only, never fit
feat_df["risk_probability"] = model.predict_proba(X_score_s)[:, 1]

factor = score_params["pdo"] / np.log(2)
offset = score_params["base_score"] - factor * np.log(score_params["base_odds"])

def prob_to_score(prob_bad):
    prob_bad = np.clip(prob_bad, 1e-6, 1 - 1e-6)
    odds_good = (1 - prob_bad) / prob_bad
    return np.clip(offset + factor * np.log(odds_good), 300, 900)

feat_df["credit_score"] = prob_to_score(feat_df["risk_probability"]).round(0)
feat_df["risk_flag"] = pd.cut(
    feat_df["credit_score"], bins=[0, 580, 700, 900],
    labels=["RED (High Risk)", "AMBER (Moderate)", "GREEN (Reliable)"]
)

print(f"Scored {len(feat_df)} dealers using the persisted model (0 training calls)")
print(f"Dealers routed to cold-start (insufficient history): {insufficient_history if insufficient_history else 'NONE'}")
print()
print("--- Sample scores ---")
print(feat_df[["dealer_id", "dealer_name", "credit_score", "risk_flag"]]
      .sort_values("credit_score").head(5).to_string(index=False))

feat_df.to_csv(BASE_DIR / "dealer_scores_from_persisted_model.csv", index=False)
