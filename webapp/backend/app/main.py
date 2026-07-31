"""
FastAPI Backend — Distributor Credit Risk Scoring
Problem 01: Distributor Credit Risk on Gut Feel

Exposes the VERIFIED pipeline module (app/pipeline.py) as HTTP endpoints.
This file contains NO scoring logic of its own -- it only orchestrates
calls into pipeline.py, so there is exactly one implementation of the
scoring math, not two.
"""

import io
import os
import time
import uuid
import json
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.pipeline import compute_features, score_with_model, cold_start_score, clean_transactions, build_risk_card_docx, resolve_cutoff_date, normalize_dealers, normalize_salesmen, build_reliability_report, assess_distribution_shift, try_train_on_uploaded_data, TRANSACTION_COLUMN_ALIASES, _canon

app = FastAPI(title="Distributor Credit Risk API")

# Rate limiting: protects the expensive /api/score endpoint from being
# hammered. Keyed by client IP -- note that behind a reverse proxy (Render,
# Railway, etc.) this needs the proxy to forward the real client IP via
# X-Forwarded-For, which most standard hosting setups do by default.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: locked to explicit origins via env var, comma-separated. Defaults to
# local dev only -- once deployed, set ALLOWED_ORIGINS to the real frontend
# URL(s), since "*" would let any website on the internet call this API
# directly on a visitor's behalf.
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_ARTIFACT = joblib.load("model/credit_risk_model.joblib")

# Upload safety limits -- prevent a single huge file from hanging the
# per-dealer feature-engineering loop or exhausting server memory.
MAX_FILE_SIZE_BYTES = int(os.environ.get("MAX_FILE_SIZE_BYTES", 20 * 1024 * 1024))  # 20MB per file
MAX_TRANSACTION_ROWS = int(os.environ.get("MAX_TRANSACTION_ROWS", 200_000))

REQUIRED_SALESMAN_COLUMNS = ["salesman_id", "salesman_name"]

def looks_like_transactions_file(raw_bytes: bytes) -> bool:
    """Header-only sanity check that catches an obviously wrong file (e.g. a
    dealers file uploaded into the transactions slot).

    Built on the SAME alias map the cleaner uses. The previous version had its
    own narrow hardcoded list, so it rejected real headers like 'Customer Code'
    that the pipeline could actually parse -- a gate stricter than the engine
    behind it.
    """
    try:
        header_df = pd.read_csv(io.BytesIO(raw_bytes), nrows=0)
    except Exception:
        return False
    canon = {_canon(c) for c in header_df.columns}
    has_dealer_col = bool(canon & TRANSACTION_COLUMN_ALIASES["dealer_id"])
    date_or_amount = (TRANSACTION_COLUMN_ALIASES["invoice_date"]
                      | TRANSACTION_COLUMN_ALIASES["due_date"]
                      | TRANSACTION_COLUMN_ALIASES["payment_date"]
                      | TRANSACTION_COLUMN_ALIASES["amount_pkr"])
    return has_dealer_col and bool(canon & date_or_amount)

# In-memory session store: uploaded/scored data keyed by a session id, each
# entry tagged with its creation time. NOTE: still in-memory (fine for a
# single-instance demo deployment); a persistent-storage real deployment
# would replace this with a database or object store, and would need this
# same TTL/eviction logic ported over regardless of storage backend.
SESSIONS: dict = {}
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", 3600))
MAX_SESSIONS = int(os.environ.get("MAX_SESSIONS", 500))


def cleanup_expired_sessions():
    """Removes sessions older than SESSION_TTL_SECONDS, then -- as a defensive
    second layer -- evicts the oldest remaining sessions if the store still
    exceeds MAX_SESSIONS (protects against a burst of uploads exhausting
    memory even within the TTL window)."""
    now = time.time()
    expired = [sid for sid, s in SESSIONS.items() if now - s["created_at"] > SESSION_TTL_SECONDS]
    for sid in expired:
        del SESSIONS[sid]

    if len(SESSIONS) > MAX_SESSIONS:
        oldest_first = sorted(SESSIONS.items(), key=lambda kv: kv[1]["created_at"])
        for sid, _ in oldest_first[: len(SESSIONS) - MAX_SESSIONS]:
            del SESSIONS[sid]


