"""Historical APY proxies closest to Fluid Lite official (UI) Net APY.

Official Net/Gross APY is a *forward* estimate from current rates × positions.
This module only uses *trailing* share-price history and asks which trailing
definition lands nearest the live Net figure — for side-by-side comparison,
not as a replacement for the official number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.calculators.apy import annualize, nearest_on_or_before, period_return


def _parse_date(s: str) -> datetime:
    return datetime.fromisoformat(s)


def simple_annualize(total_return: float, days: float) -> float | None:
    """Linear / simple annualization: R × (365.25 / days)."""
    if days < 1:
        return None
    return total_return * (365.25 / days)


@dataclass(frozen=True)
class ProxyCandidate:
    name: str
    method: str
    window: str
    start_date: str
    end_date: str
    days: float
    hold_return: float
    apy: float
    notes: str


# Recommended proxy after scanning fixed windows + EWMA against live Net APY
# (2026-07-15 snapshot: Net ≈ 5.84%). Short trailing windows (~3%) are far;
# inception + simple annualization is the closest fee-aligned trailing metric.
RECOMMENDED_PROXY_NAME = "inception_hold_simple"
RECOMMENDED_PROXY_DEFINITION = (
    "Inception Hold APY with simple (linear) annualization: "
    "R = share_price_T / share_price_0 − 1; "
    "APY = R × (365.25 / days). "
    "No exit fee (matches UI Net fee treatment: performance fee already in "
    "share price; exit fee not in Net APY)."
)


def _inception_hold(
    series: list[dict[str, Any]],
    *,
    method: str,
) -> ProxyCandidate | None:
    if len(series) < 2:
        return None
    start, end = series[0], series[-1]
    days = float((_parse_date(end["date"]) - _parse_date(start["date"])).days)
    if days < 1:
        return None
    ret = period_return(float(start["share_price"]), float(end["share_price"]))
    if method == "simple":
        apy = simple_annualize(ret, days)
        name = "inception_hold_simple"
        notes = RECOMMENDED_PROXY_DEFINITION
    else:
        apy = annualize(ret, days)
        name = "inception_hold_compound"
        notes = (
            "Inception Hold APY with compound annualization: "
            "APY = (1+R)^(365.25/days) − 1. Same fee treatment as UI Net "
            "(no exit fee); repo default trailing method."
        )
    if apy is None:
        return None
    return ProxyCandidate(
        name=name,
        method=method,
        window="inception",
        start_date=start["date"],
        end_date=end["date"],
        days=days,
        hold_return=ret,
        apy=apy,
        notes=notes,
    )


def _fixed_window_hold(
    series: list[dict[str, Any]],
    *,
    days_n: int,
    method: str,
) -> ProxyCandidate | None:
    if not series:
        return None
    end = series[-1]
    end_dt = _parse_date(end["date"])
    start_target = (end_dt - timedelta(days=days_n)).strftime("%Y-%m-%d")
    if series[0]["date"] > start_target:
        return None
    start = nearest_on_or_before(series, start_target)
    if start is None:
        return None
    days = float((_parse_date(end["date"]) - _parse_date(start["date"])).days)
    if days < 1:
        return None
    ret = period_return(float(start["share_price"]), float(end["share_price"]))
    apy = simple_annualize(ret, days) if method == "simple" else annualize(ret, days)
    if apy is None:
        return None
    return ProxyCandidate(
        name=f"{days_n}d_hold_{method}",
        method=method,
        window=f"{days_n}d",
        start_date=start["date"],
        end_date=end["date"],
        days=days,
        hold_return=ret,
        apy=apy,
        notes=f"{days_n}d trailing Hold APY ({method} annualization), no exit fee.",
    )


def enumerate_proxy_candidates(
    series: list[dict[str, Any]],
    *,
    window_days: list[int] | None = None,
) -> list[ProxyCandidate]:
    """Enumerate trailing Hold APY candidates (no exit fee)."""
    window_days = window_days or [7, 30, 90, 180, 365]
    out: list[ProxyCandidate] = []
    for n in window_days:
        for method in ("compound", "simple"):
            c = _fixed_window_hold(series, days_n=n, method=method)
            if c is not None:
                out.append(c)
    for method in ("compound", "simple"):
        c = _inception_hold(series, method=method)
        if c is not None:
            out.append(c)
    return out


def pick_closest_to_official(
    candidates: list[ProxyCandidate],
    official_net_apy: float,
) -> ProxyCandidate | None:
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs(c.apy - official_net_apy))


def candidate_to_dict(c: ProxyCandidate) -> dict[str, Any]:
    return {
        "name": c.name,
        "method": c.method,
        "window": c.window,
        "start_date": c.start_date,
        "end_date": c.end_date,
        "days": c.days,
        "hold_return_pct": round(c.hold_return * 100, 6),
        "apy_pct": round(c.apy * 100, 6),
        "notes": c.notes,
    }


def build_official_comparison(
    series: list[dict[str, Any]],
    *,
    official_net_apy: float,
    official_gross_apy: float | None = None,
    official_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build comparison payload: recommended proxy + ranked candidates vs Net APY.

    Parameters
    ----------
    official_net_apy / official_gross_apy
        Absolute fractions (e.g. 0.0584 for 5.84%), matching UI Net / Gross.
    """
    candidates = enumerate_proxy_candidates(series)
    ranked = sorted(candidates, key=lambda c: abs(c.apy - official_net_apy))
    empirical_best = ranked[0] if ranked else None
    recommended = next((c for c in candidates if c.name == RECOMMENDED_PROXY_NAME), None)
    if recommended is None:
        recommended = empirical_best

    def delta_pp(apy: float) -> float:
        return round((apy - official_net_apy) * 100, 6)

    ranked_rows = []
    for c in ranked:
        row = candidate_to_dict(c)
        row["abs_delta_vs_official_net_pp"] = round(abs(c.apy - official_net_apy) * 100, 6)
        row["delta_vs_official_net_pp"] = delta_pp(c.apy)
        ranked_rows.append(row)

    out: dict[str, Any] = {
        "definition": {
            "recommended_proxy_name": RECOMMENDED_PROXY_NAME,
            "recommended_proxy_formula": RECOMMENDED_PROXY_DEFINITION,
            "why": (
                "Among trailing share-price Hold APYs (7d/30d/90d/180d/365d/"
                "inception × compound|simple), inception + simple annualization "
                "is empirically closest to the UI Net APY on the 2026-07-15 "
                "series, and matches Net fee treatment (perf fee in price, "
                "no exit fee). Official APY remains forward-looking; this is "
                "only a historical proxy for comparison."
            ),
            "fee_alignment": {
                "performance_fee": "included (already in share price)",
                "exit_fee": "excluded (UI Net also excludes exit fee)",
            },
        },
        "official": {
            "net_apy_pct": round(official_net_apy * 100, 6),
            "gross_apy_pct": (
                None if official_gross_apy is None else round(official_gross_apy * 100, 6)
            ),
            **(official_meta or {}),
        },
        "recommended_proxy": None,
        "empirical_best_on_this_series": None,
        "candidates_ranked_by_abs_delta_vs_net": ranked_rows,
    }

    if recommended is not None:
        out["recommended_proxy"] = {
            **candidate_to_dict(recommended),
            "delta_vs_official_net_pp": delta_pp(recommended.apy),
            "abs_delta_vs_official_net_pp": round(
                abs(recommended.apy - official_net_apy) * 100, 6
            ),
        }
    if empirical_best is not None:
        out["empirical_best_on_this_series"] = {
            **candidate_to_dict(empirical_best),
            "delta_vs_official_net_pp": delta_pp(empirical_best.apy),
            "abs_delta_vs_official_net_pp": round(
                abs(empirical_best.apy - official_net_apy) * 100, 6
            ),
            "matches_recommended": empirical_best.name == RECOMMENDED_PROXY_NAME,
        }
    return out
