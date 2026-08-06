---
name: harmonic-detect
description: 谐波形态检测（kaabar ch08）：在任意股票上自动识别 XABCD 结构（Gartley/Bat/Crab/Butterfly/ABCD），按斐波那契比例校验，可视化 X→A→B→C→D 折线与比例标注、D 点入场位与止损位，输出结论。当用户说「看下某股票有没有谐波形态/蝴蝶/蝙蝠」「谐波分析」时使用。反触发：单K形态用 pattern-detect；斐波那契回撤线用 fibonacci-detect；价格形态用 price-pattern-detect。
---

# harmonic-detect — 谐波形态检测

基于 kaabar ch08：谐波 = 满足斐波那契比例关系的 XABCD 五段结构。自动找摆动点、校验比例、画图、给结论。

## 使用

```bash
python3 market/skills/harmonic-detect/scripts/harmonic-detect.py <股票代码> [--json]
```

## 检测的形态（D 相对 XA 的极端值）

| 形态 | D 回撤 | 含义 |
|------|--------|------|
| ABCD | BC/AB 与 CD/BC 满足比例 | 量度移动 |
| Gartley | 78.6% | 趋势中回撤反转 |
| Bat | 88.6% | 更深回撤反转 |
| Butterfly | 127.2% | 中等反转 |
| Crab | 161.8% | 极端反转 |

## 输出

- 终端：识别的形态、XABCD 各点价格/日期、D 点入场建议与止损、目标位
- PNG：K线 + XABCD 折线（每段标注实际比例）+ D 点入场/止损水平线 + 结论标题（`/tmp/harmonic_<code>.png` 自动打开）
- `--json`：结构化结果

## 数据源

- 日 K：`_shared/kline.py`（东财→新浪兜底）；摆动点用枢轴窗口（默认 3）
- 仅技术面参考，不构成投资建议
