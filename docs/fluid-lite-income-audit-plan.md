# Fluid Lite ETH — full income audit plan

**Branch:** `cursor/07180455-fluid-lite-income-audit-fc33`  
**Timestamp:** 07180455 UTC (MMDDHHmm)  
**Vault:** iETHv2 `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78`  
**Status:** Plan only — implementation follows on this branch.

---

## 1. Goal

Build a **complete, verifiable map** of every income line that affects a Fluid Lite ETH depositor:

| Question | Deliverable |
|----------|-------------|
| What can the vault earn? | Income taxonomy + per-source data feeds |
| What is already in `convertToAssets` (stETH/share)? | On-chain attribution vs Hold APY |
| What is in official UI Net APY but not realized? | Forward-model decomposition (e.g. eETH spot premium) |
| What is earned but **not** in share price? | Separate-claim / off-chain items |
| What is taken as fees? | Performance 20%, exit 0.05%, `revenue()` skim |

**North-star metric for depositors:** trailing **Hold APY** from `convertToAssets` (stETH/share).  
Everything else is explanation, attribution, or comparison.

---

## 2. Accounting frame (protocol params)

```
asset()              = stETH (rebasing reference; vault holds wstETH/weETH internally)
share price          = convertToAssets(1e18)  [stETH per iETHv2]
NAV                  = totalAssets() ≈ collateral_stETH_equiv − debt_ETH
Gross UI APY         = forward: Σ(position × spot rate) / TVL
Net UI APY           = Gross × (1 − revenueFee/100)     [revenueFee = 20%]
Realized depositor   = Δ share price over window, annualized (Hold APY)
```

**Verified baseline (2026-07-17 mainnet):**

| Parameter | Value |
|-----------|-------|
| `convertToAssets(1e18)` | 1.214666441 stETH/share |
| `totalAssets` | 74,186.60 stETH |
| `totalSupply` | 61,075.70 iETHv2 |
| Collateral (API `totalStEthBal`) | 594,660 stETH-equiv |
| Debt (API `wethDebtAmt`) | 520,475 ETH |
| Equity / TVL | 74,186 (~8.0× gross) |
| Idle (~37% TVL) | TVL − Σ protocol `netAssets` |

**Key prior finding (to validate in this audit):**

- UI Net ~6.08% is **forward**; Hold ~3–4% is **realized**.
- ~2.4 pp of forward Net ≈ **eETH spot premium** (`eETHSupplyYield` − `stETHSupplyYield`) on leveraged notional.
- vaults.fyi `totalApy` ≈ 6.5% **double-counts** staking via `intrinsicApy` compose on a stETH-denominated share price.

---

## 3. Income taxonomy

### A. In share price (Hold APY) — primary depositor yield

| # | Income line | Mechanism | Where it shows up | Verify via |
|---|-------------|-----------|-------------------|------------|
| A1 | **Lido staking** (wstETH/weETH → stETH rate) | Collateral appreciates vs ETH | `totalAssets` ↑ | `wstETH.stEthPerToken()` delta; share price − borrow drag |
| A2 | **Leverage spread** | supply yield − borrow cost on looped book | `totalAssets` ↑ | Per-protocol supply/borrow notionals × realized rates |
| A3 | **Fluid DEX fees** | `dexYield` on ETH-unit supply notional | `totalAssets` ↑ | `protocolsInfo.fluidDex.dexYield`; on-chain DEX volume if needed |
| A4 | **Idle buffer yield** | ~35–40% TVL not deployed; earns `stETH.netStakingApr` | `totalAssets` ↑ | `idle = TVL − Σ netAssets` × staking APR |
| A5 | **eETH / weETH restaking premium** (realized) | ether.fi yield above base staking, in token rate | `totalAssets` ↑ | weETH/eETH exchange rate vs ETH over window |
| A6 | **Rebalancer PnL** | swaps, refi between Aave/Spark/Fluid/Compound | `totalAssets` ↑ | DSA tx trace; NAV jumps vs rate model residual |

