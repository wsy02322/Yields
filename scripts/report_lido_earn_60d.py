#!/usr/bin/env python3
"""Trailing 60-day Lido EarnETH report from the on-chain oracle share price.

Extends ``data/lido-earn-eth/daily_share_price.csv`` from the day after the
last stored snapshot through 2026-09-29 (last complete UTC day agreed for this
pull). Writes a separate 60-day report. Does not rewrite the 2026-07-17
independent-audit artifacts.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import eth_call, get_block_header, load_w3  # noqa: E402
from src.calculators.apy import compute_window, period_return, window_to_dict  # noqa: E402
from src.fetchers import earneth as earneth_fetcher  # noqa: E402
from src.fetchers.earneth_official import fetch_official_earneth_apy  # noqa: E402

END_DATE = "2026-09-29"
WINDOWS_DAYS = [1, 7, 14, 30, 60]
CSV_FIELDS = [
    "date",
    "block",
    "block_timestamp_est",
    "oracle_price_d18",
    "oracle_report_timestamp",
    "oracle_suspicious",
    "share_price_wei",
    "share_price",
]


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
                "oracle_price_d18": int(row["oracle_price_d18"]),
                "oracle_report_timestamp": int(row["oracle_report_timestamp"]),
                "oracle_suspicious": str(row["oracle_suspicious"]).lower() == "true",
            }
        )
    out.sort(key=lambda r: r["date"])
    return out


def assert_continuous(series: list[dict], end_date: str) -> None:
    dates = [datetime.fromisoformat(r["date"]).date() for r in series if r["date"] <= end_date]
    if not dates:
        raise SystemExit("empty series")
    cursor = dates[0]
    seen = set(dates)
    missing = []
    while cursor <= datetime.fromisoformat(end_date).date():
        if cursor not in seen:
            missing.append(cursor.isoformat())
        cursor += timedelta(days=1)
    if missing:
        raise SystemExit(f"missing daily snapshots: {missing[:8]}")


def build_pinned_windows(
    series: list[dict],
    *,
    end_date: str,
    windows_days: list[int],
    exit_fee: float,
) -> list[dict]:
    """Exact calendar windows ending on ``end_date``.

    Unlike ``rolling_windows``, a flat final day is kept, and inception is not
    added. Each window must land on the requested start and end dates.
    """
    end_dt = datetime.fromisoformat(end_date)
    out = []
    for n in windows_days:
        start_date = (end_dt - timedelta(days=n)).date().isoformat()
        window = compute_window(
            series,
            label=f"{n}d",
            start_date=start_date,
            end_date=end_date,
            exit_fee=exit_fee,
        )
        if window is None:
            raise SystemExit(f"missing {n}d window ending {end_date}")
        if window.start_date != start_date or window.end_date != end_date or int(window.days) != n:
            raise SystemExit(
                f"{n}d window snapped to {window.start_date}→{window.end_date} "
                f"({window.days}d), wanted {start_date}→{end_date}"
            )
        out.append(window_to_dict(window))
    return out


def build_daily_path(series: list[dict], *, start_date: str, end_date: str) -> list[dict]:
    """Opening snapshot plus each later day through ``end_date``.

    ``daily_return`` on the opening row is null: that snapshot is the window
    baseline, not a return inside the window. Later rows are the daily moves
    that compound to the window return.
    """
    rows = [r for r in series if start_date <= r["date"] <= end_date]
    if not rows or rows[0]["date"] != start_date or rows[-1]["date"] != end_date:
        raise SystemExit(f"daily path does not cover {start_date}→{end_date}")
    out = []
    for i, row in enumerate(rows):
        if i == 0:
            daily = None
        else:
            daily = period_return(float(rows[i - 1]["share_price"]), float(row["share_price"]))
        out.append(
            {
                "date": row["date"],
                "share_price": row["share_price"],
                "share_price_wei": row["share_price_wei"],
                "oracle_price_d18": row["oracle_price_d18"],
                "oracle_report_timestamp": row["oracle_report_timestamp"],
                "oracle_suspicious": row["oracle_suspicious"],
                "block": row["block"],
                "daily_return_pct": None if daily is None else daily * 100,
                "in_window_move": i > 0,
            }
        )
    return out


def compounded_daily_return(path: list[dict]) -> float:
    value = 1.0
    for row in path:
        if row["daily_return_pct"] is None:
            continue
        value *= 1.0 + row["daily_return_pct"] / 100.0
    return value - 1.0


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def write_daily_csv(path: Path, path_rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "share_price",
        "daily_return_pct",
        "share_price_wei",
        "oracle_price_d18",
        "oracle_report_timestamp",
        "oracle_suspicious",
        "block",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in path_rows:
            out = dict(row)
            if out["daily_return_pct"] is None:
                out["daily_return_pct"] = ""
            writer.writerow(out)


def markdown_report(report: dict) -> str:
    lines = [
        "# Lido EarnETH trailing 60-day oracle report",
        "",
        f"End date: **{report['end_date']}** UTC (last complete day in this pull).",
        "",
        "Primary metric is Hold return / Hold APY from the on-chain Mellow oracle "
        "ETH share price. Fees minted on each oracle report are already inside "
        "that price. Redeem fee stayed 0, so realized equals hold. "
        "Mellow Points, Obol, and SSV are not in the share price and are excluded.",
        "",
        "The 2026-07-17 independent audit files are left unchanged.",
        "",
        "## Windows ending 2026-09-29",
        "",
        "| Window | Start → End | Hold return | Hold APY |",
        "|--------|-------------|------------:|---------:|",
    ]
    for w in report["windows"]:
        lines.append(
            f"| {w['window']} | {w['start_date']} → {w['end_date']} | "
            f"{w['hold_return_pct']:.6f}% | {w['hold_apy_pct']:.6f}% |"
        )
    ref = report.get("published_apy_untrusted_reference") or {}
    prior = report.get("fee_change_before_window")
    if prior:
        prev = prior["previous_rates"]
        lines.extend(
            [
                "",
                "The "
                f"{prev['performance_fee'] * 100:.4g}% performance / "
                f"{prev['protocol_fee'] * 100:.4g}% protocol schedule from the "
                "2026-07-17 audit ended at "
                f"{prior['timestamp_utc']} (block {prior['block']}), "
                "before this window opened.",
                "",
            ]
        )
    lines.extend(["", "## Fee parameters during the 60-day window", ""])
    lines.append(
        "Read from FeeManager at the window's snapshot blocks. "
        "These are the rates in force while the share price was updating, "
        "not the 1% / 10% schedule stored for the 2026-07-17 audit."
    )
    lines.append("")
    lines.append("| Status | UTC | Block | Performance | Protocol | Deposit | Redeem |")
    lines.append("|--------|-----|------:|------------:|---------:|--------:|-------:|")
    for regime in report["fee_regimes"]:
        rates = regime["rates"]
        lines.append(
            f"| {regime['kind']} | {regime['timestamp_utc']} | {regime['block']} | "
            f"{rates['performance_fee'] * 100:.4g}% | {rates['protocol_fee'] * 100:.4g}% | "
            f"{rates['deposit_fee'] * 100:.4g}% | {rates['redeem_fee'] * 100:.4g}% |"
        )
    lines.extend(["", "## Untrusted UI reference", ""])
    if ref.get("apy_pct") is None:
        lines.append(f"Published APY* was not used. {ref.get('error', '')}".rstrip())
    else:
        lines.append(
            f"Mellow `{ref.get('label')}` = **{ref['apy_pct']:.6f}%** "
            f"(source only, not the result). "
            f"Independent {ref.get('days')}d Hold APY = "
            f"**{ref.get('independent_hold_apy_pct_same_window')}%**."
        )
    lines.extend(
        [
            "",
            "## 60-day path",
            "",
            "Opening row is the baseline. The following daily moves compound to the 60-day hold return.",
            "",
            "| Date | Share price (ETH) | Daily change |",
            "|------|------------------:|-------------:|",
        ]
    )
    for row in report["daily_path"]:
        change = "—" if row["daily_return_pct"] is None else f"{row['daily_return_pct']:.6f}%"
        lines.append(f"| {row['date']} | {row['share_price']:.10f} | {change} |")
    lines.append("")
    return "\n".join(lines)


def read_fees_at(w3, fee_manager: str, block: int) -> dict[str, int]:
    out = {}
    for name in ("depositFeeD6", "redeemFeeD6", "performanceFeeD6", "protocolFeeD6"):
        (val,) = eth_call(w3, fee_manager, f"{name}()", [], [], ["uint256"], block=block)
        out[name] = int(val)
    return out


def fee_regimes(w3, fee_manager: str, start_block: int, end_block: int) -> list[dict]:
    """Piecewise fee settings from ``start_block`` through ``end_block``.

    Each regime records the block where that setting became visible. The first
    regime is the setting already in force at ``start_block``.
    """
    start_fees = read_fees_at(w3, fee_manager, start_block)
    regimes = [{"block": start_block, "fees": start_fees}]
    cursor = start_block
    while cursor < end_block:
        end_fees = read_fees_at(w3, fee_manager, end_block)
        if end_fees == regimes[-1]["fees"]:
            break
        lo, hi = cursor, end_block
        before = regimes[-1]["fees"]
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if read_fees_at(w3, fee_manager, mid) == before:
                lo = mid
            else:
                hi = mid
        regimes.append({"block": hi, "fees": read_fees_at(w3, fee_manager, hi)})
        cursor = hi
    for regime in regimes:
        header = get_block_header(w3, regime["block"])
        regime["timestamp"] = header["timestamp"]
        regime["timestamp_utc"] = datetime.fromtimestamp(
            header["timestamp"], tz=timezone.utc
        ).isoformat()
        fees = regime["fees"]
        regime["rates"] = {
            "deposit_fee": fees["depositFeeD6"] / 1e6,
            "redeem_fee": fees["redeemFeeD6"] / 1e6,
            "performance_fee": fees["performanceFeeD6"] / 1e6,
            "protocol_fee": fees["protocolFeeD6"] / 1e6,
        }
    return regimes


def verify_blocks(w3, oracle: str, asset: str, series: list[dict], dates: list[str]) -> None:
    by_date = {row["date"]: row for row in series}
    for date in dates:
        row = by_date[date]
        price, report_ts, suspicious = earneth_fetcher.get_oracle_report(
            w3, oracle, asset, row["block"]
        )
        if price != row["oracle_price_d18"] or int(report_ts) != row["oracle_report_timestamp"]:
            raise SystemExit(
                f"oracle mismatch on {date} block {row['block']}: "
                f"csv={row['oracle_price_d18']} chain={price}"
            )
        if bool(suspicious) != row["oracle_suspicious"]:
            raise SystemExit(f"suspicious flag mismatch on {date}")
        wei = earneth_fetcher.eth_per_share_wei(price)
        if wei != row["share_price_wei"]:
            raise SystemExit(f"share wei mismatch on {date}: csv={row['share_price_wei']} calc={wei}")


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    vault = cfg["vaults"]["lido_earn_eth"]
    series_path = ROOT / "data" / "lido-earn-eth" / "daily_share_price.csv"
    existing = read_csv(series_path)
    if not existing:
        raise SystemExit(f"missing series: {series_path}")
    last_stored = existing[-1]["date"]
    fetch_start = (datetime.fromisoformat(last_stored) + timedelta(days=1)).date().isoformat()

    w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
    tip = w3.eth.get_block("latest")
    tip_ts = int(tip["timestamp"])
    end_close_ts = int(
        datetime.fromisoformat(END_DATE).replace(tzinfo=timezone.utc).timestamp()
    ) + 86400
    if tip_ts < end_close_ts:
        raise SystemExit(
            f"chain tip {tip_ts} is before {END_DATE} 24:00 UTC; refusing a partial end day"
        )

    appended = 0
    if fetch_start <= END_DATE:
        print(f"pulling {fetch_start} → {END_DATE}")
        fresh = earneth_fetcher.fetch_daily_series(
            w3,
            vault["oracle"],
            vault["base_asset"],
            start_block=int(vault["deployment_block"]),
            start_date=fetch_start,
            end_date=END_DATE,
            max_workers=4,
        )
        have = {row["date"] for row in existing}
        new_rows = [row for row in fresh if row["date"] not in have and row["date"] <= END_DATE]
        new_rows.sort(key=lambda row: row["date"])
        if new_rows[0]["date"] != fetch_start or new_rows[-1]["date"] != END_DATE:
            raise SystemExit(
                f"fetch covered {new_rows[0]['date']}→{new_rows[-1]['date']}, "
                f"wanted {fetch_start}→{END_DATE}"
            )
        append_csv(series_path, new_rows)
        appended = len(new_rows)
        print(f"appended {appended} rows")
    else:
        print(f"series already reaches {last_stored}; no pull")

    rows = as_series(read_csv(series_path))
    rows = [row for row in rows if row["date"] <= END_DATE]
    assert_continuous(rows, END_DATE)

    fee_params = earneth_fetcher.read_fee_params(w3, vault["fee_manager"])
    exit_fee = fee_params["redeemFeeD6"] / 1e6
    windows = build_pinned_windows(
        rows, end_date=END_DATE, windows_days=WINDOWS_DAYS, exit_fee=exit_fee
    )
    window_60 = next(w for w in windows if w["window"] == "60d")
    by_date = {row["date"]: row for row in rows}
    regimes = fee_regimes(
        w3,
        vault["fee_manager"],
        by_date[window_60["start_date"]]["block"],
        by_date[window_60["end_date"]]["block"],
    )
    regimes[0]["kind"] = "in_force_at_window_open"
    for regime in regimes[1:]:
        regime["kind"] = "changed"
    if any(regime["fees"]["redeemFeeD6"] != 0 for regime in regimes):
        raise SystemExit("redeem fee changed inside the window; realized is not identical to hold")
    prior_row = by_date.get("2026-07-17")
    fee_change_before_window = None
    if prior_row is not None:
        before = fee_regimes(
            w3,
            vault["fee_manager"],
            prior_row["block"],
            by_date[window_60["start_date"]]["block"],
        )
        if len(before) > 1 and before[-1]["fees"] == regimes[0]["fees"]:
            change = before[-1]
            change["kind"] = "changed_before_window_open"
            change["previous_rates"] = before[0]["rates"]
            fee_change_before_window = change
    path = build_daily_path(
        rows, start_date=window_60["start_date"], end_date=window_60["end_date"]
    )
    compounded = compounded_daily_return(path)
    raw_60 = period_return(path[0]["share_price"], path[-1]["share_price"])
    if abs(compounded - raw_60) > 1e-12:
        raise SystemExit(
            f"daily path {compounded:.12f} != 60d price ratio return {raw_60:.12f}"
        )

    verify_blocks(
        w3,
        vault["oracle"],
        vault["base_asset"],
        rows,
        [fetch_start if fetch_start <= END_DATE else END_DATE, window_60["start_date"], END_DATE],
    )

    published_ref: dict | None
    try:
        official = fetch_official_earneth_apy()
        match_days = int(official.get("days") or 14)
        ours = next((w for w in windows if w["window"] == f"{match_days}d"), None)
        published_ref = {
            "trust": "untrusted_reference_only",
            "label": official["label"],
            "apy_pct": official["apy_pct"],
            "days": official["days"],
            "source_url": official["source_url"],
            "fetched_at_utc": official["fetched_at_utc"],
            "apy_last_update_utc": official.get("apy_last_update_utc"),
            "independent_hold_apy_pct_same_window": None if ours is None else ours["hold_apy_pct"],
            "note": "Shown only for contrast. The result is the oracle Hold APY.",
        }
    except Exception as exc:  # noqa: BLE001
        published_ref = {
            "trust": "untrusted_reference_only",
            "error": str(exc),
            "note": "Published APY fetch failed. The result still uses the oracle only.",
        }

    report = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "tip_block": int(tip["number"]),
        "tip_timestamp": tip_ts,
        "end_date": END_DATE,
        "rows_appended_this_run": appended,
        "snapshots_after_2026_07_17": sum(1 for row in rows if row["date"] > "2026-07-17"),
        "series_first_date": rows[0]["date"],
        "series_last_date": rows[-1]["date"],
        "vault": {
            "name": vault["name"],
            "vault": vault["vault"],
            "share_token": vault["share_token"],
            "oracle": vault["oracle"],
            "fee_manager": vault["fee_manager"],
        },
        "method": {
            "share_price": "Mellow oracle getReport(ETH); eth_per_share = 1e36 / priceD18",
            "hold_return": "end_share_price / start_share_price - 1",
            "hold_apy": "(1+R)^(365.25/days)-1",
            "fees_in_price": (
                "Fees minted on each oracle report are already in the net share price. "
                "fee_regimes is the live schedule across this window. "
                "The 1% protocol / 10% performance schedule belongs to the 2026-07-17 audit "
                "and was not the live schedule here."
            ),
            "redeem_fee": exit_fee,
            "excluded": ["Mellow Points", "Obol rewards", "SSV rewards", "published UI APY*"],
        },
        "on_chain_fees_at_tip": {
            "depositFeeD6": fee_params["depositFeeD6"],
            "redeemFeeD6": fee_params["redeemFeeD6"],
            "performanceFeeD6": fee_params["performanceFeeD6"],
            "protocolFeeD6": fee_params["protocolFeeD6"],
        },
        "fee_regimes": regimes,
        "fee_change_before_window": fee_change_before_window,
        "windows": windows,
        "daily_path_compounds_to_60d_hold_return": True,
        "published_apy_untrusted_reference": published_ref,
        "daily_path": path,
        "unchanged_prior_audit": [
            "data/lido-earn-eth/summary.json",
            "data/lido-earn-eth/independent_audit.json",
            "results/lido-earn-eth.json",
            "results/lido-earn-eth-independent-audit.json",
            "results/LIDO_EARN_AUDIT.md",
        ],
    }

    daily_csv = ROOT / "data" / "lido-earn-eth" / "last_60d_daily.csv"
    json_path = ROOT / "results" / "lido-earn-eth-60d.json"
    md_path = ROOT / "results" / "LIDO_EARN_60D.md"
    write_daily_csv(daily_csv, path)
    write_json(json_path, report)
    write_json(ROOT / "data" / "lido-earn-eth" / "last_60d.json", report)
    md_path.write_text(markdown_report(report))
    print(f"wrote {json_path}")
    for w in windows:
        print(
            f"{w['window']}: {w['start_date']}→{w['end_date']} "
            f"return={w['hold_return_pct']:.6f}% apy={w['hold_apy_pct']:.6f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
