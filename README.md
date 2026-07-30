# Distributor Credit Risk — "The Ledger"

A credit risk scorecard for distributors, replacing salesman gut-feel with a
defensible, explainable score. Built around six Pakistan-specific behavioural
signals: post-dated cheque bounce history, Eid/Ramzan seasonality,
salesman-vouch bias, territory clustering, PKR-inflation-adjusted exposure, and
business continuity.

Every dealer receives a 300–900 score, a RED/AMBER/GREEN tier, and
plain-language reason codes explaining the result.

---

## Project structure

```
skillSYNC Project-2/
  Day1/                 Source data: dealers.csv, salesmen.csv, transactions.csv
  Day2/  Day3/  Day4/   Development history (stress tests, model training, deck)
  CHANGELOG.md          What changed at each stage
  webapp/
    backend/            FastAPI service — the live scoring API
      app/
        main.py         HTTP endpoints
        pipeline.py     All scoring logic (authoritative)
      model/
        credit_risk_model.joblib
      tests/            63 tests
      requirements.txt
    frontend/           Next.js dashboard
```

`webapp/backend/app/pipeline.py` is authoritative for all scoring logic. The
Day2/Day3 CLI scripts are historical and may differ.

---

## Prerequisites

- Python 3.12+
- Node.js 18+
- The three source CSVs in `Day1/`

---

## Backend

```powershell
cd webapp\backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks venv activation, run once:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### Verify before running

```powershell
python -m pytest tests\ -v
```

Expect **63 passing**: 6 regression tests pinning known-verified values
(D0080 = 418, the 220 / 178 / 36 / 6 split), plus 57 hermetic tests covering
portability and model adaptation. The hermetic ones need neither `Day1/` nor the
model artifact, so they run anywhere including CI.

### Run

```powershell
uvicorn app.main:app --reload
```

Serves on `http://127.0.0.1:8000`; interactive docs at `/docs`.

### Environment variables

All optional — defaults preserve the original behaviour exactly.

| Variable | Default | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated frontend origins permitted by CORS. **Must be set in production.** |
| `SESSION_TTL_SECONDS` | `3600` | How long a scored session survives in memory |
| `MAX_SESSIONS` | `500` | Hard cap on stored sessions |
| `MAX_FILE_SIZE_BYTES` | `20971520` (20 MB) | Per-file upload limit |
| `MAX_TRANSACTION_ROWS` | `200000` | Maximum valid transaction rows |
| `FEATURE_CUTOFF_DATE` | `2025-01-01` | Default boundary between feature history and later data. Overridden automatically when it falls outside the uploaded range. |
| `RUNTIME_TRAINING_MODE` | `auto` | `never` / `auto` / `always`. `auto` trains a portfolio-specific model only when the shipped model is a poor fit. |
| `ANNUAL_CURRENCY_EROSION` | `0.18` | Annual currency erosion for inflation-adjusted exposure. Wrong outside Pakistan; adjust per market. |
| `LATE_PAYMENT_THRESHOLD_DAYS` | `15` | Days late that counts as a default when deriving training labels. A distributor on 60-day terms needs a higher value. |

---

## Frontend

```powershell
cd webapp\frontend
npm install
```

