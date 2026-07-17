# Yield comparison matrix

Generated: **2026-07-17 UTC** by Cursor Cloud Agent (committed to GitHub `main`).

**Fluid Hold / Lido Hold:** trailing compound `(1+R)^(365.25/days)−1`.  
**Fluid Official-algo (our):** reconstructed Instadapp forward Net from live rates × positions.  
**Fluid Official UI:** Instadapp API Net APY.  
**Lido Official UI:** Mellow APY\* (14d avg.).

## Comparison table

| Window | Fluid Hold (our) | Fluid Official-algo (our) | Fluid Official UI | Lido Hold (our) | Lido Official UI |
|--------|------------------|---------------------------|-------------------|-----------------|------------------|
| 1d | 3.34% | **5.92%** | **5.93%** | — | — |
| 7d | 3.58% | — | — | 2.77% | — |
| 14d | 3.15% | — | — | 3.39% | 3.56% |
| 30d | 3.17% | — | — | 3.69% | — |
| 90d | 2.58% | — | — | 2.61% | — |
| Lido Earn inception | 2.49% | — | — | 2.66% | — |
| 360d | 3.78% | — | — | — | — |
| Fluid Lite inception | 5.32% | — | — | — | — |

### Why 1d Hold (3.34%) ≠ Official UI (5.93%)

They are different metrics:

| | 1d Hold | Official-algo / Official UI |
|--|---------|------------------------------|
| Nature | Trailing (yesterday’s share-price gain, annualized) | Forward (current rates × positions) |
| Today | 3.34% | **5.92% / 5.93%** |
| Gap vs UI | −2.59 pp | **−0.013 pp** (algo vs UI) |

So the large Hold-vs-UI gap is expected. Our **Official-algo** reconstruction matches the UI Net within ~0.01–0.02 pp.

### Fluid Official-algo formula

```
protocol_pnl = Σ (supplyAmt × supplyApy) − Σ (borrowAmt × borrowApy)
             + dexYield × ETH-supply notional   # Fluid DEX
idle         = TVL − Σ protocol netAssets
Gross APY    = (protocol_pnl + idle × stETH.netStakingApr) / TVL
Net APY      = Gross × (1 − 0.20)
```

Detail: `results/fluid-lite-official-algo-apy.json`

### Official UI history (DefiLlama) vs Hold / Official-algo

Instadapp has **no** public historical Net API. We pull DefiLlama’s daily series
(same field as UI Net: `apy.apyWithoutFee`) into the repo and join it with our
trailing Hold APYs.

| | Value |
|--|------|
| Source | DefiLlama pool `e72916f7-…` |
| Coverage | **2023-02-20 → 2026-07-17** (**1243** days) |
| Overlap with our share series | 882 days (`2024-02-16` onward) |
| Latest UI Net | **5.93%** |
| Latest Official-algo | **5.92%** (Δ vs UI **−0.012 pp**) |
| Latest Hold 1d / 7d / 30d | 3.34% / 3.58% / 3.17% |

Recent 30d Hold − UI gap (mean):

| Window | mean Δ | median Δ |
|--------|--------|----------|
| 1d Hold − UI | **−1.83 pp** | −1.58 pp |
| 7d Hold − UI | **−1.90 pp** | −1.89 pp |
| 30d Hold − UI | **−1.28 pp** | −1.04 pp |

Files: `data/fluid-lite-eth/official_ui_apy_history.csv` · `results/fluid-lite-official-ui-history-compare.json`

### Official snapshots (this run)

| Source | Value |
|--------|-------|
| Fluid Official UI Net / Gross | 5.9331% / 7.4163% |
| Fluid Official-algo Net / Gross | 5.9201% / 7.4002% (Δ Net **−0.013 pp**) |
| Lido APY\* (14d avg.) | 3.5633% |

## Where to look on GitHub

| File | Contents |
|------|----------|
| `results/RESULTS.md` | This table |
| `results/comparison_matrix.json` | Full matrix |
| `results/fluid-lite-official-algo-apy.json` | Official-algo breakdown |
| `results/fluid-lite-official-ui-history-compare.json` | UI history vs Hold stats |
| `data/fluid-lite-eth/official_ui_apy_history.csv` | Daily Official UI + Hold join |
| `results/summary.json` | Per-vault windows |

```bash
python scripts/build_comparison_matrix.py        # CSV + live official APIs
python scripts/build_comparison_matrix.py --pull # also refresh share prices
python scripts/fetch_fluid_official_ui_history.py  # DefiLlama UI history + Hold compare
```
