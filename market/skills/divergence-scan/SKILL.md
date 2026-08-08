---
name: divergence-scan
description: 批量 RSI 背离扫描：对板块/组合/代码列表批量检测底背离与顶背离（摆动极值 + Wilder RSI，与 multi-lens 的 RSI 背离维度同算法），输出背离股票与摆动点详情。当用户说「扫描XX板块背离」「哪些股票底背离」「板块背离检测」时使用。反触发：单股背离检测用 divergence-detect；完整7维用 multi-lens。
---

# divergence-scan — 批量 RSI 背离扫描

对板块成分 / 组合持仓 / 代码列表批量检测 RSI 底背离与顶背离。

## 使用

```bash
python3 /Users/yyz/.agents/skills/stock/divergence-scan/scripts/divergence-scan.py --block BK0448
python3 .../divergence-scan.py --account 7维选股
python3 .../divergence-scan.py 600775 300620 [--json]
```

参数：

- `--block BKxxxx`：板块全部成分
- `--account <名>`：组合持仓（复用 portfolio 技能）
- `--window`：摆动窗口（默认 5）
- `--rsi`：RSI 周期（默认 14）
- `--lmt`：K线数据长度（默认 120——与 multi-lens 一致）
- `--json`：JSON 输出（含摆动点日期/价格/RSI）

## 算法（与 multi-lens 的 RSI 背离维度完全一致）

1. 摆动极值：`win=5` 局部最高/最低（high/low == 前后 ±5 日极值）
2. RSI 序列：Wilder 平滑（`gains*(n-1)/n + max(d,0)`），非简单平均
3. 判定：取**最后两个**摆动低点/高点——
   - 底背离：价格新低（p2<p1）但 RSI 未新低（r2>r1）→ 看涨
   - 顶背离：价格新高（p2>p1）但 RSI 未新高（r2<r1）→ 看跌

## 依赖与注意

- `_shared/kline.py`（带 5 分钟本地缓存，批量扫描快）
- 注意与 `divergence-detect` 的关系：divergence-detect 曾因 `kline.rsi()` 单值 bug 检不出背离（已修复）；本技能内置 RSI 序列实现，不依赖该函数
- 背离为左侧信号：底背离出现后常伴随反弹（如通信板块 6/29→7/21 底背离 → 7/27-28 两连板）

## 典型用途

- 板块超跌后找"动量先行"标的（底背离 = 反转候选）
- 组合持仓背离监控（顶背离 = 减仓警示）
- 与 multi-lens 7维共振交叉验证
