#!/usr/bin/env python3
"""WP-A: Fluid Lite ETH deposit→withdraw round-trips vs same-window share path.

Only this work package — no third-party / off-chain / forward model.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import load_w3  # noqa: E402
from src.calculators.fluid_lite_tx_roundtrips import (  # noqa: E402
    IETH_V2,
    enrich_legs_with_share_path,
    fetch_vault_events,
    match_round_trips_fifo,
    round_trip_to_row,
    summarize_round_trips,
)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def markdown_report(summary: dict, trips_preview: list[dict], *, lookback_blocks: int) -> str:
    g = summary.get("abs_gap_return_pp") or {}
    ga = summary.get("abs_gap_apy_pp") or {}

    def fmt_stat(d: dict, key: str) -> str:
        v = d.get(key) if d else None
        return "—" if v is None else f"{float(v):.6f}"

    lines = [
        "# Fluid Lite ETH — tx round-trips vs share-price path",
        "",
        f"Generated: **{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC**.",
        "",
        "Compares **actual Deposit→Withdraw** asset returns to **`convertToAssets`** "
        "over the same `[t0, t1]` (exit fee 0.05% on withdraw side).",
        "",
        f"Lookback: last **{lookback_blocks}** blocks · vault `{IETH_V2}`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Round-trips matched (FIFO) | {summary.get('n', 0)} |",
        f"| Median abs gap return pp | {fmt_stat(g, 'median')} |",
        f"| p90 abs gap return pp | {fmt_stat(g, 'p90')} |",
        f"| Max abs gap return pp | {fmt_stat(g, 'max')} |",
        f"| Median abs gap APY pp | {fmt_stat(ga, 'median')} |",
        "",
        "### By hold length",
        "",
        "| Bucket | n | Median abs gap return pp | Median tx APY % |",
        "|--------|--:|-------------------------:|----------------:|",
    ]
    for k, label in [
        ("lt_7d", "<7d"),
        ("d7_30", "7–30d"),
        ("d30_90", "30–90d"),
        ("ge_90d", "≥90d"),
    ]:
        b = (summary.get("buckets") or {}).get(k) or {}
        gap = b.get("median_abs_gap_return_pp")
        apy = b.get("median_tx_apy_pct")
        gap_s = "—" if gap is None else f"{float(gap):.6f}"
        apy_s = "—" if apy is None else f"{float(apy):.4f}"
        lines.append(f"| {label} | {b.get('n', 0)} | {gap_s} | {apy_s} |")
    lines += [
        "",
        "## Reading the gap",
        "",
        "- **Near-zero gap** → share price (stETH/share) fully explains depositor cash return.",
        "- **Systematic positive tx−share gap** → possible income outside share price.",
        "- **Systematic negative** → fee/parse mismatch or deposit asset normalization issue.",
        "",
        "## Sample rows (largest abs gap return first)",
        "",
        "| days | assets_in | tx_ret% | share_exit% | gap_ret_pp | tx_apy% | share_apy% |",
        "|-----:|----------:|--------:|------------:|-----------:|--------:|-----------:|",
    ]
    ranked = sorted(
        trips_preview,
        key=lambda r: abs(float(r.get("gap_return_pp") or 0)),
        reverse=True,
    )[:15]
    for r in ranked:
        ta = r.get("tx_apy_pct")
        sa = r.get("share_apy_after_exit_pct")
        lines.append(
            "| {days:.2f} | {ain:.4f} | {tr:.4f} | {sr:.4f} | {g:.6f} | {ta} | {sa} |".format(
                days=float(r["days"]),
                ain=float(r["assets_in"]),
                tr=float(r["tx_return_pct"]),
                sr=float(r["share_return_after_exit_pct"]),
                g=float(r["gap_return_pp"]),
                ta="—" if ta is None else f"{float(ta):.3f}",
                sa="—" if sa is None else f"{float(sa):.3f}",
            )
        )
    lines += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "python scripts/audit_fluid_lite_tx_roundtrips.py --lookback-blocks 500000",
        "```",
        "",
        "Files: `data/fluid-lite-eth/tx_vs_share_compare.csv` · "
        "`results/fluid-lite-tx-vs-share.md`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lookback-blocks",
        type=int,
        default=500_000,
        help="Blocks to scan back from tip (~500k ≈ 70d). Increase for more history.",
    )
    parser.add_argument("--chunk", type=int, default=3000)
    parser.add_argument(
        "--min-days",
        type=float,
        default=0.05,
        help="Drop round-trips shorter than this (dust / same-day noise).",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
    tip = int(w3.eth.block_number)
    from_block = max(0, tip - args.lookback_blocks)
    # Prefer not before vault deployment if known
    dep = int(cfg["vaults"]["fluid_lite_eth"].get("deployment_block") or 0)
    if dep:
        from_block = max(from_block, dep)

    print(f"=== WP-A: scan iETHv2 events blocks {from_block} → {tip} ===")
    deposits, withdraws = fetch_vault_events(
        w3, from_block=from_block, to_block=tip, chunk=args.chunk
    )
    print(f"deposits={len(deposits)} withdraws={len(withdraws)}")

    legs = match_round_trips_fifo(deposits, withdraws, min_days=args.min_days)
    print(f"FIFO-matched legs={len(legs)}")

    print("=== enrich with convertToAssets at deposit/withdraw blocks ===")
    trips = enrich_legs_with_share_path(w3, legs)
    rows = [round_trip_to_row(t) for t in trips]
    summary = summarize_round_trips(trips)
    summary["as_of"] = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "tip_block": tip,
        "from_block": from_block,
        "lookback_blocks": args.lookback_blocks,
        "vault": IETH_V2,
        "method": (
            "FIFO match Deposit(owner)→Withdraw(owner); "
            "tx_return=assets_out/assets_in-1; "
            "share_after_exit=p1/p0*(1-0.0005)-1"
        ),
    }

    write_csv(ROOT / "data" / "fluid-lite-eth" / "tx_vs_share_compare.csv", rows)
    write_json(
        ROOT / "data" / "fluid-lite-eth" / "tx_vs_share_summary.json",
        {"summary": summary, "n_deposits": len(deposits), "n_withdraws": len(withdraws)},
    )
    write_json(ROOT / "results" / "fluid-lite-tx-vs-share.json", {"summary": summary, "rows": rows})
    md = markdown_report(summary, rows, lookback_blocks=args.lookback_blocks)
    (ROOT / "results" / "fluid-lite-tx-vs-share.md").write_text(md)

    print(md)
    print("wrote data/fluid-lite-eth/tx_vs_share_compare.csv and results/fluid-lite-tx-vs-share.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
