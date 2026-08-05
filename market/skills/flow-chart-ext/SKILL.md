---
name: flow-chart-ext
description: 个股资金流向深度图表（复用 stock/app.py generate_flow_chart 的 plot_hist_flow）：生成 8 面板 matplotlib PNG —— 实时资金流向、历史主力资金趋势、日涨幅/累计、主力累计、K线+MA、成交量、RSI、MACD；带 hist_chart_cache 缓存策略（--force/--clear）。同时输出逐日资金流与 N 日累计的终端摘要。当用户说「画个股资金流向深度图/专业图表」「主力吸筹图」「flow chart 图片」时使用。反触发：要交互式 HTML 资金流图用 flow-chart；看价格走势用 stock-trend。
---

# flow-chart-ext — 个股资金流向深度图表（PNG）

复用 `stock/app.py` 的 `generate_flow_chart` 逻辑（`utils_cap.plot_hist_flow`），生成专业 8 面板资金流分析图，与股票 Web 应用同款。

## 使用

```bash
python3 market/skills/flow-chart-ext/scripts/flow-chart-ext.py <代码> [--days N] [--out 路径] [--force] [--clear] [--no-cache] [--json]
```

参数：

- `<代码>`（必填）：股票代码，如 `603776`
- `--days N`：资金流/K线显示最近 N 个交易日（默认 80）
- `--out, -o`：PNG 输出路径（默认 `generated/cache/stockd/charts/hist_flow_<code>_<date>.png`，与 Web 应用缓存同目录）
- `--force`：忽略缓存强制重新生成
- `--clear`：清除该股历史图表缓存并重新生成
- `--no-cache`：拉取资金流数据时不用 CSV 缓存
- `--json`：输出 JSON（含图表路径 + 资金流摘要）

## 图表内容（8 面板）

| 位置 | 内容 |
|------|------|
| 左上 | 当日实时资金流向（主力/超大单/大单/中单/小单） |
| 左中上 | 历史主力资金流向趋势（日柱） |
| 左中下 | 日涨幅与累积涨幅 |
| 左下 | 历史资金流向累积趋势 |
| 右侧 4 面板 | K线+MA5/10/20/30、成交量、RSI(70/30线)、MACD |

## 缓存策略（与 app.py 一致）

- 图表按 `generated/cache/stockd/charts/hist_flow_<code>_<date>.png` 缓存，交易时段 5 分钟内复用
- 资金流 CSV 缓存于 `generated/cache/stockd/`（`get_hist_flow` 内部处理）
- `--force` / `--clear` 可强制刷新

## ⚠️ 已知注意

- `utils_cap.get_hist_flow` 的**超大单/大单/中单/小单列名与接口实际顺序不一致**（接口为 小单/中单/大单/超大单）—— 图表中的分项可能错位，但**主力净流入列正确**；本技能的终端摘要按接口真实口径输出
- 终端资金流摘要带重试；接口限流/网络异常时**自动降级**（图表仍正常生成，摘要跳过）
- 需 matplotlib（已随 stock 依赖安装），中文字体用 SimHei
