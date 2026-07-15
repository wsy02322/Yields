# Historical yield results (one-shot)

Share-price snapshot: **2026-07-15 UTC** (tip block `25539401`).  
Summaries recomputed with shared window `since_earneth`.  
No automatic refresh — full re-fetch only on explicit request.

Vaults are **independent**; `since_earneth` is a shared **calendar** window only (not a ranking).

## Shared window: `since_earneth`

| | |
|--|--|
| Start | **2026-02-02** (Lido EarnETH deployment) |
| End | **2026-07-15** (latest snapshot) |
| Days | **163** |

| Vault | Hold APY | Realized APY | Hold return | Realized return |
|-------|----------|--------------|-------------|-----------------|
| Fluid Lite ETH | **2.47%** | **2.36%** | +1.10% | +1.05% |
| Lido EarnETH | **2.69%** | **2.69%** | +1.19% | +1.19% |

## Fluid Lite ETH (`iETHv2`)

- Series: **881** daily points (`2024-02-16` → `2026-07-15`)
- Share price: `1.07155` → `1.21426` stETH per share
- Fees in main APY: **20% performance** (in share price) + **0.05% exit** (realized only)

| Window | Hold APY | Realized APY (w/ 0.05% exit) |
|--------|----------|------------------------------|
| 7d | 3.19% | 0.53%* |
| 30d | 3.07% | 2.45% |
| 90d | 2.62% | 2.41% |
| **since_earneth** (163d) | **2.47%** | **2.36%** |
| inception (880d) | **5.33%** | **5.30%** |

\*Short windows: one-time exit fee dominates period return when annualized.

## Lido EarnETH

- Series: **164** daily points (`2026-02-02` → `2026-07-15`)
- Share price: `1.00000` → `1.01191` ETH per share
- Fees in main APY: **1% protocol + 10% performance** (already in share price)
- On-chain: `depositFeeD6=0`, `redeemFeeD6=0` → realized = hold
- For EarnETH, `since_earneth` ≡ `inception`

| Window | Hold / Realized APY |
|--------|---------------------|
| 7d | 3.92% |
| 30d | 3.93% |
| 90d | 2.68% |
| **since_earneth** (163d) | **2.69%** |
| inception (163d) | **2.69%** |

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
