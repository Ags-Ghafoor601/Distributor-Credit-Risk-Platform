"""
Portability tests — the fixes that let this app score ANY distributor's data,
not just the dataset it was built against.

These are deliberately HERMETIC: they build their own tiny fixtures inline and
need neither the Day1 CSVs nor the trained model. They run anywhere, including
CI, and they stay valid even if the model is retrained.

Each test exists because of a specific real defect:
  - a hardcoded 2025-01-01 cutoff that silently emptied the feature window
    for any newer data, producing "no dealers could be scored"
  - a hardcoded Eid/Ramzan table that expired in June 2025, after which the
    seasonality feature stopped working with no error at all
  - a 9-column schema requirement including two columns (territory_risk_tier,
    is_salesman_favorite) that no real distributor could ever supply
  - a z-score that produced NaN on small or homogeneous portfolios, which
    surfaced as an opaque "Input X contains NaN" 500
"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.pipeline import (
    DEFAULT_CUTOFF_DATE,
    _EXPLICIT_SEASONAL_WINDOWS,
    _computed_windows_for_hijri_year,
    _hijri_to_date,
    _safe_zscore,
    is_seasonal,
    normalize_dealers,
    normalize_salesmen,
    resolve_cutoff_date,
)


def _txns(dates):
    return pd.DataFrame({"due_date": pd.to_datetime(dates)})


# ---------------------------------------------------------------------------
# Feature-window cutoff
# ---------------------------------------------------------------------------
def test_cutoff_uses_default_when_data_straddles_it():
    """The original dataset spans 2023-2026, so the configured default falls
    inside it and must still be chosen — this is what keeps existing scores
    byte-identical."""
    cutoff, info = resolve_cutoff_date(_txns(["2023-01-16", "2024-06-01", "2026-02-14"]))
    assert cutoff == DEFAULT_CUTOFF_DATE
    assert "configured default" in info["strategy"]


def test_cutoff_derived_when_all_data_is_newer():
    """The exact failure that motivated this: a distributor uploading recent
    data got an empty feature window and a confusing error."""
    txns = _txns(["2026-01-15", "2026-05-20", "2026-10-02"])
    cutoff, info = resolve_cutoff_date(txns)
    assert cutoff > txns["due_date"].max()
    assert "derived" in info["strategy"]
    assert (txns["due_date"] < cutoff).all(), "all history must survive the filter"


def test_cutoff_derived_when_all_data_is_older():
    txns = _txns(["2020-03-01", "2021-07-15", "2022-11-30"])
    cutoff, info = resolve_cutoff_date(txns)
    assert "derived" in info["strategy"]
    assert (txns["due_date"] < cutoff).all()


def test_cutoff_handles_empty_input_without_crashing():
    cutoff, info = resolve_cutoff_date(pd.DataFrame({"due_date": pd.to_datetime([])}))
    assert cutoff == DEFAULT_CUTOFF_DATE
    assert "no valid dates" in info["strategy"]


# ---------------------------------------------------------------------------
# Eid / Ramzan seasonal windows
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("d,expected", [
    (date(2023, 3, 10), True),   # first day of an explicit window
    (date(2023, 3, 9), False),   # day before it
    (date(2025, 4, 15), True),   # last day of an explicit window
    (date(2025, 4, 16), False),  # day after it
    (date(2024, 6, 30), True),
])
def test_explicit_windows_are_authoritative_for_2023_2025(d, expected):
    """Guarantees the original dataset's seasonal flags are unchanged."""
    assert is_seasonal(d) is expected


def test_future_years_are_no_longer_silently_unflagged():
    """Before this fix EVERY date after June 2025 returned False. At least one
    date in a future Ramadan window must now register."""
    ramadan_2026 = [date(2026, 2, m) for m in range(20, 29)] + \
                   [date(2026, 3, d) for d in range(1, 15)]
    assert any(is_seasonal(d) for d in ramadan_2026), \
        "no 2026 date flagged seasonal — the Hijri computation is not running"


def test_far_future_years_covered():
    dates_2032 = [date(2032, m, d) for m in range(1, 13) for d in (1, 15)]
    assert any(is_seasonal(d) for d in dates_2032)


