#!/usr/bin/env python3
"""Fetch official APY displays and compare to our trailing share-price APYs.

EarnETH:
  - UI label: APY* (14d avg.) on stake.lido.fi
  - Mellow API: weekly (time_range=604800s = 7d)

Fluid Lite:
  - UI label: Net APY (spot projection from live rates; not trailing)
  - API: apy.apyWithoutFee (Net), apy.apyWithFee (Gross)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_summary() -> dict:
    return json.loads((ROOT / "results" / "summary.json").read_text())


def window_map(vault_summary: dict) -> dict[str, dict]:
    return {w["window"]: w for w in vault_summary.get("windows", [])}


def fetch_earneth_official(cfg: dict) -> dict:
    meta = cfg["official_apy"]["lido_earn_eth"]
    r = requests.get(meta["api_url"], timeout=45)
    r.raise_for_status()
    vaults = r.json()
    vault = next(v for v in vaults if v.get("id") == meta["api_vault_id"])
    breakdown = (vault.get("apr_breakdown") or [{}])[0]
    time_range = int(breakdown.get("time_range") or 0)
    return {
        "source": "mellow_api",
        "ui_url": meta["ui_url"],
        "ui_label": meta["ui_label"],
        "ui_window_days": meta["ui_window_days"],
        "api_apy_pct": float(vault["apy"]),
        "api_window_days": time_range / 86400.0 if time_range else meta["api_window_days"],
        "api_updated_at": breakdown.get("updated_at"),
        "notes": meta.get("notes") or [],
    }


def fetch_fluid_official(cfg: dict) -> dict:
    meta = cfg["official_apy"]["fluid_lite_eth"]
    r = requests.get(meta["api_url"], timeout=45)
    r.raise_for_status()
    rows = r.json()
    target = meta["api_vault"].lower()
    item = next(x for x in rows if x.get("vault", "").lower() == target)
    apy = item.get("apy") or {}
    net = float(apy["apyWithoutFee"])
    gross = float(apy["apyWithFee"])
    return {
        "source": "instadapp_lite_api",
        "ui_url": meta["ui_url"],
        "ui_label": meta["ui_label"],
        "methodology": meta["methodology"],
        "ui_window_days": meta["ui_window_days"],
        "net_apy_pct": net,
        "gross_apy_pct": gross,
        "implied_perf_fee": 1.0 - (net / gross) if gross else None,
        "exchange_price": item.get("exchangePriceiETHV2"),
        "withdrawal_fee_pct": float(item.get("withdrawalFee", 0)),
        "revenue_fee_pct": float(item.get("revenueFee", 0)),
        "notes": meta.get("notes") or [],
    }


def delta(ours: float | None, official: float | None) -> float | None:
    if ours is None or official is None:
        return None
    return round(ours - official, 6)


def compare(cfg: dict, summary: dict) -> dict:
    earn_off = fetch_earneth_official(cfg)
    fluid_off = fetch_fluid_official(cfg)

    earn = summary["vaults"]["lido_earn_eth"]
    fluid = summary["vaults"]["fluid_lite_eth"]
    ew = window_map(earn)
    fw = window_map(fluid)

    earn_cmp = {
        "official": earn_off,
        "ours": {
            "7d_hold_apy_pct": (ew.get("7d") or {}).get("hold_apy_pct"),
            "14d_hold_apy_pct": (ew.get("14d") or {}).get("hold_apy_pct"),
            "7d_realized_apy_pct": (ew.get("7d") or {}).get("realized_apy_pct"),
            "14d_realized_apy_pct": (ew.get("14d") or {}).get("realized_apy_pct"),
        },
        "deltas": {
            "ours_7d_hold_minus_mellow_api": delta(
                (ew.get("7d") or {}).get("hold_apy_pct"), earn_off["api_apy_pct"]
            ),
            "ours_14d_hold_minus_mellow_api": delta(
                (ew.get("14d") or {}).get("hold_apy_pct"), earn_off["api_apy_pct"]
            ),
        },
        "alignment": {
            "primary_match_window": "7d",
            "reason": "Mellow API time_range=7d (weekly); Lido UI label is 14d avg — both windows reported.",
            "matched_field": "hold_apy (fees already in share price; redeem fee=0)",
        },
    }

    fluid_cmp = {
        "official": fluid_off,
        "ours": {
            "7d_hold_apy_pct": (fw.get("7d") or {}).get("hold_apy_pct"),
            "14d_hold_apy_pct": (fw.get("14d") or {}).get("hold_apy_pct"),
            "30d_hold_apy_pct": (fw.get("30d") or {}).get("hold_apy_pct"),
            "90d_hold_apy_pct": (fw.get("90d") or {}).get("hold_apy_pct"),
            "since_earneth_hold_apy_pct": (fw.get("since_earneth") or {}).get("hold_apy_pct"),
            "inception_hold_apy_pct": (fw.get("inception") or {}).get("hold_apy_pct"),
        },
        "deltas_vs_spot_net": {
            "7d": delta((fw.get("7d") or {}).get("hold_apy_pct"), fluid_off["net_apy_pct"]),
            "14d": delta((fw.get("14d") or {}).get("hold_apy_pct"), fluid_off["net_apy_pct"]),
            "30d": delta((fw.get("30d") or {}).get("hold_apy_pct"), fluid_off["net_apy_pct"]),
        },
        "alignment": {
            "primary_match_window": None,
            "reason": (
                "Official Net APY is spot/projected from live protocol rates, "
                "not a trailing share-price window — no identical window to add."
            ),
            "matched_field": "hold_apy is historical realized path; official Net is forward-looking rate",
        },
    }

    return {
        "compared_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "share_price_as_of": summary.get("as_of"),
        "vaults": {
            "lido_earn_eth": earn_cmp,
            "fluid_lite_eth": fluid_cmp,
        },
    }


def to_markdown(cmp: dict) -> str:
    e = cmp["vaults"]["lido_earn_eth"]
    f = cmp["vaults"]["fluid_lite_eth"]
    eo, fo = e["official"], f["official"]
    lines = [
        "# Official APY comparison",
        "",
        f"Compared at: **{cmp['compared_at_utc']}**",
        "",
        "Vaults remain independent; this is a display-alignment check only.",
        "",
        "## Lido EarnETH",
        "",
        f"- UI: [{eo['ui_label']}]({eo['ui_url']}) → window label **{eo['ui_window_days']}d**",
        f"- API (Mellow): **{eo['api_apy_pct']:.4f}%** over **{eo['api_window_days']:.0f}d**",
        f"- Ours 7d hold: **{e['ours']['7d_hold_apy_pct']}%** (Δ vs API: {e['deltas']['ours_7d_hold_minus_mellow_api']})",
        f"- Ours 14d hold: **{e['ours']['14d_hold_apy_pct']}%** (Δ vs API: {e['deltas']['ours_14d_hold_minus_mellow_api']})",
        f"- Alignment: {e['alignment']['reason']}",
        "",
        "## Fluid Lite ETH",
        "",
        f"- UI: [{fo['ui_label']}]({fo['ui_url']}) — methodology **{fo['methodology']}** (no trailing window)",
        f"- API Net (`apyWithoutFee`): **{fo['net_apy_pct']:.4f}%**",
        f"- API Gross (`apyWithFee`): **{fo['gross_apy_pct']:.4f}%**",
        f"- Implied perf fee from Gross→Net: **{(fo['implied_perf_fee'] or 0)*100:.2f}%** (docs: 20%)",
        f"- Ours trailing hold APY — 7d: {f['ours']['7d_hold_apy_pct']}% | 14d: {f['ours']['14d_hold_apy_pct']}% | 30d: {f['ours']['30d_hold_apy_pct']}%",
        f"- Note: {f['alignment']['reason']}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    summary = load_summary()
    cmp = compare(cfg, summary)
    out_json = ROOT / "results" / "official_comparison.json"
    out_md = ROOT / "results" / "OFFICIAL_COMPARISON.md"
    out_json.write_text(json.dumps(cmp, indent=2) + "\n")
    out_md.write_text(to_markdown(cmp) + "\n")
    print(to_markdown(cmp))
    print(f"Wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
