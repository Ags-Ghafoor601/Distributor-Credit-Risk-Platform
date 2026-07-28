"""
Synthetic Dealer Payment History Generator
Problem 01: Distributor Credit Risk on Gut Feel
skillSYNC AI/ML Sprint — Day 1, Step 2

Generates realistic, messy trade-credit data for a Pakistani FMCG/Pharma/Textile
distributor with 3-10 salesmen and 50-500 dealers, with embedded ground-truth
risk patterns for model validation and demo storytelling.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
import random

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
N_SALESMEN = 8
N_DEALERS = 220
SIM_START = date(2023, 1, 1)
SIM_END = date(2025, 12, 31)

CITIES = {
    "Karachi": "Medium",
    "Lahore": "Low",
    "Rawalpindi": "Low",
    "Islamabad": "Low",
    "Faisalabad": "Medium",
    "Gujranwala": "Medium",
    "Interior Sindh": "High",
    "Interior Punjab": "Medium",
    "Peshawar": "High",
    "Multan": "Medium",
}
SECTORS = ["FMCG", "Pharma", "Textile"]
PAYMENT_METHODS_WEIGHTS = {"PDC": 0.60, "cash": 0.25, "bank_transfer": 0.15}

# Approximate Eid-ul-Fitr / Eid-ul-Azha + Ramzan windows for 2023-2025
# (kept approximate deliberately -- precision to the day isn't the point,
# the *seasonal cash-flow distortion pattern* is)
SEASONAL_WINDOWS = [
    (date(2023, 3, 10), date(2023, 5, 5)),   # Ramzan + Eid-ul-Fitr 2023
    (date(2023, 6, 15), date(2023, 7, 10)),  # Eid-ul-Azha 2023
    (date(2024, 2, 28), date(2024, 4, 25)),  # Ramzan + Eid-ul-Fitr 2024
    (date(2024, 6, 5), date(2024, 6, 30)),   # Eid-ul-Azha 2024
    (date(2025, 2, 15), date(2025, 4, 15)),  # Ramzan + Eid-ul-Fitr 2025
    (date(2025, 5, 25), date(2025, 6, 20)),  # Eid-ul-Azha 2025
]

# Approx PKR/USD depreciation proxy -> annual inflation-style multiplier
# applied to "real exposure" calc later (used at feature stage, not here)
ANNUAL_PKR_EROSION = 0.18  # ~18%/yr average erosion of real purchasing power


def is_seasonal(d: date) -> bool:
    return any(start <= d <= end for start, end in SEASONAL_WINDOWS)


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 0)))


# ---------------------------------------------------------------------------
# 1. SALESMEN
# ---------------------------------------------------------------------------
salesman_names = [
    "Tariq Mehmood", "Aamir Sohail", "Bilal Aslam", "Nasir Iqbal",
    "Kamran Shahid", "Waqas Ahmed", "Imran Yousaf", "Rizwan Malik",
]

salesmen = pd.DataFrame({
    "salesman_id": [f"SM{i+1:03d}" for i in range(N_SALESMEN)],
    "salesman_name": salesman_names[:N_SALESMEN],
    "territory": random.choices(list(CITIES.keys()), k=N_SALESMEN),
    "years_experience": np.random.randint(1, 18, size=N_SALESMEN),
})

# ---------------------------------------------------------------------------
# 2. DEALERS
# ---------------------------------------------------------------------------
dealer_rows = []
for i in range(N_DEALERS):
    dealer_id = f"D{i+1:04d}"
    city = random.choices(list(CITIES.keys()),
                           weights=[3, 3, 2, 2, 2, 1, 2, 2, 1, 1], k=1)[0]
    territory_risk_tier = CITIES[city]
    sector = random.choice(SECTORS)
    salesman = salesmen.sample(1).iloc[0]
    salesman_id = salesman["salesman_id"]

    # True risk profile -- ground truth, driven by territory risk + randomness
    # (NOT visible to the model -- used only for generating behavior + validation)
    risk_roll = np.random.rand()
    territory_bias = {"Low": -0.10, "Medium": 0.0, "High": 0.15}[territory_risk_tier]
    adj_roll = risk_roll + territory_bias
    if adj_roll < 0.55:
        true_risk = "Reliable"
    elif adj_roll < 0.80:
        true_risk = "Moderate"
    else:
        true_risk = "Risky"

    # Salesman favorites: ~15% of dealers, weighted toward being vouched
    # regardless of true risk (this is the whole point -- gut feel is blind to it)
    is_favorite = np.random.rand() < 0.15

    onboarding_date = random_date(date(2021, 1, 1), date(2024, 6, 1))
    base_limit = np.random.choice([50000, 100000, 200000, 350000, 500000, 750000])

    dealer_rows.append({
        "dealer_id": dealer_id,
        "dealer_name": f"{sector[:2]}-{city.replace(' ', '')}-{i+1:04d} Traders",
        "city": city,
        "territory_risk_tier": territory_risk_tier,
        "sector": sector,
        "salesman_id": salesman_id,
        "is_salesman_favorite": is_favorite,
        "credit_limit_pkr": base_limit,
        "onboarding_date": onboarding_date,
        "true_risk_profile": true_risk,   # ground truth, held out from model input
    })

dealers = pd.DataFrame(dealer_rows)

# ---------------------------------------------------------------------------
# 3. TRANSACTIONS (invoice / payment level)
# ---------------------------------------------------------------------------
risk_bounce_prob = {"Reliable": 0.02, "Moderate": 0.10, "Risky": 0.30}
risk_late_days_mean = {"Reliable": 2, "Moderate": 10, "Risky": 28}
risk_late_days_std = {"Reliable": 2, "Moderate": 6, "Risky": 15}

txn_rows = []
txn_counter = 1

for _, dealer in dealers.iterrows():
    n_invoices = np.random.randint(15, 60)  # transaction history depth varies
    true_risk = dealer["true_risk_profile"]

    for _ in range(n_invoices):
        invoice_date = random_date(
            max(dealer["onboarding_date"], SIM_START), SIM_END
        )
        due_date = invoice_date + timedelta(days=random.choice([15, 30, 45]))
        seasonal = is_seasonal(due_date)

        amount = round(np.random.uniform(20000, 300000), -2)
        method = random.choices(
            list(PAYMENT_METHODS_WEIGHTS.keys()),
            weights=list(PAYMENT_METHODS_WEIGHTS.values()), k=1
        )[0]

        bounce_prob = risk_bounce_prob[true_risk]
        # Bounces only meaningful for PDC method
        bounced = (method == "PDC") and (np.random.rand() < bounce_prob)

        if bounced:
            payment_date = None
            days_late = None
        else:
            mean_late = risk_late_days_mean[true_risk]
            std_late = risk_late_days_std[true_risk]
            # Seasonal periods add genuine extra delay (real cash-flow effect,
            # not just noise) -- roughly +40% during Eid/Ramzan windows
            if seasonal:
                mean_late = mean_late * 1.4
            late_days = max(0, int(np.random.normal(mean_late, std_late)))
            payment_date = due_date + timedelta(days=late_days)
            days_late = late_days

        txn_rows.append({
            "transaction_id": f"T{txn_counter:06d}",
            "dealer_id": dealer["dealer_id"],
            "invoice_date": invoice_date,
            "due_date": due_date,
            "payment_date": payment_date,
            "amount_pkr": amount,
            "payment_method": method,
            "cheque_bounced": bounced,
            "days_late": days_late,
            "is_eid_ramzan_period": seasonal,
        })
        txn_counter += 1

transactions = pd.DataFrame(txn_rows)

# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------
salesmen.to_csv("salesmen.csv", index=False)
dealers.to_csv("dealers.csv", index=False)
transactions.to_csv("transactions.csv", index=False)

print("Generated:")
print(f"  salesmen.csv     -> {len(salesmen)} rows")
print(f"  dealers.csv      -> {len(dealers)} rows")
print(f"  transactions.csv -> {len(transactions)} rows")
print()
print("True risk profile distribution (ground truth, hidden from model):")
print(dealers["true_risk_profile"].value_counts())
print()
print("Salesman-favorite dealers by true risk (the gut-feel blind spot):")
print(dealers[dealers["is_salesman_favorite"]]["true_risk_profile"].value_counts())