def test_hijri_conversion_matches_observed_dates_within_tolerance():
    """The tabular Islamic calendar is arithmetic, not moon-sighting based.
    A day or two of drift is expected and absorbed by the window padding —
    but a large error would mean the conversion is simply wrong."""
    known = [
        (1444, 9, 1, date(2023, 3, 23)),
        (1445, 9, 1, date(2024, 3, 11)),
        (1446, 9, 1, date(2025, 3, 1)),
        (1444, 12, 10, date(2023, 6, 28)),
        (1446, 12, 10, date(2025, 6, 7)),
    ]
    for hy, hm, hd, observed in known:
        assert abs((_hijri_to_date(hy, hm, hd) - observed).days) <= 2


def test_computed_windows_are_ordered_and_plausible():
    for hy in (1447, 1450, 1455):
        for start, end in _computed_windows_for_hijri_year(hy):
            assert start < end
            assert 10 <= (end - start).days <= 90


def test_is_seasonal_tolerates_missing_dates():
    assert is_seasonal(pd.NaT) is False


# ---------------------------------------------------------------------------
# Schema normalization
# ---------------------------------------------------------------------------
def _full_dealers():
    return pd.DataFrame({
        "dealer_id": ["D1", "D2"], "dealer_name": ["A", "B"],
        "city": ["Lahore", "Karachi"], "sector": ["FMCG", "Pharma"],
        "salesman_id": ["S1", "S2"], "is_salesman_favorite": [False, True],
        "credit_limit_pkr": [50000, 200000],
        "onboarding_date": ["2021-07-11", "2022-01-05"],
        "territory_risk_tier": ["Low", "Medium"],
    })


def test_complete_file_passes_through_untouched():
    """Backward compatibility: a file with every column must produce no notes
    and no altered values."""
    out, notes = normalize_dealers(_full_dealers())
    assert notes == []
    assert list(out["is_salesman_favorite"]) == [False, True]
    assert list(out["territory_risk_tier"]) == ["Low", "Medium"]


def test_realistic_minimal_export_is_accepted():
    """A real distributor has no territory_risk_tier or is_salesman_favorite —
    these were invented by this project. Requiring them rejected real data."""
    minimal = pd.DataFrame({
        "dealer_id": ["X1", "X2"], "dealer_name": ["Karim & Sons", "Bilal Medicos"],
        "city": ["Lahore", "Karachi"], "salesman_id": ["S1", "S2"],
        "credit_limit_pkr": [150000, 80000],
        "onboarding_date": ["2023-04-01", "2023-09-15"],
    })
    out, notes = normalize_dealers(minimal)
    for col in ("sector", "is_salesman_favorite", "territory_risk_tier"):
        assert col in out.columns
    assert not out["is_salesman_favorite"].any(), "must default to nobody flagged"
    assert list(out["territory_risk_tier"]) == ["Lahore", "Karachi"], \
        "territory grouping should fall back to city"
    assert len(notes) == 3


@pytest.mark.parametrize("raw,expected", [
    (["Yes", "No"], [True, False]),
    (["TRUE", "false"], [True, False]),
    ([1, 0], [True, False]),
    ([True, False], [True, False]),
])
def test_favorite_flag_coercion(raw, expected):
    df = _full_dealers()
    df["is_salesman_favorite"] = raw
    out, _ = normalize_dealers(df)
    assert list(out["is_salesman_favorite"]) == expected


@pytest.mark.parametrize("col", ["dealer_id", "salesman_id", "credit_limit_pkr", "onboarding_date"])
def test_missing_essential_column_fails_loudly(col):
    with pytest.raises(ValueError) as e:
        normalize_dealers(_full_dealers().drop(columns=[col]))
    assert col in str(e.value)


def test_salesman_name_is_optional():
    out, notes = normalize_salesmen(pd.DataFrame({"salesman_id": ["S1", "S2"]}))
    assert list(out["salesman_name"]) == ["S1", "S2"]
    assert len(notes) == 1


def test_missing_salesman_id_fails_loudly():
    with pytest.raises(ValueError):
        normalize_salesmen(pd.DataFrame({"salesman_name": ["Alice"]}))


# ---------------------------------------------------------------------------
# Safe z-score
# ---------------------------------------------------------------------------
def test_zscore_matches_plain_formula_on_varied_data():
    """Backward compatibility: with real spread the result must be identical
    to the original expression, or every existing score would shift."""
    s = pd.Series([5.0, 12.0, 30.0, 8.0, 22.0])
    assert np.allclose(_safe_zscore(s), (s - s.mean()) / s.std())


