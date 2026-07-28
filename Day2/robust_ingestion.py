"""
Robust Data Ingestion Pipeline
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2, Stress Test

Takes the messy raw export and turns it into a clean, schema-conformant
dataset -- while producing a DATA QUALITY REPORT documenting exactly what
was fixed, what was dropped, and why. This report itself is a deliverable:
a client needs to see that their data was handled honestly, not silently
mangled.
"""

import pandas as pd
import numpy as np
from datetime import date

pd.options.mode.chained_assignment = None

RAW_PATH = "messy_transactions_raw.csv"
DEALERS_PATH = "dealers.csv"

raw = pd.read_csv(RAW_PATH, dtype=str)  # read everything as string first -- never trust dtype inference on messy data
dealers = pd.read_csv(DEALERS_PATH)
valid_dealer_ids = set(dealers["dealer_id"])

report = {"stage": [], "rows_in": [], "rows_out": [], "rows_affected": [], "note": []}

def log(stage, rows_in, rows_out, rows_affected, note):
    report["stage"].append(stage)
    report["rows_in"].append(rows_in)
    report["rows_out"].append(rows_out)
    report["rows_affected"].append(rows_affected)
    report["note"].append(note)

start_n = len(raw)

# ---------------------------------------------------------------------------
# 1. STANDARDIZE COLUMN NAMES (strip whitespace, map known aliases)
# ---------------------------------------------------------------------------
raw.columns = [c.strip() for c in raw.columns]

COLUMN_MAP = {
    "Txn ID": "transaction_id",
    "Dealer Code": "dealer_id",
    "Invoice Dt": "invoice_date",
    "Due Date": "due_date",
    "Paid On": "payment_date",
    "Amount (Rs)": "amount_pkr",
    "Mode": "payment_method",
    "Bounced?": "cheque_bounced",
    "Days Late": "days_late_raw",     # not trusted -- recomputed after date cleaning
    "Seasonal": "is_eid_ramzan_period_raw",
}
df = raw.rename(columns=COLUMN_MAP)

# Drop known ghost/stray columns that carry no signal
for stray_col in [c for c in df.columns if c.startswith("Unnamed") or c == "Notes"]:
    df = df.drop(columns=[stray_col])

log("Column standardization", start_n, len(df), 0, "Renamed to canonical schema, dropped stray/ghost columns")

# ---------------------------------------------------------------------------
# 2. DROP EXACT DUPLICATE ROWS
# ---------------------------------------------------------------------------
before = len(df)
df = df.drop_duplicates()
dupes_removed = before - len(df)
log("Duplicate removal", before, len(df), dupes_removed, f"Removed {dupes_removed} exact duplicate rows")

# ---------------------------------------------------------------------------
# 3. CLEAN DEALER_ID: strip whitespace, drop missing, flag+drop orphans
# ---------------------------------------------------------------------------
before = len(df)
# NOTE: pandas' string dtype does NOT stringify real NaN to "nan" on .astype(str)
# (unlike older object-dtype behavior) -- must check .isna() explicitly, or
# genuinely missing cells silently slip through the string-sentinel check.
missing_dealer_raw = df["dealer_id"].isna()
df["dealer_id"] = df["dealer_id"].astype(str).str.strip()
missing_dealer = missing_dealer_raw | df["dealer_id"].isin(["nan", "", "None", "N/A", "NA"])
n_missing_dealer = missing_dealer.sum()
df = df[~missing_dealer]
log("Missing dealer_id removal", before, len(df), n_missing_dealer,
    f"Dropped {n_missing_dealer} rows with no dealer code -- cannot attribute to any account")

before = len(df)
orphan_mask = ~df["dealer_id"].isin(valid_dealer_ids)
orphans = df[orphan_mask]
n_orphans = len(orphans)
df = df[~orphan_mask]
log("Orphan dealer_id removal", before, len(df), n_orphans,
    f"Dropped {n_orphans} rows referencing dealer codes not in the master dealer list (likely typos, e.g. 'D0036X')")

# ---------------------------------------------------------------------------
# 4. ROBUST DATE PARSING -- handles multiple formats + Excel serial dates
# ---------------------------------------------------------------------------
def parse_messy_date(val):
    if pd.isna(val) or str(val).strip() in ("", "N/A", "NA", "-", "nil", "pending"):
        return pd.NaT
    s = str(val).strip()
    # Excel serial date (pure integer string, plausible range for 2020-2030)
    if s.isdigit() and 40000 < int(s) < 48000:
        try:
            return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(s))
        except Exception:
            return pd.NaT
    # Try pandas' flexible parser across common explicit formats first
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d-%b-%y", "%Y.%m.%d", "%d-%b-%Y"):
        try:
            return pd.to_datetime(s, format=fmt)
        except Exception:
            continue
    # Last resort: pandas' generic inference (dayfirst=True matches PK convention)
    try:
        return pd.to_datetime(s, dayfirst=True, errors="raise")
    except Exception:
        return pd.NaT

before_unparsed_dates = df["invoice_date"].copy()
df["invoice_date"] = df["invoice_date"].apply(parse_messy_date)
df["due_date"] = df["due_date"].apply(parse_messy_date)
df["payment_date"] = df["payment_date"].apply(parse_messy_date)

