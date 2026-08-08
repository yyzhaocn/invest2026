---
name: divergence-monitor
description: 每日盘后背离监控：扫描组合持仓/板块的 RSI 背离，与上次结果对比，报告新增/消失背离并生成 Markdown 日报（含顶背离减仓预警）。当用户说「每日背离监控」「定时扫描背离」「背离日报」时使用。反触发：单次扫描用 divergence-scan；单股背离用 divergence-detect。
---

# divergence-monitor — 每日背离监控日报

盘后扫描组合/板块背离，对比上次结果报告**新增/消失**背离，输出 Markdown 日报。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/divergence-monitor/scripts/divergence-monitor.py --account 7维选股
python3 .../divergence-monitor.py --account 7维选股 --blocks BK0448,BK1033
python3 .../divergence-monitor.py --blocks BK0448 --out report.md
python3 .../divergence-monitor.py --account 7维选股 --full   # 全部背离（非仅新增）
```

## 输出

- Terminal 日报 + `generated/divergence_monitor/<日期>.md`
- 快照 JSON：`generated/divergence_monitor/<日期>.json`（次日对比用）
- 对比逻辑：报告**新增**背离（上次没有的）；--full 显示全部

## Cron 定时（每日盘后 15:30）

```cron
30 15 * * 1-5 cd /Users/yyz/pydev/invest2026 && /usr/bin/python3 /Users/yyz/.agents/skills/stock/divergence-monitor/scripts/divergence-monitor.py --account 7维选股 >> /tmp/divergence_monitor.log 2>&1
```

安装：`crontab -e` 粘贴上面一行（周一到周五 15:30 收盘后运行）。

## 依赖

- `divergence-scan`（算法，importlib 加载——路径: 兄弟 skill 目录）
- `_shared/kline.py`（带 5 分钟缓存，监控快）
- `portfolio`（--account 读持仓）

## 监控价值

- **顶背离新增** = 减仓预警（如华天科技 07-13 顶背离 → 07-15 四连跌停，--end-date 验证过可提前发现）
- **底背离新增** = 反转候选（组合内 13 只底背离 = 超跌动量先行）
- 与 portfolio-review 组合使用：背离 → 减仓建议 → 执行
