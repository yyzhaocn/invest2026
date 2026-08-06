#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pair-detect: 协整配对交易检测（Ernest Chan ch07）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.tsa.stattools import adfuller  # noqa: E402


def load_aligned(code_a, code_b, lmt=300):
    na, pa = fetch_kline(code_a, lmt=lmt)
    nb, pb = fetch_kline(code_b, lmt=lmt)
    if not pa or not pb:
        return None, None, None, None
    da = pd.DataFrame(pa)[['date', 'close']].rename(columns={'close': 'A'})
    db = pd.DataFrame(pb)[['date', 'close']].rename(columns={'close': 'B'})
    m = da.merge(db, on='date', how='inner').dropna()
    if len(m) < 60:
        return None, None, None, None
    return m, na or resolve_name(code_a), nb or resolve_name(code_b), m


def half_life(spread):
    """spread ~ AR(1): s_t = a + b*s_{t-1} → hl = -ln2/ln(b)。"""
    s = spread.values
    b = np.polyfit(s[:-1], s[1:], 1)[0]
    if b <= 0 or b >= 1:
        return None
    return -np.log(2) / np.log(b)


def run_pair(m, cost):
    A, B = m['A'], m['B']
    beta, alpha = np.polyfit(A, B, 1)
    spread = B - beta * A
    p_adf = adfuller(spread.dropna(), autolag='AIC')[1]
    hl = half_life(spread)
    z = (spread - spread.rolling(20).mean()) / spread.rolling(20).std()

    # 策略: z<-2 多价差 / z>+2 空价差 / |z|<0.5 平仓
    # 收益代理: 每个 z-score 单位变动 ≈ 1% 名义（避免除以近零价差爆炸）
    pos = 0
    trades, equity = [], [1.0]
    entry = None
    for i in range(20, len(z)):
        zi = z.iloc[i]
        if pd.isna(zi):
            equity.append(equity[-1])
            continue
        ret = 0.0
        if pos != 0 and pd.notna(z.iloc[i - 1]):
            ret = pos * (zi - z.iloc[i - 1]) * 0.01 - cost
        if pos == 0 and zi < -2:
            pos, entry = 1, (m['date'].iloc[i], spread.iloc[i])
        elif pos == 0 and zi > 2:
            pos, entry = -1, (m['date'].iloc[i], spread.iloc[i])
        elif pos != 0 and abs(zi) < 0.5:
            trades.append({'entry': entry, 'exit': (m['date'].iloc[i], spread.iloc[i]),
                           'pnl': ret, 'days': 0})
            entry, pos = None, 0
        equity.append(max(equity[-1] * (1 + ret), 0.01))
    equity = np.array(equity[1:])
    rets = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0])
    sharpe = rets.mean() / (rets.std() + 1e-9) * np.sqrt(252) if len(rets) > 2 else 0
    wins = sum(1 for t in trades if t['pnl'] > 0)
    return {'beta': round(beta, 4), 'alpha': round(alpha, 2), 'adf_p': round(p_adf, 4),
            'half_life': round(hl, 1) if hl else None, 'trades': len(trades),
            'win_rate': round(wins / len(trades) * 100, 1) if trades else None,
            'sharpe': round(float(sharpe), 2), 'final': round(float(equity[-1]), 3),
            'z': z, 'spread': spread}


def main():
    ap = argparse.ArgumentParser(description="协整配对交易检测")
    ap.add_argument("code_a", help="股票 A 代码")
    ap.add_argument("code_b", help="股票 B 代码")
    ap.add_argument("--cost", type=float, default=0.0005, help="单边成本，默认 0.05%")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ca, cb = str(args.code_a).zfill(6), str(args.code_b).zfill(6)
    m, na, nb, _ = load_aligned(ca, cb)
    if m is None:
        sys.exit(f"❌ 无法获取 {ca}/{cb} 对齐 K 线（东财/新浪均失败或数据不足）")
    r = run_pair(m, args.cost)

    if args.json:
        print(json.dumps({"code_a": ca, "name_a": na, "code_b": cb, "name_b": nb,
                          "pairs": len(m), **{k: v for k, v in r.items() if k not in ('z', 'spread')}},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== 协整配对: {na} ({ca}) vs {nb} ({cb}) ｜ {len(m)} 日对齐数据 ===")
    print(f"回归: {nb} = {r['alpha']:.2f} + {r['beta']:.4f} × {na}")
    coint = r['adf_p'] < 0.05
    print(f"ADF 检验: p = {r['adf_p']} {'✅ 协整（spread 平稳）' if coint else '❌ 不协整（不可做价差策略）'}")
    if r['half_life']:
        hl = r['half_life']
        verdict = "✅ 适中" if 5 <= hl <= 60 else ("⚠️ 太短(噪声)" if hl < 5 else "⚠️ 太长(等不起)")
        print(f"半衰期: {hl:.1f} 日 {verdict} → 建议 lookback ≈ {max(5, int(hl))} 日")
    else:
        print("半衰期: 无法估计（AR 系数异常）")
    if r['trades']:
        print(f"z-score 策略回测（{r['trades']} 笔，成本 {args.cost*100:.2f}%）：胜率 {r['win_rate']}% ｜ "
              f"Sharpe {r['sharpe']} ｜ 终值 {r['final']}（1.0 起）")
        print(f"  → {'✅ 含成本后可用（Sharpe>1）' if r['sharpe'] > 1 else '⚠️ 含成本后不可用'}")
    else:
        print("z-score 策略：窗口内无触发（价差未到 ±2σ）")

    # 图
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    seg = m.tail(120).reset_index(drop=True)
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(13, 8.5), sharex=True,
                                        gridspec_kw={'height_ratios': [1.4, 1, 1], 'hspace': 0.12})
    dts = pd.to_datetime(seg['date'])
    ax1.plot(dts, seg['A'] / seg['A'].iloc[0] * 100, color='#1971c2', lw=1.2, label=na)
    ax1.plot(dts, seg['B'] / seg['B'].iloc[0] * 100, color='#e03131', lw=1.2, label=nb)
    ax1.set_ylabel('归一化价格(起点=100)')
    ax1.legend(loc='upper left', fontsize=8); ax1.grid(alpha=0.25)

    z = r['z'].tail(120).reset_index(drop=True)
    sp = r['spread'].tail(120).reset_index(drop=True)
    ax2.plot(dts, sp, color='#7048e8', lw=1.2, label='spread (B-βA)')
    ax2.axhline(sp.mean(), color='#868e96', ls='--', lw=0.8)
    ax2.legend(loc='upper left', fontsize=8); ax2.grid(alpha=0.25)
    ax2.set_ylabel('价差')

    ax3.plot(dts, z, color='#2f9e44', lw=1.2, label='z-score')
    ax3.axhline(2, color='#e03131', ls='--', lw=0.8); ax3.axhline(-2, color='#e03131', ls='--', lw=0.8)
    ax3.axhline(0, color='#868e96', ls='-', lw=0.6)
    ax3.legend(loc='upper left', fontsize=8); ax3.grid(alpha=0.25)
    ax3.set_ylabel('z-score')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

    coint_txt = '协整' if coint else '不协整'
    ax1.set_title(f"配对 {na} vs {nb} ｜ {coint_txt} (ADF p={r['adf_p']}) ｜ 半衰期 {r['half_life']}日 ｜ Sharpe {r['sharpe']}",
                  fontsize=11.5, fontweight='bold')
    out = Path(f"/tmp/pair_{ca}_{cb}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
