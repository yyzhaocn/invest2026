---
name: fund_list
description: 获取东方财富基金代码列表并搜索基金。支持按基金代码前缀、名称子串、拼音简拼查询；数据源为本地缓存（fund/fundcode_search.js 含基金类型、fund/fundcode.csv 含持仓图链接）或网络刷新。当用户问「有哪些基金」「帮我找某基金代码」「基金代码是多少」「列出某类型的基金」时使用。
---

# fund_list — 基金代码列表查询

查询东方财富全部基金（约 2.5 万只）的代码、名称、类型，并支持按代码 / 名称 / 拼音搜索。

## 使用

```bash
python3 market/skills/fund_list/scripts/fund_list.py <查询词> [--top N] [--type 类型] [--refresh]
```

参数：

- `查询词`（可选）：基金代码前缀、名称子串或拼音简拼（如 `161631`、`人工智能`、`ZHRGZN`）。缺省列出前 20 条。
- `--top N`：最多显示 N 条（默认 20，`-1` 显示全部）。
- `--type 类型`：按类型过滤，如 `指数型`、`混合型`、`股票型`（支持模糊包含）。
- `--refresh`：从网络 `http://fund.eastmoney.com/js/fundcode_search.js` 刷新本地缓存后再查询。

## 数据源

本地优先（免网络、快）：

| 文件 | 内容 |
|------|------|
| `fund/fundcode_search.js` | `[代码, 拼音简拼, 名称, 类型, 全拼]`，官方每日更新 |
| `fund/fundcode.csv` | `fundcode,fundname,holders`（持仓图链接） |

缓存缺失或过期时用 `--refresh` 从东方财富拉取最新列表。

## 输出示例

```
匹配 3 条 (共 25878 只基金):
代码      名称                      类型
161631    融通人工智能指数(LOF)A     指数型-股票
013942    融通人工智能指数(LOF)C     指数型-股票
...
```

## 与 fund_pl 的关系

拿到基金代码后，如需计算该基金当日持仓预计盈亏，使用 `fund_pl` 技能：

```bash
python3 market/skills/fund_pl/scripts/fund_pl.py <基金代码>
```
