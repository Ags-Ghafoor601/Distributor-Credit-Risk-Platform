"""
Messy Data Generator — simulates a REAL Pakistani distributor's Excel export
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 2, Stress Test

Takes the clean synthetic transactions.csv and deliberately corrupts a
realistic subset of rows the way manual Excel/ledger entry actually would:
inconsistent date formats, currency strings, mixed boolean encodings,
missing fields, duplicates, orphan references, typos, stray columns.

This is the actual test of the brief's core claim: "turns a distributor's
raw, unstructured payment history into a clear, defensible risk signal."
Everything up to now has been clean data. This is the first real test.
"""

import pandas as pd
import numpy as np
import random

SEED = 7
random.seed(SEED)
np.random.seed(SEED)

CORRUPTION_RATE = 0.35  # ~35% of rows get some form of real-world messiness

txns = pd.read_csv("transactions.csv")
dealers = pd.read_csv("dealers.csv")

messy = txns.copy()

# ---------------------------------------------------------------------------
# 1. RENAME COLUMNS the way a distributor's own Excel sheet actually would
#    (inconsistent casing, spaces, local shorthand -- not our clean schema)
# ---------------------------------------------------------------------------
messy = messy.rename(columns={
    "transaction_id": "Txn ID",
    "dealer_id": "Dealer Code ",       # trailing space, common in Excel
    "invoice_date": "Invoice Dt",
    "due_date": "Due Date",
    "payment_date": "Paid On",
    "amount_pkr": "Amount (Rs)",
    "payment_method": "Mode",
    "cheque_bounced": "Bounced?",
    "days_late": "Days Late",
    "is_eid_ramzan_period": "Seasonal",
})

n = len(messy)
corrupt_idx = np.random.choice(n, size=int(n * CORRUPTION_RATE), replace=False)

# Cast columns we'll inject mixed strings into as object dtype up front
for col in ["Invoice Dt", "Due Date", "Paid On", "Amount (Rs)", "Bounced?", "Dealer Code ", "Mode"]:
    messy[col] = messy[col].astype(object)


def pick_subset(indices, frac):
    k = int(len(indices) * frac)
    return np.random.choice(indices, size=k, replace=False)

# ---------------------------------------------------------------------------
# 2. DATE FORMAT CHAOS -- real ledgers mix these constantly
# ---------------------------------------------------------------------------
date_format_pool = [
    lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"),
    lambda d: pd.to_datetime(d).strftime("%m-%d-%Y"),
    lambda d: pd.to_datetime(d).strftime("%d-%b-%y"),
    lambda d: pd.to_datetime(d).strftime("%Y.%m.%d"),
    lambda d: str(int(pd.Timestamp(d).to_julian_date() - 2415018.5)),  # Excel serial date
]
date_targets = pick_subset(corrupt_idx, 0.5)
for i in date_targets:
    fmt = random.choice(date_format_pool)
    try:
        messy.loc[i, "Invoice Dt"] = fmt(messy.loc[i, "Invoice Dt"])
        messy.loc[i, "Due Date"] = fmt(messy.loc[i, "Due Date"])
    except Exception:
        pass

# Some payment dates blank (still open) written as text instead of null
blank_variants = ["", "N/A", "NA", "-", "nil", "pending", "  "]
blank_targets = pick_subset(corrupt_idx, 0.15)
for i in blank_targets:
    messy.loc[i, "Paid On"] = random.choice(blank_variants)

# ---------------------------------------------------------------------------
# 3. CURRENCY STRING CHAOS
# ---------------------------------------------------------------------------
def messy_amount(val):
    style = random.choice(["comma", "rs_prefix", "slash_suffix", "parens_neg", "plain_float", "spaced"])
    v = float(val)
    if style == "comma":
        return f"{v:,.0f}"
    elif style == "rs_prefix":
        return f"Rs. {v:,.0f}"
    elif style == "slash_suffix":
        return f"{v:,.0f}/-"
    elif style == "parens_neg":
        return f"({v:,.0f})"  # accounting-style, NOT actually negative here but visually confusing
    elif style == "spaced":
        return f" {v:,.0f} "
    return str(v)

