---
name: portfolio
description: 纸面交易（模拟盘）组合管理中枢：初始化模拟资金、买入/卖出股票或基金记账（默认按实时行情/最新净值成交）、查看持仓与浮动盈亏/仓位占比。数据持久化在 shared/paper/（git 忽略）。当用户说「模拟盘买入/卖出」「建个模拟组合」「查看我的持仓/仓位」「paper trading」时使用。反触发：只查行情/走势用 stock-trend / fund-trend；复盘交易用 trade-journal；看净值曲线用 performance。
---

# portfolio — 纸面交易组合管理

模拟盘组合中枢：现金 + 持仓 + 交易流水，支持股票（实时行情成交）与基金（最新净值成交）。

## 使用

```bash
python3 market/skills/portfolio/scripts/portfolio.py init [--cash 100000] [--force]
python3 market/skills/portfolio/scripts/portfolio.py buy <代码> <数量> [--price P] [--note 买入理由]
python3 market/skills/portfolio/scripts/portfolio.py sell <代码> <数量> [--price P] [--note 卖出理由]
python3 market/skills/portfolio/scripts/portfolio.py add-cash <金额>
python3 market/skills/portfolio/scripts/portfolio.py show [--json]
```

所有命令支持 `--account <账户名>`（**多组合**）：默认 `main`（兼容旧数据，存 `shared/paper/` 根目录）；命名账户存 `shared/paper/<账户>/`，数据完全隔离。示例：

```bash
portfolio.py --account momentum init --cash 200000   # 动量账户
portfolio.py --account value buy 161631 5000 --note 定投
portfolio.py --account momentum show                  # 只查 momentum
```

命令：

- `init`：初始化组合（默认初始资金 10 万；已存在时需 `--force` 重置）
- `buy <代码> <数量>`：买入。股票按实时行情成交（`--price` 可覆盖），**A 股默认按 100 股整手校验**（`--allow-odd` 放行）；基金按最新净值成交
- `sell <代码> <数量>`：卖出，自动计算**已实现盈亏**（均价法）
- `add-cash <金额>`：入金（正数）/ 出金（负数）
- `show`：持仓表（成本/现价/市值/浮动盈亏/占比）+ 现金 + 组合总市值与总盈亏

## 输出示例

```
现金 90,000.00 ｜ 持仓市值 12,240.00 ｜ 总市值 102,240.00 ｜ 总盈亏 +2,240.00 (+2.24%)
代码    名称          类型  数量   成本    现价    市值      盈亏      盈亏%   仓位%
600600  青岛啤酒     股票  100    52.00   53.80  5,380    +180.00  +3.46%  52.6%
161631  融通人工智能 基金  2000   2.70    2.88   5,760    +360.00  +6.67%  47.4%
```

## 数据流

- 行情：`_shared/paper.py`（股票 push2delay ulist 实时；基金 pingzhongdata 最新净值）
- 持久化：`shared/paper/<账户>/portfolio.json` + `trades.csv`（`main` 账户在根目录；买入卖出均记流水，含理由 note）
- 卖出自动按均价法记已实现盈亏，供 `trade-journal` 复盘（`trade-journal --account <名>`）
- 绩效：`performance --account <名> snapshot/report`

## 注意事项

- 手续费默认忽略（模拟盘）；基金申购赎回费忽略
- 停牌/无行情标的需 `--price` 手动指定
- 全卖后持仓自动移除，但流水保留
