"""Instadapp Lite vault API (official UI/APY source)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_VAULTS_URL = (
    "https://api.instadapp.io/v2/mainnet/lite/users/"
    "0x0000000000000000000000000000000000000000/vaults"
)


def fetch_vaults(url: str = DEFAULT_VAULTS_URL, *, timeout: float = 20.0) -> list[dict[str, Any]]:
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "yields-research/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if not isinstance(data, list):
        raise ValueError("expected list of vaults from Instadapp API")
    return data


def pick_vault(vaults: list[dict[str, Any]], receipt_token: str) -> dict[str, Any] | None:
    target = receipt_token.lower()
    for v in vaults:
        addr = (v.get("address") or v.get("vault") or "").lower()
        if addr == target:
            return v
    return None


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def fetch_official_apy(
    receipt_token: str,
    *,
    api_url: str = DEFAULT_VAULTS_URL,
    snapshot_path: Path | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Return official Net/Gross APY; live API first, then local snapshot."""
    fetched_at = datetime.now(tz=timezone.utc).isoformat()
    try:
        vaults = fetch_vaults(api_url, timeout=timeout)
        vault = pick_vault(vaults, receipt_token)
        if vault is None:
            raise ValueError(f"vault {receipt_token} not found in API response")
        apy = vault.get("apy") or {}
        return {
            "source": "live_api",
            "source_url": api_url,
            "fetched_at_utc": fetched_at,
            "vault": receipt_token,
            "exchangePrice": vault.get("exchangePrice") or vault.get("exchangePriceiETHV2"),
            "exchangePriceiETHV2": vault.get("exchangePriceiETHV2") or vault.get("exchangePrice"),
            "revenueFee": vault.get("revenueFee"),
            "withdrawalFee": vault.get("withdrawalFee"),
            "vaultTVLInAsset": vault.get("vaultTVLInAsset"),
            "apy": {
                "apyWithoutFee": apy.get("apyWithoutFee"),
                "apyWithFee": apy.get("apyWithFee"),
            },
            "protocolsInfo_yields": vault.get("protocolsInfo"),
        }
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
        if snapshot_path is None or not snapshot_path.is_file():
            raise RuntimeError(f"official APY fetch failed and no snapshot: {exc}") from exc
        snap = load_snapshot(snapshot_path)
        return {
            "source": "local_snapshot",
            "source_url": snap.get("source_url", api_url),
            "fetched_at_utc": snap.get("fetched_at_utc", fetched_at),
            "vault": snap.get("vault", receipt_token),
            "exchangePrice": snap.get("exchangePriceiETHV2") or snap.get("exchangePrice"),
            "exchangePriceiETHV2": snap.get("exchangePriceiETHV2") or snap.get("exchangePrice"),
            "revenueFee": snap.get("revenueFee"),
            "withdrawalFee": snap.get("withdrawalFee"),
            "vaultTVLInAsset": snap.get("vaultTVLInAsset"),
            "apy": snap.get("apy", {}),
            "protocolsInfo_yields": snap.get("protocolsInfo_yields") or snap.get("protocolsInfo"),
            "fallback_reason": str(exc),
        }
