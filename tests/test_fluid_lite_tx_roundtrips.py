"""Unit tests for Fluid Lite tx round-trip FIFO matching (no RPC)."""

from __future__ import annotations

from src.calculators.fluid_lite_tx_roundtrips import VaultEvent, match_round_trips_fifo


def _dep(owner: str, block: int, assets: float, shares: float, ts: int) -> VaultEvent:
    return VaultEvent(
        kind="deposit",
        block=block,
        timestamp=ts,
        tx_hash=f"0xdep{block}",
        log_index=0,
        owner=owner,
        assets=assets,
        shares=shares,
    )


def _wd(owner: str, block: int, assets: float, shares: float, ts: int) -> VaultEvent:
    return VaultEvent(
        kind="withdraw",
        block=block,
        timestamp=ts,
        tx_hash=f"0xwd{block}",
        log_index=0,
        owner=owner,
        assets=assets,
        shares=shares,
        receiver=owner,
    )


def test_fifo_full_round_trip():
    owner = "0x1111111111111111111111111111111111111111"
    deps = [_dep(owner, 100, assets=10.0, shares=8.0, ts=1_000_000)]
    wds = [_wd(owner, 200, assets=10.05 * 0.9995, shares=8.0, ts=1_000_000 + 7 * 86400)]
    legs = match_round_trips_fifo(deps, wds, min_days=1.0)
    assert len(legs) == 1
    assert abs(legs[0]["assets_in"] - 10.0) < 1e-12
    assert abs(legs[0]["shares"] - 8.0) < 1e-12
    assert abs(legs[0]["days"] - 7.0) < 1e-9


def test_fifo_partial_two_lots():
    owner = "0x2222222222222222222222222222222222222222"
    deps = [
        _dep(owner, 100, assets=10.0, shares=10.0, ts=1_000_000),
        _dep(owner, 110, assets=20.0, shares=20.0, ts=1_000_100),
    ]
    wds = [_wd(owner, 200, assets=15.0, shares=15.0, ts=1_000_000 + 10 * 86400)]
    legs = match_round_trips_fifo(deps, wds, min_days=0.01)
    assert len(legs) == 2
    assert abs(legs[0]["shares"] - 10.0) < 1e-12
    assert abs(legs[0]["assets_in"] - 10.0) < 1e-12
    assert abs(legs[1]["shares"] - 5.0) < 1e-12
    assert abs(legs[1]["assets_in"] - 5.0) < 1e-12


def test_clean_full_round_trip_accepted():
    from src.calculators.fluid_lite_tx_roundtrips import match_clean_full_round_trips

    owner = "0x3333333333333333333333333333333333333333"
    deps = [_dep(owner, 100, assets=10.0, shares=8.0, ts=1_000_000)]
    wds = [_wd(owner, 200, assets=10.1 * 0.9995, shares=8.0, ts=1_000_000 + 14 * 86400)]
    legs = match_clean_full_round_trips(deps, wds, min_days=1.0)
    assert len(legs) == 1
    assert legs[0]["sample"] == "clean_full"
    assert abs(legs[0]["assets_in"] - 10.0) < 1e-12
    assert abs(legs[0]["assets_out"] - 10.1 * 0.9995) < 1e-12


def test_clean_rejects_intervening_deposit():
    from src.calculators.fluid_lite_tx_roundtrips import match_clean_full_round_trips

    owner = "0x4444444444444444444444444444444444444444"
    deps = [
        _dep(owner, 100, assets=10.0, shares=8.0, ts=1_000_000),
        _dep(owner, 150, assets=1.0, shares=0.8, ts=1_000_000 + 3 * 86400),
    ]
    wds = [_wd(owner, 200, assets=10.0, shares=8.0, ts=1_000_000 + 14 * 86400)]
    legs = match_clean_full_round_trips(deps, wds, min_days=1.0)
    assert legs == []


def test_clean_rejects_partial_share_mismatch():
    from src.calculators.fluid_lite_tx_roundtrips import match_clean_full_round_trips

    owner = "0x5555555555555555555555555555555555555555"
    deps = [_dep(owner, 100, assets=10.0, shares=8.0, ts=1_000_000)]
    wds = [_wd(owner, 200, assets=5.0, shares=4.0, ts=1_000_000 + 14 * 86400)]
    legs = match_clean_full_round_trips(deps, wds, min_days=1.0)
    assert legs == []
