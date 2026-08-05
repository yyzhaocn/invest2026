---
name: backtest
description: 简单策略回测：对单只股票回测 MA 金叉/动量/买入持有策略，输出与买入持有的收益对比、最大回撤、胜率、交易明细，可生成净值曲线 HTML。数据来自东方财富日 K（前复权）。当用户说「回测一下 MA 金叉策略」「这个股票用动量策略收益如何」「策略回测」时使用。反触发：只看当前信号用 signal；仓位风控用 position-size。
---

# backtest — 简单策略回测

对单只股票运行规则策略回测（收盘价信号、次日开盘成交、全仓、100 股整手），输出绩效与交易明细。

## 使用

```bash
python3 market/skills/backtest/scripts/backtest.py <代码> \
    [--strategy ma-cross|momentum|buy-hold] [--ma-fast 5] [--ma-slow 20] \
    [--mom-window 20] [--mom-thresh 5] \
    [--start 2025-01-01] [--initial 100000] [--fee 0.0005] [--out 路径] [--json]
```

参数：

- `--strategy`：`ma-cross`（默认，MA 金叉买/死叉卖）、`momentum`（动量：近 N 日涨幅 > 阈值持有，转负卖出）、`buy-hold`（买入持有基准）
- `--ma-fast / --ma-slow`：MA 参数（默认 5/20）
- `--mom-window / --mom-thresh`：动量窗口/阈值 %（默认 20 日 / 5%）
- `--start`：回测起始日（默认全部数据）
- `--initial`：初始资金（默认 10 万）
- `--fee`：单边费率（默认 0.05%）
- `--out`：生成净值曲线 HTML（默认 `/tmp/backtest.html`）

## 输出

- 策略 vs 买入持有：区间收益、最大回撤、年化
- 交易明细：买卖日期/价格/持仓天数/单笔盈亏、胜率、交易次数、平均持仓
- `--out`：净值曲线（策略 vs 基准）HTML

## 口径

- 信号基于收盘价；**次日开盘成交**；全仓进出；100 股整手；单边费率默认 0.05%（佣金+印花税简化）
- 不计算停牌/涨跌停无法成交等约束（简化模拟盘参考）