Create `.env.local`:
```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

```powershell
npm run dev          # http://localhost:3000
npm run build        # verify a clean production build
```

If styling changes don't appear, delete `.next` and restart — Turbopack caches
compiled CSS and will not always pick up newly added theme tokens.

---

## Working with any distributor's data

Four behaviours make this usable beyond the dataset it was built on. Each is
reported back in the API response rather than applied silently.

**Flexible column names.** Common real-world headers are recognised
automatically — `Party Code`, `Booker Code`, `Credit Limit (Rs)`,
`Account Opened`, and many others — with casing, spacing and punctuation
ignored. Only four columns are genuinely required: a dealer identifier, a
salesman identifier, a credit limit, and an onboarding date. Anything else is
substituted with a sensible default and reported in `input_notes`.

**Any date range.** The feature/outcome boundary is derived from the uploaded
data when the configured default falls outside its range, so recent or
historical data both work. Reported in `cutoff_info`.

**Eid/Ramzan for any year.** Seasonal windows are computed from the tabular
Islamic calendar rather than a fixed table. Accurate to within about a day of
observed dates, which the ±2-week window padding absorbs comfortably — and
observed dates vary by country anyway.

**Model applicability, reported honestly.** Every response includes a
`reliability` block:

- `scores_reliable` — the portfolio resembles the training data
- `scores_indicative` — somewhat different; rankings hold, treat numbers loosely
- `use_ranking_only` — substantially different; use the tier, not the number

When the fit is poor and the data supports it, a portfolio-specific model is
trained at runtime and cross-validated. It is only used if it clears an AUC
floor of 0.65 — otherwise the app declines and says why. Training requires at
least 50 dealers, 18 months of history, and both outcomes present. Those gates
exist because thin data trains "successfully" and produces confident noise,
which is worse than an honest refusal.

---

## Known limitations

- **The shipped model has never seen a real default.** Every reported metric
  (cross-validated AUC 0.860 ± 0.098) comes from synthetic data. The runtime
  training path addresses this per-portfolio; the shipped model itself remains
  unvalidated against reality.
- **Exact scores are directional, not calibrated.** Calibration was tested and
  did not improve at this sample size. The RED/AMBER/GREEN tier is the reliable
  signal.
- **Scores are portfolio-relative.** Several features are computed within the
  uploaded batch, so the same dealer in two different portfolios scores
  differently. Appropriate for "who is riskiest in my book"; inappropriate for
  absolute cross-company comparison.
- **Sessions live in memory.** Fine for one instance; a multi-replica
  deployment needs shared storage (Redis or a database), since sessions do not
  sync across replicas.
- **A single bounced cheque in the outcome window marks a dealer high-risk.**
  Deliberately sensitive, but it means "high risk" means "showed any bad
  signal," not "consistently bad."

---

## Deployment

Backend on Render (or any Python host), frontend on Vercel. Vercel's Python
serverless runtime is a poor fit for a pandas/scikit-learn service.

### Before pushing

Confirm the model artifact is **not** gitignored — if it is, the deployed
backend crashes on startup with `FileNotFoundError`:

```powershell
git check-ignore -v webapp\backend\model\credit_risk_model.joblib
```

Any output means it is being excluded. Fix `.gitignore` first.

### Backend (Render)

- **Root Directory:** `webapp/backend`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment:** set `ALLOWED_ORIGINS` (initially `http://localhost:3000`)

`$PORT` is required — Render assigns the port dynamically, and a hardcoded
`8000` fails to bind and reports as unhealthy.

Verify at `https://<your-service>.onrender.com/api/health`. On the free tier the
service sleeps after ~15 minutes idle; the first request then takes 30–60
seconds to wake. Warm it before any demo.

### Frontend (Vercel)

- **Root Directory:** `webapp/frontend`
- **Framework Preset:** `Next.js` — **verify this explicitly**
- **Environment:** `NEXT_PUBLIC_API_URL` = the Render URL

If the preset is left as `Other`, the build **succeeds** and then serves
`404: NOT_FOUND` at `/`. Vercel looks for a static `public/` directory and never
wires up the Next.js routes. Nothing in the build log looks wrong, which makes
this easy to misdiagnose.

Leave all Build / Output / Install overrides off — the correct preset fills them
in.

### Close the loop

Update `ALLOWED_ORIGINS` on Render to the real Vercel URL and let it redeploy.
It must match exactly, including `https://` and no trailing slash.

### Verify end to end

Upload the three CSVs from `Day1/` and confirm 220 dealers scored, D0080 at 418,
a downloadable Risk Card, and CSV export.
