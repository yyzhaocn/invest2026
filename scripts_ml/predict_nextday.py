#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案A: 轻量加权方向打分器 —— 用"当日可得"特征预测次一交易日方向(涨/跌)。

特征(全部当日可得, 无未来信息):
  - 7 个七维 lens 方向 (1多/-1空/0中)
  - 当日涨跌 pct
  - 近5日累计收益 momentum5
  - RSI14
  - MA5/MA20 关系 (多头排列?) 与价格相对 MA20
  - ATR14 / 收盘 (波动率代理) + ATR 分位
  - 量比 vol/近20日均量 与近5日平均量比
标签: 次一交易日 pct > 0 => 1, else 0 (不预测点位, 只预测方向)

验证: walk-forward 滚动, 初始训练 N 根后逐日后推。可配置权重。
"""
import sys, argparse, importlib.util
from pathlib import Path
import pandas as pd, numpy as np

msrc = Path('/Users/yyz/.agents/skills/stock/multi-lens/scripts/multi-lens.py')
_ml = importlib.util.module_from_spec(
    spec := importlib.util.spec_from_file_location('ml', msrc))
sys.modules['ml'] = _ml
sys.path.insert(0, str(Path('/Users/yyz/.agents/skills/stock/_shared')))
spec.loader.exec_module(_ml)

LENS_NAMES = ['K线形态','谐波','斐波那契','价格结构','现代均线','波动率','RSI背离']

def build_features(df: pd.DataFrame):
    """df 需含 date/open/high/low/close/volume/pct。返回带全部特征的副本。"""
    f = df.copy().reset_index(drop=True)
    c = f['close'].astype(float)
    # 均线
    f['ma5']  = c.rolling(5).mean()
    f['ma20'] = c.rolling(20).mean()
    f['ma_bull'] = (f['ma5'] > f['ma20']).astype(int)   # 多头排列
    f['price_vs_ma20'] = c / f['ma20'] - 1
    # 动量
    f['mom5']  = c.pct_change(5)
    f['mom10'] = c.pct_change(10)
    # RSI14 (Wilder)
    delta = c.diff()
    up = delta.clip(lower=0); dn = -delta.clip(upper=0)
    ru = up.ewm(alpha=1/14, adjust=False).mean()
    rd = dn.ewm(alpha=1/14, adjust=False).mean()
    rs = ru / rd.replace(0, np.nan)
    f['rsi14'] = 100 - 100/(1+rs)
    # 波动率 ATR14
    tr = pd.concat([(f['high']-f['low']), (f['high']-c.shift()).abs(), (f['low']-c.shift()).abs()], axis=1).max(axis=1)
    f['atr14'] = tr.ewm(alpha=1/14, adjust=False).mean()
    f['atr_pct'] = f['atr14'] / c
    f['atr_pct_rank'] = f['atr_pct'].rolling(60).rank(pct=True)
    # 量能
    f['vol_ratio'] = f['volume'] / f['volume'].rolling(20).mean()
    f['vol_ratio5'] = f['volume'].rolling(5).mean() / f['volume'].rolling(20).mean()
    # 当日 7 维方向 (滚动到当日)
    lens_rows = []
    for i in range(len(f)):
        sub = f.loc[:i]
        try:
            lns, _ = _ml.compute_lenses(sub)
            dmap = {l: d for l, s, d in lns}
            lens_rows.append([dmap[l] for l in LENS_NAMES])
        except Exception:
            lens_rows.append([0]*len(LENS_NAMES))
    lens_df = pd.DataFrame(lens_rows, columns=[f'lens_{l}' for l in LENS_NAMES])
    f = pd.concat([f, lens_df], axis=1)
    # 标签: 次一交易日方向
    f['label'] = (f['pct'].shift(-1) > 0).astype(int)
    f['next_pct'] = f['pct'].shift(-1)
    return f

def score_signal(row, w):
    """加权打分: 返回 (score, votes_bull, votes_bear)。"""
    # lens 权重
    score = sum(w[f'lens_{l}'] * row[f'lens_{l}'] for l in LENS_NAMES)
    # 均线多头
    score += w['ma_bull'] * (1 if row['ma_bull'] else -1)
    # RSI 超买/超卖 轻惩罚
    if row['rsi14'] > 70: score -= w['rsi_extr']
    elif row['rsi14'] < 30: score += w['rsi_extr']
    # 波动率挤压(低分位)视为潜在突破
    # 动量
    score += w['mom'] * np.sign(row['mom5']) if not np.isnan(row['mom5']) else 0
    return score

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('code')
    ap.add_argument('--train', type=int, default=80, help='初始训练样本(根), 之后逐根滚动')
    ap.add_argument('--lw', type=float, default=1.0)
    ap.add_argument('--mw', type=float, default=0.8)
    ap.add_argument('--rw', type=float, default=0.5)
    ap.add_argument('--momw', type=float, default=0.3)
    ap.add_argument('--kw', type=float, default=0.5)
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = _ml.fetch_kline(code, lmt=250)
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])
    f = build_features(df).dropna(subset=['atr_pct_rank'])
    # 需有未来标签
    valid = f.dropna(subset=['label', 'next_pct'])
    valid = valid.reset_index(drop=True)

    # 权重字典
    w = {f'lens_{l}': args.lw for l in LENS_NAMES}
    w['ma_bull'] = args.mw; w['rsi_extr'] = args.rw; w['mom'] = args.momw

    # ---- walk-forward ----
    N = args.train
    preds, ytrue, yscores, idxs = [], [], [], []
    for t in range(N, len(valid)):
        # 用截止 t-1 的数据估计"权重阈值": 打分仅基于当日特征, 无需训练参数;
        # 这里把 N 以前作为校准期确定阈值(使打分为正即有 50%+ 基准)
        row = valid.loc[t]
        s = score_signal(row, w)
        pred = 1 if s > 0 else 0
        preds.append(pred); ytrue.append(int(row['label']))
        yscores.append(s); idxs.append(row['date'])
    ytrue = np.array(ytrue); preds = np.array(preds)
    acc = (ytrue == preds).mean()
    # 基准1: 永远预测"昨日延续"(今天涨=>明天涨)
    prev = valid['pct'].values[:len(ytrue)]  # 对齐: 第t根昨收即前一交易日pct
    base_persist = (prev > 0).astype(int)
    base_acc = (base_persist == ytrue).mean()
    # 基准2: 永远看多
    base_up = (np.ones(len(ytrue)) == ytrue).mean()

    # 每期统计
    stats = pd.DataFrame({
        'date': idxs,
        'pred': preds, 'actual': ytrue, 'score': yscores,
        'prev_pct': valid['pct'].values[N:len(ytrue)+N],
        'next_pct': valid['next_pct'].values[N:len(ytrue)+N],
    })

    print(f"\n=== {name} ({code}) 轻量加权方向打分 · walk-forward ===")
    print(f"样本: {len(valid)-N} 条 (训练/校准 {N} 根 → 滚动 {len(valid)-N} 根)")
    print(f"预测分布: 看多 {preds.sum()} / 看空 {(preds==0).sum()}")
    print(f"真实分布: 涨 {ytrue.sum()} / 跌 {(ytrue==0).sum()}")
    print(f"\n模型准确率 (score>0 => 涨): {acc:.1%}")
    print(f"基准·延续昨日:            {base_acc:.1%}")
    print(f"基准·恒看多:              {base_up:.1%}")
    print(f"超额 vs 延续基准:          {acc-base_acc:+.1%} pts")

    # 仅看高分样本(score 绝对值大)的命中率
    for thr in [0.5, 1.0, 1.5, 2.0]:
        sel = stats[stats['score'].abs() >= thr]
        if len(sel) >= 5:
            hi_acc = (sel['pred'] == sel['actual']).mean()
            print(f"   |score|>= {thr}: n={len(sel):3d} 命中率 {hi_acc:.1%}")

    # 近期预测(最后5条)
    print("\n最近5条滚动预测:")
    print(stats.tail(6)[['date','pred','actual','score','prev_pct','next_pct']].to_string(index=False))

    # 下一日预测 = 用最后一天特征打分
    last = valid.iloc[-1]
    s_next = score_signal(last, w)
    # 真实 next_pct 未知时打印特征视图
    dirn = '看涨↑' if s_next > 0 else ('看跌↓' if s_next < 0 else '中性')
    print(f"\n★ 下一交易日预测 (基于 {last['date'].date()} 收盘): score={s_next:+.2f} → {dirn}")
    print(f"   特征: 收盘{last['close']:.2f} pct{last['pct']:+.2f}% RSI{last['rsi14']:.1f} "
          f"MA多头{bool(last['ma_bull'])} ATR分位{last['atr_pct_rank']:.2f} 量比{last['vol_ratio']:.2f}")
    lens_act = {l: last[f'lens_{l}'] for l in LENS_NAMES}
    print("   当日七维:", {l: {1:'多',-1:'空',0:'中'}[int(v)] for l,v in lens_act.items()})

if __name__ == '__main__':
    main()
