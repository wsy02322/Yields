"""Fluid Lite ETH — independent Net Hold APY across trailing windows.

Net Hold APY answers: if you deposit 1 stETH (or 1 ETH → vault) and stay
deposited, how much extra stETH/ETH would you earn over a year, if the
observed trailing window's share-price growth compounds.

Share price = ERC-4626 convertToAssets(1e18) = stETH per iETHv2 share.
The 20% performance fee is already inside that price (Net). Exit fee is
NOT applied (Hold = still deposited).
"""

from __future__ import annotations

from typing import Any

from src.calculators.apy import annualize, compute_window, rolling_windows

# Trailing windows requested for independent Fluid Net Hold APY.
NET_HOLD_WINDOWS_DAYS: list[int] = [1, 7, 14, 30, 90, 120, 180]

MEANING = (
    "Net Hold APY ≈ annualized growth of underlying stETH claim per share "
    "(ETH-equivalent while stETH≈ETH). Example: 5% Net Hold APY means "
    "1 stETH deposited → ~1.05 stETH after one year if that window's "
    "growth compounds; same reading for ETH deposited into the vault."
)


def hold_window_to_dict(w) -> dict[str, Any]:
    """Serialize a window as Hold-only (no realized / exit-fee fields)."""

    def pct(x: float | None) -> float | None:
        return None if x is None else round(x * 100, 6)

    return {
        "window": w.label,
        "start_date": w.start_date,
        "end_date": w.end_date,
        "days": w.days,
        "start_share_price_steth": w.start_share_price,
        "end_share_price_steth": w.end_share_price_hold,
        "hold_return_pct": pct(w.hold_return),
        "net_hold_apy_pct": pct(w.hold_apy),
        "steth_after_1y_per_1_steth": (
            None if w.hold_apy is None else round(1.0 + w.hold_apy, 8)
        ),
        "eth_after_1y_per_1_eth": (
            None if w.hold_apy is None else round(1.0 + w.hold_apy, 8)
        ),
    }


def compute_net_hold_windows(
    series: list[dict[str, Any]],
    *,
    windows_days: list[int] | None = None,
    include_inception: bool = False,
) -> list[dict[str, Any]]:
    """Trailing Net Hold APY for each window (exit_fee=0 → Hold only)."""
    days = list(windows_days or NET_HOLD_WINDOWS_DAYS)
    windows = rolling_windows(series, exit_fee=0.0, windows_days=days)
    if not include_inception:
        windows = [w for w in windows if w.label != "inception"]
    return [hold_window_to_dict(w) for w in windows]


def summarize_fluid_lite_net_hold_apy(
    series: list[dict[str, Any]],
    *,
    windows_days: list[int] | None = None,
    fees: dict[str, Any] | None = None,
    as_of: dict[str, Any] | None = None,
    vault_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Fluid-only Net Hold APY report."""
    windows = compute_net_hold_windows(series, windows_days=windows_days)
    return {
        "vault": vault_meta
        or {
            "name": "Fluid Lite ETH Vault",
            "url": "https://fluid.io/lite/1/ETH",
            "receipt_token": "0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78",
            "receipt_symbol": "iETHv2",
            "underlying": "stETH (ETH-correlated)",
        },
        "metric": {
            "name": "net_hold_apy",
            "formula": "APY = (1 + R)^(365.25/days) - 1",
            "R": "share_price_T / share_price_T0 - 1",
            "share_price": "convertToAssets(1e18) → stETH per share",
            "performance_fee": "20% already inside share price (Net)",
            "exit_fee": "not applied (Hold = still deposited)",
            "meaning": MEANING,
        },
        "as_of": as_of,
        "points": len(series),
        "first_date": series[0]["date"] if series else None,
        "last_date": series[-1]["date"] if series else None,
        "first_share_price_steth": series[0]["share_price"] if series else None,
        "last_share_price_steth": series[-1]["share_price"] if series else None,
        "fees": fees
        or {
            "performance_fee": 0.20,
            "exit_fee": 0.0005,
            "management_fee": 0.0,
            "note": "exit_fee listed for reference only; not used in Net Hold APY",
        },
        "windows_days": list(windows_days or NET_HOLD_WINDOWS_DAYS),
        "windows": windows,
        "notes": [
            MEANING,
            "Independent Fluid-only calculation; no Lido / cross-vault compare.",
            "Trailing (historical path), not the Fluid UI forward Net APY.",
            "stETH≈ETH reading: vault NAV is stETH-denominated; ETH deposit "
            "enters the same share-price path, so Net Hold APY is the ETH "
            "growth rate under a stable stETH/ETH peg.",
        ],
    }


def verify_annualize_identity(hold_return: float, days: float) -> float | None:
    """Expose annualize for tests / scripts without re-importing apy."""
    return annualize(hold_return, days)


def window_from_dates(
    series: list[dict[str, Any]],
    *,
    label: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any] | None:
    w = compute_window(
        series,
        label=label,
        start_date=start_date,
        end_date=end_date,
        exit_fee=0.0,
    )
    return None if w is None else hold_window_to_dict(w)
