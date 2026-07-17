# Lido EarnETH independent APY audit

Generated: **2026-07-17 UTC** (branch tag `07171359`).

UI under audit: [https://stake.lido.fi/earn/eth/deposit](https://stake.lido.fi/earn/eth/deposit)

**Trust model:** do **not** trust Lido Earn / Mellow published APY. Primary metric is trailing **Hold APY** from on-chain oracle share price.

## Independent Hold APY

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

### Series

| | |
|--|--|
| Points | 166 |
| First | 2026-02-02 @ 1.0 |
| Last | 2026-07-17 @ 1.0119763248137752 |
| Oracle | `0xAda1f4c24603aB2fe5aBd35BCD12370e98A20358` |
| Vault | `0x6a37725ca7f4CE81c004c955f7280d5C704a249e` |

## Published APY* (untrusted reference only)

| | |
|--|--|
| Label | APY* (14d avg.) |
| Published | 3.5256% |
| Our same-window Hold | 3.539569% |
| Δ (ours − published) | 0.014009 pp |

_Shown for contrast only — not used as audit truth._

## Reproduce

```bash
python scripts/audit_lido_earn_apy.py --pull
```

Files: `results/lido-earn-eth-independent-audit.json` · `data/lido-earn-eth/daily_share_price.csv`
