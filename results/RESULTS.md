# Historical yield results (one-shot)

Share-price snapshot: **2026-07-15 UTC** (tip block `25539401`).  
Windows include **14d** (Lido UI) and **7d** (Mellow weekly API).  
No automatic refresh — full re-fetch only on explicit request.

Vaults are **independent**; `since_earneth` is a shared **calendar** window only (not a ranking).

## Official APY comparison (summary)

Full detail: [`OFFICIAL_COMPARISON.md`](./OFFICIAL_COMPARISON.md)

### Lido EarnETH

| Source | Window | APY |
|--------|--------|-----|
| Lido UI label | **14d** avg. | (label only; value from API/UI live) |
| Mellow API | **7d** (`time_range=604800`) | **3.87%** |
| Ours | 7d hold | **3.92%** (Δ +0.05pp) |
| Ours | 14d hold | **3.84%** (Δ −0.03pp vs API) |

UI says 14d; backend/config is weekly (7d) — **both windows kept**.

### Fluid Lite ETH

| Source | Window | APY |
|--------|--------|-----|
| Official Net (`apyWithoutFee`) | **spot / projected** (not trailing) | **5.84%** |
| Official Gross (`apyWithFee`) | spot | **7.30%** |
| Ours trailing hold | 7d / 14d / 30d | 3.19% / 2.93% / 3.07% |

Official Net ≈ Gross × 0.8 (20% perf fee). **No matching trailing window on the official UI** — nothing extra to add beyond documenting the methodology gap.

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
| **14d** | **2.93%** | **1.60%** |
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
| **7d** (Mellow weekly) | **3.92%** |
| **14d** (Lido UI label) | **3.84%** |
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
- `results/official_comparison.json`
- `results/OFFICIAL_COMPARISON.md`
