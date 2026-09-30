#!/usr/bin/env python3
"""Trailing 60-day Fluid Lite ETH report from ERC-4626 share price.

Extends ``data/fluid-lite-eth/daily_share_price.csv`` from the day after the
last stored snapshot through 2026-09-29. New snapshots use the last block at
or before 23:59:59 UTC, because iETHv2 accrues continuously. Does not rewrite
the 2026-07-17 summary or other existing audit artifacts.

2026-07-17 in the stored series is an intraday tip (05:36 UTC), not an EOD
snapshot. It is left unchanged and is not an endpoint of these windows.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.report_lido_earn_60d import (  # noqa: E402
    END_DATE,
    WINDOWS_DAYS,
    assert_continuous,
    build_daily_path,
    build_pinned_windows,
    compounded_daily_return,
    write_json,
)
from src import (  # noqa: E402
    estimate_block_for_timestamp,
    eth_call,
    get_block_header,
    load_w3,
)
from src.calculators.apy import period_return  # noqa: E402
from src.fetchers.fluid_lite import assets_per_share  # noqa: E402
from src.fetchers.fluid_lite_official import fetch_official_vault_apy  # noqa: E402

CSV_FIELDS = [
    "date",
    "share_price",
    "share_price_wei",
    "block",
    "block_timestamp_est",
]
FEE_SCALE = 1_000_000


def last_block_on_or_before(timestamp_of, target_ts: int, lo: int, hi: int) -> int:
    """Greatest block in ``[lo, hi]`` whose timestamp is <= ``target_ts``.

    ``timestamp_of(lo)`` must be <= target. If ``timestamp_of(hi)`` is still
    <= target, ``hi`` is the answer (the search already reached the tip).
    """
    if timestamp_of(lo) > target_ts:
        raise ValueError("lower block is after the target timestamp")
    if timestamp_of(hi) <= target_ts:
        return hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if timestamp_of(mid) <= target_ts:
            lo = mid
        else:
            hi = mid
    return lo


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def append_csv(path: Path, rows: list[dict]) -> None:
    with path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})


def as_series(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append(
            {
                "date": row["date"],
                "share_price": float(row["share_price"]),
                "share_price_wei": int(row["share_price_wei"]),
                "block": int(row["block"]),
                "block_timestamp_est": int(row["block_timestamp_est"]),
            }
        )
    out.sort(key=lambda r: r["date"])
    return out


def eod_timestamp(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()) + 86400 - 1


def block_for_eod(w3, day: str, *, tip_number: int, tip_ts: int, start_block: int) -> tuple[int, int]:
    target = eod_timestamp(day)
    est = estimate_block_for_timestamp(target, tip_number=tip_number, tip_ts=tip_ts)
    cache: dict[int, int] = {}

    def timestamp_of(block: int) -> int:
        if block not in cache:
            cache[block] = get_block_header(w3, block)["timestamp"]
        return cache[block]

    lo = max(start_block, est - 4000)
    hi = min(tip_number, max(est, lo) + 4000)
    while timestamp_of(lo) > target:
        lo = max(start_block, lo - 8000)
        if lo == start_block and timestamp_of(lo) > target:
            raise SystemExit(f"no block on or before {day} EOD")
    while timestamp_of(hi) <= target and hi < tip_number:
        hi = min(tip_number, hi + 8000)
    block = last_block_on_or_before(timestamp_of, target, lo, hi)
    return block, timestamp_of(block)


def fetch_eod_row(w3, token: str, day: str, *, tip_number: int, tip_ts: int, start_block: int) -> dict:
    block, actual_ts = block_for_eod(
        w3, day, tip_number=tip_number, tip_ts=tip_ts, start_block=start_block
    )
    target = eod_timestamp(day)
    if actual_ts > target or target - actual_ts > 30:
        raise SystemExit(
            f"{day} block {block} timestamp {actual_ts} is not within 30s before EOD {target}"
        )
    assets = assets_per_share(w3, token, block)
    return {
        "date": day,
        "block": block,
        "block_timestamp": actual_ts,
        "block_timestamp_est": target,
        "share_price_wei": assets,
        "share_price": assets / 1e18,
    }


def read_fees_at(w3, token: str, block: int) -> dict[str, int]:
    out = {}
    for name in ("revenueFeePercentage", "withdrawalFeePercentage"):
        (val,) = eth_call(w3, token, f"{name}()", [], [], ["uint256"], block=block)
        out[name] = int(val)
    return out


def fee_rates(raw: dict[str, int]) -> dict[str, float]:
    return {
        "performance_fee": raw["revenueFeePercentage"] / FEE_SCALE,
        "exit_fee": raw["withdrawalFeePercentage"] / FEE_SCALE,
    }


def fee_regimes(w3, token: str, start_block: int, end_block: int) -> list[dict]:
    start_fees = read_fees_at(w3, token, start_block)
    regimes = [{"block": start_block, "fees": start_fees}]
    cursor = start_block
    while cursor < end_block:
        if read_fees_at(w3, token, end_block) == regimes[-1]["fees"]:
            break
        lo, hi = cursor, end_block
        before = regimes[-1]["fees"]
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if read_fees_at(w3, token, mid) == before:
                lo = mid
            else:
                hi = mid
        regimes.append({"block": hi, "fees": read_fees_at(w3, token, hi)})
        cursor = hi
    for regime in regimes:
        header = get_block_header(w3, regime["block"])
        regime["timestamp"] = header["timestamp"]
        regime["timestamp_utc"] = datetime.fromtimestamp(
            header["timestamp"], tz=timezone.utc
        ).isoformat()
        regime["rates"] = fee_rates(regime["fees"])
    return regimes


def write_daily_csv(path: Path, path_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "share_price",
        "daily_return_pct",
        "share_price_wei",
        "block",
        "block_timestamp",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in path_rows:
            out = dict(row)
            if out.get("daily_return_pct") is None:
                out["daily_return_pct"] = ""
            writer.writerow(out)


def markdown_report(report: dict) -> str:
    lines = [
        "# Fluid Lite ETH trailing 60-day share-price report",
        "",
        f"End date: **{report['end_date']}** UTC (last complete day in this pull).",
        "",
        "Share price is ERC-4626 `convertToAssets(1e18)` of iETHv2, denominated in **stETH**. "
        "The 20% performance fee is already inside that price. "
        "Hold return ignores the 0.05% exit fee. Realized return applies that exit fee once "
        "at the window end. Mellow-style points are not part of this vault.",
        "",
        "New daily rows use the last block at or before 23:59:59 UTC. "
        "The stored 2026-07-17 row is an intraday snapshot and is not an endpoint here. "
        "The 2026-07-17 summary files are left unchanged.",
        "",
        "## Windows ending 2026-09-29",
        "",
        "| Window | Start → End | Hold return | Hold APY | Realized return | Realized APY | Preferred |",
        "|--------|-------------|------------:|---------:|----------------:|-------------:|-----------|",
    ]
    for w in report["windows"]:
        lines.append(
            f"| {w['window']} | {w['start_date']} → {w['end_date']} | "
            f"{w['hold_return_pct']:.6f}% | {w['hold_apy_pct']:.6f}% | "
            f"{w['realized_return_pct']:.6f}% | {w['realized_apy_pct']:.6f}% | "
            f"{w['preferred_metric']} |"
        )
    lines.extend(
        [
            "",
            "For windows of 30 days or less, prefer Hold APY. "
            "Annualizing the one-time 0.05% exit fee over a short window is marked cautionary.",
            "",
            "## Fee parameters",
            "",
            "| Status | UTC | Block | Performance | Exit |",
            "|--------|-----|------:|------------:|-----:|",
        ]
    )
    for regime in report["fee_regimes"]:
        rates = regime["rates"]
        lines.append(
            f"| {regime['kind']} | {regime['timestamp_utc']} | {regime['block']} | "
            f"{rates['performance_fee'] * 100:.4g}% | {rates['exit_fee'] * 100:.4g}% |"
        )
    if len(report["fee_regimes"]) == 1:
        lines.append("")
        lines.append("These rates were unchanged at the 2026-09-29 snapshot.")
    ref = report.get("published_apy_untrusted_reference") or {}
    lines.extend(["", "## Untrusted UI reference", ""])
    if ref.get("net_apy_pct") is None:
        lines.append(f"Instadapp Lite API was not used. {ref.get('error', '')}".rstrip())
    else:
        lines.append(
            f"Instadapp forward-looking Net APY = **{ref['net_apy_pct']:.6f}%**, "
            f"Gross APY = **{ref['gross_apy_pct']:.6f}%**. "
            "This is a spot estimate of the current position, not a trailing 60-day result. "
            f"Independent 1d Hold APY = **{ref.get('independent_1d_hold_apy_pct'):.6f}%**."
        )
    lines.extend(
        [
            "",
            "## 60-day path",
            "",
            "Opening row is the baseline in stETH per share. "
            "Daily moves are hold changes and compound to the 60-day hold return. "
            "The exit fee is not applied to each day.",
            "",
            "| Date | Share price (stETH) | Daily change |",
            "|------|--------------------:|-------------:|",
        ]
    )
    for row in report["daily_path"]:
        change = "—" if row["daily_return_pct"] is None else f"{row['daily_return_pct']:.6f}%"
        lines.append(f"| {row['date']} | {row['share_price']:.10f} | {change} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    vault = cfg["vaults"]["fluid_lite_eth"]
    token = vault["receipt_token"]
    series_path = ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv"
    existing = read_csv(series_path)
    if not existing:
        raise SystemExit(f"missing series: {series_path}")
    last_stored = existing[-1]["date"]
    fetch_start_dt = datetime.fromisoformat(last_stored) + timedelta(days=1)
    fetch_start = fetch_start_dt.date().isoformat()

    w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
    tip = w3.eth.get_block("latest")
    tip_number = int(tip["number"])
    tip_ts = int(tip["timestamp"])
    if tip_ts < eod_timestamp(END_DATE):
        raise SystemExit(f"chain tip is before {END_DATE} 23:59:59 UTC")

    appended = 0
    if fetch_start <= END_DATE:
        print(f"pulling EOD snapshots {fetch_start} → {END_DATE}")
        days = []
        cursor = fetch_start_dt
        end_dt = datetime.fromisoformat(END_DATE)
        while cursor <= end_dt:
            days.append(cursor.date().isoformat())
            cursor += timedelta(days=1)
        fresh = []
        for i, day in enumerate(days, start=1):
            fresh.append(
                fetch_eod_row(
                    w3,
                    token,
                    day,
                    tip_number=tip_number,
                    tip_ts=tip_ts,
                    start_block=int(vault["deployment_block"]),
                )
            )
            if i % 10 == 0 or i == len(days):
                print(f"Fluid Lite: {i}/{len(days)} days", flush=True)
        have = {row["date"] for row in existing}
        new_rows = [row for row in fresh if row["date"] not in have]
        if not new_rows or new_rows[0]["date"] != fetch_start or new_rows[-1]["date"] != END_DATE:
            raise SystemExit("fetch did not cover the requested dates")
        append_csv(series_path, new_rows)
        appended = len(new_rows)
        print(f"appended {appended} rows")
    else:
        print(f"series already reaches {last_stored}; no pull")

    rows = as_series(read_csv(series_path))
    rows = [row for row in rows if row["date"] <= END_DATE]
    assert_continuous(rows, END_DATE)
    by_date = {row["date"]: row for row in rows}

    # Re-read the new endpoints so the CSV matches convertToAssets at the pinned block.
    for day in (fetch_start if appended else END_DATE, "2026-07-31", END_DATE):
        row = by_date[day]
        assets = assets_per_share(w3, token, row["block"])
        if assets != row["share_price_wei"]:
            raise SystemExit(f"share mismatch on {day}: csv={row['share_price_wei']} chain={assets}")
        header = get_block_header(w3, row["block"])
        if int(header["timestamp"]) > int(row["block_timestamp_est"]):
            raise SystemExit(f"{day} block is after its EOD target")

    regimes = fee_regimes(
        w3, token, by_date["2026-07-31"]["block"], by_date[END_DATE]["block"]
    )
    regimes[0]["kind"] = "in_force_at_window_open"
    for regime in regimes[1:]:
        regime["kind"] = "changed"
    exit_fee = regimes[-1]["rates"]["exit_fee"]
    if any(abs(regime["rates"]["exit_fee"] - exit_fee) > 1e-12 for regime in regimes):
        print("exit fee changed inside the window; realized uses the end-of-window rate")

    windows = build_pinned_windows(
        rows, end_date=END_DATE, windows_days=WINDOWS_DAYS, exit_fee=exit_fee
    )
    window_60 = next(w for w in windows if w["window"] == "60d")
    path = build_daily_path(
        rows, start_date=window_60["start_date"], end_date=window_60["end_date"]
    )
    for row in path:
        src = by_date[row["date"]]
        row["block_timestamp"] = get_block_header(w3, src["block"])["timestamp"]
    compounded = compounded_daily_return(path)
    raw_60 = period_return(path[0]["share_price"], path[-1]["share_price"])
    if abs(compounded - raw_60) > 1e-12:
        raise SystemExit(f"daily path {compounded:.12f} != 60d hold {raw_60:.12f}")

    published_ref: dict
    try:
        official = fetch_official_vault_apy(vault=token)
        one_day = next(w for w in windows if w["window"] == "1d")
        published_ref = {
            "trust": "untrusted_forward_looking_reference",
            "net_apy_pct": official["net_apy_pct"],
            "gross_apy_pct": official["gross_apy_pct"],
            "revenue_fee": official.get("revenue_fee"),
            "withdrawal_fee": official.get("withdrawal_fee"),
            "source_url": official["source_url"],
            "fetched_at_utc": official["fetched_at_utc"],
            "independent_1d_hold_apy_pct": one_day["hold_apy_pct"],
            "note": (
                "UI Net/Gross APY is a spot forward estimate. "
                "It is not the trailing 60-day hold result."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        published_ref = {
            "trust": "untrusted_forward_looking_reference",
            "error": str(exc),
            "note": "Official API fetch failed. The result still uses share price only.",
        }

    report = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "tip_block": tip_number,
        "tip_timestamp": tip_ts,
        "end_date": END_DATE,
        "rows_appended_this_run": appended,
        "snapshots_after_2026_07_17": sum(1 for row in rows if row["date"] > "2026-07-17"),
        "series_first_date": rows[0]["date"],
        "series_last_date": rows[-1]["date"],
        "intraday_row_left_unchanged": {
            "date": "2026-07-17",
            "block_timestamp_est": by_date["2026-07-17"]["block_timestamp_est"],
            "note": "Stored tip is 2026-07-17 05:36 UTC, not EOD. Not used as a window endpoint.",
        },
        "vault": {
            "name": vault["name"],
            "receipt_token": token,
            "underlying_asset": vault["underlying_asset"],
            "underlying_symbol": "stETH",
        },
        "method": {
            "share_price": "ERC-4626 convertToAssets(1e18), stETH per iETHv2 share",
            "sampling": "last block at or before 23:59:59 UTC for rows appended by this report",
            "hold_return": "end_share_price / start_share_price - 1",
            "hold_apy": "(1+R)^(365.25/days)-1",
            "realized": "exit fee applied once to the terminal share price",
            "fees_in_price": "performance fee is already in convertToAssets",
            "exit_fee_used": exit_fee,
            "excluded": ["published UI Net/Gross APY"],
        },
        "fee_regimes": regimes,
        "windows": windows,
        "daily_path_compounds_to_60d_hold_return": True,
        "published_apy_untrusted_reference": published_ref,
        "daily_path": path,
        "unchanged_prior_artifacts": [
            "data/fluid-lite-eth/summary.json",
            "results/fluid-lite-eth.json",
        ],
    }

    daily_csv = ROOT / "data" / "fluid-lite-eth" / "last_60d_daily.csv"
    json_path = ROOT / "results" / "fluid-lite-eth-60d.json"
    md_path = ROOT / "results" / "FLUID_LITE_60D.md"
    write_daily_csv(daily_csv, path)
    write_json(json_path, report)
    write_json(ROOT / "data" / "fluid-lite-eth" / "last_60d.json", report)
    md_path.write_text(markdown_report(report))
    print(f"wrote {json_path}")
    for w in windows:
        print(
            f"{w['window']}: {w['start_date']}→{w['end_date']} "
            f"hold={w['hold_return_pct']:.6f}%/{w['hold_apy_pct']:.6f}% "
            f"realized={w['realized_return_pct']:.6f}%/{w['realized_apy_pct']:.6f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
