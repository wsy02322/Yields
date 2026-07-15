# 历史净收益计算方案：Lido EarnETH vs Fluid Lite ETH

## 目标

计算以下两个 ETH 金库的**历史净收益率（含全部费用）**，并做可比对输出：

| 产品 | 入口 | 份额代币 / 合约 |
| --- | --- | --- |
| Lido EarnETH | https://stake.lido.fi/earn/eth/deposit | `earnETH` · `0x6a37725ca7f4CE81c004c955f7280d5C704a249e` |
| Fluid Lite ETH | https://lite.guides.instadapp.io/getting-started/fluid-lite-eth-vault | `iETHv2` · `0xA0D3707c569ff8C87FA923d3823eC5D81c98Be78` |

输出口径统一为：**以 ETH（或等价 ETH 单位）计价的持有期净回报**，并给出 7d / 30d / 90d / 自部署以来 的年化。

---

## 1. 产品与费用模型（必须先定清楚）

### 1.1 Lido EarnETH（Mellow 基础设施）

- **策略**：ETH meta-vault，在 GGV / stRATEGY 等 Lido Earn 策略间动态配置；资产为 ETH / stETH / wstETH 体系。
- **费用**：
  - Platform / management fee：**1% / 年**（按持有时间计提）
  - Performance fee：**10%**（对收益计提）
- **费用如何体现**：官方说明费用**不扣减份额余额**，而是反映在份额价格里。因此：
  - `share_price` 时间序列的涨跌 = **已扣管理费 + 业绩费后的净 NAV 回报**
  - 不需要再手工减 1% / 10%，否则会双重扣费
- **份额价格未包含**：
  - Mellow / Obol / SSV 等 **points / 可单独 claim 的奖励**（默认另列，不并入主收益）
  - 入金/出金排队等待期间的机会成本（EarnETH UI：出金最长约 72h）
  - 入金时若发生 ETH→stETH/wstETH 转换的滑点（通常极小，可作为可选扣减）

### 1.2 Fluid Lite ETH（iETHv2）

- **策略**：将存款转为 wstETH / weETH 最优组合，在 Aave / Compound / Spark / Morpho 上抵押借 ETH 再循环加杠杆，放大质押收益；weETH 侧有 weekly KING → 转 ETH 分发给用户。
- **费用**：
  - Performance fee：**20% of net profits**（文档写明已包含在界面 Net APY）
  - Exit fee：**0.05%**（出金时扣，归 DAO）
- **费用如何体现**：
  - 持有期未实现收益：看 `iETHv2` 兑换率 / ERC-4626 `convertToAssets` → **已含 20% 业绩费**
  - **实现收益（进出一轮）**：在持有期净回报上再扣 **0.05% exit fee**
  - KING 若已折算进金库 NAV / 兑换率，则已在份额价里；若为链下/单独分发，需另加「奖励补丁」项（实现阶段用链上事件或官方 API 核实）

---

## 2. 核心方法论（两边共用）

### 2.1 主指标：份额价格时间序列

对日频（或块高对齐的日快照）取：

\[
P_t = \frac{\texttt{totalAssets}_t}{\texttt{totalSupply}_t}
\quad\text{或}\quad
P_t = \texttt{convertToAssets}(10^{18})
\]

持有期简单回报：

\[
R_{[t_0,t_1]} = \frac{P_{t_1}}{P_{t_0}} - 1
\]

年化（建议同时报两种，避免歧义）：

| 名称 | 公式 | 用途 |
| --- | --- | --- |
| APR（线性） | \(R \times 365 / \Delta days\) | 短窗口、与多数 DeFi UI 对齐 |
| APY（复利） | \((1+R)^{365/\Delta days} - 1\) | 长期可比 |

窗口建议：`7d / 14d / 30d / 90d / YTD / since_inception`。

### 2.2 「全部费用」最终口径

| 口径 | EarnETH | Fluid Lite ETH |
| --- | --- | --- |
| **持仓净 APR/APY（主表）** | 仅用 \(P_t\)（已含 1%+10%） | 仅用 \(P_t\)（已含 20%） |
| **进出一轮净回报（辅表）** | \(R\) − 入金摩擦 − 出金摩擦（若可估） | \(R\) − **0.05% exit** − 入金摩擦 |
| **总额外奖励（可选）** | points / Obol / SSV（单独列，不并入主 APY） | KING 若未进 NAV 则单独列 |

原则：**份额价已内含的协议费不再二次扣减；只有份额价外的费用（如 Fluid exit fee、入金滑点）才额外扣。**

### 2.3 计价单位

- 统一报 **ETH 本位**回报（份额对应底层为 wstETH 时，用 `wstETH/stETH` 汇率折回 ETH，避免把 stETH rebase / wstETH 升值算成「策略 alpha」时口径混乱）。
- 同时可附 **USD 本位**（用 ETH/USD），但主对比用 ETH 本位。

### 2.4 不要直接当真相的数据

- UI 上的「当前 APY / 14d avg」：前瞻或短窗估计，不是历史已实现。
- DefiLlama `yields/chart`：有 Fluid Lite ETH 历史 APY（pool `e72916f7-a2d1-47ad-a4b9-2b054337cfd6`，自约 2023-02 起），但 **`pricePerShare` 为空**，且 APY 是协议上报快照，适合交叉验证，不适合作为唯一真相源。
- EarnETH 在 DefiLlama 上未见可靠同地址池；部署较新（UI 称 vault 约 2026-02），历史窗口短。

---

## 3. 数据源优先级

### Tier A — 链上份额价（推荐主路径）

