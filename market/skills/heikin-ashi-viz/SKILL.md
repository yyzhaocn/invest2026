---
name: heikin-ashi-viz
description: Heikin-Ashi 图表与趋势检测（kaabar ch04，公式核对自作者仓库）：HA close=(O+H+L+C)/4、HA open=(prev HA O+prev HA C)/2、HA high/low 取极值；检测 HA 连阳/连阴（趋势强度）、无影线强趋势、颜色翻转（趋势转折），可视化 HA K线与普通 K 线对比 + 趋势状态标注，输出结论。当用户说「某股票 Heikin-Ashi 看趋势」「HA 连阳几根了」时使用。反触发：普通K线形态用 pattern-detect；均线用 ma-signal-viz。
---

# heikin-ashi-viz — Heikin-Ashi 图表与趋势检测

Heikin-Ashi 过滤噪声、凸显趋势（ch04）。公式已对照作者仓库核实。

## 公式（已核对）

```
HA_close = (O + H + L + C) / 4
HA_open  = (prev HA_open + prev HA_close) / 2      # 首根 = 普通 open
HA_high  = max(H, HA_open, HA_close)
HA_low   = min(L, HA_open, HA_close)
```

## 趋势读数（ch04 框架）

| 信号 | 条件 | 含义 |
|------|------|------|
| 连阳 n 根 | 连续 n 根 HA 收阳 | 多头趋势强度（n≥3 确认）|
| 连阴 n 根 | 连续 n 根 HA 收阴 | 空头趋势强度 |
| 无影线 | HA 阳线无上影（close=high）| 强多头（追涨）|
| 颜色翻转 | 由阳转阴 | 趋势转折警示 |

## 使用

```bash
python3 market/skills/heikin-ashi-viz/scripts/heikin-ashi-viz.py <股票代码> [--json]
```

## 输出

- 终端：当前 HA 连阳/连阴计数、颜色翻转警示、趋势结论（与普通 K 线对比）
- PNG：上半 HA K线 + 下半普通 K 线对照，趋势状态标注（`/tmp/ha_<code>.png` 自动打开）
- `--json`：结构化趋势状态
