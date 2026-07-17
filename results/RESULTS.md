# Yield comparison matrix

Generated: **2026-07-17 UTC** (tip block `25550354`) by Cursor Cloud Agent.  
You do **not** need to run this on your own machine — results are committed to GitHub.

**Our APY:** compound Hold `(1+R)^(365.25/days)−1` (no exit fee).  
**Fluid Official UI:** Instadapp Lite **Net APY** (forward-looking; 1d row only).  
**Lido Official UI:** Mellow **APY\* (14d avg.)** time-weighted (14d row only).

## Comparison table

| Window | Fluid Lite (our Hold APY) | Fluid Official UI | Lido EarnETH (our Hold APY) | Lido Official UI |
|--------|---------------------------|-------------------|-----------------------------|------------------|
| 1d | 3.34% | 5.67% | — | — |
| 7d | 3.58% | — | 2.77% | — |
| 14d | 3.15% | — | 3.39% | 3.56% |
| 30d | 3.17% | — | 3.69% | — |
| 90d | 2.58% | — | 2.61% | — |
| Lido Earn inception | 2.49% | — | 2.66% | — |
| 360d | 3.78% | — | — | — |
| Fluid Lite inception | 5.32% | — | — | — |

### Notes

- **1d Fluid our** uses the latest *completed* EOD→EOD day (`2026-07-15 → 2026-07-16`); incomplete tip-day snapshots with ~0 move are skipped.
- **1d Fluid Official UI** is live Net APY (`5.67%`), not a trailing 1d figure — different definition.
- **14d Lido Official UI** = `3.56%` from Mellow `timeweighted-apy` (`days=14`), same source as [stake.lido.fi/earn/eth](https://stake.lido.fi/earn/eth/deposit).
- **Lido Earn inception** Fluid column = Fluid Hold APY over EarnETH’s inception span (`2026-02-02 → 2026-07-17`).
- **360d / Fluid Lite inception** have no Lido columns (history / product matrix).

### Official snapshots (this run)

| Source | Value |
|--------|-------|
| Fluid Net / Gross | 5.6711% / 7.0889% |
| Lido APY\* (14d avg.) | 3.5633% (last update 2026-07-16 13:11 UTC) |

## Series coverage

| Vault | Points | Range |
|-------|--------|-------|
| Fluid Lite ETH | 883 | 2024-02-16 → 2026-07-17 |
| Lido EarnETH | 166 | 2026-02-02 → 2026-07-17 |

## Where to look on GitHub

| File | Contents |
|------|----------|
| `results/RESULTS.md` | This human-readable table |
| `results/comparison_matrix.json` | Full matrix JSON |
| `results/summary.json` | Per-vault windows + `as_of` |
| `data/*/daily_share_price.csv` | Raw daily share prices |
| `data/fluid-lite-eth/official_api_snapshot.json` | Fluid UI API snapshot |
| `data/lido-earn-eth/official_api_snapshot.json` | Lido/Mellow official APY |

Refresh on Cloud Agent:

```bash
python scripts/build_comparison_matrix.py --pull
```
