---
name: k-indicators
description: K's 指标族检测（kaabar ch11，公式核对自作者 GitHub 仓库）：K's Reversal I（MACD+布林带触发）、K's Reversal II（21 根 SMA13 极端状态，价格+时间+均线三维）、K's RSI²（RSI 的 RSI 背离）。可视化信号图，输出结论。当用户说「某股票 K's 指标/现代反转信号」「K's Reversal 信号」时使用。反触发：经典指标用 signal；均线用 ma-signal-viz；单K形态用 pattern-detect。
---

# k-indicators — K's 指标族检测

作者原创「新一代」指标（ch11），公式已对照 `sofienkaabar/mastering-financial-markets-in-python` 核实。设计目标：与经典指标去相关（ch01 边际预测原则）。

## 指标（公式已核对）

### K's Reversal Indicator I（MACD + 布林带）
- 输入：MACD(12,26,9) + 布林带(100, 2σ)
- **看涨**：low < 下轨 且 high < 中轨 且 MACD_line 上穿 MACD_signal → **次日**信号
- **看跌**：high > 上轨 且 low > 中轨 且 MACD_line 下穿 MACD_signal → **次日**信号

### K's Reversal Indicator II（价格+时间+均线三维）
- SMA13；`above = close > SMA13`；`pct = above.rolling(21).sum()/21×100`
- **看涨**：pct 从 >0 变为 ==0（连续 21 根全部收在 SMA13 下方 = 极度超卖）→ 次日信号
- **看跌**：pct 从 <100 变为 ==100（连续 21 根全部收在上方 = 极度超买）→ 次日信号
- 作者的「三维」去相关信号：价格 vs 均线 × 时间计数

### K's RSI²（RSI 的 RSI）
- `RSI² = RSI(RSI(close, 14), 14)`——对 RSI 再做一次 RSI
- 用于检测 RSI 的二次背离（RSI² 双线背离），信号更平滑

## 使用

```bash
python3 market/skills/k-indicators/scripts/k-indicators.py <股票代码> [--json]
```

## 输出

- 终端：三指标当前状态 + 近 60 日信号清单 + 结论（信号频率/方向）
- PNG：K线 + SMA13/布林带 + K's Reversal I/II 信号标记（红↑/绿↓）+ RSI² 副图（`/tmp/k_<code>.png` 自动打开）
- `--json`：结构化信号

## 注意

- 信号为**次日执行**（作者规则），检测当日是触发日
- K's Reversal II 触发频率极低（21 根极端状态），属高置信低频信号——这正是「未知指标 + 去相关」的设计初衷
