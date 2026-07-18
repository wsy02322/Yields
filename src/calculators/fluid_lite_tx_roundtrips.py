"""Fluid Lite ETH: match deposit→withdraw round-trips vs share-price path.

For each FIFO-matched round-trip on iETHv2:
  tx_return  = assets_out / assets_in - 1   (Withdraw assets already net of 0.05% exit)
  share_path = convertToAssets(t1)/convertToAssets(t0) * (1 - exit_fee) - 1

Compare the two over the same [t0, t1].
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from eth_abi import decode
from eth_utils import keccak, to_checksum_address
from web3 import Web3

from src import eth_call, retry_call
from src.calculators.apy import annualize as annualize_apy

IETH_V2 = "0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78"
EXIT_FEE = 0.0005

DEPOSIT_TOPIC = "0x" + keccak(text="Deposit(address,address,uint256,uint256)").hex()
WITHDRAW_TOPIC = "0x" + keccak(text="Withdraw(address,address,address,uint256,uint256)").hex()


@dataclass
class VaultEvent:
    kind: str  # deposit | withdraw
    block: int
    timestamp: int
    tx_hash: str
    log_index: int
    owner: str
    assets: float  # stETH units
    shares: float
    # withdraw only
    receiver: str | None = None


@dataclass
class RoundTrip:
    owner: str
    deposit_tx: str
    withdraw_tx: str
    deposit_block: int
    withdraw_block: int
    deposit_ts: int
    withdraw_ts: int
    days: float
    shares: float
    assets_in: float
    assets_out: float
    tx_return: float
    tx_apy: float | None
    p0: float
    p1: float
    share_return_hold: float
    share_return_after_exit: float
    share_apy_hold: float | None
    share_apy_after_exit: float | None
    gap_return_pp: float  # (tx_return - share_return_after_exit) * 100
    gap_apy_pp: float | None


def _addr_from_topic(topic) -> str:
    h = topic.hex() if hasattr(topic, "hex") else str(topic)
    h = h[2:] if h.startswith("0x") else h
    return to_checksum_address("0x" + h[-40:])


def convert_to_assets(w3: Web3, block: int | str, vault: str = IETH_V2) -> float:
    (assets,) = eth_call(
        w3,
        vault,
        "convertToAssets(uint256)",
        ["uint256"],
        [10**18],
        ["uint256"],
        block=block,
    )
    return int(assets) / 1e18


def _get_logs_chunked(
    w3: Web3,
    *,
    address: str,
    topic: str,
    from_block: int,
    to_block: int,
    chunk: int = 3000,
) -> list:
    out = []
    for fb in range(from_block, to_block + 1, chunk):
        tb = min(fb + chunk - 1, to_block)

        def _run(fb=fb, tb=tb):
            return w3.eth.get_logs(
                {
                    "fromBlock": fb,
                    "toBlock": tb,
                    "address": to_checksum_address(address),
                    "topics": [topic],
                }
            )

        logs = retry_call(_run, retries=5, base_sleep=1.0)
        out.extend(logs)
        time.sleep(0.05)
    return out


def _block_ts_cache(w3: Web3) -> dict[int, int]:
    cache: dict[int, int] = {}

    def get(bn: int) -> int:
        if bn not in cache:
            cache[bn] = int(w3.eth.get_block(bn)["timestamp"])
        return cache[bn]

    get.cache = cache  # type: ignore[attr-defined]
    return get  # type: ignore[return-value]


def fetch_vault_events(
    w3: Web3,
    *,
    from_block: int,
    to_block: int | None = None,
    vault: str = IETH_V2,
    chunk: int = 3000,
) -> tuple[list[VaultEvent], list[VaultEvent]]:
    tip = int(w3.eth.block_number) if to_block is None else to_block
    get_ts = _block_ts_cache(w3)

    dep_logs = _get_logs_chunked(
        w3, address=vault, topic=DEPOSIT_TOPIC, from_block=from_block, to_block=tip, chunk=chunk
    )
    wd_logs = _get_logs_chunked(
        w3, address=vault, topic=WITHDRAW_TOPIC, from_block=from_block, to_block=tip, chunk=chunk
    )

    deposits: list[VaultEvent] = []
    for lg in dep_logs:
        assets, shares = decode(["uint256", "uint256"], bytes(lg["data"]))
        owner = _addr_from_topic(lg["topics"][2])
        bn = int(lg["blockNumber"])
        deposits.append(
            VaultEvent(
                kind="deposit",
                block=bn,
                timestamp=get_ts(bn),
                tx_hash=lg["transactionHash"].hex(),
                log_index=int(lg["logIndex"]),
                owner=owner,
                assets=int(assets) / 1e18,
                shares=int(shares) / 1e18,
            )
        )

    withdraws: list[VaultEvent] = []
    for lg in wd_logs:
        assets, shares = decode(["uint256", "uint256"], bytes(lg["data"]))
        owner = _addr_from_topic(lg["topics"][3])
        receiver = _addr_from_topic(lg["topics"][2])
        bn = int(lg["blockNumber"])
        withdraws.append(
            VaultEvent(
                kind="withdraw",
                block=bn,
                timestamp=get_ts(bn),
                tx_hash=lg["transactionHash"].hex(),
                log_index=int(lg["logIndex"]),
                owner=owner,
                assets=int(assets) / 1e18,
                shares=int(shares) / 1e18,
                receiver=receiver,
            )
        )

    deposits.sort(key=lambda e: (e.block, e.log_index))
    withdraws.sort(key=lambda e: (e.block, e.log_index))
    return deposits, withdraws


def match_round_trips_fifo(
    deposits: list[VaultEvent],
    withdraws: list[VaultEvent],
    *,
    min_shares: float = 1e-6,
    min_days: float = 0.01,
) -> list[dict[str, Any]]:
    """FIFO-match withdraw shares against prior deposits per owner.

    Returns unmatched structural legs (no share price yet).
    """
    # Remaining deposit lots: owner -> list of {shares_left, assets_in_per_share, ...}
    lots: dict[str, list[dict[str, Any]]] = {}
    for d in deposits:
        if d.shares <= 0:
            continue
        lots.setdefault(d.owner.lower(), []).append(
            {
                "shares_left": d.shares,
                "assets_per_share": d.assets / d.shares,
                "deposit": d,
            }
        )

    legs: list[dict[str, Any]] = []
    for w in withdraws:
        need = w.shares
        if need <= min_shares:
            continue
        queue = lots.get(w.owner.lower(), [])
        while need > min_shares and queue:
            lot = queue[0]
            take = min(lot["shares_left"], need)
            if take <= min_shares:
                queue.pop(0)
                continue
            assets_in = take * lot["assets_per_share"]
            # Pro-rate withdraw assets by shares taken / withdraw shares
            assets_out = w.assets * (take / w.shares)
            dep = lot["deposit"]
            days = (w.timestamp - dep.timestamp) / 86400.0
            if days >= min_days and assets_in > 0:
                legs.append(
                    {
                        "owner": w.owner,
                        "deposit_tx": dep.tx_hash,
                        "withdraw_tx": w.tx_hash,
                        "deposit_block": dep.block,
                        "withdraw_block": w.block,
                        "deposit_ts": dep.timestamp,
                        "withdraw_ts": w.timestamp,
                        "days": days,
                        "shares": take,
                        "assets_in": assets_in,
                        "assets_out": assets_out,
                    }
                )
            lot["shares_left"] -= take
            need -= take
            if lot["shares_left"] <= min_shares:
                queue.pop(0)
        # leftover need = withdraw without matching deposit in window (ignored)
    return legs


def enrich_legs_with_share_path(
    w3: Web3,
    legs: list[dict[str, Any]],
    *,
    vault: str = IETH_V2,
    exit_fee: float = EXIT_FEE,
) -> list[RoundTrip]:
    # Cache convertToAssets per block
    pps: dict[int, float] = {}

    def pps_at(block: int) -> float:
        if block not in pps:
            pps[block] = retry_call(lambda: convert_to_assets(w3, block, vault))
        return pps[block]

    out: list[RoundTrip] = []
    for i, leg in enumerate(legs):
        p0 = pps_at(leg["deposit_block"])
        p1 = pps_at(leg["withdraw_block"])
        days = float(leg["days"])
        tx_ret = leg["assets_out"] / leg["assets_in"] - 1.0
        share_hold = p1 / p0 - 1.0
        share_exit = p1 / p0 * (1.0 - exit_fee) - 1.0
        tx_apy = annualize_apy(tx_ret, days)
        sh_apy = annualize_apy(share_hold, days)
        sx_apy = annualize_apy(share_exit, days)
        gap_apy = None
        if tx_apy is not None and sx_apy is not None:
            gap_apy = (tx_apy - sx_apy) * 100.0
        out.append(
            RoundTrip(
                owner=leg["owner"],
                deposit_tx=leg["deposit_tx"],
                withdraw_tx=leg["withdraw_tx"],
                deposit_block=leg["deposit_block"],
                withdraw_block=leg["withdraw_block"],
                deposit_ts=leg["deposit_ts"],
                withdraw_ts=leg["withdraw_ts"],
                days=days,
                shares=leg["shares"],
                assets_in=leg["assets_in"],
                assets_out=leg["assets_out"],
                tx_return=tx_ret,
                tx_apy=tx_apy,
                p0=p0,
                p1=p1,
                share_return_hold=share_hold,
                share_return_after_exit=share_exit,
                share_apy_hold=sh_apy,
                share_apy_after_exit=sx_apy,
                gap_return_pp=(tx_ret - share_exit) * 100.0,
                gap_apy_pp=gap_apy,
            )
        )
        if (i + 1) % 25 == 0:
            print(f"  enriched {i+1}/{len(legs)} round-trips", flush=True)
    return out


def summarize_round_trips(trips: list[RoundTrip]) -> dict[str, Any]:
    if not trips:
        return {"n": 0}

    def pct(xs: list[float]) -> dict[str, float]:
        xs = sorted(xs)
        n = len(xs)

        def q(p: float) -> float:
            if n == 1:
                return xs[0]
            i = min(n - 1, max(0, int(round(p * (n - 1)))))
            return xs[i]

        return {
            "n": n,
            "min": xs[0],
            "p10": q(0.10),
            "median": q(0.50),
            "p90": q(0.90),
            "max": xs[-1],
            "mean": sum(xs) / n,
        }

    abs_gap_ret = [abs(t.gap_return_pp) for t in trips]
    abs_gap_apy = [abs(t.gap_apy_pp) for t in trips if t.gap_apy_pp is not None]
    buckets = {
        "lt_7d": [t for t in trips if t.days < 7],
        "d7_30": [t for t in trips if 7 <= t.days < 30],
        "d30_90": [t for t in trips if 30 <= t.days < 90],
        "ge_90d": [t for t in trips if t.days >= 90],
    }
    return {
        "n": len(trips),
        "exit_fee": EXIT_FEE,
        "abs_gap_return_pp": pct(abs_gap_ret),
        "abs_gap_apy_pp": pct(abs_gap_apy) if abs_gap_apy else None,
        "buckets": {
            k: {
                "n": len(v),
                "median_abs_gap_return_pp": (
                    sorted(abs(t.gap_return_pp) for t in v)[len(v) // 2] if v else None
                ),
                "median_tx_apy_pct": (
                    sorted(t.tx_apy * 100 for t in v if t.tx_apy is not None)[len(v) // 2]
                    if any(t.tx_apy is not None for t in v)
                    else None
                ),
            }
            for k, v in buckets.items()
        },
    }


def round_trip_to_row(t: RoundTrip) -> dict[str, Any]:
    d: dict[str, Any] = asdict(t)
    d["deposit_utc"] = datetime.fromtimestamp(t.deposit_ts, tz=timezone.utc).isoformat()
    d["withdraw_utc"] = datetime.fromtimestamp(t.withdraw_ts, tz=timezone.utc).isoformat()
    d["tx_return_pct"] = t.tx_return * 100
    d["tx_apy_pct"] = None if t.tx_apy is None else t.tx_apy * 100
    d["share_return_hold_pct"] = t.share_return_hold * 100
    d["share_return_after_exit_pct"] = t.share_return_after_exit * 100
    d["share_apy_hold_pct"] = None if t.share_apy_hold is None else t.share_apy_hold * 100
    d["share_apy_after_exit_pct"] = (
        None if t.share_apy_after_exit is None else t.share_apy_after_exit * 100
    )
    return d
