---
name: portfolio-review
description: 组合持仓综合复盘表：同时显示每只股票建仓时间、7维级别、技术信号与减仓建议（超买/新高/浮亏自动规则）。当用户说「股票列表显示建仓时间」「持仓减仓建议」「组合复盘表」时使用。反触发：只看持仓行情用 portfolio show；交易流水复盘用 trade-journal。
---

# portfolio-review — 组合持仓复盘表（建仓时间+信号+建议）

一键生成组合复盘表：**建仓时间 ｜ 7维级别 ｜ 技术信号 ｜ 浮盈 ｜ 减仓建议**。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/portfolio-review/scripts/portfolio-review.py --account 7维选股
python3 .../portfolio-review.py --account 7维选股 --lens "603435:3多0空,300409:3多1空"
python3 .../portfolio-review.py --account 基金持仓 --json
```

- `--account`：组合账户（默认 main）
- `--lens`：7维级别映射（`code:label` 逗号分隔，可选——不传显示 ?）
- `--json`：JSON 输出

## 数据源

1. `portfolio show --json` → 持仓/现价/浮盈/仓位
2. `shared/paper/<账户>/trades.csv` → 建仓时间（ts 精确到分）
3. `signal --portfolio --account --json` → 技术信号列表（新高/超买/放量/金叉…）

## 减仓建议规则（Grimes 纪律简化）

| 条件 | 建议 |
|---|---|
| 超买 + 新高 + 浮盈 > 0 | 🔴 止盈 1/3 |
| 超买 + 浮盈 > 0 | 🟡 减 1/4 |
| 浮亏 ≤ -2.5% | 🟢 破位减半（设止损） |
| 浮亏 < 0 | 🟢 浮亏观察（守成本） |
| 新高 + 放量 | 🟠 持有观察 |
| 其他 | ✅ 持有 |

## 依赖与注意

- 依赖 `portfolio` / `signal` 技能（同一环境，双端同步）
- signal 输出字段为 `signals` 列表（非 signal 字符串）
- 建议为规则引擎粗筛，止损/止盈价位需结合 7 维关键位（61.8%/S20）人工确认
- `--lens` 映射可用 multi-lens 扫描结果回填（或手动维护）

## 典型用途

- 每日收盘后快速过一遍持仓（哪些该止盈/止损）
- 建仓批次复盘（按建仓时间排序看成本与逻辑）
