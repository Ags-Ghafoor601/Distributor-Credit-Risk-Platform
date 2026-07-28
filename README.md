# Distributor Credit Risk — "The Ledger"

A credit risk scorecard for Pakistani distributors, replacing salesman gut-feel
with a defensible, explainable score built on 6 Pakistan-specific behavioral
signals (PDC bounce history, Eid/Ramzan seasonality, salesman-vouch bias,
territory risk, PKR-inflation-adjusted exposure, business continuity).

## Project Structure

```
skillSYNC Project-2/
  Day1/            # Source data: dealers.csv, salesmen.csv, transactions.csv
  Day2/             # Stress-test, VIF, cold-start, calibration scripts (historical)
  Day3/             # Model training, cross-validation, unified pipeline (historical)
  Day4/             # Client presentation deck
  webapp/
    backend/        # FastAPI service — the live scoring API
      app/
        main.py      # HTTP endpoints
        pipeline.py   # Scoring logic (ingestion, features, model, docx generation)
      model/
        credit_risk_model.joblib   # Trained model artifact
      tests/         # Regression test suite
      requirements.txt
    frontend/        # Next.js dashboard
      app/
      components/
      lib/
```

## Prerequisites

- Python 3.12+ (backend was built and tested against this version)
- Node.js 18+ and npm
- The 3 source CSVs in `Day1/`: `dealers.csv`, `salesmen.csv`, `transactions.csv`

## Backend Setup (FastAPI)

```powershell
cd webapp\backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the venv activation script, run once:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Verify the backend before running it

```powershell
python -m pytest tests\test_regression.py -v
```
All 6 tests should pass — these lock in known-correct values (D0080 = 418,
220 dealers, 178 GREEN / 36 RED / 6 AMBER, the seasonal-window logic
actually running, and `salesman_name` correctly populated) verified
throughout this project's development.

### Run the backend

```powershell
uvicorn app.main:app --reload
```
Runs at `http://127.0.0.1:8000`. Interactive API docs: `http://127.0.0.1:8000/docs`.

### Backend environment variables (all optional, sensible defaults apply)

| Variable | Default | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated list of frontend origins allowed to call this API (CORS) |
| `SESSION_TTL_SECONDS` | `3600` | How long a scored session stays in memory before expiring |
| `MAX_SESSIONS` | `500` | Hard cap on concurrent stored sessions |
| `MAX_FILE_SIZE_BYTES` | `20971520` (20MB) | Maximum size per uploaded file |
| `MAX_TRANSACTION_ROWS` | `200000` | Maximum valid transaction rows per upload |

## Frontend Setup (Next.js)

```powershell
cd webapp\frontend
npm install
```

Create `.env.local` (copy from `.env.local.example` if present):
```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### Run the frontend

```powershell
npm run dev
```
Runs at `http://localhost:3000`. The backend must already be running.

### Verify the frontend builds cleanly

```powershell
Remove-Item -Recurse -Force .next
npm run build
```
Should complete with zero TypeScript errors.

## Using the App

1. Open `http://localhost:3000`
2. Upload `dealers.csv`, `salesmen.csv`, and `transactions.csv` from `Day1/`
   (or a messy real-world export — the ingestion pipeline is built to clean
   mixed date formats, currency symbols, and inconsistent boolean encodings)
3. Review the scored portfolio: the Spectrum visualization, the sortable
   dealer table, and per-dealer detail panels with reason codes
4. Download the full risk table as CSV, or an individual dealer's Risk Card
   as a Word document

## Known Limitations (stated honestly, not hidden)

- **Calibration precision**: the exact numeric score is directional, not
  perfectly calibrated, given the current dataset size (~220 dealers).
  The RED/AMBER/GREEN tier is the reliable signal; the precise number will
  sharpen as more real historical data accumulates.
- **In-memory sessions**: scored data lives in server memory with a TTL,
  not a database. Fine for a single-instance deployment; a multi-instance
  production deployment would need to move this to shared storage (Redis,
  a database) since sessions don't currently sync across server replicas.
- **Static model**: reflects one training run. There's no automated
  retraining pipeline yet as new data accumulates.

## Deployment Notes

- **Backend**: deploy to a Python-capable host (Render, Railway, Fly.io —
  not Vercel, whose Python serverless support doesn't suit a
  pandas/scikit-learn-heavy service well). Set `ALLOWED_ORIGINS` to the
  real frontend URL once known.
- **Frontend**: deploy to Vercel. Set `NEXT_PUBLIC_API_URL` in the
  project's environment variables to the deployed backend's URL — if this
  is missing, the app fails loudly with a clear error rather than silently
  trying to reach `localhost` on every visitor's machine.
