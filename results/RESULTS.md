# Historical yield results (one-shot)

Generated: **2026-07-16 UTC** (tip block `25543295`).  
No automatic refresh — re-run only on explicit request.

Vaults are **independent**; no comparison metrics.

**APY definition:** compound `(1+R)^(365.25/days)−1` (standard).  
**APR (comparison only):** simple `R×(365.25/days)` — not APY.

## Fluid Lite ETH (`iETHv2`) vs official UI Net

- Series: **882** daily points (`2024-02-16` → `2026-07-16`)
- Share price: `1.07155` → `1.21442` (matches live API `exchangePriceiETHV2`)

### Official UI (live Instadapp API)

| 指标 | 数值 |
|------|------|
| **Net APY** (`apyWithoutFee`) | **5.8205%** |
| **Gross APY** (`apyWithFee`) | **7.2756%** |
| 绩效费 / 退出费 | 20% / 0.05% |

### 1-day Hold APY（用于对比官网）

Latest **completed** calendar day (skips incomplete tip-day Jul 16 which had 0% move):

```
R   = share_price(2026-07-15) / share_price(2026-07-14) − 1 = +0.013788%
APY = (1+R)^365.25 − 1
```

| | Rate | Δ vs Official Net |
|--|------|-------------------|
| Official **Net** | **5.8205%** | — |
| **1d Hold APY** (`2026-07-14 → 2026-07-15`) | **5.1647%** | **−0.656 pp** |
| 1d Hold APR (same day, simple) | 5.036% | −0.784 pp |

### Other trailing windows

| Window | Hold APY | Realized APY | Preferred |
|--------|----------|--------------|-----------|
| 1d | **5.16%** | caution* | hold_apy |
| 7d | 3.46% | 0.79%* | hold_apy |
| 30d | 3.18% | 2.56%* | hold_apy |
| 90d | 2.58% | 2.38% | hold_or_realized |
| inception (881d) | 5.33% | 5.30% | hold_or_realized |

\*Short windows with exit fee: prefer Hold APY.

| Reference proxies | Rate | Δ vs Net |
|-------------------|------|----------|
| inception_hold_apr | 5.53% APR | −0.29 pp |
| inception_hold_apy | 5.33% APY | −0.49 pp |
| **1d_hold_apy (recommended vs UI)** | **5.16% APY** | **−0.66 pp** |

Detail: `results/fluid-lite-official-apy-proxy.json` · `data/fluid-lite-eth/official_api_snapshot.json`

## Lido EarnETH

- Series: **165** daily points (`2026-02-02` → `2026-07-16`)
- On-chain redeem fee = 0 → Hold = Realized
- No official Fluid-style Net APY source for side-by-side UI compare

| Window | Hold / Realized APY | Return |
|--------|---------------------|--------|
| 7d | 3.48% | +0.066% |
| 30d | 3.81% | +0.307% |
| 90d | 2.64% | +0.645% |
| inception (164d) | **2.67%** | +1.19% |

## Files

- `data/fluid-lite-eth/daily_share_price.csv`
- `data/fluid-lite-eth/summary.json`
- `data/fluid-lite-eth/official_api_snapshot.json`
- `data/fluid-lite-eth/official_apy_proxy_comparison.json`
- `data/lido-earn-eth/daily_share_price.csv`
- `data/lido-earn-eth/summary.json`
- `results/summary.json`
- `results/fluid-lite-official-apy-proxy.json`
