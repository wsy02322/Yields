#!/usr/bin/env python3
"""One-shot historical yield pull for Fluid Lite ETH and Lido EarnETH.

Only processes data that has already occurred. Re-running / refreshing
requires an explicit user request (no scheduled updates).

Usage:
  python scripts/compute_historical_yields.py              # full on-chain pull
  python scripts/compute_historical_yields.py --recompute-only
      # rebuild summaries from existing daily CSVs (no new RPC share-price pull)
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
from src.calculators.apy import summarize_vault  # noqa: E402
from src.fetchers import earneth as earneth_fetcher  # noqa: E402
from src.fetchers import fluid_lite as fluid_fetcher  # noqa: E402


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


def read_csv(path: Path) -> list[dict]:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["share_price"] = float(r["share_price"])
        if "share_price_wei" in r and r["share_price_wei"] != "":
            r["share_price_wei"] = int(float(r["share_price_wei"]))
        if "block" in r and r["block"] != "":
            r["block"] = int(r["block"])
        if "oracle_price_d18" in r and r["oracle_price_d18"] != "":
            r["oracle_price_d18"] = int(float(r["oracle_price_d18"]))
        if "oracle_suspicious" in r and r["oracle_suspicious"] != "":
            r["oracle_suspicious"] = r["oracle_suspicious"] in ("True", "true", "1")
    return rows


def shared_windows_from_cfg(cfg: dict) -> list[dict[str, str]]:
    return [
        {"label": w["label"], "start_date": w["start_date"]}
        for w in (cfg.get("shared_windows") or [])
    ]


def print_windows(summary: dict) -> None:
    for w in summary["windows"]:
        print(
            f"  {w['window']}: hold_apy={w['hold_apy_pct']}% realized_apy={w['realized_apy_pct']}% "
            f"({w['start_date']} -> {w['end_date']}, {w['days']}d)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recompute-only",
        action="store_true",
        help="Rebuild APY summaries from existing daily CSVs without re-fetching share prices.",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    fixed_windows = shared_windows_from_cfg(cfg)
    prev: dict = {}

    if args.recompute_only:
        prev_path = ROOT / "results" / "summary.json"
        if prev_path.exists():
            prev = json.loads(prev_path.read_text())
        as_of = prev.get("as_of") or {
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "refresh_policy": "recompute-only from existing daily CSVs; share prices not refreshed",
        }
        as_of = {
            **as_of,
            "recomputed_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "recompute_mode": "from_existing_csv",
        }
        print("recompute-only", as_of)
        w3 = None
    else:
        w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
        tip = w3.eth.block_number
        tip_ts = int(w3.eth.get_block(tip)["timestamp"])
        as_of = {
            "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
            "tip_block": tip,
            "tip_timestamp": tip_ts,
            "tip_date_utc": datetime.fromtimestamp(tip_ts, tz=timezone.utc).strftime("%Y-%m-%d"),
            "refresh_policy": "historical one-shot only; no automatic updates",
        }
        print("tip", as_of)

    results: dict = {
        "as_of": as_of,
        "shared_windows": cfg.get("shared_windows") or [],
        "vaults": {},
    }

    # ---- Fluid Lite ETH ----
    fl = cfg["vaults"]["fluid_lite_eth"]
    fluid_csv = ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv"
    if args.recompute_only:
        print(f"\n=== Recomputing {fl['name']} from {fluid_csv} ===")
        fluid_rows = read_csv(fluid_csv)
    else:
        assert w3 is not None
        print(f"\n=== Fetching {fl['name']} daily share prices ===")
        fluid_rows = fluid_fetcher.fetch_daily_series(
            w3,
            fl["receipt_token"],
            start_block=int(fl["deployment_block"]),
            start_date=fl["deployment_date"],
            max_workers=6,
        )
        write_csv(fluid_csv, fluid_rows)

    fluid_summary = summarize_vault(
        fluid_rows,
        exit_fee=float(fl["fees"]["exit_fee"]),
        fees=fl["fees"],
        offchain_rewards=fl.get("offchain_rewards") or [],
        fixed_windows=fixed_windows,
        notes=[
            "Share price from ERC-4626 convertToAssets(1e18); underlying is stETH (ETH-correlated).",
            "20% performance fee is already deducted inside share price (Net).",
            "Realized APY assumes a final withdraw and applies 0.05% exit fee once at the window end.",
            "Hold APY ignores exit fee (useful for mark-to-market while still deposited).",
            "Window since_earneth is the shared calendar window from EarnETH deployment; vaults remain independent.",
        ],
    )
    write_json(ROOT / "data" / "fluid-lite-eth" / "summary.json", fluid_summary)
    write_json(
        ROOT / "results" / "fluid-lite-eth.json",
        {"as_of": as_of, **fluid_summary, "series_points": len(fluid_rows)},
    )
    results["vaults"]["fluid_lite_eth"] = fluid_summary
    print(
        f"Fluid Lite points={len(fluid_rows)} "
        f"first={fluid_rows[0]['date'] if fluid_rows else None} "
        f"last={fluid_rows[-1]['date'] if fluid_rows else None}"
    )
    print_windows(fluid_summary)

    # ---- Lido EarnETH ----
    le = cfg["vaults"]["lido_earn_eth"]
    earn_csv = ROOT / "data" / "lido-earn-eth" / "daily_share_price.csv"
    if args.recompute_only:
        print(f"\n=== Recomputing {le['name']} from {earn_csv} ===")
        earn_rows = read_csv(earn_csv)
        # Prefer previously recorded on-chain fee snapshot if present
        prev_fees = (
            prev.get("vaults", {})
            .get("lido_earn_eth", {})
            .get("fees", {})
            .get("on_chain_fee_manager")
        )
        if prev_fees:
            fee_params = {
                "depositFeeD6": int(prev_fees["depositFeeD6"]),
                "redeemFeeD6": int(prev_fees["redeemFeeD6"]),
                "performanceFeeD6": int(prev_fees["performanceFeeD6"]),
                "protocolFeeD6": int(prev_fees["protocolFeeD6"]),
            }
        else:
            fee_params = {
                "depositFeeD6": 0,
                "redeemFeeD6": 0,
                "performanceFeeD6": 100000,
                "protocolFeeD6": 10000,
            }
        print("fee snapshot", fee_params)
    else:
        assert w3 is not None
        print(f"\n=== Fetching {le['name']} daily share prices + fee params ===")
        fee_params = earneth_fetcher.read_fee_params(w3, le["fee_manager"])
        print("on-chain FeeManager", fee_params)
        earn_rows = earneth_fetcher.fetch_daily_series(
            w3,
            le["oracle"],
            le["base_asset"],
            start_block=int(le["deployment_block"]),
            start_date=le["deployment_date"],
            max_workers=6,
        )
        write_csv(earn_csv, earn_rows)

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
    earn_summary = summarize_vault(
        earn_rows,
        exit_fee=exit_fee,
        fees=fees,
        offchain_rewards=le.get("offchain_rewards") or [],
        fixed_windows=fixed_windows,
        notes=[
            "Share price derived from Mellow oracle ETH report: eth_per_share = 1e18 / (priceD18/1e18).",
            "1% protocol (platform) fee and 10% performance fee are minted as vault shares on oracle reports; already in net share price.",
            "On-chain depositFeeD6=0 and redeemFeeD6=0 at snapshot time; realized ≈ hold for redeem fee.",
            "Mellow Points, Obol, and SSV rewards are listed under offchain_rewards and are NOT included in APY.",
            "Window since_earneth matches vault inception for EarnETH; same calendar window is also reported for Fluid Lite.",
        ],
    )
    write_json(ROOT / "data" / "lido-earn-eth" / "summary.json", earn_summary)
    write_json(
        ROOT / "results" / "lido-earn-eth.json",
        {"as_of": as_of, **earn_summary, "series_points": len(earn_rows)},
    )
    results["vaults"]["lido_earn_eth"] = earn_summary
    print(
        f"EarnETH points={len(earn_rows)} "
        f"first={earn_rows[0]['date'] if earn_rows else None} "
        f"last={earn_rows[-1]['date'] if earn_rows else None}"
    )
    print_windows(earn_summary)

    write_json(ROOT / "results" / "summary.json", results)
    mode = "recompute-only" if args.recompute_only else "one-shot fetch"
    print(f"\nWrote data/ and results/. Done ({mode}; no scheduled refresh).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
