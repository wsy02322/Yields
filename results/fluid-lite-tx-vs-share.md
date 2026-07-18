# Fluid Lite ETH — tx round-trips vs share-price path

Generated: **2026-07-18 08:08 UTC**.

**Primary sample: clean full round-trips** — one Deposit, later one Withdraw, same share amount, no multi-leg FIFO noise.

From prior 500k-block scan: FIFO legs=196 → **clean=46**.

## Summary (clean)

| Metric | Value |
|--------|------:|
| Clean round-trips | 46 |
| Median abs gap return pp | 2.220446e-14 |
| Max abs gap return pp | 1.887379e-13 |
| Median abs gap APY pp | 7.438494e-13 |

### By hold length

| Bucket | n | Median abs gap return pp | Median tx APY % |
|--------|--:|-------------------------:|----------------:|
| <7d | 15 | 1.110223e-14 | -2.6635 |
| 7-30d | 23 | 2.220446e-14 | 2.0728 |
| 30-90d | 8 | 2.220446e-14 | 3.4162 |
| >=90d | 0 | — | — |

## Why clean > FIFO / random

| Sample | Pros | Cons |
|--------|------|------|
| **Clean full (推荐)** | 真实钱包一次进出；无分拆摊销 | 样本更少 |
| FIFO all legs | 覆盖广 | 部分取出/多次存入会切腿，解释差 |
| Random subset | 无 | 不如干净全量有信息量 |

## Conclusion

On clean round-trips, **tx return == share-path return after 0.05% exit** (gap ~ machine epsilon). Depositor cash income is fully explained by `convertToAssets` (stETH/share).

## Sample rows

| days | assets_in | tx_ret% | share_exit% | gap_ret_pp | tx_apy% |
|-----:|----------:|--------:|------------:|-----------:|--------:|
| 55.21 | 0.8591 | 0.5245 | 0.5245 | 2.22e-14 | 3.522 |
| 41.32 | 4.5000 | 0.3691 | 0.3691 | -2.22e-14 | 3.310 |
| 39.22 | 1.2501 | 0.3928 | 0.3928 | -2.22e-14 | 3.718 |
| 38.04 | 1.0000 | 0.3337 | 0.3337 | -2.22e-14 | 3.250 |
| 34.18 | 21.1900 | 0.3464 | 0.3464 | 0.00e+00 | 3.765 |
| 33.62 | 0.5330 | 0.3242 | 0.3242 | -4.44e-14 | 3.579 |
| 32.55 | 32.4185 | 0.2369 | 0.2369 | 2.22e-14 | 2.691 |
| 30.81 | 0.4601 | 0.2690 | 0.2690 | 2.22e-14 | 3.235 |
| 24.99 | 0.0382 | 0.2637 | 0.2637 | 0.00e+00 | 3.924 |
| 22.36 | 3.0002 | 0.1227 | 0.1227 | -4.44e-14 | 2.023 |
| 21.98 | 5.4002 | 0.1385 | 0.1385 | 0.00e+00 | 2.327 |
| 21.23 | 29.9479 | 0.1238 | 0.1238 | 0.00e+00 | 2.151 |

```bash
python scripts/audit_fluid_lite_tx_roundtrips.py --lookback-blocks 500000 --sample clean
```
