---
name: signal-divergence
description: 底背离+确认条件共振选股（恒生电子7-24模式）：找最近 N 天刚形成底背离（MACD/RSI/KDJ/量价共振）且满足 MACD金叉/柱翻红/均线多头/低位等确认条件的股票。当用户说「找最近几天底背离+金叉的股票」「背离确认信号选股」时使用。反触发：纯背离扫描用 divergence-scan/multi；完整7维用 multi-lens。
---

# signal-divergence — 底背离+确认共振选股

复现"恒生电子 7-24 买入信号"模式：**底背离（新鲜形成） + MACD金叉 + 柱翻红 + 均线多头 + 低位** 共振选股。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/signal-divergence/scripts/signal-divergence.py
python3 .../signal-divergence.py --recent 5        # 背离摆动2在最近5天
python3 .../signal-divergence.py --account 7维选股
python3 .../signal-divergence.py --block BK0448 --min-confirm 4
python3 .../signal-divergence.py 600570 300627 --json
python3 .../signal-divergence.py --account 7维选股 --plot   # 命中股票画标注K线图
```

- 默认扫**缓存 K 线股票池**（快：直接读缓存文件，337 只 ~2 秒）
- `--recent N`：背离摆动2 在最近 N 天（默认 3）
- `--min-score`：背离最低共振分（默认 2）
- `--min-confirm`：确认条件最低满足数（默认 3/5）

## 标注 K 线图（--plot）

对命中股票生成 4 面板标注图（`generated/signal_div_<code>.png`）：
- **价格**：K线 + 底背离摆动点红色连线 + 近60日支撑/压力线 + MACD金叉黄色▲
- **RSI**：紫色曲线 + 摆动点标注（灰线=未背离 / 红线=背离，含数值如 "54→51 未背离"）
- **MACD**：红绿柱 + DIF/DEA + 背离连线 + 金叉▲
- **KDJ**：K/D/J + 摆动点标注（同 RSI 规则）

RSI/KDJ 面板**始终标注**摆动点与数值——背离与否一目了然（如华测导航：MACD+量价背离、RSI/KDJ 未背离）。

## 信号条件（评分 0-5）

| # | 条件 | 说明 |
|---|---|---|
| 1 | 底背离（≥2 重共振） | **live 即时检测**（window=2 右窗口截断）捕捉最近形成的新背离 |
| 2 | MACD 金叉 | DIF > DEA |
| 3 | MACD 柱翻红 | DIF - DEA > 0 |
| 4 | 均线多头 | SMA5 > SMA20 |
| 5 | 低位 | 现价在近 60 日 30% 分位以下 |

## 原理与注意

- **live 即时检测**：标准 window=5 有 5 天确认延迟（最近 3 天摆动点检不出）；本技能用 live（window=2 右窗口截断）捕捉新鲜背离，但**摆动点待确认**——需 5 天窗口复核（建议次日 divergence-monitor 复核）
- 参考案例：恒生电子 7-24（三重底背离 + MACD金叉 + 低位 + 均线多头）→ 后续 8 天 +9.6% ✓
- 背离是预警，确认条件（金叉/翻红/多头）是执行依据；仍建议止损（近低点下方）
- 依赖 `divergence-multi` 模块（算法同源）

## 典型用途

- 每日盘后扫"昨天刚出现底背离 + 今天确认"的股票（即时买入候选）
- 组合持仓的背离确认监控
- 与 portfolio-review 减仓建议配合（顶背离版本可用同法扩展）
