"""Historical yield / APY calculators (net of on-chain fees).

Primary reported APYs are ETH-denominated:
  - Vault share-price APY in the vault's accounting asset (e.g. stETH/share)
  - Compounded with underlying→ETH intrinsic APY when the accounting asset is not ETH
    (same structure as vaults.fyi Base × Intrinsic → Total)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


SECONDS_PER_YEAR = 365.25 * 24 * 3600
# Default assumed holding period when converting a one-time exit fee into an APY drag.
# Prevents short measurement windows from annualizing a single withdraw fee over 7d/30d.
DEFAULT_EXIT_FEE_HOLD_DAYS = 365.25


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s)


@dataclass
class WindowReturn:
    label: str
    start_date: str
    end_date: str
    days: float
    start_share_price: float
    end_share_price_hold: float
    end_share_price_realized: float
    # Vault accounting-asset returns (e.g. stETH/share for Fluid, ETH/share for EarnETH)
    hold_return_underlying: float
    realized_return_underlying: float
    hold_apy_underlying: float | None
    # Underlying asset → ETH intrinsic (0 when vault already accounts in ETH)
    underlying_eth_return: float
    underlying_eth_apy: float | None
    # ETH-denominated (primary)
    hold_return: float
    realized_return: float
    hold_apy: float | None
    realized_apy: float | None
    exit_fee_apy_drag: float | None
    exit_fee_hold_days: float


def period_return(start_price: float, end_price: float) -> float:
    if start_price <= 0:
        raise ValueError("start_price must be positive")
    return end_price / start_price - 1.0


def annualize(total_return: float, days: float) -> float | None:
    if days <= 0:
        return None
    # Guard extreme / incomplete windows
    if days < 1:
        return None
    return (1.0 + total_return) ** (365.25 / days) - 1.0


def compound_returns(*returns: float) -> float:
    """(1+r1)*(1+r2)*... - 1"""
    acc = 1.0
    for r in returns:
        acc *= 1.0 + r
    return acc - 1.0


def compound_apys(*apys: float | None) -> float | None:
    """Compound APYs: (1+a1)*(1+a2)*... - 1. Any None → None."""
    if any(a is None for a in apys):
        return None
    acc = 1.0
    for a in apys:
        acc *= 1.0 + float(a)
    return acc - 1.0


def apply_exit_fee(share_price: float, exit_fee: float) -> float:
    """Reduce terminal share value by a one-time withdraw/exit fee."""
    if exit_fee < 0 or exit_fee >= 1:
        raise ValueError("exit_fee must be in [0, 1)")
    return share_price * (1.0 - exit_fee)


def exit_fee_apy_drag(
    exit_fee: float,
    hold_days: float = DEFAULT_EXIT_FEE_HOLD_DAYS,
) -> float:
    """APY reduction from a one-time exit fee amortized over ``hold_days``.

    With the default 1-year hold, drag ≈ exit_fee (e.g. 0.05% → ~0.05 pp APY).
    """
    if exit_fee < 0 or exit_fee >= 1:
        raise ValueError("exit_fee must be in [0, 1)")
    if hold_days < 1:
        raise ValueError("hold_days must be >= 1")
    return 1.0 - (1.0 - exit_fee) ** (365.25 / hold_days)


def apply_exit_fee_to_apy(
    hold_apy: float | None,
    exit_fee: float,
    hold_days: float = DEFAULT_EXIT_FEE_HOLD_DAYS,
) -> float | None:
    """Convert Hold APY → Realized APY using exit-fee drag over ``hold_days``."""
    if hold_apy is None:
        return None
    factor = (1.0 - exit_fee) ** (365.25 / hold_days)
    return (1.0 + hold_apy) * factor - 1.0


def pick_row(series: list[dict[str, Any]], date: str) -> dict[str, Any] | None:
    for row in series:
        if row["date"] == date:
            return row
    return None


def nearest_on_or_before(series: list[dict[str, Any]], date: str) -> dict[str, Any] | None:
    candidates = [r for r in series if r["date"] <= date]
    return candidates[-1] if candidates else None


def _underlying_eth_window_return(
    underlying_eth_series: list[dict[str, Any]] | None,
    start_date: str,
    end_date: str,
) -> tuple[float, float | None]:
    """Return (period_return, apy) of underlying→ETH over [start, end]."""
    if not underlying_eth_series:
        return 0.0, 0.0
    start = nearest_on_or_before(underlying_eth_series, start_date)
    end = nearest_on_or_before(underlying_eth_series, end_date)
    if start is None or end is None or end["date"] < start["date"]:
        return 0.0, 0.0
    days = (_parse_date(end["date"]) - _parse_date(start["date"])).days
    if days <= 0:
        return 0.0, 0.0
    ret = period_return(float(start["share_price"]), float(end["share_price"]))
    return ret, annualize(ret, float(days))


def compute_window(
    series: list[dict[str, Any]],
    *,
    label: str,
    start_date: str,
    end_date: str,
    exit_fee: float = 0.0,
    exit_fee_hold_days: float = DEFAULT_EXIT_FEE_HOLD_DAYS,
    underlying_eth_series: list[dict[str, Any]] | None = None,
) -> WindowReturn | None:
    start = nearest_on_or_before(series, start_date)
    end = nearest_on_or_before(series, end_date)
    if start is None or end is None:
        return None
    if end["date"] < start["date"]:
        return None

    days = (_parse_date(end["date"]) - _parse_date(start["date"])).days
    if days <= 0:
        return None

    sp0 = float(start["share_price"])
    sp1 = float(end["share_price"])
    sp1_realized = apply_exit_fee(sp1, exit_fee)

    # Vault path in accounting asset (stETH for Fluid, ETH for EarnETH)
    hold_ret_u = period_return(sp0, sp1)
    realized_ret_u = period_return(sp0, sp1_realized)
    hold_apy_u = annualize(hold_ret_u, float(days))

    # Underlying → ETH intrinsic over the same calendar window (0 if already ETH)
    u_eth_ret, u_eth_apy = _underlying_eth_window_return(
        underlying_eth_series, start["date"], end["date"]
    )

    # ETH-denominated: compound vault path with underlying→ETH (vaults.fyi Total)
    hold_ret = compound_returns(hold_ret_u, u_eth_ret)
    realized_ret = compound_returns(realized_ret_u, u_eth_ret)
    hold_apy = compound_apys(hold_apy_u, u_eth_apy)
    drag = exit_fee_apy_drag(exit_fee, exit_fee_hold_days)
    realized_apy = apply_exit_fee_to_apy(hold_apy, exit_fee, exit_fee_hold_days)

    return WindowReturn(
        label=label,
        start_date=start["date"],
        end_date=end["date"],
        days=float(days),
        start_share_price=sp0,
        end_share_price_hold=sp1,
        end_share_price_realized=sp1_realized,
        hold_return_underlying=hold_ret_u,
        realized_return_underlying=realized_ret_u,
        hold_apy_underlying=hold_apy_u,
        underlying_eth_return=u_eth_ret,
        underlying_eth_apy=u_eth_apy,
        hold_return=hold_ret,
        realized_return=realized_ret,
        hold_apy=hold_apy,
        realized_apy=realized_apy,
        exit_fee_apy_drag=drag,
        exit_fee_hold_days=float(exit_fee_hold_days),
    )


def rolling_windows(
    series: list[dict[str, Any]],
    *,
    exit_fee: float,
    windows_days: list[int] | None = None,
    exit_fee_hold_days: float = DEFAULT_EXIT_FEE_HOLD_DAYS,
    underlying_eth_series: list[dict[str, Any]] | None = None,
) -> list[WindowReturn]:
    if not series:
        return []
    windows_days = windows_days or [7, 30, 90]
    end = series[-1]
    end_date = end["date"]
    end_dt = _parse_date(end_date)
    out: list[WindowReturn] = []

    for n in windows_days:
        start_dt = end_dt - timedelta(days=n)
        start_date = start_dt.strftime("%Y-%m-%d")
        if series[0]["date"] > start_date:
            continue
        w = compute_window(
            series,
            label=f"{n}d",
            start_date=start_date,
            end_date=end_date,
            exit_fee=exit_fee,
            exit_fee_hold_days=exit_fee_hold_days,
            underlying_eth_series=underlying_eth_series,
        )
        if w is not None:
            out.append(w)

    w = compute_window(
        series,
        label="inception",
        start_date=series[0]["date"],
        end_date=end_date,
        exit_fee=exit_fee,
        exit_fee_hold_days=exit_fee_hold_days,
        underlying_eth_series=underlying_eth_series,
    )
    if w is not None:
        out.append(w)
    return out


def window_to_dict(w: WindowReturn) -> dict[str, Any]:
    def pct(x: float | None) -> float | None:
        return None if x is None else round(x * 100, 6)

    return {
        "window": w.label,
        "start_date": w.start_date,
        "end_date": w.end_date,
        "days": w.days,
        "start_share_price": w.start_share_price,
        "end_share_price_hold": w.end_share_price_hold,
        "end_share_price_realized": w.end_share_price_realized,
        # Components
        "hold_return_underlying_pct": pct(w.hold_return_underlying),
        "hold_apy_underlying_pct": pct(w.hold_apy_underlying),
        "underlying_eth_return_pct": pct(w.underlying_eth_return),
        "underlying_eth_apy_pct": pct(w.underlying_eth_apy),
        # ETH-denominated primary
        "hold_return_pct": pct(w.hold_return),
        "realized_return_pct": pct(w.realized_return),
        "hold_apy_pct": pct(w.hold_apy),
        "realized_apy_pct": pct(w.realized_apy),
        "exit_fee_apy_drag_pct": pct(w.exit_fee_apy_drag),
        "exit_fee_hold_days": w.exit_fee_hold_days,
    }


def daily_returns(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        r = period_return(float(a["share_price"]), float(b["share_price"]))
        out.append(
            {
                "date": b["date"],
                "share_price": b["share_price"],
                "daily_return": r,
                "daily_return_pct": r * 100,
            }
        )
    return out


def summarize_vault(
    series: list[dict[str, Any]],
    *,
    exit_fee: float,
    fees: dict[str, Any],
    offchain_rewards: list[dict[str, Any]] | None = None,
    notes: list[str] | None = None,
    exit_fee_hold_days: float = DEFAULT_EXIT_FEE_HOLD_DAYS,
    denomination: str = "ETH",
    accounting_asset: str = "ETH",
    underlying_eth_series: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    windows = [
        window_to_dict(w)
        for w in rolling_windows(
            series,
            exit_fee=exit_fee,
            exit_fee_hold_days=exit_fee_hold_days,
            underlying_eth_series=underlying_eth_series,
        )
    ]
    return {
        "points": len(series),
        "first_date": series[0]["date"] if series else None,
        "last_date": series[-1]["date"] if series else None,
        "first_share_price": series[0]["share_price"] if series else None,
        "last_share_price": series[-1]["share_price"] if series else None,
        "denomination": denomination,
        "accounting_asset": accounting_asset,
        "fees": fees,
        "exit_fee_applied_in_realized": exit_fee,
        "exit_fee_hold_days": exit_fee_hold_days,
        "exit_fee_apy_drag_pct": round(
            exit_fee_apy_drag(exit_fee, exit_fee_hold_days) * 100, 6
        ),
        "offchain_rewards_excluded_from_apy": offchain_rewards or [],
        "windows": windows,
        "notes": notes or [],
    }
