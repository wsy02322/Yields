#!/usr/bin/env python3
"""Independently audit trailing APY for the Fluid Lite ETH vault.

The audit reads only Ethereum chain state. It does not call Fluid, Instadapp,
or DefiLlama APY endpoints and it does not apply a withdrawal fee.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, localcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import load_w3  # noqa: E402
from src.fetchers.fluid_lite import assets_per_share  # noqa: E402

WINDOWS_DAYS = (1, 7, 14, 30, 90, 120, 180)
SECONDS_PER_DAY = 86_400
DAYS_PER_YEAR = 365.25


def latest_complete_utc_day_end(tip_timestamp: int) -> int:
    """Return the latest 23:59:59 UTC timestamp fully covered by the chain tip."""
    return (tip_timestamp // SECONDS_PER_DAY) * SECONDS_PER_DAY - 1


def block_at_or_before(
    get_block: Callable[[int], Any],
    *,
    target_timestamp: int,
    low_block: int,
    high_block: int,
) -> tuple[int, int]:
    """Find the highest block whose timestamp is at or before the target."""
    if low_block < 0 or high_block < low_block:
        raise ValueError("invalid block search bounds")

    low_ts = int(get_block(low_block)["timestamp"])
    high_ts = int(get_block(high_block)["timestamp"])
    if target_timestamp < low_ts:
        raise ValueError("target timestamp predates the low block")
    if target_timestamp >= high_ts:
        return high_block, high_ts

    lo, hi = low_block, high_block
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        mid_ts = int(get_block(mid)["timestamp"])
        if mid_ts <= target_timestamp:
            lo = mid
        else:
            hi = mid

    block_timestamp = int(get_block(lo)["timestamp"])
    return lo, block_timestamp


def compound_apy(
    start_assets: int, end_assets: int, elapsed_seconds: int
) -> tuple[float, float]:
    """Return total return and compound APY from exact integer share values."""
    if start_assets <= 0 or end_assets <= 0:
        raise ValueError("share values must be positive")
    if elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive")
    with localcontext() as context:
        context.prec = 50
        ratio = Decimal(end_assets) / Decimal(start_assets)
        total_return = ratio - Decimal(1)
        exponent = (
            Decimal(str(DAYS_PER_YEAR))
            * Decimal(SECONDS_PER_DAY)
            / Decimal(elapsed_seconds)
        )
        apy = (ratio.ln() * exponent).exp() - Decimal(1)
    return float(total_return), float(apy)


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _observation(
    w3: Any,
    contract: str,
    get_block: Callable[[int], Any],
    *,
    target_timestamp: int,
    low_block: int,
    high_block: int,
) -> dict[str, Any]:
    block, timestamp = block_at_or_before(
        get_block,
        target_timestamp=target_timestamp,
        low_block=low_block,
        high_block=high_block,
    )
    if block >= high_block:
        raise ValueError("target boundary is not finalized below the search tip")
    next_block = block + 1
    next_timestamp = int(get_block(next_block)["timestamp"])
    if next_timestamp <= target_timestamp:
        raise RuntimeError("block boundary search did not find the highest valid block")
    value = assets_per_share(w3, contract, block)
    return {
        "target_timestamp": target_timestamp,
        "target_time_utc": _iso(target_timestamp),
        "block": block,
        "block_timestamp": timestamp,
        "block_time_utc": _iso(timestamp),
        "seconds_before_target": target_timestamp - timestamp,
        "next_block": next_block,
        "next_block_timestamp": next_timestamp,
        "next_block_time_utc": _iso(next_timestamp),
        "next_block_seconds_after_target": next_timestamp - target_timestamp,
        "assets_per_1e18_shares_wei": str(value),
        "assets_per_share": value / 1e18,
    }


def audit(
    w3: Any,
    *,
    contract: str,
    deployment_block: int,
    windows_days: tuple[int, ...] = WINDOWS_DAYS,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Read exact on-chain boundary observations and calculate trailing APYs."""
    tip = w3.eth.get_block("latest")
    tip_block = int(tip["number"])
    tip_timestamp = int(tip["timestamp"])
    end_target = latest_complete_utc_day_end(tip_timestamp)
    if end_target <= int(w3.eth.get_block(deployment_block)["timestamp"]):
        raise ValueError("vault has no complete UTC day available")

    get_block = w3.eth.get_block
    end = _observation(
        w3,
        contract,
        get_block,
        target_timestamp=end_target,
        low_block=deployment_block,
        high_block=tip_block,
    )
    end_assets = int(end["assets_per_1e18_shares_wei"])

    windows: list[dict[str, Any]] = []
    for days in windows_days:
        start_target = end_target - days * SECONDS_PER_DAY
        start = _observation(
            w3,
            contract,
            get_block,
            target_timestamp=start_target,
            low_block=deployment_block,
            high_block=end["block"],
        )
        start_assets = int(start["assets_per_1e18_shares_wei"])
        elapsed_seconds = end["block_timestamp"] - start["block_timestamp"]
        total_return, apy = compound_apy(start_assets, end_assets, elapsed_seconds)
        windows.append(
            {
                "window_days": days,
                "start": start,
                "end": end,
                "actual_elapsed_seconds": elapsed_seconds,
                "actual_elapsed_days": round(elapsed_seconds / SECONDS_PER_DAY, 9),
                "total_return_pct": round(total_return * 100, 8),
                "apy_pct": round(apy * 100, 8),
            }
        )

    generated_at = generated_at or datetime.now(tz=timezone.utc)
    return {
        "schema_version": 1,
        "audit_scope": {
            "name": "Fluid Lite ETH Vault",
            "chain": "ethereum",
            "chain_id": int(w3.eth.chain_id),
            "contract": contract,
            "measurement": "trailing on-chain receipt-token exchange-rate return",
            "share_amount": "1000000000000000000",
            "windows_days": list(windows_days),
            "exit_fee_applied": 0,
            "published_apy_sources_used": [],
        },
        "as_of": {
            "generated_at_utc": generated_at.isoformat(),
            "rpc_tip_block": tip_block,
            "rpc_tip_timestamp": tip_timestamp,
            "rpc_tip_time_utc": _iso(tip_timestamp),
            "latest_complete_day_utc": datetime.fromtimestamp(
                end_target, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
        },
        "methodology": {
            "data_source": (
                "Ethereum archive RPC eth_getBlockByNumber + eth_call "
                "convertToAssets(1e18)"
            ),
            "boundary_rule": (
                "For each UTC day-end target, use the last Ethereum block whose "
                "timestamp is <= the target, located by binary search."
            ),
            "return_formula": "R = end_assets_per_share / start_assets_per_share - 1",
            "apy_formula": (
                "APY = (1 + R)^(365.25 / actual_elapsed_days) - 1"
            ),
            "fee_treatment": (
                "No exit fee. Ongoing vault accounting effects already reflected "
                "in convertToAssets."
            ),
            "limitation": (
                "This independently recomputes return from the on-chain receipt-token "
                "exchange rate; it is not a position-by-position valuation or solvency "
                "audit of the vault's underlying assets and liabilities."
            ),
        },
        "windows": windows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    scope = report["audit_scope"]
    as_of = report["as_of"]
    lines = [
        "# Fluid Lite ETH 独立 APY 审计",
        "",
        f"- 合约：`{scope['contract']}`（Ethereum）",
        f"- 截至：`{as_of['latest_complete_day_utc']} 23:59:59 UTC`",
        "- 数据：以太坊归档 RPC 的区块头与 `convertToAssets(1e18)` 链上读取",
        "- 排除：Fluid / Instadapp / DefiLlama 发布的 APY；退出费用按 0 处理",
        "- 边界：审计链上份额兑换率收益，不是底层仓位逐项估值或偿付能力审计",
        "",
        "| 窗口 | 起始日 | 结束日 | 区间收益率 | APY |",
        "|---:|---|---|---:|---:|",
    ]
    for row in report["windows"]:
        lines.append(
            "| {days} 天 | {start} | {end} | {ret:.6f}% | **{apy:.6f}%** |".format(
                days=row["window_days"],
                start=row["start"]["target_time_utc"][:10],
                end=row["end"]["target_time_utc"][:10],
                ret=row["total_return_pct"],
                apy=row["apy_pct"],
            )
        )
    lines += [
        "",
        "## 计算口径",
        "",
        "`R = 期末每份资产 / 期初每份资产 - 1`",
        "",
        "`APY = (1 + R)^(365.25 / 实际经过天数) - 1`",
        "",
        "每个边界均通过二分查找定位目标 UTC 日末之前的最后一个区块；"
        "JSON 结果保留目标时间、实际区块、区块时间和精确 wei 值以供复核。",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rpc-url", help="Ethereum archive RPC; defaults to config")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "results" / "fluid-lite-eth-independent-audit.json",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=ROOT / "results" / "FLUID_LITE_ETH_INDEPENDENT_AUDIT.md",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = yaml.safe_load((ROOT / "config" / "vaults.yaml").read_text())
    vault = cfg["vaults"]["fluid_lite_eth"]
    rpc_url = args.rpc_url or cfg["rpc"]["url"]
    w3 = load_w3(rpc_url, cfg["rpc"].get("timeout_seconds", 45))

    report = audit(
        w3,
        contract=vault["receipt_token"],
        deployment_block=int(vault["deployment_block"]),
    )
    markdown = render_markdown(report)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown_output.write_text(markdown)
    print(markdown)
    print(f"\nJSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
