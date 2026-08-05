---
name: scan
description: 全市场策略选股扫描：按当日涨跌幅、成交额、换手率、总市值、板块等条件过滤 A 股（约 5600 只），输出候选表；附带主力净流入（本地 zjlx 快照，如有）。结果缓存 10 分钟。当用户说「筛选/扫描今天哪些股票…」「主力资金流入的股票」「成交额大于 X 的」「帮我选股」时使用。反触发：看具体股票走势用 stock-trend；看板块用 block-list；模拟盘买入用 portfolio。
---

# scan — 全市场选股扫描

按条件过滤全市场 A 股，生成候选表，用于策略选股与纸面交易备选池。

## 使用

```bash
python3 market/skills/scan/scripts/scan.py [--block 板块] [--min-pct -3] [--max-pct 5] \
    [--min-amount 10] [--min-turnover 3] [--min-mcap 100] [--sort pct] [--top 30] [--json] [--refresh]
```

过滤条件（全部可选，未填不限制）：

- `--min-pct / --max-pct`：当日涨跌幅范围（%）
- `--min-amount`：最小成交额（亿元）
- `--min-turnover`：最小换手率（%）
- `--min-mcap`：最小总市值（亿元）
- `--block`：限定板块（代码 BKxxxx 或名称，如 `半导体`）——此时只扫板块内股票
- `--sort`：排序字段 `pct`(默认)/`amount`/`turnover`/`mcap`/`code`
- `--top N`：输出条数（默认 30）
- `--refresh`：忽略缓存强制重新拉取（全市场拉取约 57 页，首次 ~20 秒，之后 10 分钟内秒回）

## 输出示例

```
A 股全市场扫描（2026-08-05 14:45，共 5604 只）筛选 128 只，条件: 涨跌幅≥3%，成交额≥10亿，换手≥3%
代码      名称          现价     涨跌幅    成交额(亿) 换手%   市值(亿)  主力净流入(亿)
688432    有研硅       33.10   +17.98%    23.96   6.12    413.47    +13.28
...
```

## 数据流

1. 行情：`push2delay clist` 全市场（`f12,f14,f2,f3,f6,f8,f20,f21`，分页拉取）→ 缓存 `generated/em/scan_<yyyymmdd>.csv`（10 分钟 TTL）
2. 主力净流入：本地 `generated/em/*/zjlx_*.csv` 快照按代码 join（存在则显示，标注快照时间）
3. 板块限定：`fs=b:BKxxxx`（复用 `_shared/boards.py`）

## 与 portfolio 衔接

候选结果可直接模拟盘买入：`portfolio buy <代码> <数量> --note "scan 命中"`
