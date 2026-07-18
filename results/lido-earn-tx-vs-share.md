# Lido EarnETH — tx round-trips vs oracle share-price path

Generated: **2026-07-18 10:57 UTC**.

Compares **actual deposit→redeem claims** (ETH-equivalent) to oracle `eth_per_share` over the same `[t0, t1]` (redeem fee = 0.0).

Sample: **clean_full** — one deposit request+claim → one full redeem (same shares) → one redeem claim; ETH-equivalent via wstETH→stETH.

Blocks: `24370480` → `25559023` · vault `0x6a37725ca7f4CE81c004c955f7280d5C704a249e`.

## Summary

| Metric | Value |
|--------|------:|
| Clean full round-trips | 64 |
| Median abs gap return pp | 0.018368 |
| p90 abs gap return pp | 0.322473 |
| Max abs gap return pp | 0.630569 |
| Median abs gap APY pp | 0.136303 |

### By hold length

| Bucket | n | Median abs gap return pp | Median tx APY % |
|--------|--:|-------------------------:|----------------:|
| <7d | 13 | 0.020939 | 6.1360 |
| 7–30d | 17 | 0.000000 | 4.6812 |
| 30–90d | 31 | 0.019352 | 2.4695 |
| ≥90d | 3 | 0.021862 | 2.8599 |

## Reading the gap

- **Near-zero gap** → oracle share price fully explains depositor ETH return.
- Residual may include wstETH↔ETH basis on redeem (queue asset = wstETH).

