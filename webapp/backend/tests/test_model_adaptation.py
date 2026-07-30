"""
Model-adaptation tests — the machinery that decides whether the pretrained
model can be trusted on an uploaded portfolio, and whether to train a new one.

Also hermetic: portfolios are generated inline, so these need neither the
Day1 CSVs nor the shipped model artifact.

The guard rails matter more than the happy path here. A portfolio with thin
history, too few dealers, or almost no defaults will train "successfully" and
produce a confident model that is really just noise — which is worse than
declining. Most of these tests assert that we decline.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from app.pipeline import (
    assess_distribution_shift,
    assess_score_saturation,
    build_reliability_report,
    try_train_on_uploaded_data,
)

FEATURE_COLS = ["payment_delay_severity", "bounce_rate_lifetime", "real_exposure_pkr",
                "order_frequency_trend", "salesman_default_rate_loo",
                "territory_default_rate_loo"]
SCORE_PARAMS = {"base_score": 600, "base_odds": 1 / 19, "pdo": 40}


def make_portfolio(n_dealers=150, months=36, seed=0, risky_frac=0.35, signal=True,
                   pristine=False):
    """Builds a synthetic distributor portfolio with a controllable amount of
    real risk signal, so both the trainable and untrainable cases can be
    exercised deterministically."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2023-01-01")
    ids = [f"D{i:04d}" for i in range(n_dealers)]
    dealers = pd.DataFrame({
        "dealer_id": ids,
        "dealer_name": [f"Dealer {i}" for i in range(n_dealers)],
        "city": rng.choice(["Lahore", "Karachi", "Multan"], n_dealers),
        "sector": rng.choice(["FMCG", "Pharma"], n_dealers),
        "salesman_id": rng.choice([f"S{i}" for i in range(6)], n_dealers),
        "territory_risk_tier": rng.choice(["Low", "Medium", "High"], n_dealers),
        "is_salesman_favorite": rng.random(n_dealers) < 0.15,
        "credit_limit_pkr": rng.choice([50000, 100000, 300000], n_dealers),
        "onboarding_date": [start - pd.Timedelta(days=int(x))
                            for x in rng.integers(100, 900, n_dealers)],
    })
    salesmen = pd.DataFrame({"salesman_id": [f"S{i}" for i in range(6)],
                             "salesman_name": [f"Salesman {i}" for i in range(6)]})
    risky = rng.random(n_dealers) < risky_frac
    rows = []
    for i in range(n_dealers):
        for _ in range(rng.integers(20, 45)):
            due = start + pd.Timedelta(days=int(rng.integers(0, months * 30)))
            if pristine:
                # Nobody bounces and nobody pays late -- there is simply no
                # default behaviour for a model to learn from.
                bounced = False
                late = max(0, rng.normal(2, 1))
            elif signal:
                bounced = rng.random() < (0.28 if risky[i] else 0.02)
                late = max(0, rng.normal(28 if risky[i] else 2, 12 if risky[i] else 3))
            else:
                bounced = rng.random() < 0.15
                late = max(0, rng.normal(12, 10))
            rows.append({"dealer_id": ids[i], "due_date": due,
                         "invoice_date": due - pd.Timedelta(days=30),
                         "cheque_bounced": bool(bounced),
                         "days_late": np.nan if bounced else float(late),
                         "is_eid_ramzan_period": False})
    return dealers, salesmen, pd.DataFrame(rows)


def make_reference_artifact(feat_df):
    """A stand-in for the shipped joblib, fitted to a given feature frame."""
    X = feat_df[FEATURE_COLS]
    scaler = StandardScaler().fit(X)
    y = (np.arange(len(X)) % 2)
    model = LogisticRegression(max_iter=1000).fit(scaler.transform(X), y)
    return {"model": model, "scaler": scaler, "feature_columns": FEATURE_COLS,
            "score_params": SCORE_PARAMS, "metadata": {}}


# ---------------------------------------------------------------------------
# Distribution shift
# ---------------------------------------------------------------------------
def test_shift_is_low_against_the_portfolio_the_scaler_was_fit_on():
    from app.pipeline import compute_features
    d, s, t = make_portfolio()
    feat, _ = compute_features(d, s, t)
    result = assess_distribution_shift(feat, make_reference_artifact(feat))
    assert result["severity"] == "low"
    assert result["max_displacement_sds"] < 0.01


def test_shift_is_high_for_a_clearly_different_portfolio():
    from app.pipeline import compute_features
    d, s, t = make_portfolio()
    feat, _ = compute_features(d, s, t)
    artifact = make_reference_artifact(feat)

    # Express the shift in the scaler's own standard deviations, so the test
    # is deterministic regardless of how much spread the fixture happens to
    # have. Four SDs is unambiguously beyond the 2.5 "high" threshold.
    idx = FEATURE_COLS.index("bounce_rate_lifetime")
    one_sd = float(artifact["scaler"].scale_[idx])
    shifted = feat.copy()
    shifted["bounce_rate_lifetime"] = shifted["bounce_rate_lifetime"] + 4.0 * one_sd
    result = assess_distribution_shift(shifted, artifact)
    assert result["severity"] == "high"
    assert result["per_feature_displacement_sds"]["bounce_rate_lifetime"] > 2.5


