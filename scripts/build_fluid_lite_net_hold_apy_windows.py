#!/usr/bin/env python3
"""Build Fluid Lite ETH Net Hold APY for 1/7/14/30/90/120/180d windows.

Reads existing daily share-price CSV (no archive re-pull). Hold only —
no exit fee / realized APY.
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

from src.calculators.fluid_lite_net_hold_apy import (  # noqa: E402
    NET_HOLD_WINDOWS_DAYS,
    summarize_fluid_lite_net_hold_apy,
)


def load_series(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append(
            {
                "date": r["date"],
                "share_price": float(r["share_price"]),
                "share_price_wei": int(r["share_price_wei"]) if r.get("share_price_wei") else None,
                "block": int(r["block"]) if r.get("block") else None,
            }
        )
    return out


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def write_md(path: Path, report: dict) -> None:
    lines = [
        "# Fluid Lite ETH — Net Hold APY (independent)",
        "",
        f"Generated: **{report['as_of']['generated_at_utc'][:10]} UTC**",
        "",
        f"Vault: [{report['vault']['name']}]({report['vault']['url']})",
        "",
        "## Meaning",
        "",
        report["metric"]["meaning"],
        "",
        "## Formula",
        "",
        "```",
        "R   = share_price_T / share_price_T0 − 1   # stETH per iETHv2 share",
        "APY = (1 + R)^(365.25 / days) − 1         # Net Hold (perf fee in price)",
        "```",
        "",
        "Exit fee **not** applied. Trailing path — not UI forward Net APY.",
        "",
        "## Windows",
        "",
        "| Window | Net Hold APY | 1 stETH → after 1y | Days | Range |",
        "|--------|-------------:|-------------------:|-----:|-------|",
    ]
    for w in report["windows"]:
        apy = w["net_hold_apy_pct"]
        after = w["steth_after_1y_per_1_steth"]
        apy_s = "—" if apy is None else f"{apy:.4f}%"
        after_s = "—" if after is None else f"{after:.6f} stETH"
        lines.append(
            f"| {w['window']} | {apy_s} | {after_s} | {w['days']:.0f} | "
            f"{w['start_date']} → {w['end_date']} |"
        )
    lines.extend(
        [
            "",
            f"Series: **{report['points']}** daily points "
            f"(`{report['first_date']}` → `{report['last_date']}`).",
            "",
            "Reproduce:",
            "",
            "```bash",
            "python scripts/build_fluid_lite_net_hold_apy_windows.py",
            "```",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    fl = cfg["vaults"]["fluid_lite_eth"]
    csv_path = ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv"
    if not csv_path.exists():
        raise SystemExit(f"missing series: {csv_path}")

    series = load_series(csv_path)
    as_of = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "source_csv": str(csv_path.relative_to(ROOT)),
        "refresh_policy": "reuses existing CSV; no archive re-pull",
        "windows_days": NET_HOLD_WINDOWS_DAYS,
    }
    report = summarize_fluid_lite_net_hold_apy(
        series,
        windows_days=NET_HOLD_WINDOWS_DAYS,
        fees=fl["fees"],
        as_of=as_of,
        vault_meta={
            "name": fl["name"],
            "url": "https://fluid.io/lite/1/ETH",
            "receipt_token": fl["receipt_token"],
            "receipt_symbol": fl["receipt_symbol"],
            "underlying": "stETH (ETH-correlated)",
        },
    )

    out_json = ROOT / "results" / "fluid-lite-eth-net-hold-apy-windows.json"
    out_data = ROOT / "data" / "fluid-lite-eth" / "net_hold_apy_windows.json"
    out_md = ROOT / "results" / "fluid-lite-eth-net-hold-apy-windows.md"
    write_json(out_json, report)
    write_json(out_data, report)
    write_md(out_md, report)

    print(f"points={report['points']} {report['first_date']} -> {report['last_date']}")
    for w in report["windows"]:
        print(
            f"  {w['window']}: net_hold_apy={w['net_hold_apy_pct']}% "
            f"→ {w['steth_after_1y_per_1_steth']} stETH/ETH after 1y "
            f"({w['start_date']} -> {w['end_date']})"
        )
    print(f"wrote {out_json.relative_to(ROOT)}")
    print(f"wrote {out_md.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
