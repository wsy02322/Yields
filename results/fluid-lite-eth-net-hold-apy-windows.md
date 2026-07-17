# Fluid Lite ETH — Net Hold APY (independent)

Generated: **2026-07-17 UTC**

Vault: [Fluid Lite ETH Vault](https://fluid.io/lite/1/ETH)

## Meaning

Net Hold APY ≈ annualized growth of underlying stETH claim per share (ETH-equivalent while stETH≈ETH). Example: 5% Net Hold APY means 1 stETH deposited → ~1.05 stETH after one year if that window's growth compounds; same reading for ETH deposited into the vault.

## Formula

```
R   = share_price_T / share_price_T0 − 1   # stETH per iETHv2 share
APY = (1 + R)^(365.25 / days) − 1         # Net Hold (perf fee in price)
```

Exit fee **not** applied. Trailing path — not UI forward Net APY.

## Windows

| Window | Net Hold APY | 1 stETH → after 1y | Days | Range |
|--------|-------------:|-------------------:|-----:|-------|
| 1d | 3.3361% | 1.033361 stETH | 1 | 2026-07-15 → 2026-07-16 |
| 7d | 3.5769% | 1.035769 stETH | 7 | 2026-07-10 → 2026-07-17 |
| 14d | 3.1477% | 1.031477 stETH | 14 | 2026-07-03 → 2026-07-17 |
| 30d | 3.1738% | 1.031738 stETH | 30 | 2026-06-17 → 2026-07-17 |
| 90d | 2.5823% | 1.025823 stETH | 90 | 2026-04-18 → 2026-07-17 |
| 120d | 2.6850% | 1.026850 stETH | 120 | 2026-03-19 → 2026-07-17 |
| 180d | 2.6595% | 1.026595 stETH | 180 | 2026-01-18 → 2026-07-17 |

Series: **883** daily points (`2024-02-16` → `2026-07-17`).

Reproduce:

```bash
python scripts/build_fluid_lite_net_hold_apy_windows.py
```
