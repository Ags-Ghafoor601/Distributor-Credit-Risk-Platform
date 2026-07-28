"""
*** DEPRECATED — SUPERSEDED, DO NOT USE FOR NEW SCORING RUNS ***
This script served its purpose (found and fixed the D0055 coverage bug,
introduced the VIF-clean 6-feature set and reason codes) but is no longer
the canonical scoring pipeline. It independently re-implements feature
engineering that now lives in train_and_save_model.py / score_dealers.py,
creating a real risk of silent drift between two "sources of truth" -- this
is exactly what caused a one-off score discrepancy (D0080: 418 vs 425)
during Day 4 presentation-building. See CHANGELOG.md for the full story.

CANONICAL PIPELINE GOING FORWARD:
  1. train_and_save_model.py  -> trains once, saves credit_risk_model.joblib
  2. score_dealers.py         -> loads that artifact, scores all dealers
  3. run_pipeline.py          -> orchestrates ingestion + scoring + cards end-to-end

Kept in the repo for historical reference only.
*** END DEPRECATION NOTICE ***

Unified Scoring Pipeline — routes EVERY dealer to the correct scoring path
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2

FIXES A REAL BUG: previous scripts inner-joined feature data with label
data to build the training set, then used that SAME joined table as the
"final scored output" -- silently dropping any dealer who had enough
FEATURE history to be scored but not enough LABEL-window history to be
used for training/validation (e.g. D0055: 40+ historical invoices, but
only 2 in the 2025 outcome window). That dealer was invisible in every
prior deliverable, with no error or warning.

This pipeline separates the two concerns correctly:
  - TRAINING POOL: dealers with sufficient history in BOTH windows (used
    only to fit and validate the model)
  - SCORING POOL: every dealer with sufficient FEATURE history gets scored
    by the trained model, whether or not they were part of training
  - COLD-START POOL: dealers with insufficient FEATURE history entirely
    get routed to the rule-based provisional scorer instead

Also uses the VIF-remediated 6-feature set (payment_delay_severity
composite) instead of the original 7 collinear features.
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
MIN_INVOICES_FOR_FEATURES = 3   # minimum to compute reliable behavior features
MIN_INVOICES_FOR_LABEL = 3      # minimum to compute a trustworthy forward-looking label

pd.options.mode.chained_assignment = None

dealers = pd.read_csv("dealers.csv", parse_dates=["onboarding_date"])
salesmen = pd.read_csv("salesmen.csv")
txns = pd.read_csv("transactions.csv",
                    parse_dates=["invoice_date", "due_date", "payment_date"])

feature_window = txns[txns["due_date"] < CUTOFF_DATE]
label_window = txns[(txns["due_date"] >= CUTOFF_DATE) & (txns["due_date"] <= LABEL_WINDOW_END)]

# ---------------------------------------------------------------------------
# STEP 1: Build features for EVERY dealer with sufficient feature-window
# history (this is the full SCORING population, not just the training set)
# ---------------------------------------------------------------------------
feat_rows = []
insufficient_feature_history = []

for dealer_id, dealer_row in dealers.set_index("dealer_id").iterrows():
    dgrp = feature_window[feature_window["dealer_id"] == dealer_id]
    if len(dgrp) < MIN_INVOICES_FOR_FEATURES:
        insufficient_feature_history.append(dealer_id)
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
        "dealer_id": dealer_id, "salesman_id": dealer_row["salesman_id"],
        "territory_risk_tier": dealer_row["territory_risk_tier"],
        "sector": dealer_row["sector"], "is_salesman_favorite": dealer_row["is_salesman_favorite"],
        "dealer_name": dealer_row["dealer_name"], "city": dealer_row["city"],
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

# VIF-remediated composite feature (replaces the two collinear features)
z_late = (feat_df["avg_days_late_nonseasonal"] - feat_df["avg_days_late_nonseasonal"].mean()) / feat_df["avg_days_late_nonseasonal"].std()
z_vol = (feat_df["payment_volatility"] - feat_df["payment_volatility"].mean()) / feat_df["payment_volatility"].std()
feat_df["payment_delay_severity"] = (z_late + z_vol) / 2

FEATURE_COLS = [
    "payment_delay_severity", "bounce_rate_lifetime", "real_exposure_pkr",
    "order_frequency_trend", "salesman_default_rate_loo", "territory_default_rate_loo",
]

print(f"Dealers with sufficient FEATURE history (scoreable via statistical model): {len(feat_df)}")
print(f"Dealers with INSUFFICIENT feature history (route to cold-start): {insufficient_feature_history if insufficient_feature_history else 'NONE'}")
print()

# ---------------------------------------------------------------------------
# STEP 2: Build labels ONLY for dealers with sufficient LABEL-window history
# (used ONLY to train/validate -- NOT to decide who gets scored)
# ---------------------------------------------------------------------------
label_rows = []
for dealer_id, dgrp in label_window.groupby("dealer_id"):
    if len(dgrp) < MIN_INVOICES_FOR_LABEL:
        continue
    non_bounced = dgrp[dgrp["cheque_bounced"] == False]
    avg_late = non_bounced["days_late"].mean() if len(non_bounced) else 0
    bounced_any = dgrp["cheque_bounced"].any()
    is_high_risk = int(bounced_any or (avg_late > LATE_LABEL_THRESHOLD_DAYS))
    label_rows.append({"dealer_id": dealer_id, "is_high_risk": is_high_risk})
label_df = pd.DataFrame(label_rows)

training_pool = feat_df.merge(label_df, on="dealer_id", how="inner")
unvalidated_but_scoreable = set(feat_df["dealer_id"]) - set(training_pool["dealer_id"])

print(f"Training/validation pool (has BOTH feature + label history): {len(training_pool)}")
print(f"Scoreable but NOT usable for training (feature history OK, label window thin): "
      f"{sorted(unvalidated_but_scoreable) if unvalidated_but_scoreable else 'NONE'}")
print()

# ---------------------------------------------------------------------------
# STEP 3: Train + validate on the training pool only
# ---------------------------------------------------------------------------
X_train_pool = training_pool[FEATURE_COLS]
y_train_pool = training_pool["is_high_risk"]

X_tr, X_te, y_tr, y_te = train_test_split(
    X_train_pool, y_train_pool, test_size=0.3, random_state=42, stratify=y_train_pool
)
val_scaler = StandardScaler()
X_tr_s = val_scaler.fit_transform(X_tr)
X_te_s = val_scaler.transform(X_te)
val_model = LogisticRegression(max_iter=1000, class_weight="balanced")
val_model.fit(X_tr_s, y_tr)
val_auc = roc_auc_score(y_te, val_model.predict_proba(X_te_s)[:, 1])
print(f"Validation check (out-of-time holdout): AUC = {val_auc:.3f}")
print()

# ---------------------------------------------------------------------------
# STEP 4: PRODUCTION model -- refit on full training pool, then score
# EVERY dealer in feat_df (the full scoring population), not just those
# used for training. THIS is the fix -- scoring is no longer gated by
# label availability.
# ---------------------------------------------------------------------------
prod_scaler = StandardScaler()
X_all_train_s = prod_scaler.fit_transform(X_train_pool)
prod_model = LogisticRegression(max_iter=1000, class_weight="balanced")
prod_model.fit(X_all_train_s, y_train_pool)

X_score_all = feat_df[FEATURE_COLS]
X_score_all_s = prod_scaler.transform(X_score_all)
feat_df["risk_probability"] = prod_model.predict_proba(X_score_all_s)[:, 1]

BASE_SCORE, BASE_ODDS, PDO = 600, 1 / 19, 40
factor = PDO / np.log(2)
offset = BASE_SCORE - factor * np.log(BASE_ODDS)

def prob_to_score(prob_bad):
    prob_bad = np.clip(prob_bad, 1e-6, 1 - 1e-6)
    odds_good = (1 - prob_bad) / prob_bad
    return np.clip(offset + factor * np.log(odds_good), 300, 900)

feat_df["credit_score"] = prob_to_score(feat_df["risk_probability"]).round(0)
feat_df["risk_flag"] = pd.cut(
    feat_df["credit_score"], bins=[0, 580, 700, 900],
    labels=["RED (High Risk)", "AMBER (Moderate)", "GREEN (Reliable)"]
)
feat_df["scoring_method"] = feat_df["dealer_id"].apply(
    lambda d: "Statistical (validated in training)" if d in set(training_pool["dealer_id"])
    else "Statistical (scored, not used in training — thin recent activity)"
)

# ---------------------------------------------------------------------------
# STEP 4b: REASON CODES for every statistically-scored dealer, via the
# same additive log-odds decomposition used since Step 5 -- coefficient x
# standardized feature value. Uses the VIF-remediated 6-feature model,
# so labels/mapping must match payment_delay_severity, not the old pair.
# ---------------------------------------------------------------------------
REASON_LABELS = {
    "payment_delay_severity": "Late and inconsistent payment timing",
    "bounce_rate_lifetime": "Cheque bounce history",
    "real_exposure_pkr": "Inflation-adjusted credit exposure",
    "order_frequency_trend": "Declining order activity",
    "salesman_default_rate_loo": "Salesman's track record with similar dealers",
    "territory_default_rate_loo": "Elevated risk in dealer's territory",
}

contributions = X_score_all_s * prod_model.coef_[0]
contrib_df = pd.DataFrame(contributions, columns=FEATURE_COLS, index=feat_df.index)

def top_reasons(idx, n=3):
    row = contrib_df.loc[idx]
    row_sorted = row.reindex(row.abs().sort_values(ascending=False).index)
    top = row_sorted.head(n)
    return [
        {"factor": REASON_LABELS[f], "direction": "increases_risk" if v > 0 else "reduces_risk", "weight": round(float(v), 3)}
        for f, v in top.items()
    ]

feat_df["top_reasons"] = [top_reasons(i) for i in feat_df.index]

# ---------------------------------------------------------------------------
# STEP 5: Cold-start scoring for dealers with insufficient FEATURE history
# ---------------------------------------------------------------------------
dealer_bounce = txns.groupby("dealer_id")["cheque_bounced"].mean()
dealers_with_rate = dealers.set_index("dealer_id").join(dealer_bounce.rename("bounce_rate"))
dealers_with_rate["bounce_rate"] = dealers_with_rate["bounce_rate"].fillna(0)
salesman_track_record = dealers_with_rate.groupby("salesman_id")["bounce_rate"].mean()
territory_baseline = dealers_with_rate.groupby("territory_risk_tier")["bounce_rate"].mean()
sector_baseline = dealers_with_rate.groupby("sector")["bounce_rate"].mean()

_all_blended = []
for _, d in dealers.iterrows():
    sr = salesman_track_record.get(d["salesman_id"], dealer_bounce.mean())
    tr = territory_baseline.get(d["territory_risk_tier"], dealer_bounce.mean())
    secr = sector_baseline.get(d["sector"], dealer_bounce.mean())
    _all_blended.append(0.5 * sr + 0.3 * tr + 0.2 * secr)
_blended_min, _blended_max = min(_all_blended), max(_all_blended)

cold_start_rows = []
for dealer_id in insufficient_feature_history:
    d = dealers[dealers["dealer_id"] == dealer_id].iloc[0]
    sr = salesman_track_record.get(d["salesman_id"], dealer_bounce.mean())
    tr = territory_baseline.get(d["territory_risk_tier"], dealer_bounce.mean())
    secr = sector_baseline.get(d["sector"], dealer_bounce.mean())
    blended = 0.5 * sr + 0.3 * tr + 0.2 * secr
    normalized = (blended - _blended_min) / (_blended_max - _blended_min + 1e-9)
    score = np.clip(680 - (normalized * 200), 480, 680)
    tier = "AMBER (Provisional — Elevated Caution)" if score < 560 else "AMBER (Provisional — Standard Caution)"
    cold_start_rows.append({
        "dealer_id": dealer_id, "dealer_name": d["dealer_name"], "city": d["city"],
        "sector": d["sector"], "salesman_id": d["salesman_id"],
        "is_salesman_favorite": d["is_salesman_favorite"],
        "credit_limit_pkr": d["credit_limit_pkr"],
        "credit_score": round(score), "risk_flag": tier,
        "risk_probability": np.nan,
        "scoring_method": "Provisional (Cold-Start — insufficient history)",
        "top_reasons": [
            {"factor": "Insufficient payment history — score based on salesman/territory/sector averages only",
             "direction": "increases_risk" if score < 600 else "reduces_risk", "weight": None}
        ],
        "avg_days_late_nonseasonal": np.nan, "payment_volatility": np.nan,
        "bounce_rate_lifetime": np.nan,
    })
cold_start_df = pd.DataFrame(cold_start_rows, columns=[
    "dealer_id", "dealer_name", "city", "sector", "salesman_id", "is_salesman_favorite",
    "credit_limit_pkr", "credit_score", "risk_flag", "risk_probability", "scoring_method",
    "top_reasons", "avg_days_late_nonseasonal", "payment_volatility", "bounce_rate_lifetime",
])

# ---------------------------------------------------------------------------
# STEP 6: UNIFY into a single output covering ALL 220 dealers, with full
# fields needed for both the risk table AND the Risk Card generator
# ---------------------------------------------------------------------------
feat_df["credit_limit_pkr"] = feat_df["dealer_id"].map(dealers.set_index("dealer_id")["credit_limit_pkr"])
feat_df = feat_df.merge(salesmen[["salesman_id", "salesman_name"]], on="salesman_id", how="left")
cold_start_df = cold_start_df.merge(salesmen[["salesman_id", "salesman_name"]], on="salesman_id", how="left")

full_cols = ["dealer_id", "dealer_name", "city", "sector", "salesman_id", "salesman_name",
             "is_salesman_favorite", "credit_limit_pkr", "credit_score", "risk_flag",
             "risk_probability", "scoring_method", "top_reasons",
             "avg_days_late_nonseasonal", "payment_volatility", "bounce_rate_lifetime"]

statistical_out = feat_df[full_cols]
unified_full = pd.concat([statistical_out, cold_start_df[full_cols]], ignore_index=True)
unified_full = unified_full.sort_values("credit_score").reset_index(drop=True)

unified = unified_full[["dealer_id", "dealer_name", "city", "salesman_id",
                          "is_salesman_favorite", "credit_score", "risk_flag", "scoring_method"]]
unified.to_csv("dealer_risk_table_unified.csv", index=False)

unified_full = unified_full.rename(columns={"risk_probability": "risk_probability_calibrated"})
unified_full.to_json("dealer_cards_data.json", orient="records", indent=2)
print(f"Exported dealer_cards_data.json with {len(unified_full)} dealers (was 219 before this fix)")

print("=" * 75)
print("COVERAGE CHECK: does the unified table now include ALL 220 dealers?")
print("=" * 75)
print(f"Total dealers in master list: {len(dealers)}")
print(f"Total dealers in unified output: {len(unified)}")
print(f"D0055 present in unified output: {'D0055' in unified['dealer_id'].values}")
if "D0055" in unified["dealer_id"].values:
    row = unified[unified["dealer_id"] == "D0055"].iloc[0]
    print(f"  -> D0055: score={row['credit_score']}, flag={row['risk_flag']}, method={row['scoring_method']}")
print()
print("Scoring method breakdown:")
print(unified["scoring_method"].value_counts().to_string())
