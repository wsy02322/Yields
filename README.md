# Yields

Historical, fee-aware yield calculations for two independent ETH vaults:

1. **Fluid Lite ETH Vault** (`iETHv2`)
2. **Lido EarnETH** (`earnETH`)

Vaults are processed **separately** — no comparison / ranking / relative metrics.

## Scope decisions

| Decision | Choice |
|----------|--------|
| Relationship between vaults | Independent (no cross-vault comparison) |
| APY denomination | **ETH** for both vaults |
| Withdrawal assumption | User eventually withdraws → Fluid **0.05% exit fee** in **realized** APY |
| Exit-fee APY amortization | Default **1-year hold** (`exit_fee_hold_days: 365.25`) → ~**−0.05 pp** APY |
| EarnETH off-chain rewards | **Mellow Points / Obol / SSV listed separately**, excluded from main APY |
| Data freshness | **One-shot historical pull only**; re-run only on explicit request |

## Fees included

### Fluid Lite ETH

| Fee | Rate | How handled |
|-----|------|-------------|
| Performance | 20% of net profits | Already inside share price / Net APY |
| Exit | 0.05% | Realized APY: drag amortized over default **1-year** hold (~−0.05 pp) |
| Management | 0% | — |

Source: [Fluid Lite fees](https://lite.guides.instadapp.io/information/fees)

See also: [docs/fluid-lite-net-apy.md](docs/fluid-lite-net-apy.md) — official Net APY meaning, API fields, and on-chain authenticity check.

### Lido EarnETH (Mellow)

| Fee | Rate | How handled |
|-----|------|-------------|
| Platform / protocol | 1% | Minted as shares on oracle reports → inside share price |
| Performance | 10% | Minted as shares on oracle reports → inside share price |
| Deposit | 0% (on-chain `depositFeeD6=0`) | — |
| Redeem | 0% (on-chain `redeemFeeD6=0`) | Realized ≈ Hold for redeem fee |

Sources: [Lido Earn UI](https://stake.lido.fi/earn/eth/deposit), on-chain `FeeManager` `0xed4Fac879eE86F3aB0101993A3713e7cAA0488E1`

**Excluded from main APY (listed only):** Mellow Points, Obol rewards, SSV rewards.

## Method

### Share price

- **Fluid Lite:** ERC-4626 `convertToAssets(1e18)` on `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78` (underlying stETH).
- **EarnETH:** Mellow oracle `getReport(ETH)` on `0xAda1f4c24603aB2fe5aBd35BCD12370e98A20358`.  
  Pricing is inverted (`price ≈ shares/assets`), so:

  ```
  eth_per_share = 1e18 / (priceD18 / 1e18)
  ```

### Returns & APY (ETH-denominated)

Both vaults report primary APY in **ETH**.

**Fluid Lite** (accounting asset = stETH):

```
vault_return      = stETH_share_price_T1 / stETH_share_price_T0 - 1
steth_eth_return  = lido_share_rate_T1 / lido_share_rate_T0 - 1
                  # lido_share_rate = getTotalPooledEther / getTotalShares
ETH_return        = (1 + vault_return) × (1 + steth_eth_return) - 1
hold_apy (ETH)    = (1 + ETH_return)^(365.25 / window_days) - 1
                  # equiv. (1 + vault_apy) × (1 + steth→ETH_apy) - 1
```

**EarnETH** (accounting asset = ETH already):

```
hold_apy (ETH) = (1 + eth_per_share_T1 / eth_per_share_T0 - 1)^(365.25 / days) - 1
# no extra intrinsic layer
```

Exit fee (Fluid 0.05%) is applied as APY drag over a default **1-year** hold:

```
realized_apy = (1 + hold_apy_ETH) × (1 - exit_fee)^(365.25 / 365.25) - 1
```

Windows: **7d / 30d / 90d / inception** (when enough history exists).

Daily snapshots are UTC end-of-day approximations via archive `eth_call` at estimated blocks.

## Contracts

| Vault | Address |
|-------|---------|
| Fluid Lite iETHv2 | `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78` |
| EarnETH vault | `0x6a37725ca7f4CE81c004c955f7280d5C704a249e` |
| EarnETH share token | `0xBBFC8683C8fE8cF73777feDE7ab9574935fea0A4` |
| EarnETH oracle | `0xAda1f4c24603aB2fe5aBd35BCD12370e98A20358` |
| EarnETH FeeManager | `0xed4Fac879eE86F3aB0101993A3713e7cAA0488E1` |

## Reproduce (explicit refresh only)

```bash
pip install -r requirements.txt
python scripts/compute_historical_yields.py
```

## Outputs

```
data/fluid-lite-eth/daily_share_price.csv
data/fluid-lite-eth/daily_steth_share_rate.csv
data/fluid-lite-eth/summary.json
data/lido-earn-eth/daily_share_price.csv
data/lido-earn-eth/summary.json
results/fluid-lite-eth.json
results/lido-earn-eth.json
results/summary.json
results/RESULTS.md
```

See `results/RESULTS.md` for the latest one-shot numbers.

**Exit fee on APY:** a one-time 0.05% withdraw fee is converted to APY drag assuming a **default 1-year hold**, so impact is ~**−0.05 pp** on every window (7d/30d/90d/inception). Period `realized_return` still reflects withdrawing at the window end; only `realized_apy` uses the 1-year amortization.

Requires an Ethereum **archive** RPC (default in `config/vaults.yaml`: `https://eth.drpc.org`).

## Layout

```
config/vaults.yaml          # addresses, fees, sampling policy
src/fetchers/               # on-chain share-price collectors
src/calculators/apy.py      # returns / rolling APY
scripts/compute_historical_yields.py
data/                       # raw daily series + per-vault summaries
results/                    # report-ready JSON
```
