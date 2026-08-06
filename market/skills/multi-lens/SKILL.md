---
name: multi-lens
description: 个股多视角综合分析（kaabar 全书方法论）：一次运行输出 K线形态（pattern-detect）、谐波（harmonic-detect）、斐波那契（fibonacci-detect）、价格形态（price-pattern-detect）、均线（ma-signal-viz）、波动率（volatility-detect）、RSI背离（divergence-detect）七维检测结果 + 汇总结论（多信号共振/矛盾提示）+ 一张综合标注图。当用户说「全面分析某股票」「多维度看盘」「综合报告」「七个视角」时使用。反触发：只看单一维度用对应技能。
---

# multi-lens — 个股七维综合分析

一键聚合 7 个检测技能的结果，输出交叉验证后的综合结论。

## 使用

```bash
python3 market/skills/multi-lens/scripts/multi-lens.py <股票代码> [--json]
```

## 七个视角（kaabar 全书）

| # | 视角 | 技能 | 章节 |
|---|------|------|------|
| 1 | K线形态 | pattern-detect | ch07 |
| 2 | 谐波形态 | harmonic-detect | ch08 |
| 3 | 斐波那契 | fibonacci-detect | ch05 |
| 4 | 价格结构 | price-pattern-detect | ch10 |
| 5 | 现代均线 | ma-signal-viz | ch03 |
| 6 | 波动率 | volatility-detect | ch06 |
| 7 | RSI 背离 | divergence-detect | ch03/ch11 |

## 汇总逻辑

- **共振**：≥3 个视角方向一致 → 高置信结论
- **矛盾**：看涨与看跌视角并存 → 提示「信号分歧，降低仓位/等待确认」
- **结论** = 趋势方向（均线/斐波那契）+ 反转信号（形态/背离）+ 风险（波动率）

## 输出

- 终端：七维结果表 + 共振/矛盾判定 + 综合操作建议
- 综合图：`/tmp/multi_<code>.png` —— 主图（K线+MA20+布林带+关键位标注）+ 副图（RSI+量能），自动打开
- `--json`：七维结构化结果

## 数据源

- 全部复用 `_shared/kline.py`（东财→新浪兜底）与各检测技能逻辑
- 仅技术面参考，不构成投资建议
