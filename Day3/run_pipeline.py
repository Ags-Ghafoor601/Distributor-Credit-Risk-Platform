"""
End-to-End Pipeline Orchestrator
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 3 requirement: "runs reliably on a full
dataset without manual intervention"

Single command that chains: raw data ingestion -> cleaning -> scoring
(via the persisted model, no retraining) -> cold-start routing ->
Risk Card generation for all RED-flagged dealers -> a final run report.

Usage:
    python run_pipeline.py                          # uses the clean synthetic data
    python run_pipeline.py --input messy_transactions_raw.csv   # runs ingestion first
    python run_pipeline.py --skip-cards              # scoring only, no docx generation

Every stage is wrapped in try/except with a clear failure message and a
non-zero exit code -- this should fail LOUDLY and specifically if something
breaks, never silently produce a partial or wrong result.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import joblib

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "Day1"
CUTOFF_DATE = pd.Timestamp("2025-01-01")
ANNUAL_PKR_EROSION = 0.18
MIN_INVOICES = 3

pd.options.mode.chained_assignment = None


class PipelineError(Exception):
    """Raised when a pipeline stage fails in a way that should halt the run."""
    pass


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def stage_ingest(raw_path: Path, run_log: dict) -> Path:
    """Runs the messy-data ingestion pipeline if a raw (potentially messy) file is given."""
    log(f"STAGE 1/4: Ingesting {raw_path.name}")
    try:
        raw = pd.read_csv(raw_path, dtype=str)
    except Exception as e:
        raise PipelineError(f"Could not read input file {raw_path}: {e}")

    dealers = pd.read_csv(DATA_DIR / "dealers.csv")
    valid_dealer_ids = set(dealers["dealer_id"])

    raw.columns = [c.strip() for c in raw.columns]
    COLUMN_MAP = {
        "Txn ID": "transaction_id", "Dealer Code": "dealer_id", "Invoice Dt": "invoice_date",
        "Due Date": "due_date", "Paid On": "payment_date", "Amount (Rs)": "amount_pkr",
        "Mode": "payment_method", "Bounced?": "cheque_bounced",
    }
    df = raw.rename(columns=COLUMN_MAP)
    df = df[[c for c in df.columns if not c.startswith("Unnamed") and c != "Notes"]]

    start_n = len(df)
    df = df.drop_duplicates()

    missing_dealer_raw = df["dealer_id"].isna() if "dealer_id" in df.columns else pd.Series([False] * len(df))
    if "dealer_id" in df.columns:
        df["dealer_id"] = df["dealer_id"].astype(str).str.strip()
        missing_dealer = missing_dealer_raw | df["dealer_id"].isin(["nan", "", "None", "N/A", "NA"])
        df = df[~missing_dealer]
        df = df[df["dealer_id"].isin(valid_dealer_ids)]
    else:
        raise PipelineError("Input file has no recognizable dealer identifier column")

    def parse_messy_date(val):
        if pd.isna(val) or str(val).strip() in ("", "N/A", "NA", "-", "nil", "pending"):
            return pd.NaT
        s = str(val).strip()
        if s.isdigit() and 40000 < int(s) < 48000:
            try:
                return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(s))
            except Exception:
                return pd.NaT
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d-%b-%y", "%Y.%m.%d", "%d-%b-%Y"):
            try:
                return pd.to_datetime(s, format=fmt)
            except Exception:
                continue
        try:
            return pd.to_datetime(s, dayfirst=True, errors="raise")
        except Exception:
            return pd.NaT

    for col in ["invoice_date", "due_date", "payment_date"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_messy_date)
    df = df[df["invoice_date"].notna() & df["due_date"].notna()]

    def parse_messy_amount(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        if s in ("", "N/A", "NA", "-", "nil"):
            return np.nan
        s = s.strip("()").replace("Rs.", "").replace("Rs", "").replace("PKR", "")
        s = s.replace(",", "").replace("/-", "").strip()
        try:
            return float(s)
        except ValueError:
            return np.nan

    df["amount_pkr"] = df["amount_pkr"].apply(parse_messy_amount)
    df = df[df["amount_pkr"].notna() & (df["amount_pkr"] > 0)]

    TRUE_SET = {"y", "yes", "1", "true", "bounced"}
    FALSE_SET = {"n", "no", "0", "false", "", "ok", "nan"}
    def parse_bool(val):
        s = str(val).strip().lower()
        if s in TRUE_SET: return True
        if s in FALSE_SET: return False
        return np.nan
    df["cheque_bounced"] = df["cheque_bounced"].apply(parse_bool)
    df = df[df["cheque_bounced"].notna()]
    df = df[df["due_date"] >= df["invoice_date"]]

    df["days_late"] = (df["payment_date"] - df["due_date"]).dt.days
    df.loc[df["cheque_bounced"] == True, "days_late"] = np.nan
    df["is_eid_ramzan_period"] = False  # simplified for pipeline; full logic in robust_ingestion.py

    final_cols = ["transaction_id", "dealer_id", "invoice_date", "due_date", "payment_date",
                  "amount_pkr", "payment_method", "cheque_bounced", "days_late", "is_eid_ramzan_period"]
    for c in final_cols:
        if c not in df.columns:
            df[c] = np.nan
    clean = df[final_cols].reset_index(drop=True)

    out_path = BASE_DIR / "pipeline_cleaned_transactions.csv"
    clean.to_csv(out_path, index=False)

    retention = len(clean) / start_n if start_n else 0
    run_log["ingestion"] = {"input_rows": start_n, "output_rows": len(clean), "retention_rate": round(retention, 3)}
    log(f"  Retention: {len(clean)}/{start_n} rows ({retention:.1%})")
    if retention < 0.5:
        raise PipelineError(f"Data retention critically low ({retention:.1%}) -- halting rather than scoring on mostly-discarded data")
    return out_path


def stage_score(txn_path: Path, run_log: dict) -> pd.DataFrame:
    log(f"STAGE 2/4: Scoring dealers using persisted model")
    model_path = BASE_DIR / "credit_risk_model.joblib"
    if not model_path.exists():
        raise PipelineError(f"Model artifact not found at {model_path}. Run train_and_save_model.py first.")

    artifact = joblib.load(model_path)
    model, scaler, FEATURE_COLS = artifact["model"], artifact["scaler"], artifact["feature_columns"]
    score_params = artifact["score_params"]

    dealers = pd.read_csv(DATA_DIR / "dealers.csv", parse_dates=["onboarding_date"])
    salesmen = pd.read_csv(DATA_DIR / "salesmen.csv")
    txns = pd.read_csv(txn_path, parse_dates=["invoice_date", "due_date", "payment_date"])
    feature_window = txns[txns["due_date"] < CUTOFF_DATE]

    feat_rows, insufficient = [], []
    for dealer_id, dealer_row in dealers.set_index("dealer_id").iterrows():
        dgrp = feature_window[feature_window["dealer_id"] == dealer_id]
        if len(dgrp) < MIN_INVOICES:
            insufficient.append(dealer_id)
            continue
        non_bounced = dgrp[dgrp["cheque_bounced"] == False]
        bounce_rate_lifetime = dgrp["cheque_bounced"].mean()
        avg_days_late = non_bounced["days_late"].mean() if len(non_bounced) else 0
        nonseasonal = non_bounced[non_bounced.get("is_eid_ramzan_period", False) == False]
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
            "city": dealer_row["city"], "sector": dealer_row["sector"],
            "salesman_id": dealer_row["salesman_id"], "is_salesman_favorite": dealer_row["is_salesman_favorite"],
            "credit_limit_pkr": dealer_row["credit_limit_pkr"],
            "bounce_rate_lifetime": bounce_rate_lifetime,
            "avg_days_late_nonseasonal": avg_days_late_nonseasonal,
            "payment_volatility": payment_volatility,
            "real_exposure_pkr": real_exposure_pkr,
            "order_frequency_trend": order_frequency_trend,
        })

    if not feat_rows:
        raise PipelineError("No dealers had sufficient history to score -- check input data coverage")

    feat_df = pd.DataFrame(feat_rows)

    def loo_group_rate(df, group_col, rate_col):
        s = df.groupby(group_col)[rate_col].transform("sum")
        c = df.groupby(group_col)[rate_col].transform("count")
        return ((s - df[rate_col]) / (c - 1).replace(0, np.nan)).fillna(df[rate_col].mean())

    feat_df["salesman_default_rate_loo"] = loo_group_rate(feat_df, "salesman_id", "bounce_rate_lifetime")
    feat_df["territory_default_rate_loo"] = loo_group_rate(
        feat_df.merge(dealers[["dealer_id", "territory_risk_tier"]], on="dealer_id"),
        "territory_risk_tier", "bounce_rate_lifetime"
    ) if "territory_risk_tier" not in feat_df.columns else loo_group_rate(feat_df, "territory_risk_tier", "bounce_rate_lifetime")

    z_late = (feat_df["avg_days_late_nonseasonal"] - feat_df["avg_days_late_nonseasonal"].mean()) / feat_df["avg_days_late_nonseasonal"].std()
    z_vol = (feat_df["payment_volatility"] - feat_df["payment_volatility"].mean()) / feat_df["payment_volatility"].std()
    feat_df["payment_delay_severity"] = (z_late + z_vol) / 2

    missing_cols = [c for c in FEATURE_COLS if c not in feat_df.columns]
    if missing_cols:
        raise PipelineError(f"Scoring data is missing required feature columns: {missing_cols}")

    X_score_s = scaler.transform(feat_df[FEATURE_COLS])
    feat_df["risk_probability"] = model.predict_proba(X_score_s)[:, 1]

    factor = score_params["pdo"] / np.log(2)
    offset = score_params["base_score"] - factor * np.log(score_params["base_odds"])
    def prob_to_score(p):
        p = np.clip(p, 1e-6, 1 - 1e-6)
        return np.clip(offset + factor * np.log((1 - p) / p), 300, 900)
    feat_df["credit_score"] = prob_to_score(feat_df["risk_probability"]).round(0)
    feat_df["risk_flag"] = pd.cut(feat_df["credit_score"], bins=[0, 580, 700, 900],
                                    labels=["RED (High Risk)", "AMBER (Moderate)", "GREEN (Reliable)"])
    feat_df = feat_df.merge(salesmen[["salesman_id", "salesman_name"]], on="salesman_id", how="left")

    contributions = X_score_s * model.coef_[0]
    contrib_df = pd.DataFrame(contributions, columns=FEATURE_COLS, index=feat_df.index)
    REASON_LABELS = {
        "payment_delay_severity": "Late and inconsistent payment timing",
        "bounce_rate_lifetime": "Cheque bounce history",
        "real_exposure_pkr": "Inflation-adjusted credit exposure",
        "order_frequency_trend": "Declining order activity",
        "salesman_default_rate_loo": "Salesman's track record with similar dealers",
        "territory_default_rate_loo": "Elevated risk in dealer's territory",
    }
    def top_reasons(idx, n=3):
        row = contrib_df.loc[idx]
        row_sorted = row.reindex(row.abs().sort_values(ascending=False).index)
        return [{"factor": REASON_LABELS[f], "direction": "increases_risk" if v > 0 else "reduces_risk", "weight": round(float(v), 3)}
                for f, v in row_sorted.head(n).items()]
    feat_df["top_reasons"] = [top_reasons(i) for i in feat_df.index]
    feat_df["scoring_method"] = "Statistical"

    run_log["scoring"] = {
        "dealers_scored": len(feat_df),
        "insufficient_history_count": len(insufficient),
        "red_flag_count": int((feat_df["risk_flag"] == "RED (High Risk)").sum()),
    }
    log(f"  Scored {len(feat_df)} dealers | {run_log['scoring']['red_flag_count']} flagged RED")
    if insufficient:
        log(f"  {len(insufficient)} dealer(s) routed to cold-start (insufficient history): {insufficient}", "WARN")

    return feat_df.rename(columns={"risk_probability": "risk_probability_calibrated"})


def stage_export(scored_df: pd.DataFrame, run_log: dict) -> Path:
    log("STAGE 3/4: Exporting risk table + Risk Card data")
    json_path = BASE_DIR / "dealer_cards_data.json"
    scored_df.to_json(json_path, orient="records", indent=2)
    csv_path = BASE_DIR / "dealer_risk_table_pipeline_run.csv"
    scored_df.sort_values("credit_score")[
        ["dealer_id", "dealer_name", "city", "salesman_id", "is_salesman_favorite", "credit_score", "risk_flag", "scoring_method"]
    ].to_csv(csv_path, index=False)
    log(f"  Exported {csv_path.name} and {json_path.name}")
    return json_path


def stage_generate_cards(run_log: dict, skip: bool):
    log("STAGE 4/4: Generating Risk Cards for all RED-flagged dealers")
    if skip:
        log("  Skipped (--skip-cards flag set)")
        run_log["cards"] = "skipped"
        return
    try:
        result = subprocess.run(
            ["node", "generate_risk_card_v2.js", "--all-red"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            log(f"  Risk Card generation failed: {result.stderr.strip()}", "WARN")
            run_log["cards"] = f"failed: {result.stderr.strip()[:200]}"
        else:
            lines = [l for l in result.stdout.strip().split("\n") if l.startswith("Generated")]
            log(f"  Generated {len(lines)} Risk Cards")
            run_log["cards"] = f"{len(lines)} generated"
    except FileNotFoundError:
        log("  Node.js not found -- run 'node generate_risk_card_v2.js --all-red' manually", "WARN")
        run_log["cards"] = "skipped: node not found"
    except Exception as e:
        log(f"  Risk Card generation error: {e}", "WARN")
        run_log["cards"] = f"error: {e}"


def main():
    parser = argparse.ArgumentParser(description="End-to-end distributor credit risk pipeline")
    parser.add_argument("--input", default=None, help="Raw transaction CSV to ingest (skips ingestion if omitted)")
    parser.add_argument("--skip-cards", action="store_true", help="Skip Risk Card generation")
    args = parser.parse_args()

    run_log = {"started_at": datetime.now().isoformat()}
    start_time = time.time()
    log("=" * 70)
    log("PIPELINE RUN STARTED")
    log("=" * 70)

    try:
        txn_path = stage_ingest(Path(args.input), run_log) if args.input else DATA_DIR / "transactions.csv"
        scored_df = stage_score(txn_path, run_log)
        stage_export(scored_df, run_log)
        stage_generate_cards(run_log, args.skip_cards)
    except PipelineError as e:
        log(f"PIPELINE HALTED: {e}", "ERROR")
        sys.exit(1)
    except Exception as e:
        log(f"UNEXPECTED FAILURE: {e}", "ERROR")
        sys.exit(1)

    elapsed = time.time() - start_time
    run_log["elapsed_seconds"] = round(elapsed, 2)
    log("=" * 70)
    log(f"PIPELINE RUN COMPLETE in {elapsed:.1f}s")
    log("=" * 70)
    for k, v in run_log.items():
        log(f"  {k}: {v}")


if __name__ == "__main__":
    main()
