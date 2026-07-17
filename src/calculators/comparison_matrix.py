"""Side-by-side APY comparison matrix for Fluid Lite + Lido EarnETH.

Rows (windows) and which columns are filled follow the product matrix:

| window              | Fluid Hold | Fluid Official-algo | Fluid Official UI | Lido Hold | Lido Official UI |
|---------------------|------------|---------------------|-------------------|-----------|------------------|
| 1d                  | yes        | yes (reconstructed) | yes (Net APY)     | —         | —                |
| 7d                  | yes        | —                   | —                 | yes       | —                |
| 14d                 | yes        | —                   | —                 | yes       | yes (14d avg)    |
| 30d                 | yes        | —                   | —                 | yes       | —                |
| 90d                 | yes        | —                   | —                 | yes       | —                |
| Lido earn inception | yes*       | —                   | —                 | yes       | —                |
| 360d                | yes        | —                   | —                 | —         | —                |
| Fluid lite inception| yes        | —                   | —                 | —         | —                |

* Fluid Hold APY over the same calendar span as EarnETH inception.

``Fluid Official-algo`` = our reconstruction of Instadapp's forward Net APY
from live rates × positions (see ``fluid_lite_official_algo.py``).
"""

from __future__ import annotations

from typing import Any

from src.calculators.apy import compute_window, window_to_dict

# Default trailing day windows used for both vault summaries.
COMPARISON_WINDOWS_DAYS = [1, 7, 14, 30, 90, 360]


def _hold_apy_pct(summary: dict[str, Any], window: str) -> float | None:
    for w in summary.get("windows") or []:
        if w.get("window") == window:
            return w.get("hold_apy_pct")
    return None


def _window_meta(summary: dict[str, Any], window: str) -> dict[str, Any] | None:
    for w in summary.get("windows") or []:
        if w.get("window") == window:
            return {
                "start_date": w.get("start_date"),
                "end_date": w.get("end_date"),
                "days": w.get("days"),
                "hold_return_pct": w.get("hold_return_pct"),
            }
    return None


