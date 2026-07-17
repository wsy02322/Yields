"""Tests for Fluid Lite official-algo APY reconstruction."""

from __future__ import annotations

import pytest

from src.calculators.fluid_lite_official_algo import compute_official_algo_apy


def _sample_vault(*, api_gross: float = 7.40, api_net: float = 5.92) -> dict:
    # Tiny synthetic book: 100 supply @ 10%, 50 borrow @ 4%, TVL=60, idle=10 @ 2%
    # protocol netAssets=50, idle=10
    # pnl = 100*0.10 - 50*0.04 = 8; idle_pnl=10*0.02=0.2; gross=8.2/60; net=gross*0.8
    return {
        "vaultTVLInAsset": "60",
        "revenueFee": "20",
        "stETH": {"netStakingApr": "2.0"},
        "protocolsInfo": {
            "demo": {
                "stETHSupply": "100",
                "stETHSupplyYield": "10",
                "wETHBorrow": "50",
                "wETHBorrowYield": "4",
                "netAssets": "50",
            }
        },
        "apy": {"apyWithFee": str(api_gross), "apyWithoutFee": str(api_net)},
    }


def test_compute_official_algo_apy_basic():
    out = compute_official_algo_apy(_sample_vault())
    # gross = 8.2/60 = 0.136666...; net = *0.8
    assert out["gross_apy"] == pytest.approx(8.2 / 60)
    assert out["net_apy"] == pytest.approx((8.2 / 60) * 0.8)
    assert out["idle_assets"] == pytest.approx(10.0)
    assert out["protocols"][0]["pnl"] == pytest.approx(8.0)


def test_compute_official_algo_includes_dex_yield():
    vault = _sample_vault()
    vault["protocolsInfo"]["demo"]["ethSupply"] = "20"
    vault["protocolsInfo"]["demo"]["ethSupplyYield"] = "0"
    vault["protocolsInfo"]["demo"]["dexYield"] = "1"  # 1% on supply notional 120
    out = compute_official_algo_apy(vault)
    # supply pnl = 100*0.10 + 20*0 = 10; borrow=2; dex=120*0.01=1.2; pnl=9.2
    assert out["protocols"][0]["dex_pnl"] == pytest.approx(1.2)
    assert out["protocols"][0]["pnl"] == pytest.approx(9.2)


def test_rejects_non_positive_tvl():
    with pytest.raises(ValueError):
        compute_official_algo_apy({"vaultTVLInAsset": "0", "protocolsInfo": {}})
