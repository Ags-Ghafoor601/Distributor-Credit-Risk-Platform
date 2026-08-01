"""
Shared pytest fixtures for the backend test suite.

Uses the REAL Day1 dataset and the REAL persisted model -- these are the
same artifacts that produced every verified number throughout this project
(D0080 = 418, 220/36/6/178/5 split). Tests that load these fixtures are
therefore genuine regression tests, not tests against toy data.
"""
import sys
from pathlib import Path

import joblib
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
# Test fixtures live inside the backend so the test suite is self-contained
# and does not reach outside webapp/ for data.
DATA_DIR = BASE_DIR / "tests" / "fixtures"

sys.path.insert(0, str(BASE_DIR))


@pytest.fixture(scope="session")
def real_dealers():
    return pd.read_csv(DATA_DIR / "dealers.csv")


@pytest.fixture(scope="session")
def real_salesmen():
    return pd.read_csv(DATA_DIR / "salesmen.csv")


@pytest.fixture(scope="session")
def real_transactions():
    return pd.read_csv(
        DATA_DIR / "transactions.csv",
        parse_dates=["invoice_date", "due_date", "payment_date"],
    )


@pytest.fixture(scope="session")
def real_transactions_bytes():
    """Raw bytes, as they'd arrive via file upload -- needed for testing
    clean_transactions(), which accepts bytes not a DataFrame."""
    return (DATA_DIR / "transactions.csv").read_bytes()


@pytest.fixture(scope="session")
def model_artifact():
    return joblib.load(BASE_DIR / "model" / "credit_risk_model.joblib")


@pytest.fixture(scope="session")
def api_client():
    """FastAPI TestClient -- imported lazily so pipeline-only tests don't
    pay the cost of loading the full app + model twice."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)