### B. In official forward Net APY — may exceed Hold

| # | Income line | In UI formula? | In share price? | Verify via |
|---|-------------|----------------|-----------------|------------|
| B1 | Spot supply APY per market | `*SupplyYield` × amt | Only if rates persist | Instadapp API `protocolsInfo` |
| B2 | Spot borrow cost | `*BorrowYield` × amt | Same | Same |
| B3 | **eETH spot premium (unrealized)** | `eETHSupplyYield` (~3.01%) vs stETH (~2.26%) | Partially | Counterfactual algo; ether.fi API |
| B4 | Idle @ `netStakingApr` | idle × APR / TVL | Yes if idle persists | API `stETH.netStakingApr` |

### C. Separate from share price — NOT in Hold APY

| # | Income line | Documented? | In `offchain_rewards`? | Verify via |
|---|-------------|-------------|------------------------|------------|
| C1 | **KING rewards** (historical weETH) | Lite docs mention weekly → ETH | ❌ empty today | Rebalancer txs; ether.fi history |
| C2 | **FLUID / Merkle rewards** | Fluid docs: claim separately | ❌ | `api.fluid.instadapp.io` rewards[]; merkle API |
| C3 | **Merkl / third-party** | Fluid docs | ❌ | Merkl campaign APIs |
| C4 | **ether.fi loyalty points** | Governance posts (2.5×) | ❌ | Off-chain; exclude from APY |
| C5 | **Instadapp Lite points** | Unknown | ❌ | UI / terms |

### D. Fees (reduce depositor take)

| Fee | Rate | When | In share price? | In UI Net? |
|-----|------|------|-----------------|------------|
| Performance | 20% | On profit; skim to `revenue()` | ✅ yes (net of fee) | ✅ yes |
| Exit / withdrawal | 0.05% | On redeem | ❌ (Realized APY only) | ❌ |
| Management | 0% | — | — | — |

---

## 4. Work packages (implementation order)

### WP0 — Income ledger schema (this branch)

- [ ] `config/fluid_lite_income_sources.yaml` — canonical list A1–C5 + fee rows
- [ ] `docs/fluid-lite-income-audit-plan.md` (this file) — sign-off ready
- [ ] Extend `config/vaults.yaml` `offchain_rewards` from audit findings

### WP1 — On-chain share-price attribution

**Objective:** decompose Δ `convertToAssets` into explainable components over 1d / 7d / 30d / 90d.

| Task | Method |
|------|--------|
| Fix EOD block refinement | Binary search `eth_getBlock` for UTC EOD; closes ~0.6 pp tip-day gap vs live |
| Staking benchmark | `wstETH.stEthPerToken()` same windows → isolate leverage spread |
| Borrow drag | WETH debt × ETH borrow rate (realized or spot) |
| NAV identity daily | `totalAssets` vs API `totalStEthBal − wethDebtAmt` |
| Residual bucket | Δ NAV − explained lines → rebalancer / timing / oracle |

**Output:** `data/fluid-lite-eth/income_attribution_{window}.json`

### WP2 — Forward model line-by-line reconciliation

**Objective:** match Instadapp Net APY to sum of lines; quantify each line's pp contribution.

| Task | Method |
|------|--------|
| Extend `fluid_lite_official_algo.py` | Per-protocol PnL export + eETH premium sensitivity |
| Live API snapshot cron | `official_api_snapshot.json` + protocol breakdown |
| Counterfactuals | Remove eETH premium, remove dexYield, remove idle |
| Hold vs forward gap report | Daily join: UI Net, algo Net, Hold 1d/7d/30d |

**Output:** `results/fluid-lite-income-forward-vs-realized.json`

### WP3 — Off-chain / claimable income hunt

**Objective:** prove whether C1–C5 exist and magnitude.

