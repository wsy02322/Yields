# Yields

两金库历史净收益（含费用）计算项目。

当前状态：**方案阶段**。详见 [PLAN.md](./PLAN.md)。

## 覆盖范围

1. [Lido EarnETH](https://stake.lido.fi/earn/eth/deposit)
2. [Fluid Lite ETH Vault](https://lite.guides.instadapp.io/getting-started/fluid-lite-eth-vault)

## 核心口径（摘要）

- 主指标：日频份额价格变化 → 持有期净回报 / APR / APY
- 协议费（EarnETH 1%+10%、Fluid 20% performance）已体现在份额价中，**不再二次扣除**
- Fluid 出金 **0.05% exit fee** 仅在「进出一轮」辅表中扣除
