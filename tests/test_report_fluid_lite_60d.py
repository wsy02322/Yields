"""Block-selection helper for the Fluid Lite 60-day EOD snapshots."""

from __future__ import annotations

import pytest

from scripts.report_fluid_lite_60d import last_block_on_or_before


def test_last_block_picks_greatest_timestamp_on_or_before_target():
    timestamps = {10: 100, 11: 200, 12: 250, 13: 300}

    def timestamp_of(block: int) -> int:
        return timestamps[block]

    assert last_block_on_or_before(timestamp_of, 250, 10, 13) == 12
    assert last_block_on_or_before(timestamp_of, 249, 10, 13) == 11
    assert last_block_on_or_before(timestamp_of, 300, 10, 13) == 13


def test_last_block_rejects_lower_bound_after_target():
    with pytest.raises(ValueError):
        last_block_on_or_before(lambda block: 500, 100, 1, 2)
