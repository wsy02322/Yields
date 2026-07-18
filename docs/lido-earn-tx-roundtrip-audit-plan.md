# Lido EarnETH — tx round-trip vs share-price audit plan

**Branch:** `cursor/07180937-lidoearn-tx-roundtrip-plan-fc33`  
**Created:** 2026-07-18 UTC (`07180937`)  
**Method:** same as Fluid Lite WP-A clean samples (A vs B)  
**UI:** https://stake.lido.fi/earn/eth/deposit  
**Vault:** `0x6a37725ca7f4CE81c004c955f7280d5C704a249e`  
**Share:** earnETH `0xBBFC8683C8fE8cF73777feDE7ab9574935fea0A4`  
**Oracle:** `0xAda1f4c24603aB2fe5aBd35BCD12370e98A20358`

---

## 0. Why this plan

Fluid Lite clean Deposit→Withdraw samples proved:

| Result | Meaning |
|--------|---------|
| **A ≡ B** (machine epsilon) | Depositor cash return = share-price path |
| Hold ~2–4% vs UI Net ~6% | Official UI is **forward** and **exaggerates** vs realized |

Apply the **same ironclad method** to Lido EarnETH: real deposit→withdraw cash vs oracle share-price path on the same hold.

**Prior art already in repo (do not redo):** daily Hold APY windows (`scripts/audit_lido_earn_apy.py`, `results/LIDO_EARN_AUDIT.md`). That is EOD share series — **not** wallet round-trips. This plan adds the tx sample layer.

---

## 1. Goal

Answer with **historical on-chain evidence**:

> For clean EarnETH holders who deposited once and fully withdrew once, does  
> **A = assets_out / assets_in − 1**  
> equal  
> **B = p₁/p₀ × (1 − redeem_fee) − 1**  
> (with fees as on-chain FeeManager)?

| Priority | Question | Deliverable |
|----------|----------|-------------|
| **P0** | Clean full round-trip list | owner, txs, days, assets_in/out, A, A-APY, B, B-APY |
| **P0** | Does A ≡ B? | Gap distribution (expect ~0 if oracle price is full story) |
| **P1** | How does realized APY compare to UI APY*? | Same-window note vs Mellow 14d time-weighted APY* |
| **P2** | Off-chain (points / Obol / SSV) | Confirm excluded from A/B; list only |

**North-star:** if A ≡ B → oracle `eth_per_share` fully explains depositor ETH returns (fees already in price / zero redeem). If not → parse bug, wrong price timestamp, or income outside share price.

---

## 2. Accounting frame (EarnETH-specific)

```
base asset     = ETH (sentinel 0xEeee…)
share price p  = eth_per_share = 1e36 / oracle.getReport(ETH).priceD18
Hold return    = p1 / p0 − 1
Hold APY       = (1+R)^(365.25/days) − 1

depositFeeD6   = 0   (on-chain FeeManager)
redeemFeeD6    = 0   (on-chain FeeManager)
protocolFee    = 1%  minted as shares on oracle reports → already in p
performanceFee = 10% minted as shares on oracle reports → already in p
```

**B (share path) for EarnETH:**

```
B = p1 / p0 × (1 − redeem_fee) − 1
  = p1 / p0 − 1          # redeem_fee = 0 today
```

Unlike Fluid Lite (0.05% exit), EarnETH **should not** need an exit-fee haircut on B unless FeeManager changes.

**A (tx path):**

```
A = assets_out_ETH / assets_in_ETH − 1
```

Normalize WETH/stETH/wstETH deposit legs to **ETH-equivalent at the deposit pricing report** if multi-asset queues exist; primary path is ETH DepositQueue.

---

## 3. Critical difference vs Fluid Lite: async queues

EarnETH is **Mellow Core Vault** — not sync ERC4626 `deposit`/`withdraw`.

| Step | Fluid Lite (done) | EarnETH (this plan) |
|------|-------------------|---------------------|
| Entry | `Deposit` event: assets+shares same tx | `DepositRequested` → oracle report → `DepositRequestClaimed` (shares) |
| Exit | `Withdraw` event: assets+shares same tx | `redeem` (burn shares) → oracle / `handleBatches` → `claim` (assets) |
| Price at entry | `convertToAssets` at deposit block | Price from **report that priced the deposit request** (not request-block tip) |
| Price at exit | `convertToAssets` at withdraw block | Price from **report that priced the redeem batch** / claim settlement |
| Exit fee | 0.05% in withdraw assets | `redeemFeeD6 = 0` |

**Implication for B:** `p0` / `p1` must be the oracle prices that **actually minted / settled** that user’s shares/assets — not an arbitrary EOD snapshot between request and claim. Discovery WP0 must lock the exact events + which report timestamp maps to each claim.

---

## 4. Sample definition (mirror Fluid)

### Primary: `clean_full`

One complete economic round-trip for an owner:

1. **Single** deposit request that is later **claimed** → receives `shares_S`
2. Later **single** redeem that burns **exactly** `shares_S` (full exit)
3. Later **claim** on redeem queue → receives `assets_out`
4. **No intervening** deposit/redeem/transfer of earnETH for that owner between claim-in and redeem

Fields per sample:

| Field | Source |
|-------|--------|
| `owner` | queue account |
| `deposit_request_tx` / `deposit_claim_tx` | DepositQueue events |
| `redeem_tx` / `withdraw_claim_tx` | RedeemQueue events |
| `t0`, `t1`, `days` | Prefer **economic** hold: claim-shares timestamp → claim-assets timestamp (document alternative: request→request) |
| `assets_in`, `shares`, `assets_out` | Event amounts (ETH wei / 1e18) |
| `p0`, `p1` | Oracle eth_per_share at pricing reports for that deposit / redeem |
| **A**, **A APY** | `assets_out/assets_in−1` + annualize |
| **B**, **B APY** | `p1/p0×(1−redeem_fee)−1` + annualize |
| `gap` | A − B (pp) |

