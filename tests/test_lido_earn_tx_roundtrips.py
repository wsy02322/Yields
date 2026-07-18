"""Unit tests for Lido EarnETH clean round-trip matching (no RPC)."""

from __future__ import annotations

from src.calculators.lido_earn_tx_roundtrips import QueueEvent, match_clean_full_round_trips


def _ev(
    kind: str,
    owner: str,
    block: int,
    amount: float,
    ts: int,
    request_ts: int,
    *,
    asset: str = "ETH",
    queue: str = "0x1111111111111111111111111111111111111111",
) -> QueueEvent:
    return QueueEvent(
        kind=kind,
        queue=queue,
        asset=asset,
        block=block,
        timestamp=ts,
        tx_hash=f"0x{kind}{block}",
        log_index=0,
        owner=owner,
        amount=amount,
        request_ts=request_ts,
        receiver=owner if kind == "red_claim" else None,
    )


def test_clean_full_accepted():
    owner = "0x1111111111111111111111111111111111111111"
    req_ts = 1_000_000
    dep_reqs = [_ev("dep_req", owner, 100, 10.0, 1_000_000, req_ts)]
    dep_claims = [
        _ev("dep_claim", owner, 110, 9.5, 1_000_000 + 3600, req_ts)
    ]
    red_reqs = [
        _ev(
            "red_req",
            owner,
            200,
            9.5,
            1_000_000 + 14 * 86400,
            1_000_000 + 14 * 86400,
            asset="wstETH",
        )
    ]
    red_claims = [
        _ev(
            "red_claim",
            owner,
            210,
            8.2,
            1_000_000 + 14 * 86400 + 7200,
            1_000_000 + 14 * 86400,
            asset="wstETH",
        )
    ]
    legs = match_clean_full_round_trips(
        dep_reqs, dep_claims, red_reqs, red_claims, min_days=1.0
    )
    assert len(legs) == 1
    assert legs[0]["sample"] == "clean_full"
    assert abs(legs[0]["shares"] - 9.5) < 1e-12
    assert abs(legs[0]["assets_in_raw"] - 10.0) < 1e-12
    assert abs(legs[0]["assets_out_raw"] - 8.2) < 1e-12


def test_clean_rejects_second_deposit():
    owner = "0x2222222222222222222222222222222222222222"
    dep_reqs = [
        _ev("dep_req", owner, 100, 10.0, 1_000_000, 1_000_000),
        _ev("dep_req", owner, 120, 1.0, 1_000_000 + 86400, 1_000_000 + 86400),
    ]
    dep_claims = [
        _ev("dep_claim", owner, 110, 9.5, 1_000_000 + 3600, 1_000_000),
        _ev("dep_claim", owner, 130, 0.95, 1_000_000 + 86400 + 3600, 1_000_000 + 86400),
    ]
    red_reqs = [
        _ev("red_req", owner, 200, 9.5, 1_000_000 + 14 * 86400, 1_000_000 + 14 * 86400)
    ]
    red_claims = [
        _ev(
            "red_claim",
            owner,
            210,
            8.0,
            1_000_000 + 14 * 86400 + 100,
            1_000_000 + 14 * 86400,
        )
    ]
    assert (
        match_clean_full_round_trips(
            dep_reqs, dep_claims, red_reqs, red_claims, min_days=1.0
        )
        == []
    )


def test_clean_rejects_partial_redeem_shares():
    owner = "0x3333333333333333333333333333333333333333"
    dep_reqs = [_ev("dep_req", owner, 100, 10.0, 1_000_000, 1_000_000)]
    dep_claims = [_ev("dep_claim", owner, 110, 9.5, 1_000_000 + 100, 1_000_000)]
    red_reqs = [
        _ev("red_req", owner, 200, 4.0, 1_000_000 + 14 * 86400, 1_000_000 + 14 * 86400)
    ]
    red_claims = [
        _ev(
            "red_claim",
            owner,
            210,
            3.5,
            1_000_000 + 14 * 86400 + 100,
            1_000_000 + 14 * 86400,
        )
    ]
    assert (
        match_clean_full_round_trips(
            dep_reqs, dep_claims, red_reqs, red_claims, min_days=1.0
        )
        == []
    )
