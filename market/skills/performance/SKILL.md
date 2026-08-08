---
name: performance
description: 纸面交易组合绩效：记录每日净值快照（幂等），生成净值曲线 HTML 与区间统计（总收益、最大回撤、日收益、与沪深300对比）。数据来自 shared/paper/snapshots.csv（由 performance snapshot 写入）。当用户说「我的组合收益怎么样」「净值曲线」「回撤」「performance/report」时使用。反触发：单笔交易复盘用 trade-journal；持仓明细用 portfolio show。
---

# performance — 组合绩效与净值曲线

每日对组合记一次净值快照，累计生成净值曲线与绩效统计。

## 使用

```bash
python3 market/skills/performance/scripts/performance.py snapshot
python3 market/skills/performance/scripts/performance.py report [--days N] [--out 路径] [--no-benchmark]
python3 market/skills/performance/scripts/performance.py list
```

多组合：加 `--account <账户名>`（默认 `main`），快照/报告按账户独立（`shared/paper/<账户>/snapshots.csv`）。

命令：

- `snapshot`：记录今日组合净值（幂等，同日多次运行只保留最新）。**建议每个交易日收盘后运行一次**
- `report`：生成绩效报告 —— 终端摘要（区间收益/最大回撤/日均）+ 自包含 HTML 净值曲线（`/tmp/portfolio_perf.html`，含沪深300 基准对比）
- `list`：快照明细表
- `--days N`：报告最近 N 个快照（默认全部）
- `--no-benchmark`：跳过沪深300 对比（默认自动拉取，失败则跳过）

## 绩效口径

- **组合净值** = 现金 + 持仓市值（持仓按当日实时行情 / 基金最新净值估值）
- **区间收益** = 期末净值 / 期初净值 - 1
- **最大回撤** = max(峰顶 → 谷底跌幅)
- **基准**：沪深300（000300）收盘指数，对齐快照日期
- 总收益以初始资金为基准（`portfolio init --cash`）

## 数据流

- 快照写入 `shared/paper/snapshots.csv`
- 报告读取快照 + 沪深300 日 K（`push2his` `1.000300`）
