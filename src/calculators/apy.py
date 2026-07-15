"""Historical yield / APY calculators (net of on-chain fees)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


SECONDS_PER_YEAR = 365.25 * 24 * 3600


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
    hold_return: float
    realized_return: float
    hold_apy: float | None
    realized_apy: float | None


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


def apply_exit_fee(share_price: float, exit_fee: float) -> float:
    """Reduce terminal share value by a one-time withdraw/exit fee."""
    if exit_fee < 0 or exit_fee >= 1:
        raise ValueError("exit_fee must be in [0, 1)")
    return share_price * (1.0 - exit_fee)


def pick_row(series: list[dict[str, Any]], date: str) -> dict[str, Any] | None:
    for row in series:
        if row["date"] == date:
            return row
    return None


def nearest_on_or_before(series: list[dict[str, Any]], date: str) -> dict[str, Any] | None:
    candidates = [r for r in series if r["date"] <= date]
    return candidates[-1] if candidates else None


def compute_window(
    series: list[dict[str, Any]],
    *,
    label: str,
    start_date: str,
    end_date: str,
    exit_fee: float = 0.0,
) -> WindowReturn | None:
    start = nearest_on_or_before(series, start_date)
    end = nearest_on_or_before(series, end_date)
    if start is None or end is None:
        return None
    if end["date"] < start["date"]:
        return None

    days = (_parse_date(end["date"]) - _parse_date(start["date"])).days
    if days <= 0:
        # same-day: no return window
        return None

    sp0 = float(start["share_price"])
    sp1 = float(end["share_price"])
    sp1_realized = apply_exit_fee(sp1, exit_fee)

    # Hold return: share price change only (ongoing fees already in price).
    # Realized: assume deposit at start (no deposit fee) and withdraw at end (exit/redeem fee).
    # For a fair realized comparison over a holding window, also haircut the starting
    # price? No — deposit fees reduce shares received at T0; exit fees reduce assets at T1.
    # With deposit_fee=0 for both vaults here, realized only applies exit fee on terminal value.
    hold_ret = period_return(sp0, sp1)
    realized_ret = period_return(sp0, sp1_realized)

    return WindowReturn(
        label=label,
        start_date=start["date"],
        end_date=end["date"],
        days=float(days),
        start_share_price=sp0,
        end_share_price_hold=sp1,
        end_share_price_realized=sp1_realized,
        hold_return=hold_ret,
        realized_return=realized_ret,
        hold_apy=annualize(hold_ret, float(days)),
        realized_apy=annualize(realized_ret, float(days)),
    )


def rolling_windows(
    series: list[dict[str, Any]],
    *,
    exit_fee: float,
    windows_days: list[int] | None = None,
    fixed_windows: list[dict[str, str]] | None = None,
) -> list[WindowReturn]:
    """Build rolling + optional shared fixed windows + vault inception.

    fixed_windows entries: {"label": "...", "start_date": "YYYY-MM-DD"}
    end date is always the series last date.
    """
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
        # Only if we have data on/before start
        if series[0]["date"] > start_date:
            continue
        w = compute_window(
            series,
            label=f"{n}d",
            start_date=start_date,
            end_date=end_date,
            exit_fee=exit_fee,
        )
        if w is not None:
            out.append(w)

    # Shared / named fixed windows (e.g. since EarnETH launch for both vaults)
    for fw in fixed_windows or []:
        label = fw["label"]
        start_date = fw["start_date"]
        if series[0]["date"] > start_date:
            # Series starts after the fixed window — skip
            continue
        w = compute_window(
            series,
            label=label,
            start_date=start_date,
            end_date=end_date,
            exit_fee=exit_fee,
        )
        if w is not None:
            out.append(w)

    # Vault-specific inception (full available history for this vault)
    w = compute_window(
        series,
        label="inception",
        start_date=series[0]["date"],
        end_date=end_date,
        exit_fee=exit_fee,
    )
    if w is not None:
        # Avoid duplicate when inception coincides with a fixed window
        if not any(
            x.label == w.label and x.start_date == w.start_date and x.end_date == w.end_date
            for x in out
        ):
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
        "hold_return_pct": pct(w.hold_return),
        "realized_return_pct": pct(w.realized_return),
        "hold_apy_pct": pct(w.hold_apy),
        "realized_apy_pct": pct(w.realized_apy),
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
    fixed_windows: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    windows = [
        window_to_dict(w)
        for w in rolling_windows(series, exit_fee=exit_fee, fixed_windows=fixed_windows)
    ]
    return {
        "points": len(series),
        "first_date": series[0]["date"] if series else None,
        "last_date": series[-1]["date"] if series else None,
        "first_share_price": series[0]["share_price"] if series else None,
        "last_share_price": series[-1]["share_price"] if series else None,
        "fees": fees,
        "exit_fee_applied_in_realized": exit_fee,
        "offchain_rewards_excluded_from_apy": offchain_rewards or [],
        "windows": windows,
        "notes": notes or [],
    }