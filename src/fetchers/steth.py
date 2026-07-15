"""Lido stETH share-rate fetcher — ETH-per-share for intrinsic (stETH→ETH) yield."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from web3 import Web3

from src import eth_call, progress, retry_call

LIDO_STETH = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
WSTETH = "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"


def share_rate_at_block(w3: Web3, block: int | str = "latest") -> float:
    """ETH per stETH-share = getTotalPooledEther / getTotalShares (== wstETH.stEthPerToken)."""
    (pooled,) = eth_call(w3, LIDO_STETH, "getTotalPooledEther()", [], [], ["uint256"], block=block)
    (shares,) = eth_call(w3, LIDO_STETH, "getTotalShares()", [], [], ["uint256"], block=block)
    if int(shares) <= 0:
        raise ValueError("Lido totalShares is zero")
    return int(pooled) / int(shares)


def fetch_share_rate_for_rows(
    w3: Web3,
    rows: list[dict[str, Any]],
    *,
    max_workers: int = 6,
) -> list[dict[str, Any]]:
    """Fetch Lido share rate at each row's block (reuse vault daily sampling blocks)."""
    if not rows:
        return []

    progress(f"stETH share-rate: scheduling {len(rows)} snapshots")

    def one(row: dict[str, Any]) -> dict[str, Any]:
        block = int(row["block"])

        def _run():
            rate = share_rate_at_block(w3, block)
            return {
                "date": row["date"],
                "block": block,
                "share_rate": rate,  # ETH per stETH share
                "share_price": rate,  # alias so APY helpers can reuse share_price field
            }

        return retry_call(_run)

    out: list[dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(one, r) for r in rows]
        for fut in as_completed(futs):
            out.append(fut.result())
            done += 1
            if done % 50 == 0 or done == len(rows):
                progress(f"stETH share-rate: {done}/{len(rows)}")

    out.sort(key=lambda r: r["date"])
    return out
