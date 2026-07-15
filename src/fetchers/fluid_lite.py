"""Fluid Lite ETH (iETHv2) share-price fetcher — ERC-4626 convertToAssets."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

from web3 import Web3

from src import (
    estimate_block_for_timestamp,
    eth_call,
    get_block_header,
    progress,
    retry_call,
    ts_to_iso_date,
    utc_midnight_ts,
)


def assets_per_share(w3: Web3, token: str, block: int | str = "latest") -> int:
    (assets,) = eth_call(
        w3,
        token,
        "convertToAssets(uint256)",
        ["uint256"],
        [10**18],
        ["uint256"],
        block=block,
    )
    return int(assets)


def fetch_daily_series(
    w3: Web3,
    token: str,
    start_block: int,
    start_date: str,
    end_date: str | None = None,
    max_workers: int = 6,
) -> list[dict[str, Any]]:
    tip = get_block_header(w3, "latest")
    start_hdr = get_block_header(w3, start_block)

    dep_day = datetime.fromtimestamp(start_hdr["timestamp"], tz=timezone.utc).date()
    start_day = datetime(dep_day.year, dep_day.month, dep_day.day, tzinfo=timezone.utc)

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

    progress(f"Fluid Lite: scheduling {len(days)} daily snapshots ({days[0].date()} -> {days[-1].date()})")

    def one(day: datetime) -> dict[str, Any] | None:
        ts = utc_midnight_ts(day)
        eod_ts = min(ts + 86400 - 1, tip["timestamp"])
        if eod_ts < start_hdr["timestamp"]:
            return None

        def _run():
            block = estimate_block_for_timestamp(
                eod_ts, tip_number=tip["number"], tip_ts=tip["timestamp"]
            )
            block = max(block, start_block)
            assets = assets_per_share(w3, token, block)
            return {
                "date": day.strftime("%Y-%m-%d"),
                "block": block,
                "block_timestamp_est": eod_ts,
                "share_price_wei": assets,
                "share_price": assets / 1e18,
            }

        return retry_call(_run)

    rows: list[dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(one, d) for d in days]
        for fut in as_completed(futs):
            row = fut.result()
            done += 1
            if row is not None:
                rows.append(row)
            if done % 50 == 0 or done == len(days):
                progress(f"Fluid Lite: {done}/{len(days)} days")

    rows.sort(key=lambda r: r["date"])
    by_date: dict[str, dict[str, Any]] = {r["date"]: r for r in rows}
    return [by_date[k] for k in sorted(by_date)]


def fetch_latest(w3: Web3, token: str) -> dict[str, Any]:
    tip = get_block_header(w3, "latest")
    assets = assets_per_share(w3, token, "latest")
    return {
        "date": ts_to_iso_date(tip["timestamp"]),
        "block": tip["number"],
        "block_timestamp": tip["timestamp"],
        "share_price_wei": assets,
        "share_price": assets / 1e18,
    }