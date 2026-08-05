---
name: stock-list
description: 查询 A 股股票代码列表并搜索个股。支持按股票代码前缀、名称子串搜索，返回代码、名称、市场板块、拼音；代码查询附带本地快照最新涨跌幅。数据来自东方财富 suggest 接口（实时）与本地行情快照。当用户问「某股票的代码是多少」「有哪些股票叫 XX」「列一下代码 600 开头的股票」时使用。反触发：算某基金盈亏用 fund-pl；看个股/基金走势用 stock-trend / fund-trend。
---

# stock-list — 股票代码查询

按股票代码前缀或名称搜索 A 股个股，输出代码、名称、市场板块、拼音，代码查询附带本地最新行情快照的涨跌幅。

## 使用

```bash
python3 market/skills/stock-list/scripts/stock-list.py [<查询词>] [--top N] [--market 市场] [--json]
```

参数：

- `查询词`（可选）：股票代码前缀（如 `688256`、`6005`）或名称子串（如 `寒武纪`、`平安`）。**省略时列出全市场 A 股前 N 只**（按代码序，实时 clist 接口）。
- `--top N`：最多显示 N 条（默认 15）。
- `--market`：市场过滤（模糊包含），如 `沪`、`深`、`科创`、`创业`、`北`。
- `--json`：输出 JSON。
- 默认排除港股/美股/三板/退市，如需包含用 `--all`。

## 输出示例

```
搜索 '688256'（匹配 1 条，本地快照 2026-07-30）:
代码      名称    市场    拼音    最新涨跌幅
688256   寒武纪   科创板   HWJ    +6.76%
```

## 数据源

- **名称/代码搜索**：东方财富 suggest 接口 `searchapi.eastmoney.com/api/suggest/get`（实时，返回 Code/Name/PinYin/SecurityTypeName）
- **全市场列表**：东方财富 clist 接口 `push2delay.eastmoney.com/api/qt/clist/get`（实时，沪深京 A 股约 5600 只，含现价/涨跌幅）
- **涨跌幅补充**：本地最新行情快照 `generated/em/<date>/quote_<date>_latest.csv`（代码查询时附带当日涨跌幅）；快照日期较旧时仅供参考

## 与 stock-trend 的关系

拿到股票代码后，如需看近期走势，使用 `stock-trend` 技能：

```bash
python3 market/skills/stock-trend/scripts/stock-trend.py <股票代码>
```
