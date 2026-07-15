"""Historical proxies for Fluid Lite official (forward) Net APY."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


# Default half-life for EWMA of daily log returns on net share price.
# Empirically ~325d minimized error vs official Net APY on 2026-07-15 snapshot;
# 365d is used as the principled annual default (still closer than inception hold).
DEFAULT_EWMA_HALFLIFE_DAYS = 365.0


@dataclass
class EwmaNetApyProxy:
    """Trailing proxy intended to track UI Net APY from historical share prices."""

    halflife_days: float
    daily_log_return_ewma: float
    apy: float
    days_used: int
    last_date: str | None


def ewma_net_apy_proxy(
    series: list[dict[str, Any]],
    *,
    halflife_days: float = DEFAULT_EWMA_HALFLIFE_DAYS,
) -> EwmaNetApyProxy | None:
    """EWMA of daily log returns on share price, annualized.

    Share price is already net of the 20% performance fee (same basis as UI Net APY).
    Official UI Net APY is forward-looking (spot rates × positions); this metric is a
    trailing, recent-weighted estimate from realized share-price growth.
    """
    if len(series) < 2 or halflife_days <= 0:
        return None

    alpha = 1.0 - math.exp(-math.log(2.0) / halflife_days)
    ewma_log = 0.0
    initialized = False
    for i in range(1, len(series)):
        prev = float(series[i - 1]["share_price"])
        curr = float(series[i]["share_price"])
        if prev <= 0 or curr <= 0:
            continue
        log_r = math.log(curr / prev)
        if not initialized:
            ewma_log = log_r
            initialized = True
        else:
            ewma_log = alpha * log_r + (1.0 - alpha) * ewma_log

    if not initialized:
        return None

    apy = math.exp(ewma_log * 365.25) - 1.0
    return EwmaNetApyProxy(
        halflife_days=halflife_days,
        daily_log_return_ewma=ewma_log,
        apy=apy,
        days_used=len(series) - 1,
        last_date=series[-1].get("date"),
    )


def _pct(x: float | None, digits: int = 6) -> float | None:
    return None if x is None else round(x * 100, digits)


def build_official_apy_comparison(
    *,
    historical_proxy: EwmaNetApyProxy,
    official: dict[str, Any] | None,
    alternate_proxies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare historical EWMA proxy against official Instadapp Net/Gross APY."""
    official_net = None
    official_gross = None
    if official:
        apy = official.get("apy") or {}
        if apy.get("apyWithoutFee") is not None:
            official_net = float(apy["apyWithoutFee"]) / 100.0
        if apy.get("apyWithFee") is not None:
            official_gross = float(apy["apyWithFee"]) / 100.0

    proxy_apy = historical_proxy.apy
    delta_pp = None
    if official_net is not None:
        delta_pp = round((proxy_apy - official_net) * 100, 6)

    return {
        "purpose": "Compare trailing historical proxy vs official forward Net APY",
        "official": {
            "source": official.get("source_url") if official else None,
            "fetched_at_utc": official.get("fetched_at_utc") if official else None,
            "net_apy_pct": _pct(official_net),
            "gross_apy_pct": _pct(official_gross),
            "ui_labels": {
                "net_apy": "Net APY (apyWithoutFee; after 20% performance fee)",
                "gross_apy": "Gross APY (apyWithFee; before performance fee)",
            },
        },
        "historical_proxy": {
            "metric": "ewma_net_apy_proxy",
            "label": "EWMA Net APY proxy",
            "halflife_days": historical_proxy.halflife_days,
            "apy_pct": _pct(proxy_apy),
            "days_used": historical_proxy.days_used,
            "last_date": historical_proxy.last_date,
            "formula": "APY = exp(EWMA(ln(P_t/P_{t-1})) × 365.25) − 1 on daily share price",
            "basis": "Share price net of 20% performance fee; excludes 0.05% exit fee",
            "nature": "Trailing, recent-weighted; approximates forward UI Net APY better than fixed windows",
            "delta_vs_official_net_pp": delta_pp,
        },
        "alternate_proxies": alternate_proxies or [],
        "notes": [
            "Official Net APY is forward-looking (current protocol rates × positions), not trailing share-price growth.",
            "Among fixed hold windows on 2026-07-15, inception hold (~5.33%) was second-closest to official Net (~5.84%).",
            f"EWMA half-life {historical_proxy.halflife_days:.0f}d was chosen as an annual default; ~325d minimized error on the reference snapshot.",
        ],
    }
