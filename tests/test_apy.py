"""Unit tests for APY / APR calculators and official-proxy naming."""

from __future__ import annotations

import math

import pytest

from src.calculators.apy import (
    DEFAULT_WINDOWS_DAYS,
    LIDO_EARN_AUDIT_WINDOWS_DAYS,
    SHORT_WINDOW_MAX_DAYS,
    annualize,
    apply_exit_fee,
    compute_window,
    period_return,
    preferred_metric,
    realized_apy_is_cautionary,
    rolling_windows,
    summarize_vault,
    window_to_dict,
)
from src.calculators.official_apy_proxy import (
    RECOMMENDED_PROXY_NAME,
    build_official_comparison,
    candidate_to_dict,
    enumerate_proxy_candidates,
    simple_annualize,
)


def test_period_return_basic():
    assert period_return(100.0, 110.0) == pytest.approx(0.1)
    assert period_return(1.0, 1.0) == 0.0


def test_period_return_rejects_non_positive_start():
    with pytest.raises(ValueError):
        period_return(0.0, 1.0)
    with pytest.raises(ValueError):
        period_return(-1.0, 1.0)


def test_annualize_compound_is_standard_apy():
    # 10% over 365.25 days → ~10% APY
    assert annualize(0.10, 365.25) == pytest.approx(0.10)
    # 0 return → 0 APY
    assert annualize(0.0, 30) == 0.0
    # incomplete window
    assert annualize(0.01, 0.5) is None
    assert annualize(0.01, 0) is None


def test_annualize_matches_manual_formula():
    r, days = 0.13317507, 880.0
    expected = (1.0 + r) ** (365.25 / days) - 1.0
    assert annualize(r, days) == pytest.approx(expected)


def test_simple_annualize_is_apr_not_apy():
    r, days = 0.13317507, 880.0
    apr = simple_annualize(r, days)
    apy = annualize(r, days)
    assert apr == pytest.approx(r * (365.25 / days))
    # Positive multi-year return: APR > compound APY
    assert apr is not None and apy is not None
    assert apr > apy
    # Relative gap ≈ 3.8% on this Fluid inception sample
    assert (apr - apy) / apy == pytest.approx(0.0378, rel=0.05)


def test_apply_exit_fee():
    assert apply_exit_fee(100.0, 0.0005) == pytest.approx(99.95)
    with pytest.raises(ValueError):
        apply_exit_fee(100.0, -0.01)
    with pytest.raises(ValueError):
        apply_exit_fee(100.0, 1.0)


def _series() -> list[dict]:
    # Synthetic daily series: +0.01% per day for 100 days
    from datetime import date, timedelta

    rows: list[dict] = []
    start = date(2026, 3, 1)
    price = 1.0
    for i in range(100):
        d = start + timedelta(days=i)
        rows.append({"date": d.isoformat(), "share_price": price})
        price *= 1.0001
    return rows


def test_compute_window_hold_vs_realized_exit_fee():
    series = _series()
    w = compute_window(
        series,
        label="7d",
        start_date=series[-8]["date"],
        end_date=series[-1]["date"],
        exit_fee=0.0005,
    )
    assert w is not None
    assert w.days == 7
    assert w.hold_return > w.realized_return
    assert w.hold_apy is not None and w.realized_apy is not None
    assert w.hold_apy > w.realized_apy


def test_same_day_window_returns_none():
    series = _series()
    w = compute_window(
        series,
        label="0d",
        start_date=series[-1]["date"],
        end_date=series[-1]["date"],
        exit_fee=0.0,
    )
    assert w is None


def test_short_window_realized_caution_flags():
    assert SHORT_WINDOW_MAX_DAYS == 30
    assert realized_apy_is_cautionary(7, 0.0005) is True
    assert realized_apy_is_cautionary(30, 0.0005) is True
    assert realized_apy_is_cautionary(90, 0.0005) is False
    assert realized_apy_is_cautionary(7, 0.0) is False
    assert preferred_metric(7, 0.0005) == "hold_apy"
    assert preferred_metric(90, 0.0005) == "hold_or_realized"


def test_window_to_dict_includes_caution_on_short_realized():
    series = _series()
    w = compute_window(
        series,
        label="7d",
        start_date=series[-8]["date"],
        end_date=series[-1]["date"],
        exit_fee=0.0005,
    )
    assert w is not None
    d = window_to_dict(w)
    assert d["preferred_metric"] == "hold_apy"
    assert d["realized_apy_caution"] is True
    assert "realized_apy_note" in d
    assert "hold_apy_pct" in d


def test_window_to_dict_no_caution_without_exit_fee():
    series = _series()
    w = compute_window(
        series,
        label="7d",
        start_date=series[-8]["date"],
        end_date=series[-1]["date"],
        exit_fee=0.0,
    )
    assert w is not None
    d = window_to_dict(w)
    assert d["realized_apy_caution"] is False
    assert d["preferred_metric"] == "hold_or_realized"
    assert "realized_apy_note" not in d


