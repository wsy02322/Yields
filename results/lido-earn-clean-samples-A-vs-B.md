# Lido EarnETH — clean samples: return A vs B

n = **1** clean full round-trips (one deposit claim → one full redeem → one redeem claim).

- **A** = `eth_out / eth_in − 1` (wstETH out converted via `getStETHByWstETH`)
- **B** = `p1/p0 × (1−redeem_fee) − 1` (oracle eth_per_share; redeem_fee=0)
- **APY** = `(1+R)^(365.25/days) − 1`

| # | owner | t0 → t1 | days | in ETH | out ETH | A ret% | A APY% | B ret% | B APY% | gap pp |
|--:|-------|---------|-----:|-------:|--------:|-------:|-------:|-------:|-------:|-------:|
| 1 | `0x9CB3…F4bc` | 2026-06-26→2026-06-29 | 2.94 | 1.0000 | 1.0013 | 0.1285 | 17.268 | 0.0365 | 4.632 | 9.20e-02 |

## Source detail (txs)

| # | deposit_asset | deposit_claim_tx | withdraw_claim_tx | p0 | p1 |
|--:|---------------|------------------|-------------------|----:|----:|
| 1 | ETH | `9486a2f28b…d80b12` | `bf73233a51…41ed6f` | 1.00989615 | 1.01026481 |

Full CSV: `results/lido-earn-clean-samples-A-vs-B.csv`