amount_targets = pick_subset(corrupt_idx, 0.6)
for i in amount_targets:
    messy.loc[i, "Amount (Rs)"] = messy_amount(messy.loc[i, "Amount (Rs)"])

# ---------------------------------------------------------------------------
# 4. BOOLEAN ENCODING CHAOS (bounced flag, seasonal flag)
# ---------------------------------------------------------------------------
bool_true_variants = ["Y", "Yes", "YES", "y", "1", "TRUE", "true", "Bounced"]
bool_false_variants = ["N", "No", "NO", "n", "0", "FALSE", "false", "", "OK"]

bool_targets = pick_subset(corrupt_idx, 0.7)
for i in bool_targets:
    orig = messy.loc[i, "Bounced?"]
    if str(orig) in ("True", "1", "1.0"):
        messy.loc[i, "Bounced?"] = random.choice(bool_true_variants)
    else:
        messy.loc[i, "Bounced?"] = random.choice(bool_false_variants)

# ---------------------------------------------------------------------------
# 5. MISSING CRITICAL FIELDS
# ---------------------------------------------------------------------------
missing_dealer_targets = pick_subset(corrupt_idx, 0.03)
messy.loc[missing_dealer_targets, "Dealer Code "] = np.nan

missing_amount_targets = pick_subset(corrupt_idx, 0.02)
messy.loc[missing_amount_targets, "Amount (Rs)"] = ""

# ---------------------------------------------------------------------------
# 6. ORPHAN DEALER REFERENCES (typo'd dealer codes not in master list)
# ---------------------------------------------------------------------------
orphan_targets = pick_subset(corrupt_idx, 0.02)
for i in orphan_targets:
    orig = str(messy.loc[i, "Dealer Code "])
    if orig != "nan":
        messy.loc[i, "Dealer Code "] = orig + "X"  # typo'd code, e.g. D0080 -> D0080X

# ---------------------------------------------------------------------------
# 7. DUPLICATE ROWS (accidental re-paste, common in manual Excel work)
# ---------------------------------------------------------------------------
dup_sample = messy.sample(n=int(n * 0.02), random_state=SEED)
messy = pd.concat([messy, dup_sample], ignore_index=True)

# ---------------------------------------------------------------------------
# 8. STRAY COLUMNS (real sheets always have extra notes/unnamed columns)
# ---------------------------------------------------------------------------
messy["Notes"] = ""
note_targets = np.random.choice(len(messy), size=int(len(messy) * 0.05), replace=False)
sample_notes = ["called dealer", "cheque redeposited", "verify with salesman", "follow up next week", "owner traveling"]
for i in note_targets:
    messy.loc[i, "Notes"] = random.choice(sample_notes)

messy["Unnamed: 12"] = np.nan  # ghost column Excel sometimes adds

# ---------------------------------------------------------------------------
# 9. WHITESPACE / CASE NOISE IN TEXT FIELDS
# ---------------------------------------------------------------------------
mode_targets = pick_subset(np.arange(len(messy)), 0.2)
for i in mode_targets:
    val = str(messy.loc[i, "Mode"])
    messy.loc[i, "Mode"] = f"  {val.upper()}  " if random.random() < 0.5 else val.lower()

# Shuffle row order (real exports aren't sorted)
messy = messy.sample(frac=1, random_state=SEED).reset_index(drop=True)

messy.to_csv("messy_transactions_raw.csv", index=False)

print(f"Original clean rows: {n}")
print(f"Messy export rows (incl. duplicates): {len(messy)}")
print(f"Corrupted rows targeted: {len(corrupt_idx)} ({CORRUPTION_RATE:.0%})")
print(f"Missing dealer codes: {len(missing_dealer_targets)}")
print(f"Orphan dealer codes (typo'd): {len(orphan_targets)}")
print(f"Duplicate rows added: {len(dup_sample)}")
print()
print("Sample of messy output:")
print(messy[["Txn ID", "Dealer Code ", "Invoice Dt", "Amount (Rs)", "Bounced?", "Mode"]].head(10).to_string(index=False))
