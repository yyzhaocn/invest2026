---
name: rainbow-indicators
description: Rainbow 七色指标检测（kaabar ch03，公式核对自作者仓库）：Red（布林带回归）、Orange（RSI8 回归）、Yellow（斜率背离）、Green（RSI 斜率翻转）、Blue（价格斜率 RSI）、Indigo（斐波那契结构）、Violet（HMA 交叉）七个去相关信号，可视化七色信号标记与 RSI 副图，输出结论。当用户说「某股票 Rainbow/七色指标信号」「作者个人指标」时使用。反触发：K's 指标用 k-indicators；经典信号用 signal；均线用 ma-signal-viz。
---

# rainbow-indicators — Rainbow 七色指标

作者 ch03 的七个个人指标（去相关设计，公式已对照作者仓库核实）。全部为 **次日信号**。

## 七色指标（公式已核对）

| 颜色 | 核心逻辑 | 看涨条件（镜像为看跌）|
|------|---------|---------------------|
| 🔴 Red | EMA 布林带(20,2σ) | 连续 3 根收于下轨下方后，重回带内 → 次日 |
| 🟠 Orange | RSI(8) 35/65 | RSI 从 5 根 <35 后回到 (35,50) → 次日 |
| 🟡 Yellow | RSI(14)+斜率(14) 背离 | RSI 斜率上穿 + 价格斜率仍负 + RSI<35 → 次日 |
| 🟢 Green | RSI(14) 斜率翻转 | 斜率由负转正 + RSI<35 → 次日 |
| 🔵 Blue | 价格斜率(5)→RSI(5) | RSI_斜率进 (30,35) 且低点更低 → 次日 |
| 🟣 Indigo | 斐波那契结构 | close 在 i-1..i-34 单调（1,2,3,5,8,13,21,34 差）→ 次日 |
| 🟤 Violet | HMA(20) 交叉 | 收盘上穿 HMA，且 i-1,2,3,5,8,13,21 均在下 → 次日 |

- slope 定义：`(val[i] − val[i−n]) / n`
- 触发频率低（部分需多根极端状态）—— 去相关低频高置信设计（ch01）

## 使用

```bash
python3 market/skills/rainbow-indicators/scripts/rainbow-indicators.py <股票代码> [--json]
```

## 输出

- 终端：七色信号统计 + 近 90 日信号清单 + 汇总结论（几色共振）
- PNG：K线 + 七色信号标记（每色不同 marker/颜色）+ RSI 副图 + 结论标题（`/tmp/rainbow_<code>.png` 自动打开）
- `--json`：结构化信号
