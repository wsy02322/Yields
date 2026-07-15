# Fluid Lite Net APY — official meaning, sources, authenticity

Checked: **2026-07-15 UTC**. Scope: Fluid Lite **ETH vault** (`iETHv2`, `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78`) unless noted.

## What the official site says

Primary docs: [Fees | Instadapp Lite](https://lite.guides.instadapp.io/information/fees)

| Claim | Official wording |
|-------|------------------|
| Performance fee (ETH) | **20% on net profits** |
| Net APY | Performance fee is **already included** in the **Net APY** shown in the UI |
| Gross APY | Hover the info icon to see **Gross APY** |
| Exit fee | **0.05%** on ETH/USD vaults → DAO revenue |
| USD vault | **No** performance fee |

Launch announcement (same fee): [Introducing Lite v2](https://blog.instadapp.io/introducing-lite-v2/) — “The ETH vault will charge **20% on profits**. All fees earned by Instadapp Lite go to the DAO.”

App entry: [fluid.io/lite](https://fluid.io/lite) / [lite.instadapp.io](https://lite.instadapp.io).

## What Net APY means (ETH vault)

```
Gross APY  = strategy yield before the 20% performance cut
Net APY    = Gross APY × (1 − 0.20)   # what the UI labels “Net APY”
```

- **Net APY is forward-looking** (current leverage / supply–borrow spread estimate), not a trailing share-price APY.
- **Net APY does not subtract the 0.05% exit fee** (exit fee applies only on withdraw).
- Yield accrues via rising `exchangePrice` / ERC-4626 share price (`convertToAssets`).

## Source authenticity checklist

| Layer | Evidence | Verdict |
|-------|----------|---------|
| Official docs | fees page + Lite v2 blog | Authentic primary sources |
| Official API | `https://api.instadapp.io/v2/mainnet/lite/users/0x000…000/vaults` returns `revenueFee: "20"`, `withdrawalFee: "0.05"`, and `apy.{apyWithoutFee, apyWithFee}` | Live product API |
| On-chain fee params | `revenueFeePercentage() = 200000` → **20%** at 1e6 scale; `withdrawalFeePercentage() = 500` → **0.05%** | Matches docs/API |
| On-chain exchange price | `exchangePrice()` ≈ `convertToAssets(1e18)` ≈ API `exchangePriceiETHV2` | Consistent NAV |
| API fee math | `apyWithFee × 0.8 == apyWithoutFee` (exact) | Confirms Net = Gross × 80% |
| Third-party | DefiLlama `fluid-lite` adaptor uses `apy.apyWithoutFee` ([source](https://github.com/DefiLlama/yield-server/blob/master/src/adaptors/fluid-lite/index.js)) | Reports **Net** APY |

### Snapshot (this check)

See `data/fluid-lite-eth/official_api_snapshot.json`.

| Field | Value |
|-------|-------|
| `apyWithFee` (Gross) | ~7.30% |
| `apyWithoutFee` (Net) | ~5.84% |
| `revenueFee` | 20 |
| `withdrawalFee` | 0.05 |
| On-chain `revenueFeePercentage` | 200000 / 1e6 = 20% |
| On-chain `withdrawalFeePercentage` | 500 / 1e6 = 0.05% |

### API naming note

Official API names are inverted vs UI language:

| API field | Meaning | UI label |
|-----------|---------|----------|
| `apyWithoutFee` | After 20% performance fee | **Net APY** |
| `apyWithFee` | Before 20% performance fee | **Gross APY** |

DefiLlama correctly consumes `apyWithoutFee` (Net).

## Authenticity caveats (not forgeries — definition gaps)

1. **Forward vs trailing.** UI/API Net APY ≈ current strategy estimate. Trailing share-price Hold APY in this repo (7d/30d/90d) can be lower/higher; inception Hold APY (~5.3%) is closer to the live Net snapshot but is a different metric.
2. **Exit fee not in Net APY.** Realized deposit→withdraw return must haircut 0.05% once (this repo’s `realized` APY).
3. **USD vault.** Official: no performance fee; rate is governance floor / reward rate (`fixedRate` / `rate` in lite-usd API). Some third-party blogs wrongly claim a 20% USD performance fee — **not** supported by official fees docs or on-chain ETH fee getters for USD.
4. **Aggregator variance.** StakingBoard / AprScope / etc. may lag or mix Gross/Net; prefer official API or on-chain share price.

## Relation to this repo’s historical APY

| Metric | Includes 20% perf fee? | Includes 0.05% exit? | Nature |
|--------|------------------------|----------------------|--------|
| UI **Net APY** | Yes (deducted) | No | Forward estimate |
| UI **Gross APY** | No | No | Forward estimate |
| Repo **Hold APY** | Yes (in share price) | No | Trailing `exchangePrice` |
| Repo **Realized APY** | Yes | Yes (once at end) | Trailing + exit |

Share price is already **net of** the 20% performance fee because revenue is skimmed into `revenue()` rather than remaining in user share value.

## Bottom line

Official **Net APY** for Fluid Lite ETH is authentic: documented on the Lite fees page, exposed by Instadapp’s own API, and independently confirmed by on-chain `revenueFeePercentage` / `withdrawalFeePercentage`. Treat it as **fee-net, exit-fee-gross, forward-looking**; for historical realized returns use share-price series ± exit fee (as in `results/RESULTS.md`).
