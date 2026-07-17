"""DefiLlama historical APY for Fluid Lite ETH (proxy for Official UI Net).

Instadapp does not expose historical Net/Gross APY. DefiLlama's fluid-lite
adaptor reads the same live field ``apy.apyWithoutFee`` (UI Net) and stores
a daily series — the best publicly available Official UI history.

Pool: ``e72916f7-a2d1-47ad-a4b9-2b054337cfd6``
Chart: ``https://yields.llama.fi/chart/{pool}``
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

FLUID_LITE_ETH_DEFILLAMA_POOL_ID = "e72916f7-a2d1-47ad-a4b9-2b054337cfd6"
DEFILLAMA_CHART_URL = (
    f"https://yields.llama.fi/chart/{FLUID_LITE_ETH_DEFILLAMA_POOL_ID}"
)
DEFILLAMA_POOL_PAGE = (
    f"https://defillama.com/yields/pool/{FLUID_LITE_ETH_DEFILLAMA_POOL_ID}"
)


def fetch_official_ui_apy_history(
    *,
    pool_id: str = FLUID_LITE_ETH_DEFILLAMA_POOL_ID,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Fetch DefiLlama daily Official UI Net APY history for Fluid Lite ETH."""
    url = f"https://yields.llama.fi/chart/{pool_id}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    raw = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        raise ValueError(f"unexpected DefiLlama chart payload: {type(raw)}")

    rows: list[dict[str, Any]] = []
    for item in raw:
        ts = item.get("timestamp")
        if not ts:
            continue
        if isinstance(ts, (int, float)):
            t = float(ts)
            if t > 1e12:
                t /= 1000.0
            dt = datetime.fromtimestamp(t, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        apy = item.get("apy")
        if apy is None:
            continue
        rows.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "timestamp_utc": dt.isoformat(),
                "official_ui_apy_pct": float(apy),
                "tvl_usd": float(item["tvlUsd"]) if item.get("tvlUsd") is not None else None,
            }
        )

    # Keep last observation per calendar day (DefiLlama is ~daily).
    by_date: dict[str, dict[str, Any]] = {}
    for r in rows:
        by_date[r["date"]] = r
    series = [by_date[k] for k in sorted(by_date)]

    return {
        "fetched_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "source": "defillama",
        "source_url": url,
        "pool_id": pool_id,
        "pool_page": DEFILLAMA_POOL_PAGE,
        "note": (
            "DefiLlama fluid-lite adaptor stores Instadapp apy.apyWithoutFee "
            "(UI Net APY). Instadapp itself has no public historical Net API."
        ),
        "points": len(series),
        "first_date": series[0]["date"] if series else None,
        "last_date": series[-1]["date"] if series else None,
        "series": series,
    }
