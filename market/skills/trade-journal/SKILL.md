---
name: trade-journal
description: 纸面交易复盘：列出全部交易流水（含买卖理由），统计已实现盈亏、胜率、盈亏比、平均盈利/亏损、单笔最大亏损、持仓周期等复盘指标；可为持仓添加/更新备注。数据来自 shared/paper/trades.csv 与 portfolio.json（由 portfolio 技能写入）。当用户说「复盘我的交易」「交易记录/胜率/盈亏比」「给持仓加个备注」时使用。反触发：买卖记账用 portfolio；看净值曲线用 performance。
---

# trade-journal — 交易复盘

读取 portfolio 技能写入的交易流水与持仓，输出复盘报告：逐笔流水 + 统计指标。

## 使用

```bash
python3 market/skills/trade-journal/scripts/trade-journal.py list [--all]
python3 market/skills/trade-journal/scripts/trade-journal.py review [--json]
python3 market/skills/trade-journal/scripts/trade-journal.py note <代码> <备注>
python3 market/skills/trade-journal/scripts/trade-journal.py clear
```

多组合：加 `--account <账户名>` 复盘指定账户（默认 `main`），数据源 `shared/paper/<账户>/`。

命令：

- `list`：交易流水（默认只看卖出/已实现盈亏；`--all` 显示全部含买入）
- `review`：复盘统计 —— 已实现盈亏、胜率（卖出笔数中盈利占比）、盈亏比、平均盈/亏、单笔最大亏损、持仓天数（买卖配对）
- `note <代码> <备注>`：给持仓加备注（显示在 portfolio show 与 list 中）
- `clear`：清空全部流水（`--force` 确认）

## 复盘指标口径

- **已实现盈亏**：卖出时按均价法结算（见 portfolio sell）
- **胜率**：已了结卖出笔数中 realized_pnl > 0 的占比
- **盈亏比**：平均盈利 / 平均亏损（绝对值）
- **持仓天数**：同一代码按时间配对的 buy→sell 平均持有天数
- 未平仓的浮动盈亏不计入胜率/盈亏比，但计入流水明细

## 数据源

- `shared/paper/trades.csv`（流水，portfolio 写入）
- `shared/paper/portfolio.json`（当前持仓与备注）
