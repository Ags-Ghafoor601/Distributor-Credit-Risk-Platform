"""
Multicollinearity Check (VIF) + Remediation
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2

Explains WHY salesman_default_rate_loo and bounce_rate_lifetime showed
near-zero coefficients in the combined model despite strong standalone IV
(Step 3 finding). Computes Variance Inflation Factor per feature, remediates
if needed, and re-validates that AUC/KS hold after any change.

VIF interpretation (standard convention):
  < 5   : no concerning collinearity
  5-10  : moderate, worth watching
  > 10  : severe, coefficient estimates are unstable/untrustworthy
"""

import pandas as pd
import numpy as np
from statsmodels.stats.outliers_influence import variance_inflation_factor
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
txns = pd.read_csv("transactions.csv",
                    parse_dates=["invoice_date", "due_date", "payment_date"])

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
scaler = StandardScaler()
X_s = pd.DataFrame(scaler.fit_transform(X), columns=feature_cols)

# ---------------------------------------------------------------------------
# VIF CHECK
# ---------------------------------------------------------------------------
vif_data = pd.DataFrame()
vif_data["feature"] = feature_cols
vif_data["VIF"] = [variance_inflation_factor(X_s.values, i) for i in range(len(feature_cols))]
vif_data = vif_data.sort_values("VIF", ascending=False)

print("=" * 60)
print("VARIANCE INFLATION FACTOR (VIF) PER FEATURE")
print("=" * 60)
print(vif_data.round(2).to_string(index=False))
print()
print("Reference: <5 fine, 5-10 moderate/watch, >10 severe")
print()

# Correlation matrix -- shows WHICH pairs are driving any high VIF
print("--- Correlation matrix ---")
print(X.corr().round(2).to_string())
print()

# ---------------------------------------------------------------------------
# REMEDIATION: only act if VIF crosses the moderate threshold (>5)
# ---------------------------------------------------------------------------
high_vif = vif_data[vif_data["VIF"] > 5]["feature"].tolist()
print(f"Features with VIF > 5 (remediation candidates): {high_vif if high_vif else 'NONE'}")
print()

if not high_vif:
    print("No severe multicollinearity detected by VIF. The near-zero coefficients")
    print("observed for bounce_rate_lifetime / salesman_default_rate_loo in Step 4")
    print("are therefore better explained as WEAKER marginal contribution once")
    print("avg_days_late_nonseasonal and payment_volatility are already in the model")
    print("-- i.e. genuine but overlapping signal, not a VIF-flagged collinearity problem.")
    print("No feature removal needed. Retaining full feature set.")
else:
    print(f"Remediating: combining {high_vif} into a single composite feature")
    print("(dropping either one outright would lose information; both measure")
    print(" related-but-distinct aspects of payment lateness behavior)")
    print()

    X_composite = X.copy()
    z_late = (X["avg_days_late_nonseasonal"] - X["avg_days_late_nonseasonal"].mean()) / X["avg_days_late_nonseasonal"].std()
    z_vol = (X["payment_volatility"] - X["payment_volatility"].mean()) / X["payment_volatility"].std()
    X_composite["payment_delay_severity"] = (z_late + z_vol) / 2
    X_composite = X_composite.drop(columns=["avg_days_late_nonseasonal", "payment_volatility"])

    new_feature_cols = X_composite.columns.tolist()
    X_composite_s = pd.DataFrame(StandardScaler().fit_transform(X_composite), columns=new_feature_cols)

    vif_new = pd.DataFrame()
    vif_new["feature"] = new_feature_cols
    vif_new["VIF"] = [variance_inflation_factor(X_composite_s.values, i) for i in range(len(new_feature_cols))]
    vif_new = vif_new.sort_values("VIF", ascending=False)
    print("--- VIF after remediation ---")
    print(vif_new.round(2).to_string(index=False))
    print()

    def evaluate(X_in, y_in, label):
        X_train, X_test, y_train, y_test = train_test_split(
            X_in, y_in, test_size=0.3, random_state=42, stratify=y_in
        )
        sc = StandardScaler()
        X_train_s = sc.fit_transform(X_train)
        X_test_s = sc.transform(X_test)
        model = LogisticRegression(max_iter=1000, class_weight="balanced")
        model.fit(X_train_s, y_train)
        probs = model.predict_proba(X_test_s)[:, 1]
        auc = roc_auc_score(y_test, probs)

        def ks_stat(y_true, y_prob):
            d = pd.DataFrame({"y": y_true, "p": y_prob}).sort_values("p")
            d["cum_bad"] = (d["y"] == 1).cumsum() / (d["y"] == 1).sum()
            d["cum_good"] = (d["y"] == 0).cumsum() / (d["y"] == 0).sum()
            return np.max(np.abs(d["cum_bad"] - d["cum_good"]))
        ks = ks_stat(y_test.values, probs)

        coefs = pd.DataFrame({"feature": X_in.columns, "coefficient": model.coef_[0]})
        coefs = coefs.sort_values("coefficient", key=abs, ascending=False)
        print(f"[{label}] AUC: {auc:.3f} | KS: {ks:.3f}")
        print(coefs.round(3).to_string(index=False))
        print()
        return auc, ks

    print("=" * 60)
    print("BEFORE vs AFTER REMEDIATION")
    print("=" * 60)
    evaluate(X, y, "ORIGINAL 7 FEATURES")
    evaluate(X_composite, y, "REMEDIATED: 6 FEATURES (payment_delay_severity composite)")
