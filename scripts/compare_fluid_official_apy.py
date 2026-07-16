#!/usr/bin/env python3
"""Compare historical share-price APY proxies vs Fluid Lite official Net APY.

Uses existing daily_share_price.csv (no archive re-pull) + live Instadapp API.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.calculators.official_apy_proxy import (  # noqa: E402
    RECOMMENDED_PROXY_NAME,
    build_official_comparison,
)
from src.fetchers.fluid_lite_official import fetch_official_vault_apy  # noqa: E402


def load_series(csv_path: Path) -> list[dict]:
    rows = list(csv.DictReader(csv_path.open()))
    out = []
    for r in rows:
        out.append(
            {
                "date": r["date"],
                "share_price": float(r["share_price"]),
                "share_price_wei": r.get("share_price_wei"),
                "block": r.get("block"),
            }
        )
    return out


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def main() -> int:
    series_path = ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv"
    if not series_path.exists():
        print(f"missing series: {series_path}", file=sys.stderr)
        return 1

    series = load_series(series_path)
    print(f"loaded {len(series)} points ({series[0]['date']} → {series[-1]['date']})")

    official = fetch_official_vault_apy()
    print(
        f"official Net={official['net_apy_pct']:.6f}% "
        f"Gross={official['gross_apy_pct']:.6f}%"
    )

    comparison = build_official_comparison(
        series,
        official_net_apy=official["net_apy"],
        official_gross_apy=official["gross_apy"],
        official_meta={
            "source_url": official["source_url"],
            "fetched_at_utc": official["fetched_at_utc"],
            "vault": official["vault"],
            "revenue_fee": official["revenue_fee"],
            "withdrawal_fee": official["withdrawal_fee"],
            "api_field_net": "apy.apyWithoutFee",
            "api_field_gross": "apy.apyWithFee",
        },
    )
    comparison["as_of"] = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "series_path": str(series_path.relative_to(ROOT)),
        "series_points": len(series),
        "series_first_date": series[0]["date"],
        "series_last_date": series[-1]["date"],
    }

    out_data = ROOT / "data" / "fluid-lite-eth" / "official_apy_proxy_comparison.json"
    out_results = ROOT / "results" / "fluid-lite-official-apy-proxy.json"
    write_json(out_data, comparison)
    write_json(out_results, comparison)

    compact = {
        "recommended_proxy_name": RECOMMENDED_PROXY_NAME,
        "recommended_proxy": comparison["recommended_proxy"],
        "official_net_apy_pct": comparison["official"]["net_apy_pct"],
        "official_gross_apy_pct": comparison["official"]["gross_apy_pct"],
        "detail_file": "data/fluid-lite-eth/official_apy_proxy_comparison.json",
    }

    # Attach compact block onto existing fluid summary / results if present
    summary_path = ROOT / "data" / "fluid-lite-eth" / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        summary["official_apy_comparison"] = compact
        write_json(summary_path, summary)

    results_fluid = ROOT / "results" / "fluid-lite-eth.json"
    if results_fluid.exists():
        rf = json.loads(results_fluid.read_text())
        rf["official_apy_comparison"] = compact
        write_json(results_fluid, rf)

    proxy = comparison["recommended_proxy"]
    proxy_pct = proxy.get("annualized_pct", proxy.get("apr_pct", proxy.get("apy_pct")))
    print(
        f"recommended {proxy['name']} ({proxy.get('rate_kind', '?')}): "
        f"{proxy_pct:.6f}% "
        f"(Δ vs Net {proxy['delta_vs_official_net_pp']:+.4f} pp)"
    )
    best = comparison["empirical_best_on_this_series"]
    best_pct = best.get("annualized_pct", best.get("apr_pct", best.get("apy_pct")))
    print(
        f"empirical best {best['name']} ({best.get('rate_kind', '?')}): "
        f"{best_pct:.6f}% "
        f"(abs Δ {best['abs_delta_vs_official_net_pp']:.4f} pp, "
        f"matches_recommended={best['matches_recommended']})"
    )
    print(f"wrote {out_data.relative_to(ROOT)} and {out_results.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
