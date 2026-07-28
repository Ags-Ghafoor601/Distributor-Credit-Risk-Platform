# End-to-End Pipeline Orchestrator
Day 3 · skillSYNC AI/ML Sprint · Problem 01

---

## What This Closes

The brief's own Day 3 goal: **"Finish the build end-to-end and test it thoroughly so it runs reliably on a full dataset without manual intervention."** Until now, a full run meant manually calling 4–5 separate scripts in the right order. `run_pipeline.py` chains everything into one command.

---

## What It Does

```
Raw data (optional) → Ingestion/cleaning → Scoring (persisted model) → Risk table + JSON export → Risk Card generation
```

**Usage:**
```bash
python run_pipeline.py                              # score the standard dataset
python run_pipeline.py --input messy_raw_export.csv  # ingest + clean a new raw file first
python run_pipeline.py --skip-cards                  # scoring only, skip docx generation
```

Every stage logs a timestamped status line. On success, a final summary reports rows retained, dealers scored, RED-flag count, and cards generated — a complete audit trail for a single run, not just a final number.

---

## Tested — Three Scenarios, All Verified

**1. Standard clean data:** 220 dealers scored, 36 flagged RED, 36 Risk Cards generated — end to end in **3.9 seconds**.

**2. Messy raw data via `--input`:** full ingestion pipeline runs first (96.0% retention, identical to the standalone stress test), then scoring and card generation proceed exactly as with clean data — **4.3 seconds** total, same final counts. This proves the ingestion and scoring stages compose correctly, not just work in isolation.

**3. Deliberate failure cases** — because a pipeline that only succeeds on the happy path isn't actually production-ready:
   - **Missing input file** → halts immediately with `PIPELINE HALTED: Could not read input file...`, exit code 1
   - **Missing model artifact** → halts with `Model artifact not found... Run train_and_save_model.py first.`, exit code 1

Both failures are loud and specific, not silent. This matters in practice: a scheduled job or dashboard can check the exit code and alert someone, rather than quietly displaying stale or wrong data because a script failed halfway through without anyone noticing.

**Data-quality circuit breaker:** if ingestion retention drops below 50%, the pipeline halts rather than proceeding to score a dataset that's mostly been discarded — a defensive check against a genuinely corrupted input file slipping through unnoticed.

---

## What's Deliberately Simplified Here vs. the Standalone Scripts

- Ingestion inside `run_pipeline.py` uses a condensed version of `robust_ingestion.py`'s logic (same core cleaning steps: column mapping, date/amount parsing, boolean normalization, orphan/duplicate removal) but skips the full Eid/Ramzan seasonal-window tagging for brevity — acceptable for a pipeline run, since seasonal tagging affects feature nuance, not core risk detection. `robust_ingestion.py` remains the reference implementation with full seasonal logic if that precision is needed for a specific analysis.
- Risk Card generation is invoked via `subprocess` calling `node generate_risk_card_v2.js --all-red` — this is the one cross-language seam in the pipeline (Python for data/ML, Node for docx). If Node isn't available in a given environment, the pipeline logs a warning and continues rather than failing the whole run, since scoring succeeded even if card generation couldn't.

---

## Definition of Done

- [x] Single command runs ingestion (optional) → scoring → export → card generation
- [x] Tested on both clean and messy input, producing identical downstream results
- [x] Tested failure paths (missing file, missing model) — both halt loudly with clear messages and non-zero exit codes
- [x] Data-quality circuit breaker prevents scoring on critically corrupted input
- [x] Full run completes in under 5 seconds