def test_rolling_windows_and_summarize():
    series = _series()
    windows = rolling_windows(series, exit_fee=0.0005, windows_days=[7, 30])
    labels = [w.label for w in windows]
    assert "7d" in labels
    assert "30d" in labels
    assert "inception" in labels

    summary = summarize_vault(series, exit_fee=0.0005, fees={"exit_fee": 0.0005})
    assert summary["short_window_max_days"] == 30
    assert summary["points"] == len(series)
    short = next(w for w in summary["windows"] if w["window"] == "7d")
    assert short["realized_apy_caution"] is True
    long = next(w for w in summary["windows"] if w["window"] == "inception")
    assert long["realized_apy_caution"] is False


def test_proxy_candidates_label_apr_vs_apy():
    series = _series()
    candidates = enumerate_proxy_candidates(series, window_days=[7, 30])
    names = {c.name for c in candidates}
    assert "1d_hold_apy" in names
    assert "1d_hold_apr" in names
    assert "7d_hold_apr" in names
    assert "7d_hold_apy" in names
    assert "inception_hold_apr" in names
    assert "inception_hold_apy" in names
    # No legacy "simple"/"compound" suffixes in names
    assert not any(n.endswith("_simple") or n.endswith("_compound") for n in names)

    apr = next(c for c in candidates if c.name == "inception_hold_apr")
    apy = next(c for c in candidates if c.name == "inception_hold_apy")
    assert apr.rate_kind == "apr"
    assert apy.rate_kind == "apy"
    assert RECOMMENDED_PROXY_NAME == "1d_hold_apy"

    d_apr = candidate_to_dict(apr)
    d_apy = candidate_to_dict(apy)
    assert "apr_pct" in d_apr and "apy_pct" not in d_apr
    assert "apy_pct" in d_apy and "apr_pct" not in d_apy
    assert "annualized_pct" in d_apr and "annualized_pct" in d_apy


def test_last_complete_1d_skips_flat_tip_and_recommends_1d_apy():
    from datetime import date, timedelta

    from src.calculators.official_apy_proxy import last_complete_1d_pair

    series = _series()
    # Closed day already ends at series[-1]. Append flat tip day.
    tip_date = (date.fromisoformat(series[-1]["date"]) + timedelta(days=1)).isoformat()
    series_flat_tip = list(series) + [
        {"date": tip_date, "share_price": series[-1]["share_price"]}
    ]
    pair = last_complete_1d_pair(series_flat_tip)
    assert pair is not None
    start, end = pair
    assert end["date"] == series[-1]["date"]
    assert start["date"] == series[-2]["date"]

    one_d = next(
        c for c in enumerate_proxy_candidates(series_flat_tip) if c.name == "1d_hold_apy"
    )
    assert one_d.end_date == series[-1]["date"]
    assert one_d.days == 1.0

    cmp_ = build_official_comparison(
        series_flat_tip,
        official_net_apy=one_d.annualized,
        official_gross_apy=one_d.annualized / 0.8,
    )
    assert cmp_["definition"]["recommended_proxy_name"] == "1d_hold_apy"
    assert cmp_["definition"]["legacy_name"] == "inception_hold_apr"
    assert cmp_["recommended_proxy"]["rate_kind"] == "apy"
    assert "apy_pct" in cmp_["recommended_proxy"]
    assert math.isclose(
        cmp_["recommended_proxy"]["abs_delta_vs_official_net_pp"], 0.0, abs_tol=1e-9
    )


def test_rolling_windows_includes_1d():
    series = _series()
    windows = rolling_windows(series, exit_fee=0.0005)
    labels = [w.label for w in windows]
    assert "1d" in labels
    assert "7d" in labels
    assert "14d" in labels
    assert "30d" in labels
    assert "90d" in labels
    # 100-day synthetic series: 120/180/360 unavailable
    assert "120d" not in labels
    assert "180d" not in labels
    assert DEFAULT_WINDOWS_DAYS == [1, 7, 14, 30, 90, 120, 180, 360]
    assert LIDO_EARN_AUDIT_WINDOWS_DAYS == [1, 7, 14, 30, 90, 120, 180]


def test_summarize_marks_unavailable_audit_windows():
    series = _series()  # 100 days
    summary = summarize_vault(
        series,
        exit_fee=0.0,
        fees={"redeem_fee": 0.0},
        windows_days=list(LIDO_EARN_AUDIT_WINDOWS_DAYS),
    )
    assert summary["windows_days_requested"] == LIDO_EARN_AUDIT_WINDOWS_DAYS
    labels = {w["window"] for w in summary["windows"]}
    assert "90d" in labels
    assert "120d" not in labels
    unavail = {u["window"]: u for u in summary["unavailable_windows"]}
    assert unavail["120d"]["reason"] == "insufficient_history"
    assert unavail["180d"]["reason"] == "insufficient_history"
    assert unavail["120d"]["history_days"] == 99


def test_rolling_windows_includes_120_180_when_history_allows():
    from datetime import date, timedelta

    rows: list[dict] = []
    start = date(2025, 1, 1)
    price = 1.0
    for i in range(200):
        d = start + timedelta(days=i)
        rows.append({"date": d.isoformat(), "share_price": price})
        price *= 1.00005
    windows = rolling_windows(
        rows, exit_fee=0.0, windows_days=list(LIDO_EARN_AUDIT_WINDOWS_DAYS)
    )
    labels = [w.label for w in windows]
    assert labels[:7] == ["1d", "7d", "14d", "30d", "90d", "120d", "180d"]
    assert "inception" in labels