def test_shift_reports_per_feature_so_the_cause_is_identifiable():
    from app.pipeline import compute_features
    d, s, t = make_portfolio()
    feat, _ = compute_features(d, s, t)
    result = assess_distribution_shift(feat, make_reference_artifact(feat))
    assert set(result["per_feature_displacement_sds"]) == set(FEATURE_COLS)


# ---------------------------------------------------------------------------
# Score saturation
# ---------------------------------------------------------------------------
def test_saturation_low_for_a_healthy_spread():
    scored = pd.DataFrame({"credit_score": np.linspace(400, 850, 100)})
    result = assess_score_saturation(scored)
    assert result["severity"] == "low"
    assert result["pct_clipped"] == 0.0


def test_saturation_high_when_many_dealers_pin_to_the_bounds():
    scored = pd.DataFrame({"credit_score": [300] * 30 + [900] * 30 + [600] * 40})
    result = assess_score_saturation(scored)
    assert result["severity"] == "high"
    assert result["clipped_at_floor"] == 30
    assert result["clipped_at_ceiling"] == 30
    assert result["pct_clipped"] == 0.6


def test_saturation_handles_empty_input():
    result = assess_score_saturation(pd.DataFrame({"credit_score": []}))
    assert result["severity"] == "low"


# ---------------------------------------------------------------------------
# Combined verdict
# ---------------------------------------------------------------------------
def test_verdict_reliable_when_both_signals_are_clean():
    from app.pipeline import compute_features
    d, s, t = make_portfolio()
    feat, _ = compute_features(d, s, t)
    scored = pd.DataFrame({"credit_score": np.linspace(400, 850, len(feat))})
    report = build_reliability_report(feat, scored, make_reference_artifact(feat))
    assert report["verdict"] == "scores_reliable"


def test_verdict_downgrades_when_scores_saturate():
    """Saturation alone must trigger the warning even if inputs look normal —
    it is the direct evidence the model cannot discriminate."""
    from app.pipeline import compute_features
    d, s, t = make_portfolio()
    feat, _ = compute_features(d, s, t)
    scored = pd.DataFrame({"credit_score": [900] * len(feat)})
    report = build_reliability_report(feat, scored, make_reference_artifact(feat))
    assert report["verdict"] == "use_ranking_only"
    assert report["guidance"]


# ---------------------------------------------------------------------------
# Runtime training — guard rails
# ---------------------------------------------------------------------------
def test_trains_on_a_healthy_portfolio_and_reports_its_own_accuracy():
    from app.pipeline import compute_features
    d, s, t = make_portfolio(n_dealers=150, months=36, seed=1)
    feat, _ = compute_features(d, s, t)
    artifact, report = try_train_on_uploaded_data(d, s, t, make_reference_artifact(feat))

    assert report["trained"] is True
    assert artifact is not None
    assert artifact["feature_columns"] == FEATURE_COLS
    assert report["cv_auc_mean"] >= 0.65, "a model below this floor should never ship"
    assert report["training_pool_size"] >= 50
    assert 0.0 < report["base_rate"] < 1.0


def test_declines_when_too_few_dealers():
    from app.pipeline import compute_features
    d, s, t = make_portfolio(n_dealers=25, seed=2)
    feat, _ = compute_features(d, s, t)
    artifact, report = try_train_on_uploaded_data(d, s, t, make_reference_artifact(feat))
    assert artifact is None and report["trained"] is False
    assert "dealers" in report["reason"]


def test_declines_when_history_is_too_short_to_split():
    from app.pipeline import compute_features
    d, s, t = make_portfolio(months=10, seed=3)
    feat, _ = compute_features(d, s, t)
    artifact, report = try_train_on_uploaded_data(d, s, t, make_reference_artifact(feat))
    assert artifact is None and report["trained"] is False
    assert "months" in report["reason"]


def test_declines_when_the_resulting_model_would_be_no_better_than_guessing():
    """The most important guard: data with no real signal must NOT produce a
    confident-looking model."""
    from app.pipeline import compute_features
    d, s, t = make_portfolio(signal=False, seed=7)
    feat, _ = compute_features(d, s, t)
    artifact, report = try_train_on_uploaded_data(d, s, t, make_reference_artifact(feat))
    assert artifact is None and report["trained"] is False
    assert "cross-validation" in report["reason"]


def test_declines_when_almost_nobody_defaulted():
    """Note: risky_frac alone is not enough to create this case -- the label
    marks a dealer high-risk on a SINGLE bounce, so even a 2% bounce rate
    yields plenty of positives. A genuinely pristine portfolio is required."""
    from app.pipeline import compute_features
    d, s, t = make_portfolio(pristine=True, seed=4)
    feat, _ = compute_features(d, s, t)
    artifact, report = try_train_on_uploaded_data(d, s, t, make_reference_artifact(feat))
    assert artifact is None and report["trained"] is False


def test_decline_reasons_are_human_readable():
    """These strings surface in the UI, so they must explain rather than
    reference internals."""
    from app.pipeline import compute_features
    d, s, t = make_portfolio(n_dealers=25, seed=5)
    feat, _ = compute_features(d, s, t)
    _, report = try_train_on_uploaded_data(d, s, t, make_reference_artifact(feat))
    reason = report["reason"]
    assert len(reason) > 30
    assert "Traceback" not in reason and "None" not in reason
