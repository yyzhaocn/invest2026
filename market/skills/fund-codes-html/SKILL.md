---
name: fund-codes-html
description: 将东方财富全部基金代码列表生成为自包含的可搜索 HTML 页面（代码/名称/拼音/类型实时过滤，点击跳转基金主页）。默认输出 /tmp/fund_codes.html，可用 --output 指定路径；--refresh 先从网络更新本地缓存。当用户要求「基金列表做成 HTML」「导出基金代码网页」「fund codes as html」时使用。反触发：只查代码/名称用 fund-list；算盈亏用 fund-pl；看走势用 fund-trend。
---

# fund-codes-html — 基金代码列表 HTML

把东方财富基金列表生成为一个**自包含**（无外部依赖）的可搜索 HTML 页面。

**默认排除债券类基金**（类型含「债」或「固收」：债券型-*、QDII-纯债/混合债、混合型-偏债、指数型-固收等；货币型保留），如需包含用 `--include-bonds`。

## 使用

```bash
python3 market/skills/fund-codes-html/scripts/fund-codes-html.py [--output /path/to/fund_codes.html] [--refresh] [--include-bonds]
```

参数：

- `--output, -o`：输出路径，默认 `/tmp/fund_codes.html`。
- `--refresh`：先从网络 `http://fund.eastmoney.com/js/fundcode_search.js` 刷新本地缓存（`fund/fundcode_search.js`）再生成。
- `--include-bonds`：包含债券型基金（默认排除）。
- `--top N`：仅嵌入前 N 只（调试用，默认全部）。

## 产物

单文件 HTML（约 3 MB），含：

- 顶部 sticky 搜索框：按 **代码前缀 / 名称 / 拼音简拼 / 类型** 实时过滤
- 表格：代码、名称、类型（sticky 表头、斑马纹），点击跳转 `fund.eastmoney.com/{code}.html`
- 顶部显示总基金数与当前匹配数

## 数据流

1. （可选）`--refresh` 拉取东方财富 `fundcode_search.js` 覆盖 `fund/fundcode_search.js`
2. 解析本地 JS 缓存 → JSON 数组 `[代码, 拼音简拼, 名称, 类型, 全拼]`
3. 嵌入 HTML 模板，页面刷新时间写入 meta 行

浏览器打开即可使用：`open /tmp/fund_codes.html`