def build_comparison_matrix(
    *,
    fluid_summary: dict[str, Any],
    earn_summary: dict[str, Any],
    fluid_series: list[dict[str, Any]],
    fluid_exit_fee: float,
    fluid_official_net_apy_pct: float | None,
    lido_official_apy_pct: float | None,
    fluid_official_algo_net_apy_pct: float | None = None,
    fluid_official_meta: dict[str, Any] | None = None,
    lido_official_meta: dict[str, Any] | None = None,
    fluid_official_algo_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the fixed comparison matrix payload + markdown-friendly rows."""

    # Fluid Hold APY over EarnETH inception span (same start/end dates).
    earn_incep = next(
        (w for w in (earn_summary.get("windows") or []) if w.get("window") == "inception"),
        None,
    )
    fluid_over_earn_incep: dict[str, Any] | None = None
    if earn_incep is not None:
        w = compute_window(
            fluid_series,
            label="lido_earn_inception",
            start_date=earn_incep["start_date"],
            end_date=earn_incep["end_date"],
            exit_fee=fluid_exit_fee,
        )
        if w is not None:
            fluid_over_earn_incep = window_to_dict(w)

    def row(
        window: str,
        *,
        fluid: float | None = None,
        fluid_official_algo: float | None = None,
        fluid_official: float | None = None,
        lido: float | None = None,
        lido_official: float | None = None,
        notes: str | None = None,
        fluid_meta: dict[str, Any] | None = None,
        lido_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "window": window,
            "fluid_lite_hold_apy_pct": fluid,
            "fluid_official_algo_net_apy_pct": fluid_official_algo,
            "fluid_official_ui_apy_pct": fluid_official,
            "lido_hold_apy_pct": lido,
            "lido_official_ui_apy_pct": lido_official,
            "fluid_meta": fluid_meta,
            "lido_meta": lido_meta,
            "notes": notes,
        }

    rows: list[dict[str, Any]] = [
        row(
            "1d",
            fluid=_hold_apy_pct(fluid_summary, "1d"),
            fluid_official_algo=fluid_official_algo_net_apy_pct,
            fluid_official=fluid_official_net_apy_pct,
            fluid_meta=_window_meta(fluid_summary, "1d"),
            notes=(
                "Fluid Hold = completed 1d trailing share-price APY. "
                "Fluid Official-algo = our reconstruction of Instadapp forward "
                "Net from rates×positions. "
                "Fluid Official UI = live API Net APY."
            ),
        ),
        row(
            "7d",
            fluid=_hold_apy_pct(fluid_summary, "7d"),
            lido=_hold_apy_pct(earn_summary, "7d"),
            fluid_meta=_window_meta(fluid_summary, "7d"),
            lido_meta=_window_meta(earn_summary, "7d"),
        ),
        row(
            "14d",
            fluid=_hold_apy_pct(fluid_summary, "14d"),
            lido=_hold_apy_pct(earn_summary, "14d"),
            lido_official=lido_official_apy_pct,
            fluid_meta=_window_meta(fluid_summary, "14d"),
            lido_meta=_window_meta(earn_summary, "14d"),
            notes=(
                "Lido Official UI = Mellow time-weighted APY* (14d avg.). "
                "Lido our = trailing 14d Hold APY from share price."
            ),
        ),
        row(
            "30d",
            fluid=_hold_apy_pct(fluid_summary, "30d"),
            lido=_hold_apy_pct(earn_summary, "30d"),
            fluid_meta=_window_meta(fluid_summary, "30d"),
            lido_meta=_window_meta(earn_summary, "30d"),
        ),
        row(
            "90d",
            fluid=_hold_apy_pct(fluid_summary, "90d"),
            lido=_hold_apy_pct(earn_summary, "90d"),
            fluid_meta=_window_meta(fluid_summary, "90d"),
            lido_meta=_window_meta(earn_summary, "90d"),
        ),
        row(
            "lido_earn_inception",
            fluid=(
                None
                if fluid_over_earn_incep is None
                else fluid_over_earn_incep.get("hold_apy_pct")
            ),
            lido=_hold_apy_pct(earn_summary, "inception"),
            fluid_meta=(
                None
                if fluid_over_earn_incep is None
                else {
                    "start_date": fluid_over_earn_incep.get("start_date"),
                    "end_date": fluid_over_earn_incep.get("end_date"),
                    "days": fluid_over_earn_incep.get("days"),
                    "hold_return_pct": fluid_over_earn_incep.get("hold_return_pct"),
                }
            ),
            lido_meta=_window_meta(earn_summary, "inception"),
            notes="Fluid Hold APY over EarnETH inception calendar span.",
        ),
        row(
            "360d",
            fluid=_hold_apy_pct(fluid_summary, "360d"),
            fluid_meta=_window_meta(fluid_summary, "360d"),
        ),
        row(
            "fluid_lite_inception",
            fluid=_hold_apy_pct(fluid_summary, "inception"),
            fluid_meta=_window_meta(fluid_summary, "inception"),
        ),
    ]

    def fmt(x: float | None) -> str:
        return "—" if x is None else f"{x:.2f}%"

    markdown_lines = [
        "| Window | Fluid Hold (our) | Fluid Official-algo (our) | Fluid Official UI | Lido Hold (our) | Lido Official UI |",
        "|--------|------------------|---------------------------|-------------------|-----------------|------------------|",
    ]
    label = {
        "1d": "1d",
        "7d": "7d",
        "14d": "14d",
        "30d": "30d",
        "90d": "90d",
        "lido_earn_inception": "Lido Earn inception",
        "360d": "360d",
        "fluid_lite_inception": "Fluid Lite inception",
    }
    for r in rows:
        markdown_lines.append(
            f"| {label[r['window']]} | {fmt(r['fluid_lite_hold_apy_pct'])} | "
            f"{fmt(r['fluid_official_algo_net_apy_pct'])} | "
            f"{fmt(r['fluid_official_ui_apy_pct'])} | {fmt(r['lido_hold_apy_pct'])} | "
            f"{fmt(r['lido_official_ui_apy_pct'])} |"
        )

    return {
        "definition": {
            "columns": [
                "window",
                "fluid_lite_hold_apy_pct",
                "fluid_official_algo_net_apy_pct",
                "fluid_official_ui_apy_pct",
                "lido_hold_apy_pct",
                "lido_official_ui_apy_pct",
            ],
            "our_hold_apy": "compound Hold APY = (1+R)^(365.25/days)−1; no exit fee in Hold",
            "fluid_official_algo": (
                "Reconstructed Instadapp forward Net: "
                "(Σ protocol supply×apy − borrow×apy + idle×stETH APR)/TVL × (1−20%)"
            ),
            "fluid_official_ui": "Instadapp Lite Net APY from API (forward; 1d row only)",
            "lido_official_ui": "Mellow timeweighted-apy (UI APY* 14d avg.; 14d row only)",
            "windows_days": COMPARISON_WINDOWS_DAYS,
        },
        "official": {
            "fluid": {
                "net_apy_pct": fluid_official_net_apy_pct,
                **(fluid_official_meta or {}),
            },
            "fluid_official_algo": {
                "net_apy_pct": fluid_official_algo_net_apy_pct,
                **(fluid_official_algo_meta or {}),
            },
            "lido": {
                "apy_pct": lido_official_apy_pct,
                **(lido_official_meta or {}),
            },
        },
        "rows": rows,
        "markdown_table": "\n".join(markdown_lines) + "\n",
    }