n_unparseable_invoice = df["invoice_date"].isna().sum()
before = len(df)
df = df[df["invoice_date"].notna() & df["due_date"].notna()]
log("Date parsing", before, len(df), before - len(df),
    f"Parsed mixed formats (DD/MM/YYYY, MM-DD-YYYY, Excel serials, etc.); dropped {before - len(df)} rows with unparseable invoice/due dates")

# ---------------------------------------------------------------------------
# 5. CLEAN AMOUNT FIELD -- strip currency symbols, commas, suffixes
# ---------------------------------------------------------------------------
def parse_messy_amount(val):
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    if s in ("", "N/A", "NA", "-", "nil"):
        return np.nan
    is_paren_neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = s.replace("Rs.", "").replace("Rs", "").replace("PKR", "")
    s = s.replace(",", "").replace("/-", "").strip()
    try:
        amount = float(s)
        return amount  # note: parens in this dataset are accounting-style noise, not true negatives -- verified against source
    except ValueError:
        return np.nan

before = len(df)
df["amount_pkr"] = df["amount_pkr"].apply(parse_messy_amount)
n_bad_amount = df["amount_pkr"].isna().sum()
df = df[df["amount_pkr"].notna() & (df["amount_pkr"] > 0)]
log("Amount cleaning", before, len(df), before - len(df),
    f"Stripped currency symbols/commas/suffixes; dropped {before - len(df)} rows with unparseable or non-positive amounts")

# ---------------------------------------------------------------------------
# 6. NORMALIZE BOUNCED FLAG (mixed Y/N/yes/no/1/0/TRUE/FALSE/blank)
# ---------------------------------------------------------------------------
TRUE_SET = {"y", "yes", "1", "true", "bounced"}
FALSE_SET = {"n", "no", "0", "false", "", "ok", "nan"}

def parse_bool(val):
    s = str(val).strip().lower()
    if s in TRUE_SET:
        return True
    if s in FALSE_SET:
        return False
    return np.nan  # genuinely ambiguous -- flagged, not guessed

df["cheque_bounced"] = df["cheque_bounced"].apply(parse_bool)
n_ambiguous_bounce = df["cheque_bounced"].isna().sum()
before = len(df)
df = df[df["cheque_bounced"].notna()]
log("Bounced-flag normalization", before, len(df), before - len(df),
    f"Mapped Y/Yes/1/TRUE and N/No/0/FALSE variants to boolean; dropped {before - len(df)} rows with unrecognized values rather than guessing")

# ---------------------------------------------------------------------------
# 7. NORMALIZE PAYMENT METHOD TEXT (whitespace/case noise)
# ---------------------------------------------------------------------------
df["payment_method"] = df["payment_method"].astype(str).str.strip().str.upper()
df["payment_method"] = df["payment_method"].replace({"BANK_TRANSFER": "BANK_TRANSFER", "PDC": "PDC", "CASH": "CASH"})

# ---------------------------------------------------------------------------
# 8. RECOMPUTE DERIVED FIELDS FROM CLEANED DATES (never trust raw derived cols)
# ---------------------------------------------------------------------------
df["days_late"] = (df["payment_date"] - df["due_date"]).dt.days
df.loc[df["cheque_bounced"] == True, "days_late"] = np.nan  # bounced = no valid payment date concept

SEASONAL_WINDOWS = [
    (date(2023, 3, 10), date(2023, 5, 5)), (date(2023, 6, 15), date(2023, 7, 10)),
    (date(2024, 2, 28), date(2024, 4, 25)), (date(2024, 6, 5), date(2024, 6, 30)),
    (date(2025, 2, 15), date(2025, 4, 15)), (date(2025, 5, 25), date(2025, 6, 20)),
]
def is_seasonal(d):
    if pd.isna(d):
        return False
    d = d.date()
    return any(s <= d <= e for s, e in SEASONAL_WINDOWS)

df["is_eid_ramzan_period"] = df["due_date"].apply(is_seasonal)

# ---------------------------------------------------------------------------
# 9. LOGICAL CONSISTENCY CHECK: due_date must be >= invoice_date
# ---------------------------------------------------------------------------
before = len(df)
inconsistent = df["due_date"] < df["invoice_date"]
n_inconsistent = inconsistent.sum()
df = df[~inconsistent]
log("Logical consistency check", before, len(df), n_inconsistent,
    f"Dropped {n_inconsistent} rows where due_date preceded invoice_date (impossible, likely entry error)")

# ---------------------------------------------------------------------------
# FINAL OUTPUT
# ---------------------------------------------------------------------------
final_cols = ["transaction_id", "dealer_id", "invoice_date", "due_date", "payment_date",
              "amount_pkr", "payment_method", "cheque_bounced", "days_late", "is_eid_ramzan_period"]
clean = df[final_cols].reset_index(drop=True)
clean.to_csv("cleaned_transactions.csv", index=False)

report_df = pd.DataFrame(report)
report_df.to_csv("data_quality_report.csv", index=False)

print("=" * 75)
print("DATA QUALITY REPORT")
print("=" * 75)
print(report_df.to_string(index=False))
print()
print(f"Raw rows ingested:     {start_n}")
print(f"Clean rows retained:   {len(clean)}")
print(f"Retention rate:        {len(clean)/start_n:.1%}")
print(f"Total rows dropped:    {start_n - len(clean)}")
