# Fluid Lite Net APY — official meaning, sources, authenticity

Checked: **2026-07-16 UTC**. Scope: Fluid Lite **ETH vault** (`iETHv2`, `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78`) unless noted.

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

- **Net APY does not subtract the 0.05% exit fee** (exit fee applies only on withdraw).
- Yield *actually accrues* via rising `exchangePrice` / ERC-4626 share price (`convertToAssets`) — that path is separate from the UI APY number.

## “前瞻估算”是什么意思

UI / API 上的 Net·Gross APY **不是**过去 7/30 天份额价格涨了多少再年化，而是：

> 用**此刻**各借贷市场的供给/借款利率，乘以**此刻**金库存量仓位，假设这些利率与仓位结构保持不变，推算一年能赚多少。

| | UI Net/Gross APY | 本仓库 Hold APY |
|--|------------------|-----------------|
| 输入 | 当前各协议 supply/borrow rate + 当前仓位 | 历史每日 `exchangePrice` |
| 性质 | 瞬时 / 前瞻（spot → annualized） | 事后 / 回顾（realized path） |
| 会变的原因 | 利率一变、rebalance 一变，数字立刻变 | 只有份额净值真涨了才变 |
| 本次对照 | Gross ≈ 7.28%、Net ≈ 5.82% | 近 7d Hold ≈ 3.46%（份额路径） |

所以叫「当前策略的前瞻估算」：描述的是**现在这套杠杆策略在现行利率下的预期年化**，不是「你过去已经拿到的年化」。

## 数据源

唯一公开产品源（UI 同源）：

```
GET https://api.instadapp.io/v2/mainnet/lite/users/0x0000000000000000000000000000000000000000/vaults
```

| 字段 | 含义 | 更底层从哪来（推断） |
|------|------|----------------------|
| `protocolsInfo.*.stETHSupply` / `eETHSupply` / `wETHBorrow` / … | 各协议当前仓位规模（ETH 计量） | 金库 DSA 在 Aave V3 / Compound III / Spark / Fluid 等的 on-chain 余额 |
| `protocolsInfo.*.stETHSupplyYield` / `eETHSupplyYield` / `wETHBorrowYield` / … | 各市场**当前**供给/借款 APY（%） | 各借贷协议实时利率（+ weETH 等再质押收益） |
| `stETH.netStakingApr` / `grossStakingApr` | Lido 质押 APR | Lido / stETH 预言机类数据 |
| `vaultTVLInAsset` | 金库净资产（equity） | ≈ 总抵押 − 总债务（与 `totalStEthBal − wethDebtAmt` 一致） |
| `revenueFee` | 绩效费 %（20） | 与链上 `revenueFeePercentage` 一致 |
| `apy.apyWithFee` | **Gross APY** | 后端按仓位×利率汇总（见下） |
| `apy.apyWithoutFee` | **Net APY** | `apyWithFee × (1 − revenueFee/100)` |

Instadapp **未开源**这段汇总代码；DefiLlama 只是读取上述 API 的 `apyWithoutFee`，自己不算。

## 算法（逆向复现，与 API 误差约 0.02pp）

对每个协议仓位（用 API 里 **ETH 计量**的供给/借款字段，避免把 wstETH/weETH 与 stETH/eETH 重复计数）：

```
protocol_pnl = Σ (supplyAmt_i × supplyApy_i)
             − Σ (borrowAmt_j × borrowApy_j)
             [+ dexYield × notional   # Fluid DEX 仓可选]
```

其中 `supplyApy` / `borrowApy` 已是百分比形式的年化利率（如 `2.25` 表示 2.25%）。

未部署进杠杆策略的资金（约 TVL 的 35–40%，含提款缓冲等）：

```
idle = vaultTVLInAsset − Σ protocol_netAssets
idle_pnl ≈ idle × stETH.netStakingApr
```

汇总：

```
Gross APY ≈ (Σ protocol_pnl + idle_pnl) / vaultTVLInAsset
Net APY   = Gross APY × (1 − 0.20)
```

