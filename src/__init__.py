"""Shared helpers for Ethereum RPC access and block/time utilities."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from eth_abi import decode, encode
from eth_utils import keccak, to_checksum_address
from web3 import Web3


def load_w3(rpc_url: str, timeout: int = 45) -> Web3:
    return Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout}))


def selector(signature: str) -> bytes:
    return keccak(text=signature)[:4]


def eth_call(
    w3: Web3,
    to: str,
    signature: str,
    arg_types: list[str],
    args: list[Any],
    out_types: list[str],
    block: int | str = "latest",
) -> tuple:
    data = selector(signature)
    if arg_types:
        data += encode(arg_types, args)
    raw = w3.eth.call({"to": to_checksum_address(to), "data": data}, block)
    if not out_types:
        return (raw,)
    return decode(out_types, raw)


def utc_midnight_ts(day: datetime) -> int:
    d = day.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


def ts_to_iso_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def get_block_header(w3: Web3, block: int | str) -> dict:
    b = w3.eth.get_block(block)
    return {"number": int(b["number"]), "timestamp": int(b["timestamp"])}


def estimate_block_for_timestamp(
    w3: Web3,
    target_ts: int,
    *,
    tip_number: int | None = None,
    tip_ts: int | None = None,
    avg_block_time: float = 12.0,
    refine: bool = True,
) -> int:
    """Estimate the latest block with timestamp <= target_ts."""
    if tip_number is None or tip_ts is None:
        tip = get_block_header(w3, "latest")
        tip_number, tip_ts = tip["number"], tip["timestamp"]

    if target_ts >= tip_ts:
        return tip_number

    delta = tip_ts - target_ts
    est = max(0, tip_number - int(delta / avg_block_time))
    if not refine:
        return est

    # One refine pass using the estimated block's actual timestamp.
    try:
        hdr = get_block_header(w3, est)
        adj = int((hdr["timestamp"] - target_ts) / avg_block_time)
        est2 = max(0, est - adj)
        # Clamp to tip
        return min(est2, tip_number)
    except Exception:
        return min(est, tip_number)


def retry_call(fn, retries: int = 5, base_sleep: float = 0.6):
    last = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — network retries
            last = e
            time.sleep(base_sleep * (2**i))
    raise last  # type: ignore[misc]