"""Tests for the chain-only Fluid Lite ETH APY audit."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from scripts.audit_fluid_eth_apy import (
    block_at_or_before,
    compound_apy,
    latest_complete_utc_day_end,
    render_markdown,
)


def test_latest_complete_utc_day_end_excludes_partial_tip_day():
    tip = int(datetime(2026, 7, 17, 13, 15, tzinfo=timezone.utc).timestamp())
    result = latest_complete_utc_day_end(tip)
    assert datetime.fromtimestamp(result, tz=timezone.utc) == datetime(
        2026, 7, 16, 23, 59, 59, tzinfo=timezone.utc
    )


def test_block_at_or_before_finds_exact_boundary():
    timestamps = [100, 112, 125, 137, 149, 162]

    def get_block(number: int) -> dict[str, int]:
        return {"number": number, "timestamp": timestamps[number]}

    assert block_at_or_before(
        get_block, target_timestamp=137, low_block=0, high_block=5
    ) == (3, 137)
    assert block_at_or_before(
        get_block, target_timestamp=148, low_block=0, high_block=5
    ) == (3, 137)
    assert block_at_or_before(
        get_block, target_timestamp=162, low_block=0, high_block=5
    ) == (5, 162)


def test_block_at_or_before_rejects_target_before_search_range():
    with pytest.raises(ValueError, match="predates"):
        block_at_or_before(
            lambda number: {"timestamp": 100 + number},
            target_timestamp=99,
            low_block=0,
            high_block=5,
        )


def test_compound_apy_uses_actual_elapsed_time():
    total_return, apy = compound_apy(
        10**18,
        1_001_000_000_000_000_000,
        30 * 86_400,
    )
    assert total_return == pytest.approx(0.001)
    assert apy == pytest.approx(math.expm1(math.log1p(0.001) * 365.25 / 30))


def test_rendered_report_discloses_independent_sources_and_zero_exit_fee():
    observation = {"target_time_utc": "2026-07-16T23:59:59+00:00"}
    report = {
        "audit_scope": {
            "contract": "0xabc",
            "exit_fee_applied": 0,
            "published_apy_sources_used": [],
        },
        "as_of": {"latest_complete_day_utc": "2026-07-16"},
        "windows": [
            {
                "window_days": 7,
                "start": {"target_time_utc": "2026-07-09T23:59:59+00:00"},
                "end": observation,
                "total_return_pct": 0.1,
                "apy_pct": 5.35,
            }
        ],
    }
    rendered = render_markdown(report)
    assert "归档 RPC" in rendered
    assert "退出费用按 0 处理" in rendered
    assert "Fluid / Instadapp / DefiLlama 发布的 APY" in rendered
    assert "| 7 天 " in rendered
