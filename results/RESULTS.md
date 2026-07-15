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

### Closest historical proxy vs official Net APY

Official UI Net APY is forward-looking (rates × positions). Among trailing Hold algorithms on this series, the closest fee-aligned proxy is:

```
inception_hold_simple:  R = share_price_T / share_price_0 − 1
                        APY = R × (365.25 / days)     # no exit fee
```

| | APY | Notes |
|--|-----|-------|
| Official **Net** (`apyWithoutFee`) | **5.84%** | Live API / UI |
| Official **Gross** (`apyWithFee`) | 7.30% | Live API / UI |
| **`inception_hold_simple`** (proxy) | **5.53%** | Δ ≈ **−0.31 pp** vs Net |
| Inception Hold compound (repo default) | 5.33% | Δ ≈ −0.51 pp vs Net |
| 7d / 30d / 90d Hold | 3.19% / 3.07% / 2.62% | Far from spot Net |

Detail: `results/fluid-lite-official-apy-proxy.json` · `docs/fluid-lite-net-apy.md`

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
- `data/fluid-lite-eth/official_apy_proxy_comparison.json`
- `data/lido-earn-eth/daily_share_price.csv`
- `data/lido-earn-eth/summary.json`
- `results/summary.json`
- `results/fluid-lite-official-apy-proxy.json`
