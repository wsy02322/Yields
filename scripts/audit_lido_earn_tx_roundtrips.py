#!/usr/bin/env python3
"""WP-A: Lido EarnETH deposit→withdraw round-trips vs oracle share path."""

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
from src.calculators.lido_earn_tx_roundtrips import (  # noqa: E402
    REDEEM_FEE,
    VAULT,
    enrich_legs_with_share_path,
    fetch_queue_events,
    match_clean_full_round_trips,
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


def markdown_summary(summary: dict, *, from_block: int, to_block: int) -> str:
    g = summary.get("abs_gap_return_pp") or {}
    ga = summary.get("abs_gap_apy_pp") or {}

    def fmt(d: dict, key: str) -> str:
        v = d.get(key) if d else None
        return "—" if v is None else f"{float(v):.6f}"

    lines = [
        "# Lido EarnETH — tx round-trips vs oracle share-price path",
        "",
        f"Generated: **{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC**.",
        "",
        "Compares **actual deposit→redeem claims** (ETH-equivalent) to oracle "
        "`eth_per_share` over the same `[t0, t1]` "
        f"(redeem fee = {REDEEM_FEE}).",
        "",
        f"Sample: **{summary.get('sample')}** — {summary.get('sample_definition')}.",
        "",
        f"Blocks: `{from_block}` → `{to_block}` · vault `{VAULT}`.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Clean full round-trips | {summary.get('n', 0)} |",
        f"| Median abs gap return pp | {fmt(g, 'median')} |",
        f"| p90 abs gap return pp | {fmt(g, 'p90')} |",
        f"| Max abs gap return pp | {fmt(g, 'max')} |",
        f"| Median abs gap APY pp | {fmt(ga, 'median')} |",
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
        "- **Near-zero gap** → oracle share price fully explains depositor ETH return.",
        "- Residual may include wstETH↔ETH basis on redeem (queue asset = wstETH).",
        "",
    ]
    return "\n".join(lines) + "\n"


def markdown_ab_table(rows: list[dict]) -> str:
    lines = [
        "# Lido EarnETH — clean samples: return A vs B",
        "",
        f"n = **{len(rows)}** clean full round-trips "
        "(one deposit claim → one full redeem → one redeem claim).",
        "",
        "- **A** = `eth_out / eth_in − 1` (wstETH out converted via `getStETHByWstETH`)",
        "- **B** = `p1/p0 × (1−redeem_fee) − 1` (oracle eth_per_share; redeem_fee=0)",
        "- **APY** = `(1+R)^(365.25/days) − 1`",
        "",
        "| # | owner | t0 → t1 | days | in ETH | out ETH | A ret% | A APY% | B ret% | B APY% | gap pp |",
        "|--:|-------|---------|-----:|-------:|--------:|-------:|-------:|-------:|-------:|-------:|",
    ]
    for i, r in enumerate(rows, 1):
        owner = str(r["owner"])
        own_s = f"`{owner[:6]}…{owner[-4:]}`"
        a = float(r["tx_return"]) * 100
        b = float(r["share_return_after_exit"]) * 100
        aa = float(r["tx_apy"]) * 100 if r.get("tx_apy") is not None else float("nan")
        ba = (
            float(r["share_apy_after_exit"]) * 100
            if r.get("share_apy_after_exit") is not None
            else float("nan")
        )
        gap = float(r["gap_return_pp"])
        lines.append(
            f"| {i} | {own_s} | {r['deposit_date']}→{r['withdraw_date']} | "
            f"{float(r['days']):.2f} | {float(r['assets_in']):.4f} | "
            f"{float(r['assets_out']):.4f} | {a:.4f} | {aa:.3f} | "
            f"{b:.4f} | {ba:.3f} | {gap:.2e} |"
        )
    lines += [
        "",
        "## Source detail (txs)",
        "",
        "| # | deposit_asset | deposit_claim_tx | withdraw_claim_tx | p0 | p1 |",
        "|--:|---------------|------------------|-------------------|----:|----:|",
    ]
    for i, r in enumerate(rows, 1):
        dc = str(r["deposit_claim_tx"])
        wc = str(r["withdraw_claim_tx"])
        lines.append(
            f"| {i} | {r.get('deposit_asset')} | `{dc[:10]}…{dc[-6:]}` | "
            f"`{wc[:10]}…{wc[-6:]}` | {float(r['p0']):.8f} | {float(r['p1']):.8f} |"
        )
    lines += [
        "",
        "Full CSV: `results/lido-earn-clean-samples-A-vs-B.csv`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--from-block",
        type=int,
        default=None,
        help="Start block (default: vault deployment)",
    )
    ap.add_argument("--to-block", type=int, default=None)
    ap.add_argument(
        "--lookback-blocks",
        type=int,
        default=None,
        help="If set, scan tip-lookback → tip instead of full history",
    )
    ap.add_argument(
        "--eth-only-deposits",
        action="store_true",
        help="Only ETH deposit queues (cleaner A; still redeem wstETH→ETH)",
    )
    ap.add_argument("--min-days", type=float, default=0.01)
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    le = cfg["vaults"]["lido_earn_eth"]
    w3 = load_w3(cfg["rpc"]["url"], timeout=int(cfg["rpc"].get("timeout_seconds", 45)))
    tip = int(w3.eth.block_number)
    deploy = int(le["deployment_block"])

    if args.lookback_blocks is not None:
        from_block = max(deploy, tip - int(args.lookback_blocks))
    elif args.from_block is not None:
        from_block = int(args.from_block)
    else:
        from_block = deploy
    to_block = int(args.to_block) if args.to_block is not None else tip

    print(
        f"scanning blocks {from_block}→{to_block} "
        f"(eth_only_deposits={args.eth_only_deposits})",
        flush=True,
    )
    dep_reqs, dep_claims, red_reqs, red_claims = fetch_queue_events(
        w3,
        from_block=from_block,
        to_block=to_block,
        eth_only_deposits=args.eth_only_deposits,
    )
    print(
        f"events: dep_req={len(dep_reqs)} dep_claim={len(dep_claims)} "
        f"red_req={len(red_reqs)} red_claim={len(red_claims)}",
        flush=True,
    )

    legs = match_clean_full_round_trips(
        dep_reqs,
        dep_claims,
        red_reqs,
        red_claims,
        min_days=args.min_days,
    )
    print(f"clean_full matched (pre-enrich): {len(legs)}", flush=True)
    enriched = enrich_legs_with_share_path(w3, legs)
    rows = [round_trip_to_row(r) for r in enriched]
    summary = summarize_round_trips(enriched)
    summary["from_block"] = from_block
    summary["to_block"] = to_block
    summary["event_counts"] = {
        "dep_req": len(dep_reqs),
        "dep_claim": len(dep_claims),
        "red_req": len(red_reqs),
        "red_claim": len(red_claims),
    }

    data_dir = ROOT / "data" / "lido-earn-eth"
    res_dir = ROOT / "results"
    write_csv(data_dir / "tx_vs_share_compare_clean.csv", rows)
    write_csv(res_dir / "lido-earn-clean-samples-A-vs-B.csv", rows)
    write_json(data_dir / "tx_vs_share_summary.json", summary)
    write_json(res_dir / "lido-earn-tx-vs-share.json", {"summary": summary, "rows": rows})
    (res_dir / "lido-earn-tx-vs-share.md").write_text(
        markdown_summary(summary, from_block=from_block, to_block=to_block)
    )
    (res_dir / "lido-earn-clean-samples-A-vs-B.md").write_text(markdown_ab_table(rows))
    print(f"wrote {len(rows)} clean samples → results/lido-earn-clean-samples-A-vs-B.md")
    print(
        "gap median pp:",
        (summary.get("abs_gap_return_pp") or {}).get("median"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
