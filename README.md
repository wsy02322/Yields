# Yields

Historical, fee-aware yield calculations for two independent ETH vaults:

1. **Fluid Lite ETH Vault** (`iETHv2`)
2. **Lido EarnETH** (`earnETH`)

Vaults are processed **separately** — no comparison / ranking / relative metrics.

## Scope decisions

| Decision | Choice |
|----------|--------|
| Relationship between vaults | Independent (no cross-vault comparison) |
| Withdrawal assumption | User eventually withdraws → Fluid **0.05% exit fee** included in **realized** APY |
| EarnETH off-chain rewards | **Mellow Points / Obol / SSV listed separately**, excluded from main APY |
| Data freshness | **One-shot historical pull only**; re-run only on explicit request |

## Fees included

### Fluid Lite ETH

| Fee | Rate | How handled |
|-----|------|-------------|
| Performance | 20% of net profits | Already inside share price / Net APY |
| Exit | 0.05% | Applied once at window end in **realized** APY |
| Management | 0% | — |

Source: [Fluid Lite fees](https://lite.guides.instadapp.io/information/fees)

See also: [docs/fluid-lite-net-apy.md](docs/fluid-lite-net-apy.md) — official Net APY meaning, API fields, on-chain authenticity check, and the **`inception_hold_apr`** historical proxy (simple/linear APR, not compound APY) used to compare against UI Net APY.

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

### Returns & APY

```
hold_return     = share_price_T1 / share_price_T0 - 1
realized_price  = share_price_T1 * (1 - exit_fee)   # Fluid exit 0.05%; EarnETH redeem 0
realized_return = realized_price / share_price_T0 - 1
APY             = (1 + return)^(365.25 / days) - 1   # compound — repo default / standard
APR             = return × (365.25 / days)           # simple/linear — not APY
```

Windows: **7d / 30d / 90d / inception** (when enough history exists).

**Display guidance:** prefer **Hold APY** for short mark-to-market windows (≤30d). **Realized APY** is for deposit→withdraw (especially inception); short-window realized values are flagged `realized_apy_caution` because a one-time exit fee dominates after annualization.

**Fluid Lite vs official Net APY (comparison only):** among trailing Hold metrics, **`inception_hold_apr`** (`R × 365.25/days` over inception, no exit fee — this is **APR**, not compound APY) is empirically closest to the UI Net figure. See `docs/fluid-lite-net-apy.md` and `results/fluid-lite-official-apy-proxy.json`.

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

Compare historical proxy vs live official Net APY (reuses existing CSV; no archive re-pull):

```bash
python scripts/compare_fluid_official_apy.py
```

## Outputs

```
data/fluid-lite-eth/daily_share_price.csv
data/fluid-lite-eth/summary.json
data/fluid-lite-eth/official_apy_proxy_comparison.json
data/lido-earn-eth/daily_share_price.csv
data/lido-earn-eth/summary.json
results/fluid-lite-eth.json
results/fluid-lite-official-apy-proxy.json
results/lido-earn-eth.json
results/summary.json
results/RESULTS.md
```

See `results/RESULTS.md` for the latest one-shot numbers.

**Note on Fluid exit fee:** realized APY applies the 0.05% exit fee once at the window end, then annualizes. On short windows (e.g. 7d) this one-time haircut dominates the period return and **understates** annualized realized APY — use hold APY for short mark-to-market views and realized for deposit→withdraw (esp. inception). Outputs set `realized_apy_caution=true` and `preferred_metric=hold_apy` when days ≤ 30 and exit fee > 0.

Requires an Ethereum **archive** RPC (default in `config/vaults.yaml`: `https://eth.drpc.org`).

## Tests

```bash
python -m pytest tests/ -q
```

## Layout

```
config/vaults.yaml          # addresses, fees, sampling policy
src/fetchers/               # on-chain share-price collectors + official API
src/calculators/apy.py      # returns / rolling APY
src/calculators/official_apy_proxy.py  # closest trailing proxy vs UI Net
scripts/compute_historical_yields.py
scripts/compare_fluid_official_apy.py
data/                       # raw daily series + per-vault summaries
results/                    # report-ready JSON
```
