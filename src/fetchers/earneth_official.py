"""Fetch Lido EarnETH official UI APY (Mellow 14d time-weighted).

Lido Earn UI labels this as ``APY* (14d avg.)`` and reads:

  GET https://api.mellow.finance/v1/chain/1/core-vaults/{vault}/timeweighted-apy

Same source as lidofinance/ethereum-staking-widget ``fetchEthVaultStatsApr``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

EARNETH_VAULT = "0x6a37725ca7f4CE81c004c955f7280d5C704a249e"
MELLOW_TIMEWEIGHTED_APY_URL = (
    "https://api.mellow.finance/v1/chain/1/core-vaults/"
    f"{EARNETH_VAULT}/timeweighted-apy"
)


def fetch_official_earneth_apy(
    *,
    url: str = MELLOW_TIMEWEIGHTED_APY_URL,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Return official EarnETH APY fraction + metadata (UI 14d avg)."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected API payload type: {type(payload)}")

    apy_raw = payload.get("apy")
    days = payload.get("days")
    last_update = payload.get("apyLastUpdate")
    if apy_raw is None or days is None:
        raise KeyError("apy / days missing from Mellow timeweighted-apy response")

    apy_pct = float(apy_raw)
    return {
        "fetched_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "source_url": url,
        "vault": EARNETH_VAULT,
        "apy": apy_pct / 100.0,
        "apy_pct": apy_pct,
        "days": int(days),
        "apy_last_update": int(last_update) if last_update is not None else None,
        "apy_last_update_utc": (
            None
            if last_update is None
            else datetime.fromtimestamp(int(last_update), tz=timezone.utc).isoformat()
        ),
        "label": f"APY* ({int(days)}d avg.)",
        "ui_url": "https://stake.lido.fi/earn/eth/deposit",
    }
