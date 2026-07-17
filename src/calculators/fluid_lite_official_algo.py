"""Reconstruct Fluid Lite ETH Gross/Net APY from live Instadapp vault payload.

Official UI Net/Gross is a *forward* estimate. Instadapp does not open-source the
aggregator, but the Lite fees docs + API fields reverse-engineer to:

    protocol_pnl = Σ (supplyAmt × supplyApy) − Σ (borrowAmt × borrowApy)
                 [+ dexYield × supply_notional for Fluid DEX]
    idle         = vaultTVLInAsset − Σ protocol netAssets
    idle_pnl     ≈ idle × stETH.netStakingApr
    Gross APY    ≈ (Σ protocol_pnl + idle_pnl) / vaultTVLInAsset
    Net APY      = Gross APY × (1 − revenueFee/100)

Amounts/yields use ETH-denominated fields (stETH/eETH/ETH supply, wETH/stETH
borrow) to avoid double-counting wstETH/weETH wrappers.

Typical residual vs API ``apyWithFee`` / ``apyWithoutFee`` is ~0.01–0.03 pp.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from src.fetchers.fluid_lite_official import FLUID_LITE_VAULTS_URL, IETH_V2

# ETH-unit supply / borrow (skip wstETH/weETH wrappers — same economic exposure).
_SUPPLY_PAIRS = (
    ("stETHSupply", "stETHSupplyYield"),
    ("eETHSupply", "eETHSupplyYield"),
    ("ethSupply", "ethSupplyYield"),
)
_BORROW_PAIRS = (
    ("wETHBorrow", "wETHBorrowYield"),
    ("stETHBorrow", "stETHBorrowYield"),
)


def _f(x: Any) -> float:
    if x is None or x == "":
        return 0.0
    return float(x)


@dataclass(frozen=True)
class ProtocolPnl:
    name: str
    supply_pnl: float
    borrow_pnl: float
    dex_pnl: float
    net_assets: float

    @property
    def pnl(self) -> float:
        return self.supply_pnl - self.borrow_pnl + self.dex_pnl


def _protocol_pnl(name: str, info: dict[str, Any]) -> ProtocolPnl:
    supply_pnl = 0.0
    supply_notional = 0.0
    for amt_k, yld_k in _SUPPLY_PAIRS:
        amt = _f(info.get(amt_k))
        yld_pct = _f(info.get(yld_k))
        if amt:
            supply_pnl += amt * (yld_pct / 100.0)
            supply_notional += amt

    borrow_pnl = 0.0
    for amt_k, yld_k in _BORROW_PAIRS:
        amt = _f(info.get(amt_k))
        yld_pct = _f(info.get(yld_k))
        if amt:
            borrow_pnl += amt * (yld_pct / 100.0)

    # Fluid DEX: docs allow + dexYield × notional; use ETH-unit supplies.
    dex_pnl = 0.0
    if "dexYield" in info and supply_notional > 0:
        dex_pnl = supply_notional * (_f(info.get("dexYield")) / 100.0)

    return ProtocolPnl(
        name=name,
        supply_pnl=supply_pnl,
        borrow_pnl=borrow_pnl,
        dex_pnl=dex_pnl,
        net_assets=_f(info.get("netAssets")),
    )


def compute_official_algo_apy(vault_item: dict[str, Any]) -> dict[str, Any]:
    """Compute Gross/Net APY fractions from one Instadapp lite vault JSON object."""
    tvl = _f(vault_item.get("vaultTVLInAsset"))
    if tvl <= 0:
        raise ValueError("vaultTVLInAsset must be positive")

    revenue_fee_pct = _f(vault_item.get("revenueFee"))
    steth = vault_item.get("stETH") or {}
    net_staking_apr_pct = _f(steth.get("netStakingApr"))

    protocols = vault_item.get("protocolsInfo") or {}
    protocol_rows: list[ProtocolPnl] = []
    for name, info in protocols.items():
        if isinstance(info, dict):
            protocol_rows.append(_protocol_pnl(name, info))

    protocol_pnl = sum(p.pnl for p in protocol_rows)
    protocol_net_assets = sum(p.net_assets for p in protocol_rows)
    idle = tvl - protocol_net_assets
    idle_pnl = idle * (net_staking_apr_pct / 100.0)

    gross = (protocol_pnl + idle_pnl) / tvl
    net = gross * (1.0 - revenue_fee_pct / 100.0)

    api_apy = vault_item.get("apy") or {}
    api_gross_pct = _f(api_apy.get("apyWithFee")) if api_apy.get("apyWithFee") is not None else None
    api_net_pct = (
        _f(api_apy.get("apyWithoutFee")) if api_apy.get("apyWithoutFee") is not None else None
    )

    def pct(x: float | None) -> float | None:
        return None if x is None else round(x * 100, 6)

    return {
        "method": "fluid_lite_official_algo_reconstructed",
        "formula": (
            "Gross=(Σ protocol_pnl + idle×stETH.netStakingApr)/TVL; "
            "Net=Gross×(1−revenueFee/100); "
            "protocol_pnl=Σ supply×supplyApy − Σ borrow×borrowApy "
            "[+ dexYield×ETH-supply notional]"
        ),
        "gross_apy": gross,
        "net_apy": net,
        "gross_apy_pct": pct(gross),
        "net_apy_pct": pct(net),
        "revenue_fee_pct": revenue_fee_pct,
        "vault_tvl_in_asset": tvl,
        "protocol_net_assets": protocol_net_assets,
        "idle_assets": idle,
        "idle_share_of_tvl_pct": round(idle / tvl * 100, 6),
        "steth_net_staking_apr_pct": net_staking_apr_pct,
        "protocol_pnl": protocol_pnl,
        "idle_pnl": idle_pnl,
        "protocols": [
            {
                "name": p.name,
                "pnl": p.pnl,
                "supply_pnl": p.supply_pnl,
                "borrow_pnl": p.borrow_pnl,
                "dex_pnl": p.dex_pnl,
                "net_assets": p.net_assets,
                "levered_net_apy_pct": (
                    None if p.net_assets <= 0 else round(p.pnl / p.net_assets * 100, 6)
                ),
            }
            for p in protocol_rows
        ],
        "api_comparison": {
            "api_gross_apy_pct": api_gross_pct,
            "api_net_apy_pct": api_net_pct,
            "delta_gross_pp": (
                None if api_gross_pct is None else round(gross * 100 - api_gross_pct, 6)
            ),
            "delta_net_pp": (
                None if api_net_pct is None else round(net * 100 - api_net_pct, 6)
            ),
        },
    }


def fetch_vault_item(
    *,
    vault: str = IETH_V2,
    url: str = FLUID_LITE_VAULTS_URL,
    timeout: float = 30.0,
) -> dict[str, Any]:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    vault_l = vault.lower()
    for item in payload:
        addr = str(item.get("vault") or item.get("tokenAddress") or "").lower()
        if addr == vault_l:
            return item
    raise LookupError(f"vault {vault} not found in Fluid Lite API response")


def fetch_and_compute_official_algo_apy(
    *,
    vault: str = IETH_V2,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Live fetch + reconstruct; includes API Net/Gross for side-by-side delta."""
    item = fetch_vault_item(vault=vault, timeout=timeout)
    computed = compute_official_algo_apy(item)
    return {
        "fetched_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "source_url": FLUID_LITE_VAULTS_URL,
        "vault": vault,
        "exchange_price": item.get("exchangePriceiETHV2"),
        "withdrawal_fee": item.get("withdrawalFee"),
        "revenue_fee": item.get("revenueFee"),
        "vault_tvl_in_asset": item.get("vaultTVLInAsset"),
        "api_apy": item.get("apy"),
        **computed,
    }
