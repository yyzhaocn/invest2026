---
name: divergence-detect
description: 价格与 RSI 背离检测（kaabar ch03/ch11 斜率背离技术）：识别最近摆动高低点上的顶背离（价格新高+RSI 未新高）与底背离（价格新低+RSI 未新低），可视化双面板（价格+RSI）+ 背离连线，输出结论。当用户说「某股票有没有顶/底背离」「RSI 背离分析」时使用。反触发：单K形态用 pattern-detect；均线用 ma-signal-viz；波动率用 volatility-detect。
---

# divergence-detect — RSI 背离检测

斜率背离（kaabar ch03 Yellow indicator / ch11 K's RSI² 基础技术）：价格与 RSI 创新高/低不同步 = 反转前兆。

## 使用

```bash
python3 market/skills/divergence-detect/scripts/divergence-detect.py <股票代码> [--window 5] [--rsi 14] [--json]
```

参数：

- `--window`：摆动点窗口（默认 5）
- `--rsi`：RSI 周期（默认 14）

## 检测

| 背离 | 条件 |
|------|------|
| 顶背离 | 价格创更高高点的同时 RSI 未创新高 → 看跌反转前兆 |
| 底背离 | 价格创更低低点的同时 RSI 未创新低 → 看涨反转前兆 |

- 用最近两个摆动高点/低点对比价格与 RSI 极值
- 背离 = 价格极值方向与 RSI 极值方向相反

## 输出

- 终端：摆动点、价格/RSI 极值对比、背离类型与结论
- PNG：上价格K线 + 下 RSI 双面板，背离摆动点连线标注（`/tmp/divergence_<code>.png` 自动打开）
- `--json`：结构化结果
