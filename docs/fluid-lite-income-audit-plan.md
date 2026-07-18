# Fluid Lite ETH — income audit plan (reviewed)

**Branch:** `cursor/07180455-fluid-lite-income-audit-fc33`  
**Reviewed:** 2026-07-18 UTC  
**Vault:** iETHv2 `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78`

---

## 0. Review decisions

| Feedback | Decision |
|----------|----------|
| **真实存取交易收益 vs 同窗口份额价收益** | **P0 主战场** — 两边独立算、并排对比 |
| **第三方 APY 对照** | **砍掉** |
| **链外 / claim 排查** | **轻量限时** |
| 其他 | 见优先级 |

**原则：** 用链上 **Deposit/Withdraw 真钱路径** 验证 **stETH/share** 是否讲全了收入故事。

---

## 1. Goal (revised)

Answer with **historical on-chain evidence**:

> If a depositor held iETHv2 over calendar window \(T_0 \rightarrow T_1\), how much stETH per share did they earn, and what drove that?

| Priority | Question | Deliverable |
|----------|----------|-------------|
| **P0** | What did **real deposit→withdraw txs** earn? | Tx round-trip returns (assets_out / assets_in) |
| **P0** | Does **stETH/share** over the same `[t0,t1]` match those txs? | Side-by-side tx vs share-path compare |
| **P0** | Is share-price readable accurately at those blocks? | `convertToAssets` at deposit/withdraw blocks |
| **P1** | What income lines sit inside NAV growth? | Attribution (staking vs leverage residual) |
| **P2** | Why does UI Net (~6%) ≠ Hold (~3–4%)? | Short forward gap note — not depositor truth |
| **P2** | Any material income **outside** share price? | Timeboxed off-chain scan |

**North-star:** **tx-realized return** vs **share-price path** on the same hold interval.  
If they match → share price is the full income story. If not → missing income or fee/parse bug.

---

## 2. Accounting frame (unchanged, still the source of truth)

```
asset()       = stETH
share price   = convertToAssets(1e18)     # stETH per iETHv2
NAV           = totalAssets() ≈ collateral − debt
Hold return   = share_price_T1 / share_price_T0 − 1
Hold APY      = (1 + R)^(365.25 / days) − 1
Realized APY  = same after ×(1 − 0.0005) exit fee once at end
```

Baseline params (2026-07-17): share ≈ 1.21467; TVL ≈ 74,186 stETH; ~8× gross leverage.

---

## 3. Off-chain / claimable — judgment (WP3)

**Verdict: do a short scan, do not make it a pillar.**

| Candidate | Prior evidence | Likely outcome | Effort |
|-----------|----------------|----------------|--------|
| **KING** | Docs say weekly → ETH to users; Lite API has **no** reward/KING field; KING largely deprecated | If sold into vault → **already in Hold**; if separate → rare/zero now | Light: one API + sample rebalancer txs |
| **FLUID Merkle** | Fluid docs: claimable, **not** in exchange rate; Lite vault payload has **no** `rewards[]` | **None for Lite ETH depositors** (or negligible) | Light: Fluid + merkle API once |
| **Merkl / points** | Off-chain loyalty (ether.fi 2.5×, etc.) | **Not cash APY** — list & exclude | Docs only |

**Why not deep-dive:** Real income for Lite ETH is overwhelmingly **NAV (stETH/share)**. Spending weeks on claimables that don’t show in API and don’t move Hold adds noise.  
**Exit criterion:** write `offchain_income_scan.json` with either (a) quantified claimables or (b) `"none_material_found"` + what was checked. Cap ~few hours, not a multi-day WP.

---

## 4. Work packages (revised order)

### WP0 — Schema & plan — **done**

- [x] `docs/fluid-lite-income-audit-plan.md`
- [x] `config/fluid_lite_income_sources.yaml`
- [x] This review pass

---

### WP-A — Tx-realized vs share-price path — **P0 / centerpiece**

**This is the substantive audit.** Two independent measurements of the **same** hold interval, then compare.

#### Side ① — Actual user deposit → withdraw (transactions)

From on-chain vault events / txs (Deposit, Withdraw/Redeem, or ETH wrapper equivalents):

| Field | Source |
|-------|--------|
| `user`, `deposit_tx`, `withdraw_tx` | Event logs |
| `t0`, `t1`, `days` | Block timestamps of those txs |
| `assets_in` | ETH or stETH deposited (normalize to stETH-equiv) |
| `shares` | iETHv2 minted |
| `assets_out` | stETH (or ETH) received on redeem **after** protocol exit fee |
| `tx_return` | `assets_out / assets_in - 1` |
| `tx_apy` | annualize(`tx_return`, days) |

This is **what wallets actually got** — includes 0.05% exit fee when charged on withdraw.

#### Side ② — Share-price path over the **same** `[t0, t1]`

| Field | Source |
|-------|--------|
| `p0` | `convertToAssets(1e18)` at deposit block (or nearest) |
| `p1` | `convertToAssets(1e18)` at withdraw block |
| `share_return` | `p1/p0 - 1` (hold, no exit) |
| `share_return_after_exit` | `p1/p0 * (1 - 0.0005) - 1` |
| `share_apy` / `share_apy_after_exit` | annualize same days |

#### Compare ① vs ②

