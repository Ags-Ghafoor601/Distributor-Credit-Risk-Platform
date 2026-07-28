# Cross-Validation + Model Persistence
Day 3 · skillSYNC AI/ML Sprint · Problem 01

---

## 1. Cross-Validation — The Honest Performance Range

Every AUC/KS number reported until now came from a single 70/30 split. With only 219 labeled dealers, that's a real risk — one split can be lucky or unlucky. Ran stratified 5-fold cross-validation on the final VIF-remediated 6-feature model to find out.

**Result:**

| Metric | Mean | Std Dev | Range Across Folds |
|---|---|---|---|
| AUC | 0.860 | ±0.098 | 0.763 – 0.989 |
| KS | 0.667 | ±0.175 | 0.490 – 0.929 |

**The honest takeaway:** the mean (0.860) sits close to what the single split reported (0.847) — reassuring, the original number wasn't a fluke. But the *spread* is real and needs to be communicated: on some folds performance looks excellent (0.989), on others merely acceptable (0.763). **The correct claim to make to a client is a range — "AUC of roughly 0.76 to 0.99, centered around 0.86" — not a single confident decimal.** This is now embedded directly in the persisted model's metadata (see below), so it travels with the model rather than living only in a document someone might not open before quoting a number.

---

## 2. Model Persistence — Separating Training from Scoring

**Problem:** every script in this project retrained the model from scratch on every run. Fine for development; not how a real deployed system works — a distributor's dashboard should score dealers in milliseconds, not re-run training every time.

**`train_and_save_model.py`** trains once on the full labeled pool (219 dealers) and saves a single artifact (`credit_risk_model.joblib`) containing:
- The fitted model and scaler
- The exact feature column order (so scoring can never silently misalign columns)
- Score-scaling parameters (base score, PDO)
- **Metadata**: training timestamp, training pool size, base rate, and — critically — the cross-validated performance range and known limitations, baked directly into the artifact

**`score_dealers.py`** loads that artifact and scores all 220 dealers with **zero training calls** — verified directly (`grep -c "\.fit("` on the file returns only comment-line matches, confirmed no actual `.fit()` calls execute). Feature *engineering* still runs per-dealer (that's not training, it's data prep), but the model and scaler are used exactly as saved.

**Verified working:** scored 220/220 dealers, output matches the unified pipeline's results, model loaded in milliseconds versus the several seconds a full retrain takes.

---

## What This Changes Going Forward

- Any future scoring run (new dealer batch, dashboard refresh, Risk Card generation) should use `score_dealers.py` against the saved artifact, not retrain from scratch
- Retraining should be a deliberate, periodic action (e.g., monthly, as new payment data accumulates) via `train_and_save_model.py` — not something that happens implicitly every time someone runs a script
- The cross-validated range, not the single-split number, is now the figure to use in any client-facing materials

---

## Definition of Done

- [x] 5-fold stratified cross-validation run on the final feature set
- [x] Honest range reported (not just the favorable mean)
- [x] Model trained once and persisted with joblib, including full metadata
- [x] Separate scoring script verified to perform zero training calls
- [x] Known limitations embedded in the model artifact itself, not just in documentation
