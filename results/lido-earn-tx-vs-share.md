# Lido EarnETH — tx round-trips vs oracle share-price path

Generated: **2026-07-18 10:08 UTC**.

Compares **actual deposit→redeem claims** (ETH-equivalent) to oracle `eth_per_share` over the same `[t0, t1]` (redeem fee = 0.0).

Sample: **clean_full** — one deposit request+claim → one full redeem (same shares) → one redeem claim; ETH-equivalent via wstETH→stETH.

Blocks: `25308840` → `25558840` · vault `0x6a37725ca7f4CE81c004c955f7280d5C704a249e`.

## Summary

| Metric | Value |
|--------|------:|
| Clean full round-trips | 1 |
| Median abs gap return pp | 0.091990 |
| p90 abs gap return pp | 0.091990 |
| Max abs gap return pp | 0.091990 |
| Median abs gap APY pp | 12.636486 |

### By hold length

| Bucket | n | Median abs gap return pp | Median tx APY % |
|--------|--:|-------------------------:|----------------:|
| <7d | 1 | 0.091990 | 17.2680 |
| 7–30d | 0 | — | — |
| 30–90d | 0 | — | — |
| ≥90d | 0 | — | — |

## Reading the gap

- **Near-zero gap** → oracle share price fully explains depositor ETH return.
- Residual may include wstETH↔ETH basis on redeem (queue asset = wstETH).

