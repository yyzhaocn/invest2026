---
name: data-zjlx
description: 拉取东财全市场资金流向（zjlx）快照 CSV（主力净流入/超大单/大单等全字段），保存到 generated/em/YYMMDD/，供 scan 等技能 join 主力净流入。当用户说「补全 zjlx 数据」「拉资金流向快照」「更新主力资金数据」时使用。反触发：单股资金流图用 flow-chart；板块资金流看 block-list。
---

# data-zjlx — 全市场资金流向快照

拉取东财全市场资金流向（约 5290 只），生成与 scan.py 兼容的 zjlx CSV。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/data-zjlx/scripts/data-zjlx.py [--out 目录] [--json]
```

- 默认输出：`cwd/generated/em/YYMMDD/zjlx_zlb_YYYYMMDDHHMM.csv`
- `--out`：指定目录（如 atime 存档目录）
- `--json`：输出 JSON 摘要（path/count/asof）

## 数据源与格式

- 接口：`push2delay /api/qt/clist/get`，`fid=f62`（主力净流入排序），`fs` = 全市场 7 段（沪深主板/创业/科创/B股）
- 字段：27 个东财字段 → 38 列表头（与 scan.py 读取的 `代码` + `主力净流入` 兼容）
- 编码：utf-8-sig（带 BOM，scan 用 utf-8-sig 读取）

## ⚠️ 分页坑（实测 2026-08-07）

push2delay 深分页每页**最多 100 条**：统一 `pz=100` 从 `pn=1` 拉到底（约 53 页）。
**切勿 pz=200 混用**——offset 错位会导致 3000 只后重复/缺失（本 skill 已内置按代码去重兜底）。

## 依赖

- `curl`（WAF 对 Python TLS 指纹拦截，必须走 curl 子进程）
- 网络出口需能访问 push2delay（东财国内直连，不受代理影响）

## 与 scan 衔接

```bash
data-zjlx.py && scan.py --min-pct 5 --min-amount 10   # 先补资金流，再扫描带主力净流入
```

scan 自动取 `generated/em/*/zjlx_*.csv` 最新一份 join（flow_asof 显示快照时间）。