def get_session_or_404(session_id: str) -> dict:
    """Single point of session lookup -- runs cleanup first so an expired
    session correctly reports 404 rather than serving stale data."""
    cleanup_expired_sessions()
    if session_id not in SESSIONS:
        raise HTTPException(404, "Session not found or expired")
    return SESSIONS[session_id]


async def read_upload_with_limit(file: UploadFile, label: str) -> bytes:
    """Reads an uploaded file's bytes while enforcing MAX_FILE_SIZE_BYTES --
    rejects oversized uploads before they ever reach pandas, rather than
    letting a huge file hang the server first and fail later."""
    data = await file.read()
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            413,
            f"{label} file is {len(data) / (1024*1024):.1f}MB, exceeding the "
            f"{MAX_FILE_SIZE_BYTES / (1024*1024):.0f}MB limit per file."
        )
    return data

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Starlette's default 500 bypasses the CORS middleware, so any crash
    reaches the browser as a misleading 'No Access-Control-Allow-Origin'
    error. Returning the response ourselves keeps the CORS headers attached
    and lets the frontend show what actually went wrong."""
    origin = request.headers.get("origin", "")
    headers = {"Access-Control-Allow-Origin": origin} if origin in ALLOWED_ORIGINS else {}
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
        headers=headers,
    )

@app.get("/api/health")
def health():
    return {"status": "ok", "model_trained_on": MODEL_ARTIFACT["metadata"]["trained_on"]}


@app.post("/api/score")
@limiter.limit("5/10minutes")
async def score_portfolio(
    request: Request,
    dealers_file: UploadFile = File(...),
    salesmen_file: UploadFile = File(...),
    transactions_file: UploadFile = File(...),
):
    """
    Accepts the 3 uploaded CSVs, runs ingestion + scoring, returns a
    session_id plus the scored results. Frontend polls/renders from this.
    """
    try:
        dealers_bytes = await read_upload_with_limit(dealers_file, "dealers")
        salesmen_bytes = await read_upload_with_limit(salesmen_file, "salesmen")
        dealers = pd.read_csv(io.BytesIO(dealers_bytes))
        salesmen = pd.read_csv(io.BytesIO(salesmen_bytes))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not parse dealers/salesmen file: {e}")

    try:
        dealers, dealer_notes = normalize_dealers(dealers)
        salesmen, salesmen_notes = normalize_salesmen(salesmen)
    except ValueError as e:
        raise HTTPException(400, str(e))
    input_notes = dealer_notes + salesmen_notes

    valid_dealer_ids = set(dealers["dealer_id"])
    txn_bytes = await read_upload_with_limit(transactions_file, "transactions")

    if not looks_like_transactions_file(txn_bytes):
        raise HTTPException(
            400,
            "The transactions file doesn't look like a payment history export -- "
            "expected at least a dealer identifier column and a date or amount "
            "column. Check that the correct file was uploaded in the correct slot."
        )

    try:
        cleaned_txns, quality_report = clean_transactions(txn_bytes, valid_dealer_ids)
    except Exception as e:
        raise HTTPException(400, f"Could not process transactions file: {e}")

    if len(cleaned_txns) > MAX_TRANSACTION_ROWS:
        raise HTTPException(
            413,
            f"Transactions file has {len(cleaned_txns):,} valid rows, exceeding the "
            f"{MAX_TRANSACTION_ROWS:,}-row limit per upload."
        )

    if quality_report["retention_rate"] < 0.5:
        raise HTTPException(
            422,
            f"Data retention critically low ({quality_report['retention_rate']:.1%}) — "
            f"refusing to score on mostly-discarded data. Check file format."
        )

    cutoff_date, cutoff_info = resolve_cutoff_date(cleaned_txns)
    try:
        feat_df, insufficient = compute_features(dealers, salesmen, cleaned_txns,
                                                 cutoff_date=cutoff_date)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if len(feat_df) == 0:
        raise HTTPException(
            422,
            f"No dealers had sufficient transaction history to score. The feature "
            f"window ended {cutoff_info['cutoff_date']} ({cutoff_info['strategy']}). "
            f"Each dealer needs at least 3 invoices dated before that."
        )

    # Decide which model to score with. "auto" only retrains when the
    # pretrained model is a demonstrably poor fit for this portfolio, so
    # familiar data keeps scoring exactly as before.
    training_mode = os.environ.get("RUNTIME_TRAINING_MODE", "auto").lower()
    pre_shift = assess_distribution_shift(feat_df, MODEL_ARTIFACT)

    active_artifact = MODEL_ARTIFACT
    training_report = {"attempted": False, "trained": False,
                       "reason": f"not attempted (mode={training_mode}, "
                                 f"distribution shift={pre_shift['severity']})"}

    if training_mode == "always" or (training_mode == "auto"
                                     and pre_shift["severity"] == "high"):
        candidate, training_report = try_train_on_uploaded_data(
            dealers, salesmen, cleaned_txns, MODEL_ARTIFACT)
        if candidate is not None:
            active_artifact = candidate

    scored = score_with_model(feat_df, active_artifact)
    cold = cold_start_score(dealers, cleaned_txns, insufficient)

    combined_cols = ["dealer_id", "dealer_name", "city", "sector", "salesman_id", "salesman_name",
                      "is_salesman_favorite", "credit_limit_pkr", "credit_score",
                      "risk_flag", "risk_probability", "scoring_method", "top_reasons"]
    scored_out = scored.rename(columns={"risk_probability": "risk_probability"})[combined_cols]
    all_scored = pd.concat([scored_out, cold[combined_cols]], ignore_index=True)
    all_scored = all_scored.sort_values("credit_score").reset_index(drop=True)

    model_source = ("trained_on_your_data" if training_report.get("trained")
                    else "pretrained")
    reliability = build_reliability_report(feat_df, all_scored, active_artifact,
                                           model_source=model_source,
                                           training_report=training_report)
    reliability["model_source"] = model_source
    reliability["training_report"] = training_report
    reliability["pretrained_fit_check"] = pre_shift

    session_id = str(uuid.uuid4())
    cleanup_expired_sessions()
    SESSIONS[session_id] = {
        "scored_df": all_scored,
        "quality_report": quality_report,
        "created_at": time.time(),
    }

    summary = {
        "total_dealers": len(all_scored),
        "red_count": int((all_scored["risk_flag"] == "RED").sum()),
        "amber_count": int(all_scored["risk_flag"].astype(str).str.contains("AMBER").sum()),
        "green_count": int((all_scored["risk_flag"] == "GREEN").sum()),
        "salesman_favorite_red_count": int(
            ((all_scored["is_salesman_favorite"] == True) & (all_scored["risk_flag"] == "RED")).sum()
        ),
    }

    return {
        "session_id": session_id,
        "summary": summary,
        "quality_report": quality_report,
        "cutoff_info": cutoff_info,
        "input_notes": input_notes,
        "reliability": reliability,
        "dealers": json.loads(all_scored.to_json(orient="records")),
    }


@app.get("/api/session/{session_id}/dealer/{dealer_id}")
def get_dealer_detail(session_id: str, dealer_id: str):
    session = get_session_or_404(session_id)
    df = session["scored_df"]
    row = df[df["dealer_id"] == dealer_id]
    if len(row) == 0:
        raise HTTPException(404, f"Dealer {dealer_id} not found in this session")
    return json.loads(row.iloc[0:1].to_json(orient="records"))[0]

@app.get("/api/session/{session_id}/dealer/{dealer_id}/risk-card")
def download_risk_card(session_id: str, dealer_id: str):
    session = get_session_or_404(session_id)
    df = session["scored_df"]
    row = df[df["dealer_id"] == dealer_id]
    if len(row) == 0:
        raise HTTPException(404, f"Dealer {dealer_id} not found in this session")

    dealer_dict = json.loads(row.iloc[0:1].to_json(orient="records"))[0]
    docx_bytes = build_risk_card_docx(dealer_dict)

    from fastapi.responses import Response
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={dealer_id}_Risk_Card.docx"},
    )
    
@app.get("/api/session/{session_id}/export-csv")
def export_csv(session_id: str):
    session = get_session_or_404(session_id)
    df = session["scored_df"]
    csv_bytes = df.drop(columns=["top_reasons"]).to_csv(index=False).encode()
    from fastapi.responses import Response
    return Response(
        content=csv_bytes, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dealer_risk_table.csv"},
    )
