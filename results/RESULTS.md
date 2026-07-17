# Yield comparison matrix

Generated: **2026-07-17 UTC** by Cursor Cloud Agent (committed to GitHub `main`).

**Fluid Hold / Lido Hold:** trailing compound `(1+R)^(365.25/days)−1`.  
**Fluid Official-algo (our):** reconstructed Instadapp forward Net from live rates × positions.  
**Fluid Official UI:** Instadapp API Net APY.  
**Lido Official UI:** Mellow APY\* (14d avg.).

## Lido EarnETH independent audit (do not trust UI)

Primary truth = on-chain Mellow oracle share price Hold APY.  
Published UI APY\* is **untrusted reference only**.

See full report: [`results/LIDO_EARN_AUDIT.md`](LIDO_EARN_AUDIT.md) · [`results/lido-earn-eth-independent-audit.json`](lido-earn-eth-independent-audit.json)

| Window | Hold APY (independent) | Days | Start → End | Status |
|--------|------------------------:|-----:|-------------|--------|
| 1d | **2.0701%** | 1 | 2026-07-16 → 2026-07-17 | ok |
| 7d | **3.0759%** | 7 | 2026-07-10 → 2026-07-17 | ok |
| 14d | **3.5396%** | 14 | 2026-07-03 → 2026-07-17 | ok |
| 30d | **3.7587%** | 30 | 2026-06-17 → 2026-07-17 | ok |
| 90d | **2.6334%** | 90 | 2026-04-18 → 2026-07-17 | ok |
| 120d | **3.0344%** | 120 | 2026-03-19 → 2026-07-17 | ok |
| 180d | — | — | — | insufficient_history (history=165d) |
| inception | **2.6704%** | 165 | 2026-02-02 → 2026-07-17 | ok |

Published APY\* (14d avg., untrusted): **3.5256%** · our 14d Hold **3.5396%** · Δ **+0.0140 pp**.

```bash
python scripts/audit_lido_earn_apy.py --pull
```

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

**Important:** DefiLlama publishes **one** daily Net series — it does **not** ship
native 7d/30d/… window APYs. Multi-window compare below is **our Hold** (1d / 7d / 30d)
against that **same** daily UI point each date. Official-algo is live-only (latest row).

| | Value |
|--|------|
| Source | DefiLlama pool `e72916f7-…` |
| Coverage | **2023-02-20 → 2026-07-17** (**1243** days) |
| Overlap with our share series | 882 days (`2024-02-16` onward) |

#### Latest day (2026-07-17)

| Metric | Value | Δ vs DefiLlama UI |
|--------|------:|------------------:|
| DefiLlama Official UI Net | **5.93%** | — |
| Official-algo Net (live) | **5.92%** | **−0.012 pp** |
| Hold 1d | 3.34% | −2.60 pp |
| Hold 7d | 3.58% | −2.36 pp |
| Hold 30d | 3.17% | −2.76 pp |

#### Hold − UI gap by window (pp)

| Window | Recent 30d mean | Recent 30d median | All-overlap mean | All-overlap median |
|--------|----------------:|------------------:|-----------------:|-------------------:|
| 1d Hold − UI | **−1.83** | −1.58 | −0.83 | −1.16 |
| 7d Hold − UI | **−1.90** | −1.89 | −0.98 | −0.89 |
| 30d Hold − UI | **−1.28** | −1.04 | −0.95 | −0.69 |

Hold stays below UI across 1d/7d/30d (definition gap: trailing share-price vs forward rates). Official-algo stays within ~0.01 pp of UI on the latest day.

Not yet joined in this history file: Hold 14d / 90d / 360d / inception vs UI.

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
| `results/LIDO_EARN_AUDIT.md` | Lido Earn independent multi-window audit |
| `results/lido-earn-eth-independent-audit.json` | Full audit JSON |
| `results/comparison_matrix.json` | Full matrix |
| `results/fluid-lite-official-algo-apy.json` | Official-algo breakdown |
| `results/fluid-lite-official-ui-history-compare.json` | UI history vs Hold stats |
| `data/fluid-lite-eth/official_ui_apy_history.csv` | Daily Official UI + Hold join |
| `results/summary.json` | Per-vault windows |

```bash
python scripts/build_comparison_matrix.py        # CSV + live official APIs
python scripts/build_comparison_matrix.py --pull # also refresh share prices
python scripts/fetch_fluid_official_ui_history.py  # DefiLlama UI history + Hold compare
python scripts/audit_lido_earn_apy.py --pull     # independent Lido Earn audit
```
