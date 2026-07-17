"""Tests for DefiLlama Official UI history join vs Hold APY."""

from __future__ import annotations

from datetime import date, timedelta

from src.calculators.fluid_official_ui_history import (
    build_official_ui_history_compare,
    hold_apy_asof,
)


def _share(n: int = 40, start: date | None = None) -> list[dict]:
    start = start or date(2026, 6, 1)
    rows = []
    price = 1.0
    for i in range(n):
        d = start + timedelta(days=i)
        rows.append({"date": d.isoformat(), "share_price": price})
        price *= 1.0001
    return rows


def test_hold_apy_asof_1d():
    series = _share()
    h = hold_apy_asof(series, asof_date=series[-1]["date"], window_days=1)
    assert h is not None
    assert h["days"] == 1.0
    assert h["hold_apy_pct"] is not None


def test_build_official_ui_history_compare():
    series = _share(40)
    ui = {
        "pool_id": "test",
        "source_url": "https://example.test",
        "pool_page": "https://example.test/pool",
        "fetched_at_utc": "2026-07-17T00:00:00+00:00",
        "points": 10,
        "first_date": series[-10]["date"],
        "last_date": series[-1]["date"],
        "series": [
            {
                "date": series[i]["date"],
                "official_ui_apy_pct": 5.0 + (i % 3) * 0.1,
                "tvl_usd": 1e8,
            }
            for i in range(-10, 0)
        ],
    }
    algo = {"net_apy_pct": 5.9, "gross_apy_pct": 7.4}
    out = build_official_ui_history_compare(
        official_history=ui,
        share_series=series,
        official_algo=algo,
        recent_days=5,
    )
    assert out["source"]["overlap_points"] == 10
    assert out["latest"]["official_algo_net_apy_pct"] == 5.9
    assert out["latest"]["hold_1d_apy_pct"] is not None
    assert len(out["recent_rows"]) == 5
    assert "official_ui" in out["markdown_recent_table"]
