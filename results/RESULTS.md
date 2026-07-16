# Historical yield results (one-shot)

Generated: **2026-07-16 UTC** (tip block `25543295`).  
No automatic refresh — re-run only on explicit request.

Vaults are **independent**; no comparison metrics.

**APY definition:** compound `(1+R)^(365.25/days)−1` (standard).  
**APR (comparison proxy only):** simple `R×(365.25/days)` — not APY.

## Fluid Lite ETH (`iETHv2`)

- Series: **882** daily points (`2024-02-16` → `2026-07-16`)
- Share price: `1.07155` → `1.21442` stETH per share (matches live API `exchangePriceiETHV2`)
- Fees in main APY: **20% performance** (in share price) + **0.05% exit** (realized only)

| Window | Hold APY | Realized APY (w/ 0.05% exit) | Hold return | Realized return | Preferred |
|--------|----------|------------------------------|-------------|-----------------|-----------|
| 7d | **3.46%** | 0.79%* | +0.065% | +0.015% | hold_apy |
| 30d | **3.18%** | 2.56%* | +0.258% | +0.207% | hold_apy |
| 90d | 2.58% | 2.38% | +0.630% | +0.580% | hold_or_realized |
| inception (881d) | **5.33%** | **5.30%** | +13.33% | +13.28% | hold_or_realized |

\*Short windows (≤30d): a one-time 0.05% exit haircut is large vs period return, so **annualized realized APY is distorted downward** (`realized_apy_caution=true`). Prefer **hold APY** for short mark-to-market windows; use **realized** for full deposit→withdraw scenarios (especially inception).

### Latest official UI Net APY vs historical proxies

Official UI Net APY is forward-looking (rates × positions). Live Instadapp API (**2026-07-16**):

| | Rate | Notes |
|--|------|-------|
| Official **Net** (`apyWithoutFee`) | **5.8204% APY** | Live API / UI (forward) |
| Official **Gross** (`apyWithFee`) | **7.2756% APY** | Live API / UI |
| **`inception_hold_apr`** (proxy) | **5.5277% APR** | Δ ≈ **−0.293 pp** vs Net |
| Inception Hold compound (repo default APY) | **5.3260% APY** | Δ ≈ −0.494 pp vs Net |
| 7d / 30d / 90d Hold APY | 3.46% / 3.18% / 2.58% | Far from spot Net |

```
inception_hold_apr:  R = share_price_T / share_price_0 − 1
                     APR = R × (365.25 / days)     # no exit fee; NOT APY
```

Top historical candidates by |Δ| vs official Net:

| Rank | Metric | Rate | Δ vs Net |
|------|--------|------|----------|
| 1 | inception_hold_apr | 5.53% APR | −0.29 pp |
| 2 | inception_hold_apy | 5.33% APY | −0.49 pp |
| 3 | 365d_hold_apy | 3.60% APY | −2.22 pp |
| 4 | 7d_hold_apy | 3.46% APY | −2.36 pp |

vs previous snapshot (2026-07-15): official Net moved **5.841% → 5.820%** (−0.02 pp); closest proxy gap improved slightly (−0.313 → −0.293 pp).

Detail: `results/fluid-lite-official-apy-proxy.json` · `docs/fluid-lite-net-apy.md` · `data/fluid-lite-eth/official_api_snapshot.json`

## Lido EarnETH

- Series: **165** daily points (`2026-02-02` → `2026-07-16`)
- Share price: `1.00000` → `1.01191` ETH per share
- Fees in main APY: **1% protocol + 10% performance** (already in share price)
- On-chain: `depositFeeD6=0`, `redeemFeeD6=0` → realized = hold

| Window | Hold / Realized APY | Return |
|--------|---------------------|--------|
| 7d | 3.48% | +0.066% |
| 30d | 3.81% | +0.307% |
| 90d | 2.64% | +0.645% |
| inception (164d) | **2.67%** | +1.19% |

### Off-chain rewards (excluded from APY)

| Reward | Treatment |
|--------|-----------|
| Mellow Points | Listed only; not in share price |
| Obol rewards | Listed only; claim separately |
| SSV rewards | Listed only; claim separately |

## Files

- `data/fluid-lite-eth/daily_share_price.csv`
- `data/fluid-lite-eth/summary.json`
- `data/fluid-lite-eth/official_api_snapshot.json`
- `data/fluid-lite-eth/official_apy_proxy_comparison.json`
- `data/lido-earn-eth/daily_share_price.csv`
- `data/lido-earn-eth/summary.json`
- `results/summary.json`
- `results/fluid-lite-official-apy-proxy.json`
