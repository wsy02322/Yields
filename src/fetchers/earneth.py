"""Lido EarnETH share-price fetcher via Mellow Oracle reports.

Mellow Core Vaults use inverted pricing: priceD18 ≈ shares * 1e18 / assets.
Therefore ETH-per-share = 1e36 / priceD18.
Protocol (1%) and performance (10%) fees are minted as shares on oracle
reports and are already reflected in this net share price.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

from eth_utils import to_checksum_address
from web3 import Web3

from src import eth_call, estimate_block_for_timestamp, get_block_header, retry_call, ts_to_iso_date, utc_midnight_ts


ETH_SENTINEL = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"


def get_oracle_report(
    w3: Web3, oracle: str, asset: str, block: int | str = "latest"
) -> tuple[int, int, bool]:
    price, ts, suspicious = eth_call(
        w3,
        oracle,
        "getReport(address)",
        ["address"],
        [to_checksum_address(asset)],
        ["uint224", "uint32", "bool"],
        block=block,
    )
    return int(price), int(ts), bool(suspicious)


def price_to_eth_per_share(price_d18: int) -> float:
    if price_d18 <= 0:
        raise ValueError("invalid oracle price")
    return (10**36) / price_d18 / 1e18


def eth_per_share_wei(price_d18: int) -> int:
    """Integer wei of ETH backing one share (1e18 share units)."""
    if price_d18 <= 0:
        raise ValueError("invalid oracle price")
    return (10**36) // price_d18


def read_fee_params(w3: Web3, fee_manager: str) -> dict[str, int]:
    out = {}
    for name in ("depositFeeD6", "redeemFeeD6", "performanceFeeD6", "protocolFeeD6"):
        (val,) = eth_call(w3, fee_manager, f"{name}()", [], [], ["uint256"])
        out[name] = int(val)
    return out


def fetch_daily_series(
    w3: Web3,
    oracle: str,
    base_asset: str,
    start_block: int,
    start_date: str,
    end_date: str | None = None,
    max_workers: int = 6,
) -> list[dict[str, Any]]:
    tip = get_block_header(w3, "latest")
    start_hdr = get_block_header(w3, start_block)

    dep_day = datetime.fromtimestamp(start_hdr["timestamp"], tz=timezone.utc).date()
    start_day = datetime(dep_day.year, dep_day.month, dep_day.day, tzinfo=timezone.utc)
    configured = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    if configured > start_day:
        start_day = configured

    if end_date:
        end_day = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    else:
        end_day = datetime.fromtimestamp(tip["timestamp"], tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    days: list[datetime] = []
    cur = start_day
    while cur <= end_day:
        days.append(cur)
        cur += timedelta(days=1)

    def one(day: datetime) -> dict[str, Any] | None:
        ts = utc_midnight_ts(day)
        eod_ts = min(ts + 86400 - 1, tip["timestamp"])
        if eod_ts < start_hdr["timestamp"]:
            return None

        def _run():
            block = estimate_block_for_timestamp(
                w3,
                eod_ts,
                tip_number=tip["number"],
                tip_ts=tip["timestamp"],
            )
            block = max(block, start_block)
            hdr = get_block_header(w3, block)
            price, report_ts, suspicious = get_oracle_report(w3, oracle, base_asset, block)
            wei = eth_per_share_wei(price)
            return {
                "date": day.strftime("%Y-%m-%d"),
                "block": block,
                "block_timestamp": hdr["timestamp"],
                "block_timestamp_iso": datetime.fromtimestamp(
                    hdr["timestamp"], tz=timezone.utc
                ).isoformat(),
                "oracle_price_d18": price,
                "oracle_report_timestamp": report_ts,
                "oracle_suspicious": suspicious,
                "share_price_wei": wei,
                "share_price": wei / 1e18,
            }

        return retry_call(_run)

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(one, d): d for d in days}
        for fut in as_completed(futs):
            row = fut.result()
            if row is not None:
                rows.append(row)

    rows.sort(key=lambda r: r["date"])
    by_date: dict[str, dict[str, Any]] = {}
    for r in rows:
        by_date[r["date"]] = r
    return [by_date[k] for k in sorted(by_date)]


def fetch_latest(w3: Web3, oracle: str, base_asset: str = ETH_SENTINEL) -> dict[str, Any]:
    tip = get_block_header(w3, "latest")
    price, report_ts, suspicious = get_oracle_report(w3, oracle, base_asset, "latest")
    wei = eth_per_share_wei(price)
    return {
        "date": ts_to_iso_date(tip["timestamp"]),
        "block": tip["number"],
        "block_timestamp": tip["timestamp"],
        "oracle_price_d18": price,
        "oracle_report_timestamp": report_ts,
        "oracle_suspicious": suspicious,
        "share_price_wei": wei,
        "share_price": wei / 1e18,
    }