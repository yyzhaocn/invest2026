---
name: td-setup
description: TD Setup（DeMark）计数检测（kaabar ch09，公式核对自作者仓库）：连续 close vs close[i-4] 计数至 9（含 perfected 确认变体）+ 斐波那契时机形态（8 计数，5/21 差），可视化每根 K 线计数徽章与耗尽信号，输出结论（震荡市有效/趋势市失效提示）。当用户说「某股票 TD 序列/DeMark 计数到几了」「setup 9 了吗」时使用。反触发：谐波时机用 harmonic-detect；单K形态用 pattern-detect。
---

# td-setup — TD Setup 计数检测

DeMark 的 setup 序列（ch09）：连续 9 根同向收盘 = 趋势耗尽信号。公式已对照 `sofienkaabar/mastering-financial-markets-in-python` 核实。

## 规则（公式已核对）

### TD Setup（unperfected）
- **看涨计数**：close[i] < close[i-4] → 计数+1（上限 9），否则重置 0
- **看跌计数**：close[i] > close[i-4] → 计数+1（上限 9），否则重置 0
- **信号**：计数达到 9 → 次日 bullish/bearish 信号

### Perfected（增强确认）
- 计数=9 且（看涨）low[i] < low[i-2] 且 low[i] < low[i-3] /（看跌）high[i] > high[i-2] 且 high[i] > high[i-3]

### Fibonacci Timing Pattern（ch09 第二个时机形态）
- 8 计数（final_step=8）；条件：close[i] < close[i-5] 且 close[i-5] < close[i-21]（看涨）→ 更严格的嵌套结构

## 使用

```bash
python3 market/skills/td-setup/scripts/td-setup.py <股票代码> [--perfected] [--json]
```

参数：

- `--perfected`：只显示 perfected 确认信号（默认两种都显示）
- `--json`：结构化计数与信号

## 输出

- 终端：当前看涨/看跌计数、最近 9 计数信号、perfected 状态、regime 提示（震荡市有效/趋势市失效）
- PNG：K线 + 每根 K 线下计数徽章（B/S+数字，9 高亮）+ 信号标记 + MA20 趋势区底色（`/tmp/td_<code>.png` 自动打开）

## 注意（书 ch09 明确）

- **TD setup 在震荡市（perfected 或 unperfected）表现好，趋势市失效**——信号前先看 MA20 方向