1. Ethereum RPC `eth_call` 在历史 block 上读：
   - EarnETH：`totalAssets` / `totalSupply`（或 Mellow 等价 NAV 读法）
   - Fluid：`iETHv2.convertToAssets(1e18)` 或 `totalAssets/totalSupply`
2. 日频：每个 UTC 日取当日末尾 block（或固定小时）。
3. 依赖：可靠 archive RPC（Alchemy / QuickNode / 自建）。

### Tier B — 索引 API（加速 / 补洞）

- **vaults.fyi** Historical：`GET /v2/historical/mainnet/{vault}/sharePrice`（EarnETH 已在 vaults.fyi 收录；Fluid 需确认）。可能需 API key。
- **Mellow API** `api.mellow.finance/v1/vaults`：当前 APR/TVL；历史 share price 能力待核实（实现阶段探测）。
- **Instadapp / Fluid 官方 API**：兑换率历史（实现阶段探测；公开路由目前不稳定）。

### Tier C — 交叉验证

- DefiLlama：Fluid `e72916f7-...` APY 曲线 vs 我们从 \(P_t\) 反推的滚动年化。
- Lido UI / Mellow dashboard 当前 14d APY vs 我们近 14d 计算结果。

---

## 4. 实现步骤（获批后执行）

### Phase 0 — 合约与读接口确认（0.5–1 次迭代）

- [ ] 确认 EarnETH 是否标准 ERC-4626；若为 Mellow Core vault，确认 NAV / share 读法（`convertToAssets` vs oracle NAV）。
- [ ] 确认 Fluid `iETHv2` 的 asset 单位（ETH vs stETH）及 `previewRedeem` 是否含 exit fee。
- [ ] 确认 KING 入账路径：是否 mint 进 `totalAssets`。
- [ ] 记录 EarnETH 部署 block / 时间，作为 `since_inception` 起点。

### Phase 1 — 拉取日频份额价

- [ ] 脚本：`scripts/fetch_share_prices.py`（或 TS）
  - 输入：vault 地址、起止日期、RPC
  - 输出：`data/{vault}_share_price_daily.csv` → `date,block,totalAssets,totalSupply,sharePriceEth`
- [ ] Fluid 自有历史起；EarnETH 自部署日起。

### Phase 2 — 收益引擎

- [ ] `src/yield.py`：给定份额价序列，计算各窗口 \(R\)、APR、APY。
- [ ] Fluid 辅表：`R_net_exit = (1+R)*(1-0.0005)-1`。
- [ ] EarnETH：默认不再扣 1%/10%；文档中注明已内含。
- [ ] 可选：滚动 7d/30d 年化曲线，便于和 UI「14d avg」对齐。

### Phase 3 — 输出与对比

- [ ] 生成对比表（Markdown + JSON）：

```text
vault | window | net_return | apr | apy | fees_in_share_price | extra_fees_applied | notes
```

- [ ] README：口径说明、费用处理、数据源、已知偏差（排队、points、KING）。
- [ ] 用 DefiLlama Fluid 曲线做 sanity check（方向与量级，不要求逐点相等）。

### Phase 4 — 加固（可选）

- [ ] 入金滑点 / 路由成本估计。
- [ ] EarnETH 出金等待的机会成本情景分析。
- [ ] 若 archive RPC 贵：对 Fluid 优先 vaults.fyi / 官方历史，链上抽样校验。

---

## 5. 关键设计（建议）

```text
/
├── PLAN.md                 # 本方案
├── README.md               # 口径与如何复现
├── config/vaults.yaml      # 地址、费用、起点 block
├── scripts/
│   ├── fetch_share_prices.py
│   └── compare_yields.py
├── src/
│   ├── share_price.py      # RPC / API 读取
│   ├── fees.py             # 份额外费用（exit 等）
│   └── metrics.py          # R / APR / APY
└── data/                   # 生成的 CSV / JSON（可 gitignore 大体量）
```

技术栈倾向：**Python 3 + web3.py**（脚本向、易复现）；若需前端图表再另议。

---

## 6. 风险与已知偏差

1. **EarnETH 历史短**：部署约 2026-02，长周期（90d+）可能不可用。
2. **双重扣费陷阱**：UI/文档已说明费用进份额价；切勿再减 1%+10% 或 20%。
3. **Fluid exit fee**：持仓 APY ≠ 进出一轮净 APY。
4. **计价资产**：wstETH 升值 vs 策略 alpha 需拆开，否则和「纯 ETH 持有」不可比。
5. **奖励碎片**：points / KING / Obol 若未进 NAV，主表会低估真实总回报——应用脚注标明。
6. **负收益窗口**：杠杆金库（Fluid）与策略金库（EarnETH）在借贷利率/IL/再平衡下可能出现负 APR；引擎必须允许负值，不做截断。

---

## 7. 验收标准

- [ ] 两金库均可复现：给定日期窗口 → 净回报 / APR / APY。
- [ ] 费用说明与计算一致：份额内费用不重复扣；Fluid 辅表显式含 0.05% exit。
- [ ] 与至少一方外部来源（DefiLlama Fluid 或 Lido/Mellow 当前短窗 APY）量级一致。
- [ ] README 写清口径，任何人可用同一脚本复现数字。

---

## 8. 建议默认决策（实现时可直接采用）

| 议题 | 默认 |
| --- | --- |
| 主对比指标 | ETH 本位、份额价已扣协议费后的 **30d APY** + **since_inception APR** |
| Fluid 主表 | 不含 exit fee；辅表含 |
| EarnETH 主表 | 不含 points；脚注列出 |
| 数据主源 | 链上日频份额价 |
| 短窗对齐 UI | 额外报 14d APR（EarnETH UI 用 14d avg） |

---

**下一步**：确认本方案后，按 Phase 0 → 3 实现拉取脚本与对比表。
