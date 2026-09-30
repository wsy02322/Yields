"""Pinned-window and daily-path checks for the EarnETH 60-day report."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.report_lido_earn_60d import (  # noqa: E402
    END_DATE,
    WINDOWS_DAYS,
    assert_continuous,
    build_daily_path,
    build_pinned_windows,
    compounded_daily_return,
)


def _series(start: str, days: int, price0: float = 1.0, step: float = 0.0001) -> list[dict]:
    cursor = datetime.fromisoformat(start)
    rows = []
    for i in range(days):
        day = cursor + timedelta(days=i)
        price = price0 + step * i
        rows.append(
            {
                "date": day.date().isoformat(),
                "share_price": price,
                "share_price_wei": int(price * 1e18),
                "block": 1 + i,
                "oracle_price_d18": 1,
                "oracle_report_timestamp": 1,
                "oracle_suspicious": False,
            }
        )
    return rows


def test_pinned_windows_use_exact_calendar_dates():
    series = _series("2026-07-01", 120)
    windows = build_pinned_windows(
        series, end_date=END_DATE, windows_days=WINDOWS_DAYS, exit_fee=0.0
    )
    by = {w["window"]: w for w in windows}
    assert list(by) == ["1d", "7d", "14d", "30d", "60d"]
    assert by["60d"]["start_date"] == "2026-07-31"
    assert by["60d"]["end_date"] == END_DATE
    assert by["60d"]["days"] == 60
    assert by["1d"]["start_date"] == "2026-09-28"
    assert by["30d"]["start_date"] == "2026-08-30"


def test_daily_path_compounds_to_window_return():
    series = _series("2026-07-01", 120, price0=1.0, step=0.0002)
    windows = build_pinned_windows(
        series, end_date=END_DATE, windows_days=[60], exit_fee=0.0
    )
    path = build_daily_path(
        series,
        start_date=windows[0]["start_date"],
        end_date=windows[0]["end_date"],
    )
    assert path[0]["daily_return_pct"] is None
    assert path[0]["date"] == "2026-07-31"
    assert len([row for row in path if row["in_window_move"]]) == 60
    assert compounded_daily_return(path) * 100 == pytest.approx(windows[0]["hold_return_pct"])


def test_continuous_check_rejects_gap_and_endpoint_snap():
    series = _series("2026-07-01", 120)
    gapped = [row for row in series if row["date"] != "2026-08-15"]
    with pytest.raises(SystemExit, match="missing daily snapshots"):
        assert_continuous(gapped, END_DATE)

    missing_open = [row for row in series if row["date"] != "2026-07-31"]
    with pytest.raises(SystemExit, match="snapped"):
        build_pinned_windows(
            missing_open, end_date=END_DATE, windows_days=[60], exit_fee=0.0
        )
