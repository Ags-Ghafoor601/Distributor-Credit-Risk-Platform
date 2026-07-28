"""
K-Fold Cross-Validation — robust performance estimate
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint

The headline AUC 0.848 / KS 0.702 numbers come from ONE 70/30 split. A
single split can be lucky or unlucky, especially with only 219 labeled
dealers. This runs stratified 5-fold cross-validation on the FINAL
VIF-remediated 6-feature model to report a mean +/- std performance range
-- the number that should actually be quoted to a client, not the
single-split figure.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score

CUTOFF_DATE = pd.Timestamp("2025-01-01")
LABEL_WINDOW_END = pd.Timestamp("2025-12-31")
LATE_LABEL_THRESHOLD_DAYS = 15
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES = 3

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "Day1"

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

dataset = feat_df.merge(label_df, on="dealer_id", how="inner")
X = dataset[FEATURE_COLS].reset_index(drop=True)
y = dataset["is_high_risk"].reset_index(drop=True)

print(f"Cross-validating on {len(X)} labeled dealers (base rate: {y.mean():.3f})")
print()

# ---------------------------------------------------------------------------
# STRATIFIED 5-FOLD CROSS-VALIDATION
# stratified because base rate is 37% -- plain k-fold could produce folds
# with very few positive cases given only 219 total dealers
# ---------------------------------------------------------------------------
N_FOLDS = 5
skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)

def ks_stat(y_true, y_prob):
    d = pd.DataFrame({"y": y_true, "p": y_prob}).sort_values("p")
    d["cum_bad"] = (d["y"] == 1).cumsum() / (d["y"] == 1).sum()
    d["cum_good"] = (d["y"] == 0).cumsum() / (d["y"] == 0).sum()
    return np.max(np.abs(d["cum_bad"] - d["cum_good"]))

fold_results = []
for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y), 1):
    X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
    y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    model = LogisticRegression(max_iter=1000, class_weight="balanced")
    model.fit(X_tr_s, y_tr)
    probs = model.predict_proba(X_te_s)[:, 1]

    auc = roc_auc_score(y_te, probs)
    ks = ks_stat(y_te.values, probs)
    fold_results.append({"fold": fold_idx, "n_test": len(X_te), "n_positive": int(y_te.sum()), "auc": auc, "ks": ks})
    print(f"Fold {fold_idx}: n_test={len(X_te)} (positives={int(y_te.sum())}) | AUC={auc:.3f} | KS={ks:.3f}")

results_df = pd.DataFrame(fold_results)
print()
print("=" * 60)
print("CROSS-VALIDATED PERFORMANCE (the number to actually quote)")
print("=" * 60)
print(f"AUC: {results_df['auc'].mean():.3f} +/- {results_df['auc'].std():.3f}  "
      f"(range: {results_df['auc'].min():.3f} - {results_df['auc'].max():.3f})")
print(f"KS:  {results_df['ks'].mean():.3f} +/- {results_df['ks'].std():.3f}  "
      f"(range: {results_df['ks'].min():.3f} - {results_df['ks'].max():.3f})")
print()
print(f"For comparison, the original single 70/30 split reported: AUC 0.847, KS 0.702")

results_df.to_csv(BASE_DIR / "cross_validation_results.csv", index=False)
