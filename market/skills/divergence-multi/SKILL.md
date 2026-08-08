---
name: divergence-multi
description: 多指标共振背离检测（MACD+RSI+KDJ+量价四指标共振评分）：对全部缓存K线股票/板块/组合检测最后两个摆动高低点上的多指标背离，共振分=背离指标数，≥3为最强信号。当用户说「多指标背离」「指标共振最强背离」「MACD+RSI背离」时使用。反触发：单指标RSI背离用 divergence-scan/detect；完整7维用 multi-lens。
---

# divergence-multi — 多指标共振背离检测

四指标共振背离检测（基于 底背离.md 的多指标共振原则）：RSI + MACD + KDJ + 量价同时背离时信号最强。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/divergence-multi/scripts/divergence-multi.py
python3 .../divergence-multi.py --min-score 3        # 只看≥3指标共振（最强）
python3 .../divergence-multi.py --account 7维选股     # 组合持仓
python3 .../divergence-multi.py --block BK0448 --top 20
python3 .../divergence-multi.py 600775 300620 --json
```

参数：

- 默认扫**全部缓存 kline 股票**（`generated/cache/kline/`，需先跑过 multi-lens/divergence 等填充缓存）
- `--block` / `--account` / 代码列表：限定范围
- `--min-score N`：最低共振分（默认 2；3 = RSI+MACD+KDJ 三重）
- `--window`：摆动窗口（默认 5）
- `--top` / `--json`

## 四指标背离

| 指标 | 实现 | 背离判定（对最后两个摆动低点/高点） |
|---|---|---|
| RSI(14) | Wilder 平滑 | 价格新低 + RSI 低点抬高 |
| MACD DIF | EMA12-EMA26 | 价格新低 + DIF 低点抬高 |
| KDJ K | 9日RSV平滑 | 价格新低 + K 低点抬高 |
| 量价 | 成交量 | 价格新低 + 低点缩量（<前低点97%） |

**共振分** = 背离指标数（1-4）。分越高越可靠：3 = MACD+RSI+KDJ 三重共振，4 = 全指标。

## 原理（底背离.md 要点）

- 底背离 = 价格创新低但动能（指标）不再走弱 → 抛压衰竭，反转候选
- **多指标共振最强**：MACD+RSI+KDJ 同时背离成功率明显提高
- 顶背离准确性通常高于底背离；单次背离易失效，二次背离更可靠
- 背离是预警，需金叉/突破/放量确认；严格止损

## 注意

- 依赖缓存 K 线（`_shared/kline.py` 5 分钟缓存）；未缓存的会实时拉取
- 名称字段可能显示代码（缓存 name 兜底为 code）——如需精确名称可用 block-lookup 解析
- 量价背离阈值（97%）可调——见脚本内 `vols[i2] < vols[i1] * 0.97`

## 典型用途

- 全缓存池扫"三重共振背离"（--min-score 3）= 最强信号池
- 组合持仓多指标监控（顶背离共振 = 减仓强信号）
- 与 multi-lens 7维、divergence-monitor 交叉验证
