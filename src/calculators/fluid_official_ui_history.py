"""Compare DefiLlama Official UI Net history vs trailing Hold APY.

Official-algo is only available as a live reconstruction (needs current
rates × positions), so it is attached as a latest-point reference only.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any

from src.calculators.apy import annualize, nearest_on_or_before, period_return


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


def hold_apy_asof(
    series: list[dict[str, Any]],
    *,
    asof_date: str,
    window_days: int,
) -> dict[str, Any] | None:
    """Trailing Hold APY ending on ``asof_date`` over ``window_days``.

    For 1d windows ending on a flat tip-day snapshot (incomplete UTC day with
    ~0 return vs prior EOD), use the previous completed EOD→EOD day instead.
    """
    end = nearest_on_or_before(series, asof_date)
    if end is None:
        return None

    if window_days == 1:
        # Prefer prior closed day when tip as-of is flat.
        idx = next((i for i, r in enumerate(series) if r["date"] == end["date"]), None)
        if idx is not None and idx >= 1:
            prev = series[idx - 1]
            days = (_parse(end["date"]) - _parse(prev["date"])).days
            if days == 1:
                ret = period_return(float(prev["share_price"]), float(end["share_price"]))
                is_tip = idx == len(series) - 1
                if is_tip and abs(ret) < 1e-12 and idx >= 2:
                    end = series[idx - 1]
                    prev = series[idx - 2]
                    ret = period_return(float(prev["share_price"]), float(end["share_price"]))
                    apy = annualize(ret, 1.0)
                    if apy is None:
                        return None
                    return {
                        "start_date": prev["date"],
                        "end_date": end["date"],
                        "days": 1.0,
                        "hold_return_pct": round(ret * 100, 6),
                        "hold_apy_pct": round(apy * 100, 6),
                        "note": "skipped flat tip-day; used prior completed 1d",
                    }

    start_target = (_parse(end["date"]) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    start = nearest_on_or_before(series, start_target)
    if start is None:
        return None
    days = (_parse(end["date"]) - _parse(start["date"])).days
    if days < 1:
        return None
    ret = period_return(float(start["share_price"]), float(end["share_price"]))
    apy = annualize(ret, float(days))
    if apy is None:
        return None
    return {
        "start_date": start["date"],
        "end_date": end["date"],
        "days": float(days),
        "hold_return_pct": round(ret * 100, 6),
        "hold_apy_pct": round(apy * 100, 6),
    }


def build_official_ui_history_compare(
    *,
    official_history: dict[str, Any],
    share_series: list[dict[str, Any]],
    hold_windows: list[int] | None = None,
    official_algo: dict[str, Any] | None = None,
    recent_days: int = 30,
) -> dict[str, Any]:
    """Join Official UI history with trailing Hold APYs on overlapping dates."""
    hold_windows = hold_windows or [1, 7, 30]
    ui_rows = official_history.get("series") or []
    share_dates = {r["date"] for r in share_series}

    joined: list[dict[str, Any]] = []
    for ui in ui_rows:
        date = ui["date"]
        if date not in share_dates and date < (share_series[0]["date"] if share_series else ""):
            # still keep UI-only history; hold fields null
            row = {
                "date": date,
                "official_ui_apy_pct": ui["official_ui_apy_pct"],
                "tvl_usd": ui.get("tvl_usd"),
            }
            for n in hold_windows:
                row[f"hold_{n}d_apy_pct"] = None
                row[f"delta_hold_{n}d_vs_ui_pp"] = None
            joined.append(row)
            continue

        row: dict[str, Any] = {
            "date": date,
            "official_ui_apy_pct": ui["official_ui_apy_pct"],
            "tvl_usd": ui.get("tvl_usd"),
        }
        for n in hold_windows:
            h = hold_apy_asof(share_series, asof_date=date, window_days=n)
            if h is None:
                row[f"hold_{n}d_apy_pct"] = None
                row[f"delta_hold_{n}d_vs_ui_pp"] = None
            else:
                row[f"hold_{n}d_apy_pct"] = h["hold_apy_pct"]
                row[f"delta_hold_{n}d_vs_ui_pp"] = round(
                    h["hold_apy_pct"] - ui["official_ui_apy_pct"], 6
                )
        joined.append(row)

    overlap = [r for r in joined if r.get("hold_1d_apy_pct") is not None]
    recent = overlap[-recent_days:] if overlap else []

    def _stats(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        return {
            "n": len(values),
            "min": round(min(values), 6),
            "median": round(float(median(values)), 6),
            "max": round(max(values), 6),
            "mean": round(sum(values) / len(values), 6),
        }

    summary: dict[str, Any] = {
        "ui_all": _stats([r["official_ui_apy_pct"] for r in joined]),
        "ui_overlap": _stats([r["official_ui_apy_pct"] for r in overlap]),
        "recent_days": recent_days,
    }
    for n in hold_windows:
        key = f"hold_{n}d"
        deltas = [
            r[f"delta_hold_{n}d_vs_ui_pp"]
            for r in overlap
            if r.get(f"delta_hold_{n}d_vs_ui_pp") is not None
        ]
        recent_deltas = [
            r[f"delta_hold_{n}d_vs_ui_pp"]
            for r in recent
            if r.get(f"delta_hold_{n}d_vs_ui_pp") is not None
        ]
        summary[f"{key}_vs_ui_delta_pp_all"] = _stats(deltas)
        summary[f"{key}_vs_ui_delta_pp_recent"] = _stats(recent_deltas)

    latest = overlap[-1] if overlap else (joined[-1] if joined else None)
    latest_block: dict[str, Any] | None = None
    if latest is not None:
        latest_block = dict(latest)
        if official_algo is not None:
            latest_block["official_algo_net_apy_pct"] = official_algo.get("net_apy_pct")
            latest_block["official_algo_gross_apy_pct"] = official_algo.get("gross_apy_pct")
            latest_block["official_algo_delta_vs_ui_pp"] = (
                None
                if official_algo.get("net_apy_pct") is None
                else round(
                    float(official_algo["net_apy_pct"]) - float(latest["official_ui_apy_pct"]),
                    6,
                )
            )

    # Markdown recent table
    headers = (
        ["date", "official_ui", "hold_1d", "Δ1d", "hold_7d", "Δ7d", "hold_30d", "Δ30d"]
    )
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["------"] * len(headers)) + "|",
    ]

    def f(x: float | None) -> str:
        return "—" if x is None else f"{x:.2f}%"

    def fd(x: float | None) -> str:
        return "—" if x is None else f"{x:+.2f}pp"

    for r in recent:
        lines.append(
            "| {date} | {ui} | {h1} | {d1} | {h7} | {d7} | {h30} | {d30} |".format(
                date=r["date"],
                ui=f(r.get("official_ui_apy_pct")),
                h1=f(r.get("hold_1d_apy_pct")),
                d1=fd(r.get("delta_hold_1d_vs_ui_pp")),
                h7=f(r.get("hold_7d_apy_pct")),
                d7=fd(r.get("delta_hold_7d_vs_ui_pp")),
                h30=f(r.get("hold_30d_apy_pct")),
                d30=fd(r.get("delta_hold_30d_vs_ui_pp")),
            )
        )

    return {
        "definition": {
            "official_ui": (
                "DefiLlama daily series of Instadapp apy.apyWithoutFee (UI Net APY)"
            ),
            "hold": "Our trailing compound Hold APY from share-price CSV, as-of each date",
            "official_algo": (
                "Live reconstruction of Instadapp forward Net (rates×positions); "
                "only attached on the latest row — not historically available"
            ),
            "hold_windows": hold_windows,
        },
        "source": {
            "defillama_pool_id": official_history.get("pool_id"),
            "defillama_url": official_history.get("source_url"),
            "defillama_page": official_history.get("pool_page"),
            "fetched_at_utc": official_history.get("fetched_at_utc"),
            "ui_points": official_history.get("points"),
            "ui_first_date": official_history.get("first_date"),
            "ui_last_date": official_history.get("last_date"),
            "share_first_date": share_series[0]["date"] if share_series else None,
            "share_last_date": share_series[-1]["date"] if share_series else None,
            "overlap_points": len(overlap),
        },
        "summary": summary,
        "latest": latest_block,
        "recent_rows": recent,
        "markdown_recent_table": "\n".join(lines) + "\n",
        "joined_series": joined,
    }