@pytest.mark.parametrize("values", [
    [8.0],                 # single-dealer portfolio
    [8.0, 8.0, 8.0],       # every dealer behaves identically
    [0.0, 0.0],            # all-zero feature
])
def test_zscore_returns_finite_zeros_when_there_is_no_spread(values):
    """These all produced NaN before, which reached predict_proba and raised
    'Input X contains NaN' — a 500 with no explanation."""
    out = _safe_zscore(pd.Series(values))
    assert np.isfinite(out).all()
    assert (out == 0.0).all()


def test_zscore_preserves_signal_when_only_one_input_is_degenerate():
    """A single constant feature must not poison a composite built from two."""
    constant = _safe_zscore(pd.Series([8.0, 8.0, 8.0]))
    varied = _safe_zscore(pd.Series([3.0, 4.0, 5.0]))
    composite = (constant + varied) / 2
    assert np.isfinite(composite).all()
    assert composite.nunique() > 1, "the varied feature's signal was lost"


# ---------------------------------------------------------------------------
# Column aliasing
# ---------------------------------------------------------------------------
from app.pipeline import apply_column_aliases, DEALER_COLUMN_ALIASES, SALESMAN_COLUMN_ALIASES


def test_canonical_headers_are_left_untouched():
    df = _full_dealers()
    out, notes = apply_column_aliases(df, DEALER_COLUMN_ALIASES, "dealers")
    assert list(out.columns) == list(df.columns)
    assert notes == []


def test_realistic_pakistani_export_headers_are_recognised():
    """'Party Code' and 'Booker Code' are real terminology in Pakistani
    distribution; rejecting them made the app unusable for actual businesses."""
    df = pd.DataFrame(columns=["Party Code", "Party Name", "Town", "Booker Code",
                               "Credit Limit (Rs)", "Account Opened"])
    out, notes = apply_column_aliases(df, DEALER_COLUMN_ALIASES, "dealers")
    for expected in ("dealer_id", "dealer_name", "city", "salesman_id",
                     "credit_limit_pkr", "onboarding_date"):
        assert expected in out.columns
    assert len(notes) == 6


@pytest.mark.parametrize("header", ["Dealer_ID ", "dealer id", "DEALER-ID", "Dealer.Id"])
def test_header_matching_ignores_case_spacing_and_punctuation(header):
    out, _ = apply_column_aliases(pd.DataFrame(columns=[header]),
                                  DEALER_COLUMN_ALIASES, "dealers")
    assert "dealer_id" in out.columns


def test_canonical_header_wins_when_an_alias_is_also_present():
    df = pd.DataFrame(columns=["dealer_id", "Party Code"])
    out, notes = apply_column_aliases(df, DEALER_COLUMN_ALIASES, "dealers")
    assert "dealer_id" in out.columns
    assert "Party Code" in out.columns, "the alias must not clobber the real column"
    assert notes == []


@pytest.mark.parametrize("cols", [["Code", "Name"], ["SO Code", "Officer Name"],
                                  ["salesman_code", "rep_name"]])
def test_salesman_header_variants_are_recognised(cols):
    out, _ = apply_column_aliases(pd.DataFrame(columns=cols),
                                  SALESMAN_COLUMN_ALIASES, "salesmen")
    assert "salesman_id" in out.columns and "salesman_name" in out.columns


def test_aliasing_is_wired_into_normalize_dealers():
    """End-to-end: a realistic export must now survive normalization."""
    real = pd.DataFrame({
        "Party Code": ["X1", "X2"], "Party Name": ["Karim & Sons", "Bilal Medicos"],
        "Town": ["Lahore", "Karachi"], "Booker Code": ["B1", "B2"],
        "Credit Limit (Rs)": [150000, 80000],
        "Account Opened": ["2023-04-01", "2023-09-15"],
    })
    out, notes = normalize_dealers(real)
    assert "dealer_id" in out.columns and "salesman_id" in out.columns
    assert any("Party Code" in n for n in notes)


def test_aliasing_is_wired_into_normalize_salesmen():
    out, notes = normalize_salesmen(pd.DataFrame({"SO Code": ["S1"], "Officer Name": ["Ali"]}))
    assert list(out["salesman_id"]) == ["S1"]
    assert list(out["salesman_name"]) == ["Ali"]
