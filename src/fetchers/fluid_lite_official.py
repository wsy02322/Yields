"""Fetch Fluid Lite official vault APY from Instadapp API (same source as UI)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

FLUID_LITE_VAULTS_URL = (
    "https://api.instadapp.io/v2/mainnet/lite/users/"
    "0x0000000000000000000000000000000000000000/vaults"
)
IETH_V2 = "0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78"


def fetch_official_vault_apy(
    *,
    vault: str = IETH_V2,
    url: str = FLUID_LITE_VAULTS_URL,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Return Net/Gross APY fractions plus raw API fee fields for one vault.

    API naming (inverted vs UI):
      apyWithoutFee → UI Net APY
      apyWithFee    → UI Gross APY
    """
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        raise ValueError(f"unexpected API payload type: {type(payload)}")

    vault_l = vault.lower()
    match = None
    for item in payload:
        addr = str(item.get("vault") or item.get("tokenAddress") or "").lower()
        if addr == vault_l:
            match = item
            break
    if match is None:
        raise LookupError(f"vault {vault} not found in Fluid Lite API response")

    apy = match.get("apy") or {}
    net_s = apy.get("apyWithoutFee")
    gross_s = apy.get("apyWithFee")
    if net_s is None or gross_s is None:
        raise KeyError("apy.apyWithoutFee / apy.apyWithFee missing from API item")

    net = float(net_s) / 100.0
    gross = float(gross_s) / 100.0
    return {
        "fetched_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "source_url": url,
        "vault": vault,
        "net_apy": net,
        "gross_apy": gross,
        "net_apy_pct": float(net_s),
        "gross_apy_pct": float(gross_s),
        "revenue_fee": match.get("revenueFee"),
        "withdrawal_fee": match.get("withdrawalFee"),
        "exchange_price": match.get("exchangePriceiETHV2"),
        "vault_tvl_in_asset": match.get("vaultTVLInAsset"),
        # Keep raw strings for audit
        "apy_raw": {
            "apyWithoutFee": str(net_s),
            "apyWithFee": str(gross_s),
        },
    }
