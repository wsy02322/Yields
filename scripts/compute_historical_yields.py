#!/usr/bin/env python3
"""One-shot historical yield pull for Fluid Lite ETH and Lido EarnETH.

Only processes data that has already occurred. Re-running / refreshing
requires an explicit user request (no scheduled updates).
"""

from __future__ import annotations

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
    # stable column order
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


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
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

    results: dict = {"as_of": as_of, "vaults": {}}

    # ---- Fluid Lite ETH ----
    fl = cfg["vaults"]["fluid_lite_eth"]
    print(f"\n=== Fetching {fl['name']} daily share prices ===")
    fluid_rows = fluid_fetcher.fetch_daily_series(
        w3,
        fl["receipt_token"],
        start_block=int(fl["deployment_block"]),
        start_date=fl["deployment_date"],
        max_workers=6,
    )
    write_csv(ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv", fluid_rows)
    exit_fee_hold_days = float(fl.get("exit_fee_hold_days", 365.25))
    fluid_summary = summarize_vault(
        fluid_rows,
        exit_fee=float(fl["fees"]["exit_fee"]),
        fees=fl["fees"],
        exit_fee_hold_days=exit_fee_hold_days,
        offchain_rewards=fl.get("offchain_rewards") or [],
        notes=[
            "Share price from ERC-4626 convertToAssets(1e18); underlying is stETH (ETH-correlated).",
            "20% performance fee is already deducted inside share price (Net).",
            "Realized APY = Hold APY with exit-fee drag amortized over a default 1-year hold "
            f"({exit_fee_hold_days} days), so 0.05% exit ≈ −0.05 pp APY (not annualized over 7d/30d).",
            "realized_return_pct still shows period wealth if withdrawing at window end; "
            "only realized_apy uses the 1-year fee amortization.",
            "Hold APY ignores exit fee (useful for mark-to-market while still deposited).",
            "Vaults are independent; no comparison metrics are produced against EarnETH.",
        ],
    )
    write_json(ROOT / "data" / "fluid-lite-eth" / "summary.json", fluid_summary)
    write_json(ROOT / "results" / "fluid-lite-eth.json", {"as_of": as_of, **fluid_summary, "series_points": len(fluid_rows)})
    results["vaults"]["fluid_lite_eth"] = fluid_summary
    print(f"Fluid Lite points={len(fluid_rows)} first={fluid_rows[0]['date'] if fluid_rows else None} last={fluid_rows[-1]['date'] if fluid_rows else None}")
    for w in fluid_summary["windows"]:
        print(
            f"  {w['window']}: hold_apy={w['hold_apy_pct']}% realized_apy={w['realized_apy_pct']}% "
            f"({w['start_date']} -> {w['end_date']}, {w['days']}d)"
        )

    # ---- Lido EarnETH ----
    le = cfg["vaults"]["lido_earn_eth"]
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
    write_csv(ROOT / "data" / "lido-earn-eth" / "daily_share_price.csv", earn_rows)
    # Merge config fees with on-chain confirmation
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
    exit_fee = fee_params["redeemFeeD6"] / 1e6  # 0 on-chain today
    exit_fee_hold_days = float(le.get("exit_fee_hold_days", 365.25))
    earn_summary = summarize_vault(
        earn_rows,
        exit_fee=exit_fee,
        fees=fees,
        exit_fee_hold_days=exit_fee_hold_days,
        offchain_rewards=le.get("offchain_rewards") or [],
        notes=[
            "Share price derived from Mellow oracle ETH report: eth_per_share = 1e18 / (priceD18/1e18).",
            "1% protocol (platform) fee and 10% performance fee are minted as vault shares on oracle reports; already in net share price.",
            "On-chain depositFeeD6=0 and redeemFeeD6=0 at snapshot time; realized ≈ hold for redeem fee.",
            "Exit-fee APY drag (if any) amortizes over a default 1-year hold, same as Fluid Lite.",
            "Mellow Points, Obol, and SSV rewards are listed under offchain_rewards and are NOT included in APY.",
            "Vaults are independent; no comparison metrics are produced against Fluid Lite.",
        ],
    )
    write_json(ROOT / "data" / "lido-earn-eth" / "summary.json", earn_summary)
    write_json(
        ROOT / "results" / "lido-earn-eth.json",
        {"as_of": as_of, **earn_summary, "series_points": len(earn_rows)},
    )
    results["vaults"]["lido_earn_eth"] = earn_summary
    print(f"EarnETH points={len(earn_rows)} first={earn_rows[0]['date'] if earn_rows else None} last={earn_rows[-1]['date'] if earn_rows else None}")
    for w in earn_summary["windows"]:
        print(
            f"  {w['window']}: hold_apy={w['hold_apy_pct']}% realized_apy={w['realized_apy_pct']}% "
            f"({w['start_date']} -> {w['end_date']}, {w['days']}d)"
        )

    write_json(ROOT / "results" / "summary.json", results)
    print("\nWrote data/ and results/. Done (one-shot; no scheduled refresh).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())