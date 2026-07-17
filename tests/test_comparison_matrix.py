"""Tests for comparison matrix and Lido official APY fetcher wiring."""

from __future__ import annotations

from datetime import date, timedelta

from src.calculators.apy import summarize_vault
from src.calculators.comparison_matrix import (
    COMPARISON_WINDOWS_DAYS,
    build_comparison_matrix,
)


def _series(n: int = 400, start: date | None = None, daily: float = 1.0001) -> list[dict]:
    start = start or date(2025, 1, 1)
    rows = []
    price = 1.0
    for i in range(n):
        d = start + timedelta(days=i)
        rows.append({"date": d.isoformat(), "share_price": price})
        price *= daily
    return rows


def test_comparison_windows_days():
    assert COMPARISON_WINDOWS_DAYS == [1, 7, 14, 30, 90, 360]


def test_build_comparison_matrix_shape():
    # Overlapping history so Fluid can be measured on EarnETH inception span.
    fluid = _series(500, start=date(2025, 1, 1))
    earn = _series(165, start=date(2025, 12, 1))
    fluid_summary = summarize_vault(fluid, exit_fee=0.0005, fees={"exit_fee": 0.0005})
    earn_summary = summarize_vault(earn, exit_fee=0.0, fees={"redeem_fee": 0.0})

    matrix = build_comparison_matrix(
        fluid_summary=fluid_summary,
        earn_summary=earn_summary,
        fluid_series=fluid,
        fluid_exit_fee=0.0005,
        fluid_official_net_apy_pct=5.82,
        lido_official_apy_pct=3.56,
    )

    windows = [r["window"] for r in matrix["rows"]]
    assert windows == [
        "1d",
        "7d",
        "14d",
        "30d",
        "90d",
        "lido_earn_inception",
        "360d",
        "fluid_lite_inception",
    ]

    by = {r["window"]: r for r in matrix["rows"]}

    # 1d: fluid + fluid official only
    assert by["1d"]["fluid_lite_hold_apy_pct"] is not None
    assert by["1d"]["fluid_official_ui_apy_pct"] == 5.82
    assert by["1d"]["lido_hold_apy_pct"] is None
    assert by["1d"]["lido_official_ui_apy_pct"] is None

    # 14d: fluid + lido + lido official
    assert by["14d"]["fluid_lite_hold_apy_pct"] is not None
    assert by["14d"]["lido_hold_apy_pct"] is not None
    assert by["14d"]["lido_official_ui_apy_pct"] == 3.56
    assert by["14d"]["fluid_official_ui_apy_pct"] is None

    # 360d: fluid only
    assert by["360d"]["fluid_lite_hold_apy_pct"] is not None
    assert by["360d"]["lido_hold_apy_pct"] is None

    # fluid inception: fluid only
    assert by["fluid_lite_inception"]["fluid_lite_hold_apy_pct"] is not None
    assert by["fluid_lite_inception"]["lido_hold_apy_pct"] is None

    # lido inception: both (fluid over earn span)
    assert by["lido_earn_inception"]["lido_hold_apy_pct"] is not None
    assert by["lido_earn_inception"]["fluid_lite_hold_apy_pct"] is not None
    assert (
        by["lido_earn_inception"]["fluid_meta"]["start_date"]
        == by["lido_earn_inception"]["lido_meta"]["start_date"]
    )

    assert "Fluid Lite" in matrix["markdown_table"]
