# Historical yield results (one-shot)

Generated: **2026-07-15 UTC** (tip block `25539401`).  
**Denomination: ETH** for both vaults.  
Exit-fee APY: default **1-year hold** amortization.  
No automatic refresh — re-run only on explicit request.

Vaults are **independent**; no comparison metrics.

## Fluid Lite ETH (`iETHv2`)

- Series: **881** daily points (`2024-02-16` → `2026-07-15`)
- Vault share price: `1.07155` → `1.21426` **stETH / share** (strategy / Base)
- stETH→ETH intrinsic: Lido share-rate (`getTotalPooledEther / getTotalShares`)
- Primary APY (ETH):

```
ETH_APY = (1 + vault_stETH_APY) × (1 + stETH→ETH_APY) − 1
```

- Fees: **20% performance** (in vault share price) + **0.05% exit** (realized; ≈ −0.05 pp on 1y hold)

| Window | ETH Hold APY | Vault (stETH) | stETH→ETH | ETH Realized | ETH Hold return |
|--------|--------------|---------------|-----------|--------------|-----------------|
| 7d | **5.49%** | 3.19% | 2.23% | 5.44% | +0.103% |
| 30d | **5.46%** | 3.07% | 2.32% | 5.41% | +0.438% |
| 90d | **5.14%** | 2.62% | 2.46% | 5.09% | +1.239% |
| inception (880d) | **8.37%** | 5.33% | 2.89% | 8.31% | +16.59% |

This matches vaults.fyi’s Base × Intrinsic → Total structure (their 7d Total ~6.26% uses a higher Base from hourly/TVL-weighted sampling; Intrinsic ~2.23% aligns).

## Lido EarnETH

- Series: **164** daily points (`2026-02-02` → `2026-07-15`)
- Share price: `1.00000` → `1.01191` **ETH / share** (already ETH — no extra intrinsic layer)
- Fees: **1% protocol + 10% performance** (in share price); redeem fee 0

| Window | ETH Hold / Realized APY | Return |
|--------|-------------------------|--------|
| 7d | **3.92%** | +0.074% |
| 30d | **3.93%** | +0.317% |
| 90d | **2.68%** | +0.655% |
| inception (163d) | **2.69%** | +1.19% |

### Off-chain rewards (excluded from APY)

| Reward | Treatment |
|--------|-----------|
| Mellow Points | Listed only; not in share price |
| Obol rewards | Listed only; claim separately |
| SSV rewards | Listed only; claim separately |

## Files

- `data/fluid-lite-eth/daily_share_price.csv`
- `data/fluid-lite-eth/daily_steth_share_rate.csv`
- `data/fluid-lite-eth/summary.json`
- `data/lido-earn-eth/daily_share_price.csv`
- `data/lido-earn-eth/summary.json`
- `results/summary.json`