### Secondary: `fifo` (coverage only)

FIFO match partial redeems against prior deposit claims — useful for volume, **not** primary truth (same lesson as Fluid).

### Lookback

- Vault deploy ~ **2026-02-02** (`deployment_block` 24370480) — full history is only ~months; scan **inception → tip** if RPC allows.
- Prefer samples with hold ≥7d / ≥14d / ≥30d for APY stability; still keep short holds (fee/latency effects).

---

## 5. Work packages

### WP0 — Event & queue discovery — **P0 / first**

- [ ] Resolve DepositQueue / RedeemQueue addresses for EarnETH vault (on-chain or Mellow API)
- [ ] Confirm event signatures:
  - `DepositRequested` / `DepositRequestClaimed` / cancel
  - Redeem request / claim / `ReportHandled` linkage
- [ ] Map each claimed deposit → `(assets_in, shares, priceD18_used, ts)`
- [ ] Map each claimed redeem → `(shares_burned, assets_out, priceD18_used, ts)`
- [ ] Spot-check 2–3 known txs on Etherscan vs decoded logs
- [ ] Document in `config/lido_earn_income_sources.yaml`

**Exit:** can decode a known round-trip end-to-end without guessing.

---

### WP-A — Clean samples A vs B — **P0 / centerpiece**

- [ ] Implement `src/calculators/lido_earn_tx_roundtrips.py` (parallel to Fluid)
- [ ] CLI `scripts/audit_lido_earn_tx_roundtrips.py` (`--sample clean|fifo|both`)
- [ ] Unit tests: clean matcher + fee=0 path + inverted oracle price helper
- [ ] Pull logs (chunked; same RPC caveats as Fluid)
- [ ] Outputs:
  - `data/lido-earn-eth/tx_vs_share_compare_clean.csv`
  - `results/lido-earn-clean-samples-A-vs-B.md` (+ `.csv`)
  - `results/lido-earn-tx-vs-share.md` summary

**Success criteria:**

| Outcome | Interpretation |
|---------|----------------|
| median \|gap\| ≈ 0 | Oracle share price = full cash story (expected) |
| Systematic A > B | Missing income or under-counted assets_out |
| Systematic A < B | Over-counted assets_in, wrong p0/p1 timing, or hidden fee |

---

### WP-B — UI contrast note — **P1 / after WP-A**

- [ ] For each clean sample (or bucket by hold days), compare realized A-APY to:
  - published Mellow **APY\* 14d** at nearby date (untrusted reference only)
  - our independent Hold APY over same calendar span (already audited)
- [ ] Short markdown: does UI exaggerate vs **realized round-trips**? (not vs forward)

**Do not** treat UI as truth. Same posture as Fluid.

---

### WP-C — Off-chain list — **P2 / light**

Already known excluded: Mellow Points, Obol, SSV.  
Cap: confirm still not in share price / not in claim assets; write one JSON line. No deep farm.

---

### Out of scope (this branch series)

- Third-party aggregators (DefiLlama / vaults.fyi) as primary truth
- Re-deriving daily Hold windows (already done)
- Strategy-leg PnL attribution inside subvaults (only if A≠B and needs explanation)

---

## 6. Reuse from Fluid Lite

| Component | Reuse |
|-----------|--------|
| Clean-full matching idea | Copy pattern; adapt keys to claim txs |
| A/B table markdown format | Same columns for user readability |
| Annualization | Same `(1+R)^(365.25/days)-1` |
| FIFO secondary | Same role |
| Log chunking / retry | Same RPC hygiene |

| Component | Do **not** copy blindly |
|-----------|-------------------------|
| ERC4626 `Deposit`/`Withdraw` topics | Wrong for Mellow queues |
| 0.05% exit fee on B | EarnETH redeem fee = 0 |
| `convertToAssets` | Use oracle `1e36/priceD18` |

---

## 7. Deliverable preview (user-facing)

Same shape as Fluid’s “铁证” table:

| # | 源数据（owner / 区间 / 天数 / in→out） | A 收益 | A 年化 | B 收益 | B 年化 |
|--:|----------------------------------------|-------:|-------:|-------:|-------:|
| … | … | … | … | … | … |

Plus verdict sentence: A≡B or not; UI APY\* vs realized.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Async pricing ≠ request-block tip | Bind p0/p1 to **report that settled** the request |
| Multi-asset deposit queues | Prefer ETH queue; document conversion if needed |
| Share transfers between wallets | Exclude owners with Transfer≠self on share token during hold |
| Sparse clean samples (short history) | Full-inception scan; report n and hold-day histogram |
| RPC `getLogs` limits | Chunk ~2–3k blocks; cache decoded events |

---

## 9. Status

| WP | Status |
|----|--------|
| Plan (this doc) | **done** |
| WP0 discovery | **done** |
| WP-A implementation + samples | **done** (64 clean ETH-deposit samples; median \|A−B\| ≈ 0.018 pp) |
| WP-B UI note | pending |
| WP-C off-chain | pending |

**WP-A note:** Unlike Fluid (sync ERC4626, gap≈0), EarnETH async pricing + wstETH redeem conversion leave a small residual on some lots; 7–30d bucket median gap ≈ 0 (machine epsilon). Realized A-APY (median ≥7d ≈ 2.8%) aligns with independent Hold, not a 6%-class forward overstatement.