杠杆直觉（单一市场时等价写法）：

```
r = debt / collateral
Gross_i ≈ (supplyApy − r × borrowApy) / (1 − r)
```

多协议时就是按金额加权的同一思想。

### 数值核对（与 `official_api_snapshot.json` 同日逻辑）

- `Σ protocol_pnl / Σ netAssets` ≈ 部署资金的杠杆净利率（约 10% 量级）
- 加上 idle @ `stETH.netStakingApr` 后 ÷ TVL → Gross ≈ **7.27–7.28%**
- API `apyWithFee` ≈ **7.30%**（残差 ≈ 0.02pp，可能来自 KING/奖励估算或 DEX/闲置资金的细账）
- `apyWithFee × 0.8` **精确等于** `apyWithoutFee`

### 不是什么

- ❌ 不是过去 N 天 `exchangePrice` 涨幅年化  
- ❌ 不是链上某个 `apy()` view（合约无此函数）  
- ❌ Net 已扣 20% 绩效费，但 **未扣** 0.05% 退出费

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
| `apyWithFee` (Gross) | ~7.28% |
| `apyWithoutFee` (Net) | ~5.82% |
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

1. **Forward vs trailing.** UI/API Net APY ≈ current strategy estimate. Trailing **1d Hold APY** (latest completed day) is the repo’s primary side-by-side figure vs UI Net; longer windows and `inception_hold_apr` remain available as reference.
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
| Repo **`1d_hold_apy`** (official compare) | Yes (in share price) | No | Latest completed 1d compound Hold APY |
| Repo **`inception_hold_apr`** (reference) | Yes (in share price) | No | Trailing inception, **APR** `R×365.25/d` (not APY) |

Share price is already **net of** the 20% performance fee because revenue is skimmed into `revenue()` rather than remaining in user share value.

## Closest historical proxy vs UI Net APY

Official Net is **not** recoverable exactly from share prices alone (it is spot rates × positions). For side-by-side comparison this repo uses the **latest completed 1-day Hold APY**:

| Rank | Historical algorithm | Rate (2026-07-16) | Δ vs Net (~5.82%) |
|------|----------------------|------------------|-------------------|
| UI compare | **1d Hold APY** `(1+R)^365.25−1` (2026-07-14→15) | **5.16% APY** | **−0.66 pp** |
| Ref | Inception Hold + APR `R × 365.25/days` | 5.53% APR | −0.29 pp |
| Ref | Inception Hold + compound APY | 5.33% APY | −0.49 pp |
| … | 7d / 30d / 90d Hold | ~3.5% → ~2.6% | −2.4 → −3.2 pp |

**Defined proxy (for UI Net comparison):**

```
R   = share_price_T / share_price_{T−1} − 1   # last completed EOD→EOD day
APY = (1+R)^(365.25/1) − 1                   # compound Hold APY; no exit fee
```

Name: `1d_hold_apy`. Incomplete tip-day rows with ~0 return are skipped. Fee treatment matches UI Net (perf fee in price, exit fee excluded). This is trailing, not a reconstruction of the forward formula.

Legacy reference name: `inception_hold_apr`.

Reproduce / refresh comparison (uses existing CSV + live API; no archive re-pull):

```bash
python scripts/compare_fluid_official_apy.py
```

Outputs: `data/fluid-lite-eth/official_apy_proxy_comparison.json`, `results/fluid-lite-official-apy-proxy.json`.

## Bottom line

Official **Net APY** for Fluid Lite ETH is authentic: documented on the Lite fees page, exposed by Instadapp’s own API, and independently confirmed by on-chain `revenueFeePercentage` / `withdrawalFeePercentage`. Treat it as **fee-net, exit-fee-gross, forward-looking**; for historical realized returns use share-price series ± exit fee (as in `results/RESULTS.md`); for a **trailing number to place next to UI Net**, use **`1d_hold_apy`**.