| Check | Expectation |
|-------|-------------|
| `tx_return` ≈ `share_return_after_exit` | Should match within dust / rounding / ETH↔stETH wrap |
| Large gap | Bug in fee application, wrong event parsing, or income outside share price |

**Sample selection (custom windows = each real hold):**

| Sample | Definition | Role |
|--------|------------|------|
| **`clean_full` (primary)** | One Deposit → later one Withdraw, **same shares**, **no intervening** activity for that owner | **Best data** — true once-in / once-out wallet path |
| `fifo` (secondary) | FIFO lot matching; may split partials | Coverage only; noisier |
| Random subset | — | **Not preferred** — clean full is better than random |

Default CLI: `--sample clean`. Use `--sample both` to also emit FIFO for comparison.

**Also keep calendar trailing tables (secondary):** EOD Hold for context — only after WP-A clean sample is solid.

**Caveats to document:**

- Partial withdraws / multiple deposits → pro-rate or require clean single-leg round-trips
- ETH deposit via wrapper vs stETH direct → normalize both to stETH-equiv
- Instant vs delayed withdraw paths if any
- Gas ignored (APY is asset return, not net of gas)

**Outputs:**

- `data/fluid-lite-eth/tx_roundtrips.csv` — side ①
- `data/fluid-lite-eth/tx_vs_share_compare.csv` — ① vs ② per round-trip
- `results/fluid-lite-tx-vs-share.md` — summary + gap stats

**Success:** Median `|tx_return − share_return_after_exit|` small (e.g. &lt; a few bps of period return); outliers explained.

---

### WP-B — Share-price series quality — **P0 (enables WP-A)**

Without accurate daily EOD prices, truth tables lie.

| Task | Why |
|------|-----|
| Binary-search UTC EOD blocks | Fixes tip-day ~0.6 pp error vs live |
| Reconcile `convertToAssets` = `totalAssets/totalSupply` = `exchangePrice()` | Identity check |
| Spot-check random historical days vs archive RPC | Series integrity |

**Output:** refined `daily_share_price.csv` + short QC note.

---

### WP-C — NAV attribution (light) — **P1**

Not full DSA forensics. Just answer: of historical Hold, how much is **pure staking** vs **extra (leverage/restaking/rebalancer)**?

Method: same-window `wstETH.stEthPerToken()` benchmark vs iETHv2 Hold (already proven useful: 7d Hold 4.19% vs staking 2.24%).

Optional later: residual after staking = “strategy alpha” bucket — do **not** require full Aave rate reconstruction unless residual is large and unexplained.

**Output:** columns on truth table + short attribution section in results MD.

---

### WP-D — UI forward gap note — **P2 (explanatory only)**

One short section, reuse existing algo:

- UI Net ≈ forward rates × positions  
- ~2.4 pp Net ≈ eETH spot premium counterfactual  
- **Not** used as depositor expectation  

**No** DefiLlama / vaults.fyi workstreams.

**Output:** subsection in results MD (or tiny JSON). Skip if time-constrained after WP-A/B.

---

### WP-E — Off-chain scan — **P2, timeboxed**

See §3. Cap effort. Prefer “none material” over exhaustive forensics.

**Output:** `data/fluid-lite-eth/offchain_income_scan.json`

---

### ~~WP4 Third-party APY~~ — **cancelled**

| Cancelled | Reason |
|-----------|--------|
| DefiLlama supplyAvg / chart compare | Averages forward UI Net; does not discover real income |
| vaults.fyi Total vs Base | Already diagnosed double-count; no new income discovery |
| Aggregator scoreboards | Noise |

Prior notes stay in conversation/docs; **no new deliverables**.

---

## 5. Income taxonomy (still valid; focus on A + D)

| Class | Role in this audit |
|-------|-------------------|
| **A — In NAV** | **Measure via historical Hold** (WP-A) |
| **B — Forward only** | Explain UI gap only (WP-D) |
| **C — Off-chain** | Timeboxed absence check (WP-E) |
| **D — Fees** | Apply exit fee on truth-table “withdraw” column; perf already in NAV |

---

## 6. Success criteria (revised)

| # | Criterion | Must-have? |
|---|-----------|------------|
| 1 | Sample of clean deposit→withdraw round-trips across hold-length buckets | **Yes** |
| 2 | Each row: tx return/APY **and** same-window share-path return/APY (with exit) | **Yes** |
| 3 | Gap stats: median / p90 of \|tx − share_after_exit\|; outliers explained | **Yes** |
| 4 | Optional trailing EOD Hold tables for context | Nice |
| 5 | Staking vs Hold spread on main windows | Nice |
| 6 | Off-chain scan: material / none_found | Nice |
| 7 | Third-party APY matrix | **No — cancelled** |

---

## 7. Implementation order

```
WP0 (done)
  → WP-A ONLY: tx deposit↔withdraw round-trips vs same-window share path
  → (pause everything else until WP-A is done and reviewed)
  → then WP-B / WP-C / WP-E / WP-D as needed
```

**Current focus lock:** only WP-A. No third-party, no off-chain deep dive, no forward model work until WP-A ships.
---

## 8. Out of scope

- USD vault  
- DefiLlama / vaults.fyi / aggregator APY reconciliation  
- Full DSA replay from deployment  
- Tax, MEV, points valuation as APY  

---

## 9. Next commit after this review

1. Update `config/fluid_lite_income_sources.yaml` work_package statuses  
2. Start **WP-B** (EOD block refine) then **WP-A** truth-table script
