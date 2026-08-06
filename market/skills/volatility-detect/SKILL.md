---
name: volatility-detect
description: 波动率检测与可视化（kaabar ch06）：布林带挤压（squeeze）检测 + ATR 波动率分级 + 突破标记，可视化布林带 + 挤压高亮区 + 突破标注，输出结论（低波动→突破前夜 / 高波动→警惕）。当用户说「某股票布林带挤压了吗」「波动率状态」「ATR 分级」「突破信号」时使用。反触发：均线信号用 ma-signal-viz；风控计算用 position-size；单K形态用 pattern-detect。
---

# volatility-detect — 波动率检测与可视化

布林带（BB）与 ATR 的波动状态检测 + 突破可视化。

## 使用

```bash
python3 market/skills/volatility-detect/scripts/volatility-detect.py <股票代码> [--window 20] [--k 2] [--json]
```

参数：

- `--window`：布林带周期（默认 20）
- `--k`：带宽倍数（默认 2）

## 检测（kaabar ch06）

| 信号 | 条件 |
|------|------|
| 挤压 Squeeze | 带宽（2k·σ/中轨）处于近 60 日最低 20% → 突破前夜 |
| 高波动 | 带宽 > 近 60 日 80% 分位 → 警惕追高 |
| ATR 分级 | ATR14 相对价格 %：<2% 低 / 2-4% 中 / >4% 高 |
| 突破 | 收盘突破近期挤压区后的最高/最低 |

## 输出

- 终端：当前带宽/分位、挤压状态、ATR 分级、最近挤压后突破方向
- PNG：K线 + 布林带（上下轨+中轨）+ 挤压区底色 + 突破标记 + 带宽指标副图（`/tmp/volatility_<code>.png` 自动打开）
- `--json`：结构化状态
