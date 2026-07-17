"""Tests for Fluid Lite Net Hold APY windows."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.calculators.fluid_lite_net_hold_apy import (
    MEANING,
    NET_HOLD_WINDOWS_DAYS,
    compute_net_hold_windows,
    hold_window_to_dict,
    summarize_fluid_lite_net_hold_apy,
)
from src.calculators.apy import compute_window


def _series(n: int = 200, daily_mult: float = 1.0001) -> list[dict]:
    rows: list[dict] = []
    start = date(2025, 1, 1)
    price = 1.0
    for i in range(n):
        d = start + timedelta(days=i)
        rows.append({"date": d.isoformat(), "share_price": price})
        price *= daily_mult
    return rows


def test_net_hold_windows_days_list():
    assert NET_HOLD_WINDOWS_DAYS == [1, 7, 14, 30, 90, 120, 180]


def test_hold_only_fields_no_realized():
    series = _series()
    windows = compute_net_hold_windows(series)
    assert windows
    labels = [w["window"] for w in windows]
    assert "inception" not in labels
    for w in windows:
        assert "net_hold_apy_pct" in w
        assert "hold_return_pct" in w
        assert "steth_after_1y_per_1_steth" in w
        assert "eth_after_1y_per_1_eth" in w
        assert "realized_apy_pct" not in w
        assert "realized_return_pct" not in w
        assert "end_share_price_realized" not in w
        assert w["steth_after_1y_per_1_steth"] == w["eth_after_1y_per_1_eth"]


def test_120_and_180_present_when_history_long_enough():
    series = _series(200)
    windows = compute_net_hold_windows(series)
    labels = {w["window"] for w in windows}
    for n in NET_HOLD_WINDOWS_DAYS:
        assert f"{n}d" in labels


def test_short_history_skips_long_windows():
    series = _series(40)
    windows = compute_net_hold_windows(series)
    labels = {w["window"] for w in windows}
    assert "30d" in labels
    assert "90d" not in labels
    assert "120d" not in labels
    assert "180d" not in labels


def test_net_hold_matches_apy_hold_with_zero_exit_fee():
    series = _series()
    hold_windows = compute_net_hold_windows(series, windows_days=[7, 30])
    for hw in hold_windows:
        raw = compute_window(
            series,
            label=hw["window"],
            start_date=hw["start_date"],
            end_date=hw["end_date"],
            exit_fee=0.0,
        )
        assert raw is not None
        assert hw["net_hold_apy_pct"] == pytest.approx(raw.hold_apy * 100, abs=1e-6)
        assert hw["steth_after_1y_per_1_steth"] == pytest.approx(1.0 + raw.hold_apy, abs=1e-8)


def test_steth_after_1y_identity():
    series = _series()
    raw = compute_window(
        series,
        label="30d",
        start_date=series[-31]["date"],
        end_date=series[-1]["date"],
        exit_fee=0.0,
    )
    assert raw is not None
    w = hold_window_to_dict(raw)
    assert w["steth_after_1y_per_1_steth"] == pytest.approx(
        1.0 + w["net_hold_apy_pct"] / 100.0, abs=1e-8
    )


def test_summarize_includes_meaning():
    report = summarize_fluid_lite_net_hold_apy(_series())
    assert "stETH" in MEANING or "steth" in MEANING.lower()
    assert report["metric"]["name"] == "net_hold_apy"
    assert report["windows_days"] == NET_HOLD_WINDOWS_DAYS
    assert any("stETH" in n or "ETH" in n for n in report["notes"])
    assert report["fees"]["performance_fee"] == 0.20
