---
name: larson-coc
description: "Change of Character (CoC) + MACD 标注分析技能（基于 Mark Larson 指标方法论）。对单只或股票池随机 N 只 A 股：计算 MACD(DIF/DEA/柱)定位空→多翻红日与柱状态、PRC(21/15日)与量能比(1.5×触发线)做 CoC 确认，生成标注 K 线图（主图均线+CoC标注 + MACD副图 + 量能）并输出端口文判断，按 CoC 类型归类。当用户说「larson 分析某股变动性格」「随机6只larson-coc」「Change of Character + MACD」时使用。反触发：只画七维用 multi-lens；只做背离扫描用 divergence-multi/scan；无 MACD 的其他 Larson 指标用 larson-technical-indicators。"
---

# larson-coc — Change of Character + MACD

用 Mark Larson《12 Simple Technical Indicators That Really Work》的 **Change of Character** 框架，对股票做 CoC 类型判定 + 标注图。CoC = 股票性格从空→多（accumulation=买）或多→空（distribution=卖）的枢轴，跨 MACD 柱/PRC/量能确认。

## 使用

```bash
python3 market/skills/larson-coc/scripts/larson_coc.py 600519              # 单只
python3 market/skills/larson-coc/scripts/larson_coc.py --random 6          # 股票池随机6只
python3 market/skills/larson-coc/scripts/larson_coc.py 002916 002185       # 多只
python3 market/skills/larson-coc/scripts/larson_coc.py --random 6 --json   # json
python3 ...larson_coc.py --random 6 --out_dir generated/coc               # 指定图目录
```

参数：`codes`（代码列表）、`--random N`（从本地股票池=缓存 kline 随机 N）、`--json`、`--out_dir`（图输出，默认 generated/coc/）。

## 判定逻辑（CoC 类型）

| coc_type | 判据 | 含义 |
|---|---|---|
| **bull-coc** 空→多CoC(已确立) | MACD柱翻红 + PRC21≥0 | 多头性格确立，多指标确认 |
| **bull-early** 空→多CoC(萌芽) | 仅MACD翻红，PRC21仍负 | 萌芽待确认，勿急做多 |
| **bull-weak** 多头区但柱走弱 | 红区但柱回落/无力 | 谨慎 |
| **bear-warn** 多→空逆变预警 | 翻红后柱见顶回落(近期) | 减仓/止盈预警 |
| **bear** 弱势空头区 | MACD全绿，无CoC | 观望 |
| **short** 数据不足 | K线<40根(次新股) | 仅近似，不画图 |

- **翻红日**：最近一次 MACD 柱由负转正（窗口内）
- **柱状态**：最新柱 vs 前日柱（↑升 / ↓缩）；窗口内柱顶若在近 8 根内且回落 = peaking
- **CoC 需多确认**：MACD翻红 + PRC回正 + 量比≥1.5×(commitment) + 站上关键均线

## 图内容（3 面板）
1. 主图：K线(红涨绿跌) + 5/20/30/200MA + CoC标注（Macd翻红点/柱顶/现价）+ PRC/量比信息栏
2. MACD 副图：红绿柱 + DIF/DEA 线 + 零轴
3. 量能副图（百万股）

## 数据
- 拉取：`_shared/kline.py fetch_kline`（东财→新浪兜底，本地 5min 缓存）
- 股票池（--random）：`generated/cache/kline/*.json`（506 只）
- 名称补全：本地 scan csv（code→name），兜底显示 code

## 坑
- 次新股 K 线不足 40 根 → 不画图、CoC 降级为 "short"（勿硬标柱顶）。
- 量比当 20日均量 NaN 时显示 n/a，勿当 0 处理（避免除零产生 8e6 级异常）。
- 需本地缓存/网络可达；离线仅能用已缓存池。
- 技术面仅供参考，不构成投资建议。
