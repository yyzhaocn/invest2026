---
name: ma-signal-viz
description: 现代均线信号可视化（kaabar ch03）：对任意股票计算 SMA/WMA/IWMA/HMA/KAMA 五线，检测金叉/死叉（含 WMA/IWMA 单参数交叉）、多空排列，可视化均线叠图 + 交叉标记 + 买卖区间底色，输出最新信号结论。当用户说「某股票均线金叉/死叉了吗」「画均线图」「HMA/KAMA 信号」时使用。反触发：单K形态用 pattern-detect；趋势走势用 stock-trend；信号扫描用 signal。
---

# ma-signal-viz — 现代均线信号可视化

ch03 现代均线（SMA/WMA/IWMA/HMA/KAMA）的金叉死叉检测 + 可视化。

## 使用

```bash
python3 market/skills/ma-signal-viz/scripts/ma-signal-viz.py <股票代码> [--lookback 20] [--json]
```

参数：

- `--lookback N`：均线周期（默认 20，HMA/KAMA 自动派生）

## 信号（kaabar ch03）

| 信号 | 条件 |
|------|------|
| 金叉 | 短期均线（SMA5）上穿长期（SMA20）|
| 死叉 | SMA5 下穿 SMA20 |
| WMA/IWMA 交叉 | WMA 上穿 IWMA（单参数交叉，去相关）|
| 多空排列 | 价格 > SMA5 > SMA20（多头）/ 反之（空头）|
| HMA/KAMA | 价格相对位置（低滞后/自适应）|

## 输出

- 终端：五线最新值、近 10 日交叉事件、最新信号结论
- PNG：K线 + SMA5/20 + WMA/IWMA + HMA + KAMA 五色线 + 金叉/死叉标记 + 多头/空头区间底色（`/tmp/ma_<code>.png` 自动打开）
- `--json`：结构化信号
