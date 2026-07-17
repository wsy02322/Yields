#!/usr/bin/env python3
"""Fetch DefiLlama Fluid Lite Official UI history and compare vs Hold / Official-algo.

Writes:
  data/fluid-lite-eth/official_ui_apy_history.csv
  data/fluid-lite-eth/official_ui_history_compare.json
  results/fluid-lite-official-ui-history-compare.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.calculators.fluid_lite_official_algo import (  # noqa: E402
    fetch_and_compute_official_algo_apy,
)
from src.calculators.fluid_official_ui_history import (  # noqa: E402
    build_official_ui_history_compare,
)
from src.fetchers.fluid_lite_defillama import fetch_official_ui_apy_history  # noqa: E402


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def write_history_csv(path: Path, series: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date",
        "timestamp_utc",
        "official_ui_apy_pct",
        "tvl_usd",
        "hold_1d_apy_pct",
        "delta_hold_1d_vs_ui_pp",
        "hold_7d_apy_pct",
        "delta_hold_7d_vs_ui_pp",
        "hold_30d_apy_pct",
        "delta_hold_30d_vs_ui_pp",
    ]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in series:
            w.writerow(row)


def load_share_series(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open()))
    return [
        {"date": r["date"], "share_price": float(r["share_price"])}
        for r in rows
    ]


def main() -> int:
    share_path = ROOT / "data" / "fluid-lite-eth" / "daily_share_price.csv"
    if not share_path.exists():
        print(f"missing {share_path}", file=sys.stderr)
        return 1

    print("Fetching DefiLlama Official UI history…")
    history = fetch_official_ui_apy_history()
    print(
        f"  points={history['points']} "
        f"{history['first_date']} → {history['last_date']}"
    )

    share = load_share_series(share_path)
    print(f"Share series points={len(share)} {share[0]['date']} → {share[-1]['date']}")

    try:
        algo = fetch_and_compute_official_algo_apy()
        print(
            f"Official-algo Net={algo['net_apy_pct']:.4f}% "
            f"(Δ vs API {algo['api_comparison']['delta_net_pp']:+.4f} pp)"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Official-algo skipped: {exc}")
        algo = None

    compare = build_official_ui_history_compare(
        official_history=history,
        share_series=share,
        official_algo=algo,
        recent_days=30,
    )

    # Persist full joined series as CSV (UI + Hold deltas)
    write_history_csv(
        ROOT / "data" / "fluid-lite-eth" / "official_ui_apy_history.csv",
        compare["joined_series"],
    )
    # Compact meta without the huge joined_series for results/
    compact = {k: v for k, v in compare.items() if k != "joined_series"}
    compact["history_csv"] = "data/fluid-lite-eth/official_ui_apy_history.csv"
    compact["official_algo_live"] = (
        None
        if algo is None
        else {
            "net_apy_pct": algo["net_apy_pct"],
            "gross_apy_pct": algo["gross_apy_pct"],
            "delta_net_pp_vs_api": algo["api_comparison"]["delta_net_pp"],
            "fetched_at_utc": algo["fetched_at_utc"],
        }
    )
    write_json(ROOT / "data/fluid-lite-eth/official_ui_history_compare.json", compact)
    write_json(ROOT / "results/fluid-lite-official-ui-history-compare.json", compact)

    latest = compare.get("latest") or {}
    print("\nLatest alignment:")
    print(
        f"  date={latest.get('date')} UI={latest.get('official_ui_apy_pct')}% "
        f"hold_1d={latest.get('hold_1d_apy_pct')}% "
        f"hold_7d={latest.get('hold_7d_apy_pct')}% "
        f"hold_30d={latest.get('hold_30d_apy_pct')}% "
        f"algo={latest.get('official_algo_net_apy_pct')}%"
    )
    s = compare["summary"]
    for n in (1, 7, 30):
        st = s.get(f"hold_{n}d_vs_ui_delta_pp_recent")
        if st:
            print(
                f"  recent {n}d Hold−UI: mean={st['mean']:+.2f}pp "
                f"median={st['median']:+.2f}pp "
                f"range=[{st['min']:+.2f},{st['max']:+.2f}]"
            )
    print("\n" + compare["markdown_recent_table"])
    print("wrote data/fluid-lite-eth/official_ui_apy_history.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
