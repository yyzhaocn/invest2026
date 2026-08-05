---
name: stock-hotmap-snapshot
description: 生成全市场热力图数据快照 CSV（market,code,chg_pct,流通市值,总市值），格式与 stock 应用 heatmap_snapshots/ 目录一致（按流通市值降序）。供全市场 treemap 热力图渲染。当用户说「补全今天的热力图数据」「全市场 heatmap 快照」「stockhotmap 数据」时使用。反触发：单板块热力图用 stock-hotmap；资金流用 flow-chart。
---

# stock-hotmap-snapshot — 全市场热力图快照

拉取全市场 A 股（约 5600 只）涨跌幅与市值，生成与 `generated/heatmap_snapshots/` 原格式一致的数据快照，供热力图前端渲染。

## 使用

```bash
python3 market/skills/stock-hotmap-snapshot/scripts/stock-hotmap-snapshot.py [--out 路径] [--json]
python3 market/skills/stock-hotmap-snapshot/scripts/stock-hotmap-snapshot.py --watch   # 交易时段自动打快照
```

参数：

- `--out, -o`：输出路径，默认 `generated/heatmap_snapshots/snapshot_<YYYYMMDD_HHMM>.csv`
- `--watch`：**交易时段自动模式** —— 按历史节奏（09:31 / 10:00 / 10:30 / 11:00 / 11:30 / 14:00 / 14:30 / 15:00）每 30 分钟自动打一张，午休跳过，收盘（15:00）后退出；非交易日直接退出
- `--json`：输出 JSON（统计信息）

## 输出格式（与原快照逐字段对齐）

```
market,code,chg_pct,vol_rank,amt_rank
SH,601288,-1.97,2068702,2267890
...
```

| 字段 | 含义 | 单位 |
|------|------|------|
| market | SH（6xx）/ SZ（其余） | — |
| code | 6 位代码 | — |
| chg_pct | 当日涨跌幅 | % |
| vol_rank | **流通市值**（历史命名误导，实为市值） | 百万元 |
| amt_rank | **总市值** | 百万元 |
| 排序 | 按流通市值降序 | — |

## 数据流

- 行情：`push2delay clist` 全市场分页（`f12,f3,f20,f21`，约 57 页，~20 秒）
- 去重后按流通市值降序落盘（utf-8，无 BOM，与历史快照一致）

## 用途

- 生成后可喂给热力图前端（treemap：面积 = 流通市值，颜色 = 涨跌幅）
- **收盘后（15:05+）运行**取当日最终数据；或盘中 `--watch` 自动按 30 分钟节奏打全天快照
- 历史快照在 `generated/heatmap_snapshots/`（07-13/07-15 全天 8 时点 + 08-05 收盘）
