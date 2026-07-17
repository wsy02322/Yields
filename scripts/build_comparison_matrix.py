#!/usr/bin/env python3
"""Build / refresh the Fluid + Lido comparison matrix.

Uses existing daily_share_price CSVs (no archive re-pull by default) and
live official APIs:
  - Fluid Lite Net/Gross (Instadapp)
  - EarnETH APY* 14d avg (Mellow timeweighted-apy)

Optional ``--pull`` re-fetches share-price history to tip (archive RPC).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import load_w3  # noqa: E402
from src.calculators.apy import summarize_vault  # noqa: E402
from src.calculators.comparison_matrix import (  # noqa: E402
    COMPARISON_WINDOWS_DAYS,
    build_comparison_matrix,
)
from src.calculators.official_apy_proxy import (  # noqa: E402
    RECOMMENDED_PROXY_NAME,
    build_official_comparison,
)
from src.fetchers import earneth as earneth_fetcher  # noqa: E402
from src.fetchers import fluid_lite as fluid_fetcher  # noqa: E402
from src.fetchers.earneth_official import fetch_official_earneth_apy  # noqa: E402
from src.fetchers.fluid_lite_official import (  # noqa: E402
    FLUID_LITE_VAULTS_URL,
    IETH_V2,
    fetch_official_vault_apy,
)


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


def merge_by_date(old: list[dict], new: list[dict]) -> list[dict]:
    by = {r["date"]: r for r in old}
    for r in new:
        by[r["date"]] = {
            "date": r["date"],
            "share_price": float(r["share_price"]),
            "share_price_wei": r.get("share_price_wei"),
            "block": r.get("block"),
            "block_timestamp_est": r.get("block_timestamp_est"),
        }
    return [by[k] for k in sorted(by)]


def next_day(date_s: str) -> str:
    d = datetime.fromisoformat(date_s).date() + timedelta(days=1)
    return d.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Incrementally fetch missing daily share prices to tip (archive RPC).",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    as_of: dict = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "refresh_policy": "historical one-shot only; no automatic updates",
        "refreshed_by": "cursor-cloud-agent",
        "windows_days": COMPARISON_WINDOWS_DAYS,
    }

    w3 = None
    if args.pull:
        w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
        tip = w3.eth.get_block("latest")
        tip_ts = int(tip["timestamp"])
        as_of.update(
            {
                "tip_block": int(tip["number"]),
                "tip_timestamp": tip_ts,
                "tip_date_utc": datetime.fromtimestamp(tip_ts, tz=timezone.utc).strftime(
                    "%Y-%m-%d"
                ),
            }
        )
        tip_day = as_of["tip_date_utc"]

        fl = cfg["vaults"]["fluid_lite_eth"]
        fluid_path = ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv"
        fluid_old = load_series(fluid_path) if fluid_path.exists() else []
        start = next_day(fluid_old[-1]["date"]) if fluid_old else fl["deployment_date"]
        print(f"Fluid pull {start} -> {tip_day}")
        if start <= tip_day:
            fluid_new = fluid_fetcher.fetch_daily_series(
                w3,
                fl["receipt_token"],
                start_block=int(fl["deployment_block"]),
                start_date=start,
                end_date=tip_day,
                max_workers=6,
            )
            fluid_rows = merge_by_date(fluid_old, fluid_new)
        else:
            fluid_rows = fluid_old
        write_csv(fluid_path, fluid_rows)

        le = cfg["vaults"]["lido_earn_eth"]
        earn_path = ROOT / "data" / "lido-earn-eth" / "daily_share_price.csv"
        earn_old = load_series(earn_path) if earn_path.exists() else []
        start_e = next_day(earn_old[-1]["date"]) if earn_old else le["deployment_date"]
        print(f"EarnETH pull {start_e} -> {tip_day}")
        if start_e <= tip_day:
            earn_new = earneth_fetcher.fetch_daily_series(
                w3,
                le["oracle"],
                le["base_asset"],
                start_block=int(le["deployment_block"]),
                start_date=start_e,
                end_date=tip_day,
                max_workers=4,
            )
            earn_rows = merge_by_date(earn_old, earn_new)
        else:
            earn_rows = earn_old
        write_csv(earn_path, earn_rows)
    else:
        prev = json.loads((ROOT / "results" / "summary.json").read_text())
        as_of.update({k: prev["as_of"].get(k) for k in ("tip_block", "tip_timestamp", "tip_date_utc")})
        fluid_rows = load_series(ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv")
        earn_rows = load_series(ROOT / "data" / "lido-earn-eth" / "daily_share_price.csv")

    fl = cfg["vaults"]["fluid_lite_eth"]
    le = cfg["vaults"]["lido_earn_eth"]

    # ---- Official APIs ----
    fluid_official = fetch_official_vault_apy()
    lido_official = fetch_official_earneth_apy()
    print(
        f"Fluid Official Net={fluid_official['net_apy_pct']:.6f}% "
        f"Gross={fluid_official['gross_apy_pct']:.6f}%"
    )
    print(
        f"Lido Official {lido_official['label']}={lido_official['apy_pct']:.6f}% "
        f"(days={lido_official['days']})"
    )

    # Fluid official snapshot (compact)
    import requests

    resp = requests.get(FLUID_LITE_VAULTS_URL, timeout=30)
    resp.raise_for_status()
    vault_item = next(
        i
        for i in resp.json()
        if str(i.get("vault") or "").lower() == IETH_V2.lower()
    )
    write_json(
        ROOT / "data" / "fluid-lite-eth" / "official_api_snapshot.json",
        {
            "fetched_at_utc": fluid_official["fetched_at_utc"],
            "source_url": FLUID_LITE_VAULTS_URL,
            "vault": IETH_V2,
            "exchangePriceiETHV2": vault_item.get("exchangePriceiETHV2"),
            "withdrawalFee": vault_item.get("withdrawalFee"),
            "revenueFee": vault_item.get("revenueFee"),
            "apy": vault_item.get("apy"),
            "vaultTVLInAsset": vault_item.get("vaultTVLInAsset"),
        },
    )
    write_json(
        ROOT / "data" / "lido-earn-eth" / "official_api_snapshot.json",
        lido_official,
    )

    # ---- Summaries ----
    fluid_summary = summarize_vault(
        fluid_rows,
        exit_fee=float(fl["fees"]["exit_fee"]),
        fees=fl["fees"],
        offchain_rewards=fl.get("offchain_rewards") or [],
        notes=[
            "Share price from ERC-4626 convertToAssets(1e18); underlying is stETH.",
            "Hold APY ignores exit fee; Realized applies 0.05% exit once at window end.",
            "Prefer Hold APY on short windows (≤30d).",
            "Official UI Net comparison uses completed 1d Hold APY on the matrix 1d row.",
        ],
    )
    apy_cmp = build_official_comparison(
        fluid_rows,
        official_net_apy=fluid_official["net_apy"],
        official_gross_apy=fluid_official["gross_apy"],
        official_meta={
            "source_url": fluid_official["source_url"],
            "fetched_at_utc": fluid_official["fetched_at_utc"],
            "vault": fluid_official["vault"],
            "api_field_net": "apy.apyWithoutFee",
            "api_field_gross": "apy.apyWithFee",
        },
    )
    apy_cmp["as_of"] = {
        "generated_at_utc": as_of["generated_at_utc"],
        "series_points": len(fluid_rows),
        "series_first_date": fluid_rows[0]["date"],
        "series_last_date": fluid_rows[-1]["date"],
    }
    write_json(ROOT / "data/fluid-lite-eth/official_apy_proxy_comparison.json", apy_cmp)
    write_json(ROOT / "results/fluid-lite-official-apy-proxy.json", apy_cmp)
    fluid_summary["official_apy_comparison"] = {
        "recommended_proxy_name": RECOMMENDED_PROXY_NAME,
        "recommended_proxy": apy_cmp["recommended_proxy"],
        "official_net_apy_pct": apy_cmp["official"]["net_apy_pct"],
        "official_gross_apy_pct": apy_cmp["official"]["gross_apy_pct"],
        "detail_file": "data/fluid-lite-eth/official_apy_proxy_comparison.json",
    }
    write_json(ROOT / "data/fluid-lite-eth/summary.json", fluid_summary)
    write_json(
        ROOT / "results/fluid-lite-eth.json",
        {"as_of": as_of, **fluid_summary, "series_points": len(fluid_rows)},
    )

    # EarnETH fees
    if w3 is None:
        w3 = load_w3(cfg["rpc"]["url"], cfg["rpc"].get("timeout_seconds", 45))
    fee_params = earneth_fetcher.read_fee_params(w3, le["fee_manager"])
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
    earn_summary = summarize_vault(
        earn_rows,
        exit_fee=fee_params["redeemFeeD6"] / 1e6,
        fees=fees,
        offchain_rewards=le.get("offchain_rewards") or [],
        notes=[
            "Share price from Mellow oracle ETH report.",
            "Official UI APY* (14d avg.) from Mellow timeweighted-apy endpoint.",
            "Mellow Points / Obol / SSV excluded from APY.",
        ],
    )
    earn_summary["official_apy"] = {
        "apy_pct": lido_official["apy_pct"],
        "days": lido_official["days"],
        "label": lido_official["label"],
        "source_url": lido_official["source_url"],
        "fetched_at_utc": lido_official["fetched_at_utc"],
        "apy_last_update_utc": lido_official["apy_last_update_utc"],
    }
    write_json(ROOT / "data/lido-earn-eth/summary.json", earn_summary)
    write_json(
        ROOT / "results/lido-earn-eth.json",
        {"as_of": as_of, **earn_summary, "series_points": len(earn_rows)},
    )

    matrix = build_comparison_matrix(
        fluid_summary=fluid_summary,
        earn_summary=earn_summary,
        fluid_series=fluid_rows,
        fluid_exit_fee=float(fl["fees"]["exit_fee"]),
        fluid_official_net_apy_pct=fluid_official["net_apy_pct"],
        lido_official_apy_pct=lido_official["apy_pct"],
        fluid_official_meta={
            "gross_apy_pct": fluid_official["gross_apy_pct"],
            "fetched_at_utc": fluid_official["fetched_at_utc"],
            "source_url": fluid_official["source_url"],
        },
        lido_official_meta={
            "days": lido_official["days"],
            "label": lido_official["label"],
            "fetched_at_utc": lido_official["fetched_at_utc"],
            "source_url": lido_official["source_url"],
            "apy_last_update_utc": lido_official["apy_last_update_utc"],
            "ui_url": lido_official["ui_url"],
        },
    )
    matrix["as_of"] = as_of
    write_json(ROOT / "results/comparison_matrix.json", matrix)
    write_json(ROOT / "data/comparison_matrix.json", matrix)

    write_json(
        ROOT / "results/summary.json",
        {
            "as_of": as_of,
            "vaults": {
                "fluid_lite_eth": fluid_summary,
                "lido_earn_eth": earn_summary,
            },
            "comparison_matrix_file": "results/comparison_matrix.json",
        },
    )

    print("\n" + matrix["markdown_table"])
    print("wrote results/comparison_matrix.json and updated summaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
