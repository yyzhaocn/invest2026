---
name: pair-detect
description: 协整配对交易检测（Ernest Chan《Quantitative Trading》ch07 方法）：对两只股票做线性回归 → 价差（spread）→ ADF 平稳性检验 → 半衰期估计 → z-score 交易信号（入场/出场/止损），并回测价差策略（含成本），可视化双价格线 + 价差 + z-score 信号图。当用户说「这两只股票能做配对交易吗」「协整检验」「价差均值回归」时使用。反触发：单只股票形态用 pattern-detect；回测单策略用 backtest；仓位用 position-size。
---

# pair-detect — 协整配对交易检测

Ernest Chan ch07 的完整配对工作流：协整 → 半衰期 → z-score 均值回归策略。

## 方法（Chan ch07）

```
1. 对齐两股日 K（同期）
2. 回归 B = α + β·A → 价差 spread = B − β·A
3. ADF 检验 spread 平稳性（p < 0.05 = 协整）
4. 半衰期: spread ~ AR(1) 得 β₁ → half_life = −ln(2)/ln(β₁)
5. 交易信号（z-score）:
   - z < −2  → 买入价差（多B空A）
   - z > +2  → 卖空价差（空B多A）
   - z 回归 0 → 平仓
6. 回测价差策略（含成本）→ Sharpe/胜率
```

## 使用

```bash
python3 market/skills/pair-detect/scripts/pair-detect.py <代码A> <代码B> [--cost 0.0005] [--json]
```

参数：

- `<代码A> <代码B>`：两只股票（如 `159915 510300` 或 `600519 000858`）
- `--cost`：单边交易成本（默认 0.05%）
- `--json`：结构化结果（β、ADF p、半衰期、信号清单、回测绩效）

## 输出

- 终端：β、ADF p 值（协整判断）、半衰期（→ 建议 lookback）、信号清单、回测绩效（Sharpe/胜率/成本前后对比）
- PNG：上双价格线（归一化）+ 中价差 + 下 z-score 信号图（`/tmp/pair_<A>_<B>.png` 自动打开）

## 判断标准（Chan）

| 指标 | 协整成立 |
|------|---------|
| ADF p 值 | < 0.05（spread 平稳）|
| 半衰期 | 适中（太短=噪声，太长=等不起；通常 5-60 日可用）|
| 回测 Sharpe | 含成本后仍 > 1 |

- 经济关联（同行业/同产业链）是前提，纯统计协整不可靠
- 价差结构会失效（cointegration break）—— 监控 z-score 持续单边走
