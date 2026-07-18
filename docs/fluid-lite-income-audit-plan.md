# Fluid Lite ETH — income audit plan (reviewed)

**Branch:** `cursor/07180455-fluid-lite-income-audit-fc33`  
**Reviewed:** 2026-07-18 UTC  
**Vault:** iETHv2 `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78`

---

## 0. Review decisions

| Feedback | Decision |
|----------|----------|
| **存款人真值表 + 历史段实收** | **主战场** — 唯一能回答「用户真实拿到什么」的数据 |
| **第三方 APY 对照** (DefiLlama / vaults.fyi) | **砍掉** — 不增加真实收入发现；已有结论足够，不再投入 |
| **链外 / claim 排查** | **轻量、限时做完** — 见 §3；大概率不是主收入，但必须证伪 |
| 其他 | 见下方优先级 |

**原则：** 只追能进 `convertToAssets`（或可证明确实 claimable）的钱；解释 UI 数字是次要任务。

---

## 1. Goal (revised)

Answer with **historical on-chain evidence**:

> If a depositor held iETHv2 over calendar window \(T_0 \rightarrow T_1\), how much stETH per share did they earn, and what drove that?

| Priority | Question | Deliverable |
|----------|----------|-------------|
| **P0** | What did holders **actually** earn over past windows? | Historical truth tables (Hold + exit fee) |
| **P0** | Is share-price series accurate enough for those tables? | Block-refined daily `convertToAssets` |
| **P1** | What income lines are inside that NAV growth? | Attribution (staking vs leverage residual) |
| **P2** | Why does UI Net (~6%) ≠ Hold (~3–4%)? | Short forward gap note (eETH spot) — not a product |
| **P2** | Any material income **outside** share price? | Timeboxed off-chain scan → yes/no + evidence |

**North-star:** historical **Hold APY** = \(\Delta\) `convertToAssets` (stETH/share).  
UI / DefiLlama / vaults.fyi are **not** success criteria.

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

### WP-A — Historical depositor truth tables — **P0 / centerpiece**

**This is the substantive audit.**

For each calendar window (examples):

| Window | Meaning |
|--------|---------|
| Last 7 / 14 / 30 / 90 / 180 / 360 days | Trailing Hold |
| Calendar months (e.g. 2026-01, 2026-02, …) | Month-by-month realized |
| Calendar quarters | Longer path |
| Inception → tip | Full life |

**Per row compute from on-chain share prices:**

| Column | Formula |
|--------|---------|
| `start_date`, `end_date`, `days` | EOD blocks |
| `p0`, `p1` | `convertToAssets(1e18)` |
| `hold_return_pct` | \(p_1/p_0 - 1\) |
| `hold_apy_pct` | compound 365.25 |
| `realized_apy_pct` | after 0.05% exit once |
| `stETH_out_per_1_ETH_in` | \(1 \times (1 + R) \times (1 - 0.0005)\) if withdraw |
| Optional: `pure_staking_apy` | `wstETH.stEthPerToken()` same window |
| Optional: `leverage_spread_pp` | Hold − pure staking |

**Why this is “真实实质性数据”:**  
No spot-rate assumption. Same path a redeemer’s wallet would see: fewer or more stETH per share.

**Outputs:**

- `data/fluid-lite-eth/historical_truth_tables.csv`
- `results/fluid-lite-historical-realized.md` (human table)

**Success:** Any stakeholder can pick a past month and see exact Hold / stETH-out without trusting Fluid UI.

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
| 1 | Historical truth tables for ≥ trailing 7/30/90/360d + inception + ≥3 calendar months | **Yes** |
| 2 | Each row: Hold return, Hold APY, exit-adjusted stETH-out per 1 ETH | **Yes** |
| 3 | Share series QC: tip Hold within **±0.15 pp** of live same-window RPC | **Yes** |
| 4 | Staking vs Hold spread column on main windows | Yes |
| 5 | Off-chain scan: material / none_found with evidence | Nice |
| 6 | One-paragraph UI vs Hold explanation | Nice |
| 7 | Third-party APY matrix | **No — cancelled** |

---

## 7. Implementation order

```
WP0 (done)
  → WP-B share series QC / EOD refine
  → WP-A historical truth tables   ← main value
  → WP-C staking vs Hold columns
  → WP-E off-chain timebox (parallel OK)
  → WP-D UI gap note (optional polish)
```

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