| Source | API / chain |
|--------|-------------|
| Instadapp Lite vault API | `protocolsInfo`, any `rewards` fields |
| Fluid lending/borrowing API | `api.fluid.instadapp.io/v2/borrowing/1/vaults` |
| Fluid merkle | `merkle.api.fluid.instadapp.io` |
| ether.fi | weETH rate, historical KING |
| DSA / Rebalancer | Etherscan internal txs from vault DSA |

**Output:** `data/fluid-lite-eth/offchain_income_scan.json`

### WP4 — Third-party APY cross-check

| Platform | Compare | Known issue |
|----------|---------|-------------|
| Fluid UI | Forward Net | eETH spot inflation |
| DefiLlama | UI Net history + supplyAvg7d/30d | Not Hold; avg of forward |
| vaults.fyi | Base vs Total | `intrinsicApy` double-count on stETH-denominated vault |

**Output:** `results/fluid-lite-income-third-party-compare.md`

### WP5 — Depositor truth table

One table: **1 ETH in → expected stETH out** at 7d / 30d / 1y under:

1. Hold (realized share price)  
2. Official forward Net (spot)  
3. Forward with eETH premium removed  
4. After 0.05% exit fee  

**Output:** `results/fluid-lite-depositor-expectations.md`

---

## 5. Data sources checklist

| Layer | Endpoint / contract | Used for |
|-------|---------------------|----------|
| ERC-4626 | `iETHv2.convertToAssets`, `totalAssets`, `asset` | Hold APY, denomination |
| Fee getters | `revenueFeePercentage`, `withdrawalFeePercentage`, `revenue()` | Fees |
| wstETH | `stEthPerToken()` | Staking benchmark |
| weETH / eETH | ether.fi rate, `eETHSupplyYield` | Restaking premium |
| Instadapp Lite API | `/v2/mainnet/lite/users/0x000…/vaults` | Positions, spot yields, UI APY |
| Fluid API | lending + borrowing + merkle | Native vs claimable rewards |
| DefiLlama | pool `e72916f7-…` | Historical UI Net |
| Archive RPC | `eth_call` historical | Daily series |

---

## 6. Success criteria

| # | Criterion |
|---|-----------|
| 1 | Every income line classified: **in NAV** / **forward only** / **off-chain** / **fee** |
| 2 | Hold 7d reproducible from chain within **±0.1 pp** of live block |
| 3 | Forward Net decomposed; eETH premium pp contribution documented |
| 4 | Off-chain scan complete with evidence (tx hash or API field or "none found") |
| 5 | Depositor 1y expectation: **~1.03–1.04 ETH** (not 1.06) documented with params |
| 6 | Third-party mislabeling (vaults.fyi Total, DefiLlama avg) documented |

---

## 7. Open questions for Fluid / Instadapp

1. Does UI Net include **expected** eETH restaking at spot, or trailing realized weETH rate?  
2. Are **KING** (or successor) rewards sold and recycled into `totalAssets`, or separate?  
3. What is the **DSA / Rebalancer** address for tx-level income attribution?  
4. Is any **Merkle FLUID** emission active on Lite ETH positions?  
5. Should depositor-facing APY prefer **Hold** or forward — and should eETH premium be trailing?

---

## 8. Repo touchpoints (existing)

| File | Role in this audit |
|------|-------------------|
| `src/fetchers/fluid_lite.py` | Share-price series |
| `src/calculators/fluid_lite_official_algo.py` | Forward reconstruction |
| `src/calculators/apy.py` | Hold APY |
| `docs/fluid-lite-net-apy.md` | Prior Net APY semantics |
| `data/fluid-lite-eth/official_algo_apy.json` | Live breakdown snapshot |

---

## 9. Next commit on this branch

1. `config/fluid_lite_income_sources.yaml` — machine-readable taxonomy  
2. `scripts/plan_fluid_lite_income.py` — stub that prints WP status (optional)  
3. Implement **WP1** block refinement + staking benchmark script

---

## 10. Out of scope (for now)

- USD vault (`fLiteUSD`)  
- Tax / accounting treatment  
- MEV on rebalancer swaps  
- Full DSA forensic replay from deployment block
