"""
Regression Tests: Lock In Known-Verified Values

These tests exist BECAUSE of real bugs found during this project's
development, each caught only through manual verification:
  - D0055 silently dropped from every scored output (training/scoring
    eligibility conflated in an inner join)
  - D0080 showing 425 instead of 418 in a presentation (transcription error
    that a test would have caught in seconds)
  - The seasonal-window logic silently simplified to `False` during the
    web port, changing scores without anyone noticing until tested
  - salesman_name missing from stored session data, breaking the Risk Card

If any of these regress, these tests fail LOUDLY instead of requiring
someone to manually re-verify a screenshot against a generated document.
"""
import pandas as pd
from app.pipeline import compute_features, score_with_model, cold_start_score


def test_full_portfolio_produces_known_dealer_count(real_dealers, real_salesmen, real_transactions, model_artifact):
    feat_df, insufficient = compute_features(real_dealers, real_salesmen, real_transactions)
    scored = score_with_model(feat_df, model_artifact)
    cold = cold_start_score(real_dealers, real_transactions, insufficient)

    total = len(scored) + len(cold)
    assert total == 220, (
        f"Expected 220 total dealers (219 statistical + up to 1 cold-start), got {total}. "
        f"This is the exact bug class that silently dropped D0055 -- verify the "
        f"training/scoring eligibility split hasn't been re-conflated."
    )


def test_d0080_score_matches_verified_value(real_dealers, real_salesmen, real_transactions, model_artifact):
    """D0080 is the project's most-checked dealer -- verified across CLI runs,
    the API, the frontend, and a manually-opened Word document. 418 is the
    ground truth; if this test ever shows a different number, something
    upstream changed and needs explaining before it ships."""
    feat_df, insufficient = compute_features(real_dealers, real_salesmen, real_transactions)
    scored = score_with_model(feat_df, model_artifact)

    d0080 = scored[scored["dealer_id"] == "D0080"]
    assert len(d0080) == 1, "D0080 should be present in the scored output"
    assert d0080.iloc[0]["credit_score"] == 418, (
        f"D0080 scored {d0080.iloc[0]['credit_score']}, expected 418. "
        f"This exact discrepancy happened once already (425 vs 418) due to a "
        f"manual transcription error -- if this fails, the MODEL changed, not "
        f"just a number someone typed."
    )


def test_portfolio_risk_tier_distribution_matches_verified_split(real_dealers, real_salesmen, real_transactions, model_artifact):
    feat_df, insufficient = compute_features(real_dealers, real_salesmen, real_transactions)
    scored = score_with_model(feat_df, model_artifact)

    counts = scored["risk_flag"].value_counts()
    assert counts.get("GREEN", 0) == 178, f"Expected 178 GREEN, got {counts.get('GREEN', 0)}"
    assert counts.get("RED", 0) == 36, f"Expected 36 RED, got {counts.get('RED', 0)}"
    assert counts.get("AMBER", 0) == 6, f"Expected 6 AMBER, got {counts.get('AMBER', 0)}"


def test_salesman_favorite_red_count_matches_verified_value(real_dealers, real_salesmen, real_transactions, model_artifact):
    """This is the single most narratively important number in the whole
    project -- the count of dealers a salesman personally trusts who are
    flagged high-risk by the model. If this silently changes, the demo's
    entire thesis is affected."""
    feat_df, insufficient = compute_features(real_dealers, real_salesmen, real_transactions)
    scored = score_with_model(feat_df, model_artifact)

    favorite_red = scored[(scored["is_salesman_favorite"] == True) & (scored["risk_flag"] == "RED")]
    assert len(favorite_red) == 5, f"Expected 5 salesman-favorite RED dealers, got {len(favorite_red)}"


def test_seasonal_window_logic_is_not_silently_disabled(real_transactions_bytes, real_dealers):
    """Regression guard for the exact bug caught earlier: is_eid_ramzan_period
    was hardcoded to False during the web port, which silently changed
    avg_days_late_nonseasonal for every dealer. This calls the ACTUAL
    clean_transactions() function (not just the source CSV) so a future
    reintroduction of the hardcoded-False shortcut is caught directly."""
    from app.pipeline import clean_transactions

    valid_ids = set(real_dealers["dealer_id"])
    cleaned, _ = clean_transactions(real_transactions_bytes, valid_ids)

    seasonal_count = cleaned["is_eid_ramzan_period"].sum()
    assert seasonal_count > 0, (
        "clean_transactions() produced zero seasonal-flagged rows -- the "
        "Eid/Ramzan window logic may have been silently hardcoded to False "
        "again, exactly as happened during the original web port."
    )


def test_salesman_name_is_present_in_scored_output(real_dealers, real_salesmen, real_transactions, model_artifact):
    """Regression guard for the bug where salesman_name was dropped from
    combined_cols in main.py, causing Risk Cards to show 'SM008 (SM008)'
    instead of 'Rizwan Malik (SM008)'."""
    feat_df, insufficient = compute_features(real_dealers, real_salesmen, real_transactions)
    scored = score_with_model(feat_df, model_artifact)

    d0080 = scored[scored["dealer_id"] == "D0080"].iloc[0]
    assert pd.notna(d0080["salesman_name"]), "salesman_name is missing for D0080"
    assert d0080["salesman_name"] == "Rizwan Malik", (
        f"Expected salesman_name 'Rizwan Malik', got '{d0080['salesman_name']}'"
    )
