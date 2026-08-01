"""
Verification: does the new webapp module reproduce the EXACT known values
from the validated CLI pipeline? This must pass before the module is
trusted for any API endpoint.

Known validated values (confirmed multiple times on the person's own machine):
  - 220 total dealers, 219 usable for training, 1 (D0055) scored-not-trained
  - D0080 credit_score = 418
  - Portfolio split: 178 GREEN / 36 RED / 6 AMBER
"""
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import joblib
import pandas as pd
from app.pipeline import compute_features, score_with_model, cold_start_score

DATA_DIR = BASE / "tests" / "fixtures"

dealers = pd.read_csv(DATA_DIR / "dealers.csv")
salesmen = pd.read_csv(DATA_DIR / "salesmen.csv")
txns = pd.read_csv(DATA_DIR / "transactions.csv",
                    parse_dates=["invoice_date", "due_date", "payment_date"])
artifact = joblib.load(BASE / "model" / "credit_risk_model.joblib")

feat_df, insufficient = compute_features(dealers, salesmen, txns)
scored = score_with_model(feat_df, artifact)
cold = cold_start_score(dealers, txns, insufficient)

print(f"Total scored (statistical): {len(scored)}")
print(f"Insufficient history (cold-start): {len(insufficient)}")
print(f"Total combined: {len(scored) + len(cold)}")
print()

d0080 = scored[scored["dealer_id"] == "D0080"].iloc[0]
print(f"D0080 credit_score: {d0080['credit_score']}  (expected: 418)")
assert d0080["credit_score"] == 418, f"MISMATCH: got {d0080['credit_score']}, expected 418"

counts = scored["risk_flag"].value_counts()
print(f"Portfolio split: GREEN={counts.get('GREEN', 0)}, RED={counts.get('RED', 0)}, AMBER={counts.get('AMBER', 0)}")
print(f"(expected: GREEN=178, RED=36, AMBER=6)")
assert counts.get("GREEN", 0) == 178, f"GREEN mismatch: {counts.get('GREEN', 0)}"
assert counts.get("RED", 0) == 36, f"RED mismatch: {counts.get('RED', 0)}"
assert counts.get("AMBER", 0) == 6, f"AMBER mismatch: {counts.get('AMBER', 0)}"

print()
print("=" * 60)
print("ALL ASSERTIONS PASSED — module is verified equivalent to the CLI pipeline")
print("=" * 60)

# ---------------------------------------------------------------------------
# SECOND CHECK: through clean_transactions() too, since the API always
# routes uploads through ingestion, even for already-clean files. This is
# what caught the seasonal-window bug -- verifying compute_features alone
# was NOT sufficient, the full upload path must be tested end-to-end.
# ---------------------------------------------------------------------------
from app.pipeline import clean_transactions

with open(DATA_DIR / "transactions.csv", "rb") as f:
    raw_bytes = f.read()
valid_ids = set(dealers["dealer_id"])
cleaned_via_ingestion, report = clean_transactions(raw_bytes, valid_ids)
print()
print("--- Testing full ingestion path (clean_transactions) ---")
print(f"Retention: {report['retention_rate']:.3f} (expect 1.0 for already-clean input)")
assert report["retention_rate"] == 1.0, f"Unexpected data loss on clean input: {report}"

feat_df2, insufficient2 = compute_features(dealers, salesmen, cleaned_via_ingestion)
scored2 = score_with_model(feat_df2, artifact)
d0080_v2 = scored2[scored2["dealer_id"] == "D0080"].iloc[0]
print(f"D0080 score via full ingestion path: {d0080_v2['credit_score']} (expected: 418)")
assert d0080_v2["credit_score"] == 418, f"MISMATCH via ingestion path: got {d0080_v2['credit_score']}, expected 418"

counts2 = scored2["risk_flag"].value_counts()
print(f"Portfolio split via ingestion path: GREEN={counts2.get('GREEN',0)}, RED={counts2.get('RED',0)}, AMBER={counts2.get('AMBER',0)}")
assert counts2.get("GREEN", 0) == 178 and counts2.get("RED", 0) == 36 and counts2.get("AMBER", 0) == 6

print()
print("=" * 60)
print("FULL INGESTION PATH ALSO VERIFIED — safe to expose via API")
print("=" * 60)
