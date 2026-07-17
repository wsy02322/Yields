#!/usr/bin/env python3
"""Independent Lido EarnETH APY audit (do not trust UI / Mellow published APY).

Source of truth: on-chain Mellow oracle ``getReport(ETH)`` share price only.
Official UI APY* is fetched solely as an untrusted reference for contrast.

Windows: 1 / 7 / 14 / 30 / 90 / 120 / 180 days.
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
from src.calculators.apy import (  # noqa: E402
    LIDO_EARN_AUDIT_WINDOWS_DAYS,
    summarize_vault,
)
from src.fetchers import earneth as earneth_fetcher  # noqa: E402
from src.fetchers.earneth_official import fetch_official_earneth_apy  # noqa: E402

UI_URL = "https://stake.lido.fi/earn/eth/deposit"


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


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


def load_series(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open()))
    out = []
    for r in rows:
        out.append(
            {
                "date": r["date"],
                "share_price": float(r["share_price"]),
                "share_price_wei": r.get("share_price_wei"),
                "block": r.get("block"),
                "block_timestamp_est": r.get("block_timestamp_est"),
            }
        )
    return out


def markdown_table(audit: dict) -> str:
    lines = [
        "| Window | Hold APY (independent) | Days | Start → End | Status |",
        "|--------|------------------------:|-----:|-------------|--------|",
    ]
    by = {w["window"]: w for w in audit["windows"]}
    unavail = {u["window"]: u for u in audit.get("unavailable_windows") or []}
    for n in audit["windows_days_requested"]:
        label = f"{n}d"
        if label in by:
            w = by[label]
            lines.append(
                f"| {label} | **{w['hold_apy_pct']:.4f}%** | {w['days']:.0f} | "
                f"{w['start_date']} → {w['end_date']} | ok |"
            )
        else:
            u = unavail.get(label, {})
            reason = u.get("reason", "unavailable")
            hist = u.get("history_days")
            hist_s = f"history={hist}d" if hist is not None else "—"
            lines.append(f"| {label} | — | — | — | {reason} ({hist_s}) |")
    # inception always useful for audit
    ince = by.get("inception")
    if ince:
        lines.append(
            f"| inception | **{ince['hold_apy_pct']:.4f}%** | {ince['days']:.0f} | "
            f"{ince['start_date']} → {ince['end_date']} | ok |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Full re-fetch of EarnETH daily oracle share prices from deployment.",
    )
    parser.add_argument(
        "--fetch-official-reference",
        action="store_true",
        default=True,
        help="Fetch Mellow UI APY* as untrusted reference only (default: on).",
    )
    parser.add_argument(
        "--no-fetch-official-reference",
        action="store_false",
        dest="fetch_official_reference",
        help="Skip Mellow published APY entirely.",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    le = cfg["vaults"]["lido_earn_eth"]
    earn_path = ROOT / "data" / "lido-earn-eth" / "daily_share_price.csv"

    w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
    tip = w3.eth.get_block("latest")
    tip_ts = int(tip["timestamp"])
    as_of = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "tip_block": int(tip["number"]),
        "tip_timestamp": tip_ts,
        "tip_date_utc": datetime.fromtimestamp(tip_ts, tz=timezone.utc).strftime(
            "%Y-%m-%d"
        ),
        "branch_tag": "07171359",
        "audit_purpose": "independent_lido_earn_apy",
        "ui_url": UI_URL,
        "trust_model": (
            "Do not trust Lido Earn / Mellow published APY. "
            "Primary metric = Hold APY from on-chain oracle share price only."
        ),
        "windows_days": list(LIDO_EARN_AUDIT_WINDOWS_DAYS),
        "refreshed_by": "cursor-cloud-agent",
    }

    if args.pull or not earn_path.exists():
        print("=== Independent audit: full on-chain EarnETH share-price pull ===")
        earn_rows = earneth_fetcher.fetch_daily_series(
            w3,
            le["oracle"],
            le["base_asset"],
            start_block=int(le["deployment_block"]),
            start_date=le["deployment_date"],
            max_workers=4,
        )
        write_csv(earn_path, earn_rows)
    else:
        print("=== Independent audit: using existing on-chain CSV (pass --pull to refresh) ===")
        earn_rows = load_series(earn_path)

    fee_params = earneth_fetcher.read_fee_params(w3, le["fee_manager"])
    print("on-chain FeeManager", fee_params)
    fees = {
        **le["fees"],
        "on_chain_fee_manager": {
            "depositFeeD6": fee_params["depositFeeD6"],
            "redeemFeeD6": fee_params["redeemFeeD6"],
            "performanceFeeD6": fee_params["performanceFeeD6"],
            "protocolFeeD6": fee_params["protocolFeeD6"],
            "deposit_fee": fee_params["depositFeeD6"] / 1e6,
            "redeem_fee": fee_params["redeemFeeD6"] / 1e6,
            "performance_fee": fee_params["performanceFeeD6"] / 1e6,
            "protocol_fee": fee_params["protocolFeeD6"] / 1e6,
        },
    }
    exit_fee = fee_params["redeemFeeD6"] / 1e6

    summary = summarize_vault(
        earn_rows,
        exit_fee=exit_fee,
        fees=fees,
        offchain_rewards=le.get("offchain_rewards") or [],
        windows_days=list(LIDO_EARN_AUDIT_WINDOWS_DAYS),
        notes=[
            "INDEPENDENT AUDIT: APY derived only from on-chain Mellow oracle ETH report.",
            "eth_per_share = 1e36 / priceD18; protocol 1% + performance 10% already in net price.",
            "Do NOT treat Lido Earn UI / Mellow timeweighted-apy as authoritative.",
            "Mellow Points / Obol / SSV are off-chain and excluded from APY.",
            f"UI under audit: {UI_URL}",
        ],
    )

    published_ref: dict | None = None
    if args.fetch_official_reference:
        try:
            official = fetch_official_earneth_apy()
            # Find our independent 14d (or matching days) for contrast only.
            match_days = int(official.get("days") or 14)
            our = next(
                (
                    w
                    for w in summary["windows"]
                    if w["window"] == f"{match_days}d"
                ),
                None,
            )
            published_ref = {
                "trust": "untrusted_reference_only",
                "label": official["label"],
                "apy_pct": official["apy_pct"],
                "days": official["days"],
                "source_url": official["source_url"],
                "fetched_at_utc": official["fetched_at_utc"],
                "apy_last_update_utc": official.get("apy_last_update_utc"),
                "independent_hold_apy_pct_same_window": (
                    None if our is None else our["hold_apy_pct"]
                ),
                "delta_independent_minus_published_pp": (
                    None
                    if our is None
                    else round(our["hold_apy_pct"] - official["apy_pct"], 6)
                ),
                "note": (
                    "Published figure is shown only for contrast. "
                    "Audit conclusion uses independent Hold APY columns."
                ),
            }
            print(
                f"untrusted published {official['label']}={official['apy_pct']:.6f}% | "
                f"our {match_days}d Hold="
                f"{'n/a' if our is None else f'{our['hold_apy_pct']:.6f}%'}"
            )
        except Exception as exc:  # noqa: BLE001
            published_ref = {
                "trust": "untrusted_reference_only",
                "error": str(exc),
                "note": "Could not fetch published APY; audit still uses on-chain only.",
            }
            print(f"published reference skipped: {exc}")

    audit = {
        "as_of": as_of,
        "vault": {
            "name": le["name"],
            "vault": le["vault"],
            "share_token": le["share_token"],
            "oracle": le["oracle"],
            "fee_manager": le["fee_manager"],
            "ui_url": UI_URL,
        },
        "method": {
            "share_price": "Mellow oracle getReport(ETH); eth_per_share = 1e36 / priceD18",
            "apy": "Hold APY = (1+R)^(365.25/days)-1 from on-chain share price",
            "fees_in_price": "protocol 1% + performance 10% minted as shares on reports",
            "excluded": ["Mellow Points", "Obol rewards", "SSV rewards", "published UI APY*"],
            "data_source": "ethereum archive eth_call (config/vaults.yaml rpc)",
        },
        "series_points": len(earn_rows),
        "first_date": summary["first_date"],
        "last_date": summary["last_date"],
        "first_share_price": summary["first_share_price"],
        "last_share_price": summary["last_share_price"],
        "fees": fees,
        "exit_fee_applied_in_realized": exit_fee,
        "windows_days_requested": list(LIDO_EARN_AUDIT_WINDOWS_DAYS),
        "windows": summary["windows"],
        "unavailable_windows": summary["unavailable_windows"],
        "published_apy_untrusted_reference": published_ref,
        "offchain_rewards_excluded_from_apy": summary["offchain_rewards_excluded_from_apy"],
        "notes": summary["notes"],
        "markdown_table": markdown_table(
            {
                "windows_days_requested": list(LIDO_EARN_AUDIT_WINDOWS_DAYS),
                "windows": summary["windows"],
                "unavailable_windows": summary["unavailable_windows"],
            }
        ),
    }

    write_json(ROOT / "data" / "lido-earn-eth" / "summary.json", summary)
    write_json(
        ROOT / "results" / "lido-earn-eth.json",
        {"as_of": as_of, **summary, "series_points": len(earn_rows)},
    )
    write_json(ROOT / "results" / "lido-earn-eth-independent-audit.json", audit)
    write_json(ROOT / "data" / "lido-earn-eth" / "independent_audit.json", audit)

    # Lightweight markdown report for humans.
    md_lines = [
        "# Lido EarnETH independent APY audit",
        "",
        f"Generated: **{as_of['tip_date_utc']} UTC** (branch tag `{as_of['branch_tag']}`).",
        "",
        f"UI under audit: [{UI_URL}]({UI_URL})",
        "",
        "**Trust model:** do **not** trust Lido Earn / Mellow published APY. "
        "Primary metric is trailing **Hold APY** from on-chain oracle share price.",
        "",
        "## Independent Hold APY",
        "",
        audit["markdown_table"],
        "",
        "### Series",
        "",
        f"| | |",
        f"|--|--|",
        f"| Points | {len(earn_rows)} |",
        f"| First | {summary['first_date']} @ {summary['first_share_price']} |",
        f"| Last | {summary['last_date']} @ {summary['last_share_price']} |",
        f"| Oracle | `{le['oracle']}` |",
        f"| Vault | `{le['vault']}` |",
        "",
    ]
    if published_ref and published_ref.get("apy_pct") is not None:
        md_lines += [
            "## Published APY* (untrusted reference only)",
            "",
            f"| | |",
            f"|--|--|",
            f"| Label | {published_ref.get('label')} |",
            f"| Published | {published_ref['apy_pct']:.4f}% |",
            f"| Our same-window Hold | "
            f"{published_ref.get('independent_hold_apy_pct_same_window')}% |",
            f"| Δ (ours − published) | "
            f"{published_ref.get('delta_independent_minus_published_pp')} pp |",
            "",
            "_Shown for contrast only — not used as audit truth._",
            "",
        ]
    md_lines += [
        "## Reproduce",
        "",
        "```bash",
        "python scripts/audit_lido_earn_apy.py --pull",
        "```",
        "",
        "Files: `results/lido-earn-eth-independent-audit.json` · "
        "`data/lido-earn-eth/daily_share_price.csv`",
        "",
    ]
    (ROOT / "results" / "LIDO_EARN_AUDIT.md").write_text("\n".join(md_lines))

    print("\n" + audit["markdown_table"])
    print("wrote results/lido-earn-eth-independent-audit.json and results/LIDO_EARN_AUDIT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
