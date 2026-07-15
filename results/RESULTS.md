# Historical yield results (one-shot)

Generated: **2026-07-15 UTC** (tip block `25539401`).  
No automatic refresh — re-run only on explicit request.

Vaults are **independent**; no comparison metrics.

## Fluid Lite ETH (`iETHv2`)

- Series: **881** daily points (`2024-02-16` → `2026-07-15`)
- Share price: `1.07155` → `1.21426` stETH per share
- Fees in main APY: **20% performance** (in share price) + **0.05% exit** (realized only)

| Window | Hold APY | Realized APY (w/ 0.05% exit) | Hold return | Realized return |
|--------|----------|------------------------------|-------------|-----------------|
| 7d | 3.19% | 0.53%* | +0.060% | +0.010% |
| 30d | 3.07% | 2.45% | +0.249% | +0.199% |
| 90d | 2.62% | 2.41% | +0.639% | +0.589% |
| inception (880d) | **5.33%** | **5.30%** | +13.32% | +13.26% |

\*Short windows: a one-time 0.05% exit haircut is large vs period return, so **annualized realized APY is distorted downward**. Prefer **hold APY** for short mark-to-market windows; use **realized** for full deposit→withdraw scenarios (especially inception).

### vs official UI Net APY (forward-looking)

| Metric | APY | Δ vs official Net (~5.84%) |
|--------|-----|------------------------------|
| Official Net (`apyWithoutFee`) | **5.84%** | — |
| **EWMA Net proxy** (365d half-life on daily share price) | **6.26%** | +0.42pp |
| Inception hold | 5.33% | −0.51pp |

See `official_apy_comparison` in `data/fluid-lite-eth/summary.json` and [docs/fluid-lite-net-apy.md](../docs/fluid-lite-net-apy.md).

## Lido EarnETH

- Series: **164** daily points (`2026-02-02` → `2026-07-15`)
- Share price: `1.00000` → `1.01191` ETH per share
- Fees in main APY: **1% protocol + 10% performance** (already in share price)
- On-chain: `depositFeeD6=0`, `redeemFeeD6=0` → realized = hold

| Window | Hold / Realized APY | Return |
|--------|---------------------|--------|
| 7d | 3.92% | +0.074% |
| 30d | 3.93% | +0.317% |
| 90d | 2.68% | +0.655% |
| inception (163d) | **2.69%** | +1.19% |

### Off-chain rewards (excluded from APY)

| Reward | Treatment |
|--------|-----------|
| Mellow Points | Listed only; not in share price |
| Obol rewards | Listed only; claim separately |
| SSV rewards | Listed only; claim separately |

## Files

- `data/fluid-lite-eth/daily_share_price.csv`
- `data/fluid-lite-eth/summary.json`
- `data/lido-earn-eth/daily_share_price.csv`
- `data/lido-earn-eth/summary.json`
- `results/summary.json`
