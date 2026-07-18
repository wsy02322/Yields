# Fluid Lite ETH — tx round-trips vs share-price path

Generated: **2026-07-18 05:53 UTC**.

Compares **actual Deposit→Withdraw** asset returns to **`convertToAssets`** over the same `[t0, t1]` (exit fee 0.05% on withdraw side).

Lookback: last **500000** blocks · vault `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78`.

## Summary

| Metric | Value |
|--------|------:|
| Round-trips matched (FIFO) | 196 |
| Median abs gap return pp | 0.000000 |
| p90 abs gap return pp | 0.000000 |
| Max abs gap return pp | 0.000000 |
| Median abs gap APY pp | 0.000000 |

### By hold length

| Bucket | n | Median abs gap return pp | Median tx APY % |
|--------|--:|-------------------------:|----------------:|
| <7d | 60 | 0.000000 | -2.0024 |
| 7–30d | 87 | 0.000000 | 2.4077 |
| 30–90d | 49 | 0.000000 | 3.4458 |
| ≥90d | 0 | — | — |

## Reading the gap

- **Near-zero gap** → share price (stETH/share) fully explains depositor cash return.
- **Systematic positive tx−share gap** → possible income outside share price.
- **Systematic negative** → fee/parse mismatch or deposit asset normalization issue.

## Sample rows (largest abs gap return first)

| days | assets_in | tx_ret% | share_exit% | gap_ret_pp | tx_apy% | share_apy% |
|-----:|----------:|--------:|------------:|-----------:|--------:|-----------:|
| 1.96 | 0.0005 | -0.0325 | -0.0325 | -0.000000 | -5.894 | -5.894 |
| 1.05 | 0.0003 | -0.0398 | -0.0398 | -0.000000 | -12.941 | -12.941 |
| 33.18 | 0.0005 | 0.3382 | 0.3382 | -0.000000 | 3.786 | 3.786 |
| 4.88 | 0.0071 | -0.0193 | -0.0193 | -0.000000 | -1.434 | -1.434 |
| 3.99 | 50.0001 | -0.0283 | -0.0283 | -0.000000 | -2.560 | -2.560 |
| 7.14 | 2.0000 | -0.0178 | -0.0178 | -0.000000 | -0.905 | -0.905 |
| 22.36 | 3.0002 | 0.1227 | 0.1227 | -0.000000 | 2.023 | 2.023 |
| 10.44 | 2.5002 | 0.0618 | 0.0618 | -0.000000 | 2.183 | 2.183 |
| 5.98 | 1.2544 | 0.0214 | 0.0214 | -0.000000 | 1.315 | 1.315 |
| 6.97 | 1.9825 | 0.0390 | 0.0390 | -0.000000 | 2.065 | 2.065 |
| 21.34 | 205.0070 | 0.2262 | 0.2262 | 0.000000 | 3.944 | 3.944 |
| 12.26 | 0.1401 | 0.1236 | 0.1236 | -0.000000 | 3.748 | 3.748 |
| 19.82 | 1.5410 | 0.1972 | 0.1972 | -0.000000 | 3.697 | 3.697 |
| 8.05 | 49.9906 | 0.0268 | 0.0268 | 0.000000 | 1.224 | 1.224 |
| 33.19 | 0.5200 | 0.3382 | 0.3382 | -0.000000 | 3.786 | 3.786 |

## Reproduce

```bash
python scripts/audit_fluid_lite_tx_roundtrips.py --lookback-blocks 500000
```

Files: `data/fluid-lite-eth/tx_vs_share_compare.csv` · `results/fluid-lite-tx-vs-share.md`
