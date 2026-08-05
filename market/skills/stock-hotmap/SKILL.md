---
name: stock-hotmap
description: 把指定板块（板块代码或名称）内全部股票生成为热力图（treemap）HTML —— 方块大小按市值/成交额，颜色按当日涨跌幅（红涨绿跌），悬停显示详情、点击跳转个股页。当用户说「某板块热力图」「板块股票热力图」「hotmap」「股票涨跌图」时使用。反触发：只要板块内列表用 stock-list --block；看板块走势用 block-trend。
---

# stock-hotmap — 板块股票热力图

将指定板块内全部股票渲染为自包含 HTML 热力图（treemap）：**方块面积 = 市值（或成交额/流通市值），颜色 = 当日涨跌幅**（A 股习惯红涨绿跌），悬停显示名称/现价/涨跌/成交额/换手/市值，点击跳转个股行情页。

## 使用

```bash
python3 market/skills/stock-hotmap/scripts/stock-hotmap.py <板块代码或名称> [--size 市值|流通市值|成交额] [--top N] [--output 路径] [--json]
```

参数：

- `板块`（必填）：板块代码（`BKxxxx`）或名称（如 `半导体材料`、`算力`），名称自动解析（概念+行业一/二/三级）。
- `--size`：方块面积字段：`市值`（默认，总市值）/ `流通市值` / `成交额`。
- `--top N`：只取面积前 N 只（默认 0 = 全部）。
- `--output, -o`：输出 HTML 路径，默认 `/tmp/stock_hotmap.html`。
- `--json`：输出 JSON 数据（不生成 HTML）。

## 产物

自包含单文件 HTML（无外部依赖），含：

- 标题：板块名（BK 代码）+ 数据时间 + 涨跌家数统计
- Treemap：squarified 布局，色阶红涨绿跌（±10% 封顶），中灰 = 平盘
- Tooltip：名称、代码、现价、涨跌幅、成交额、换手率、市值
- 点击方块 → 东方财富个股页（自动识别 沪/深/北）
- 图例 + 涨跌统计条

浏览器打开：`open /tmp/stock_hotmap.html`

## 数据流

1. 板块解析（复用 block-list 数据）：`_shared/boards.py resolve_block`
2. 板块内股票：`push2delay.eastmoney.com/api/qt/clist/get`，`fs=b:BKxxxx`，字段 `f12,f14,f2,f3,f6,f8,f20,f21`
3. 前端 squarified treemap 布局渲染
