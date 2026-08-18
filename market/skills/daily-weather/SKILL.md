---
name: daily-weather
description: 全市场行情天气速览。基于全市场收盘/盘中快照输出市场广度（涨/跌/平家数、占比、平均/中位数涨跌、涨停/跌停、大涨大跌）、温度判定（强势普涨/偏强/震荡/偏弱/弱势），以及分板块（二级行业/一级行业/概念）涨跌平家数与平均涨幅（领涨/领跌板块）。当用户问「今天/昨天市场行情怎么样」「市场天气/温度」「全市场涨跌家数」「普涨还是普跌」「哪个板块最强/最弱」「market summary/weather/日报」时使用。反触发：只查单板块走势用 block-trend；只查板块列表用 block-list；只抓快照存档用 market-snapshot；单股分析用 multi-lens。数据来自 market-snapshot 技能写入的 heatmap_snapshots 存档。
---

# daily-weather — 全市场行情天气速览

一键生成全市场"天气报告"：广度、温度、分板块涨跌平家数、主线总结。

## 使用

```bash
python3 market/skills/daily-weather/scripts/daily-weather.py [--date YYYY-MM-DD] [--slot HHMM] \
    [--snapshot 路径] [--sector 二级行业|一级行业|概念] [--top N] [--json] [--html] [--out 路径]
```

参数：

- `--date`：交易日（如 `2026-08-17`）。省略时自动用最新可用快照。
- `--slot`：时点，可选 `0930/1000/1030/1100/1130/1400/1430/1500`。省略时自动挑该日最新可用。
- `--snapshot`：直接指定全市场快照 CSV（`market,code,chg_pct,...`），跳过自动选档。
- `--sector`：板块统计粒度，默认`二级行业`（128个），可选`一级行业`/`概念`。
- `--top N`：前后各显示多少领涨/领跌板块（默认 12）。
- `--json`：JSON 输出（含 breadth / verdict / sectors）。
- `--html`：生成自包含 embed HTML（默认 `generated/weather_{date}_{sector}.html`）。
- `--out`：HTML 输出路径（配合 `--html`）。

## 输出内容

1. **市场广度**：样本数、涨（占比%）、跌、平，平均/中位涨跌，涨停≈、跌停≈，大涨>5%、大跌<-5%
2. **温度判定**（按涨跌家数比 + 平均涨幅）：
   - 涨跌比≥3 且 均涨≥1.5% → `🔥 强势普涨`
   - 涨跌比≥1.5 且 均涨≥0.5% → `🌤 偏强`
   - 涨跌比≥0.8 且 均跌≥-0.3% → `🌥 震荡`
   - 涨跌比≥0.5 → `🌧 偏弱`
   - 否则 → `⛈ 弱势`
3. **分板块统计**：每板块成分数、覆盖家数、涨/跌/平、平均涨跌%——前 N 领涨 + 后 N 领跌
4. **`--html` 输出**：自包含 embed 页面，含市场卡片 + 领涨/领跌板块表；**悬停任一板块行即浮出该板块东财官方K线图（RSI副图）**（nid=90.BKxxxx，webquoteklinepic），点击板块名跳东财板块主页。板块名后带 **`个股` 按钮**——点击弹窗显示该板块成分股（**按当日PL/涨跌幅降序**），每条成分股同样可悬停看东财K线。可直接 iframe 嵌入笔记/网页。复用 block-kline 的 K_TIP 悬停机制。
5. **主线判断**：领涨板块的行业共性即当日主线（如电子/半导体链、农业链等）

## 数据流

- **快照来源**：`generated/heatmap_snapshots/snapshot_{YYYYMMDD}_{HHMM}.csv`，由 `market-snapshot` 技能写入（东财 stockhotmap API）。
- **板块成分**：复用 `_shared/boards.py`（`load_boards` + `fetch_block_stocks`，带1小时缓存 + 本地缓存）。
- 快照无快照时先用 `market-snapshot` 技能抓取对应日/时点。

## 示例

```bash
# 昨日收盘天气（文字）
python3 market/skills/daily-weather/scripts/daily-weather.py --date 2026-08-17 --slot 1500
# 生成 embed HTML（悬停板块查看东财K线）
python3 market/skills/daily-weather/scripts/daily-weather.py --date 2026-08-17 --slot 1500 --html
# 最新可用快照概览（自动选档）
python3 market/skills/daily-weather/scripts/daily-weather.py
# 概念板块粒度 + JSON
python3 market/skills/daily-weather/scripts/daily-weather.py --sector 概念 --json
```

## 板块悬停K线（--html）

HTML 中每行板块 `<tr class="hover-row" data-bk="BKxxxx">`，悬停时 JS 动态加载东财官方K线图（RSI副图）：

```text
https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=90.{BK}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={ts}
```

- `nid=90.{BK}`：板块指数专用前缀（个股用 0./1.）
- `timespan`=当前 epoch 秒，每次生成自动刷新保证图最新
- 与 `block-kline` 技能同一接口/机制

## 个股弹窗（板块行内「个股」链接）

每个板块名后是 `个股` 按钮（`.stk-hot`），点击弹窗（`.modal`）拉取该板块成分股，**按当日PL/涨跌幅降序**：

```text
https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=200&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:{BK}&fields=f12,f14,f2,f3,f20
```

- 弹窗表格：代码/名称/现价/涨跌%(红绿)/总市值；`fid=f3&po=1` 即按涨跌幅降序
- 弹窗内每一条成分股（`tr.hover-row`）同样可悬停看东财K线（个股 nid=0./1.{code}）
- `KTS`/`ktip`/`kimg`/`kname` 与板块悬停共用（同一 script 块内定义）

## 注意

- 涨停≈9.8%以上、跌停≈-9.8%以下为**粗口径近似**（科创板/创业板20cm也按此近似，统计涨停家数会偏保守）。精确涨停数依赖10%/20%区分，本技能用近似值。
- 板块抓取逐板块调用东财接口，含 0.25s 间隔防限流；概念板块503个耗时较长（约2-3分钟）。
- 若东财接口被风控（HTTP 0），先稍候或用 `--snapshot` 指定已存快照 + 已有 boards 缓存。
- 快照 chg_pct 即该时点涨跌幅；盘中时点为实时快照，收盘(1500)为收盘涨幅。
