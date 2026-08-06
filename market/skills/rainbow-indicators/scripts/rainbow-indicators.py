#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rainbow-indicators: Rainbow 七色指标（kaabar ch03，公式核对自作者仓库）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import pandas as pd  # noqa: E402


def slope(s, n):
    return (s - s.shift(n)) / n


def rsi_series(s, n):
    vals = s.values
    out = [None] * len(vals)
    if len(vals) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = vals[i] - vals[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    for i in range(n, len(vals)):
        if i > n:
            d = vals[i] - vals[i - 1]
            gains = gains * (n - 1) / n + max(d, 0)
            losses = losses * (n - 1) / n + max(-d, 0)
        out[i] = 100 - 100 / (1 + gains / losses) if losses > 0 else 50.0
    return out


def e_bb(df):
    mid = df['close'].ewm(span=20, adjust=False).mean()
    sd = df['close'].rolling(20).std()
    return mid, mid + 2 * sd, mid - 2 * sd


def rainbow_signals(df):
    c = df['close']
    sigs = {name: [] for name in ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Indigo', 'Violet']}

    # Red: eBB 回归（3 根在下轨外后回带内）
    mid, up, lo = e_bb(df)
    for i in range(3, len(df)):
        if pd.notna(lo.iloc[i]):
            if (c.iloc[i] < mid.iloc[i] > lo.iloc[i] and
                    c.iloc[i - 1] < lo.iloc[i - 1] and c.iloc[i - 2] < lo.iloc[i - 2] and c.iloc[i - 3] < lo.iloc[i - 3]):
                sigs['Red'].append((i, 'bullish'))
            if (c.iloc[i] > mid.iloc[i] and c.iloc[i] < up.iloc[i] and
                    c.iloc[i - 1] > up.iloc[i - 1] and c.iloc[i - 2] > up.iloc[i - 2] and c.iloc[i - 3] > up.iloc[i - 3]):
                sigs['Red'].append((i, 'bearish'))

    # Orange: RSI(8) 35/65
    r8 = rsi_series(c, 8)
    for i in range(5, len(df)):
        if r8[i] is None:
            continue
        if 35 < r8[i] < 50 and all(r8[j] is not None and r8[j] < 35 for j in range(i - 5, i)):
            sigs['Orange'].append((i, 'bullish'))
        if 50 < r8[i] < 65 and all(r8[j] is not None and r8[j] > 65 for j in range(i - 5, i)):
            sigs['Orange'].append((i, 'bearish'))

    # Yellow: RSI14 slope cross + market slope negative + RSI<35
    r14 = rsi_series(c, 14)
    sl_r, sl_m = slope(pd.Series(r14), 14), slope(c, 14)
    for i in range(14, len(df)):
        if r14[i] is None:
            continue
        if (sl_r.iloc[i] > 0 and sl_r.iloc[i - 1] < 0 and sl_m.iloc[i] < 0 and sl_m.iloc[i - 1] < 0 and r14[i] < 35):
            sigs['Yellow'].append((i, 'bullish'))
        if (sl_r.iloc[i] < 0 and sl_r.iloc[i - 1] > 0 and sl_m.iloc[i] > 0 and sl_m.iloc[i - 1] > 0 and r14[i] > 65):
            sigs['Yellow'].append((i, 'bearish'))

    # Green: RSI14 slope flip + extreme
    for i in range(14, len(df)):
        if r14[i] is None:
            continue
        if sl_r.iloc[i] > 0 and sl_r.iloc[i - 1] < 0 and r14[i] < 35:
            sigs['Green'].append((i, 'bullish'))
        if sl_r.iloc[i] < 0 and sl_r.iloc[i - 1] > 0 and r14[i] > 65:
            sigs['Green'].append((i, 'bearish'))

    # Blue: slope(close,5) -> RSI(5), band 30/70 margin 5
    sl5 = slope(c, 5)
    rsi_slope = rsi_series(sl5, 5)
    for i in range(5, len(df)):
        if rsi_slope[i] is None:
            continue
        if 30 < rsi_slope[i] < 35 and rsi_slope[i - 1] < 30 and df['low'].iloc[i] < df['low'].iloc[i - 1]:
            sigs['Blue'].append((i, 'bullish'))
        if 65 < rsi_slope[i] < 70 and rsi_slope[i - 1] > 70 and df['high'].iloc[i] > df['high'].iloc[i - 1]:
            sigs['Blue'].append((i, 'bearish'))

    # Indigo: 斐波那契差结构 1,2,3,5,8,13,21,34
    fib = [1, 2, 3, 5, 8, 13, 21, 34]
    for i in range(35, len(df)):
        if all(c.iloc[i - fib[j]] > c.iloc[i - fib[j + 1]] for j in range(len(fib) - 1)) and c.iloc[i] > c.iloc[i - 1]:
            sigs['Indigo'].append((i, 'bullish'))
        if all(c.iloc[i - fib[j]] < c.iloc[i - fib[j + 1]] for j in range(len(fib) - 1)) and c.iloc[i] < c.iloc[i - 1]:
            sigs['Indigo'].append((i, 'bearish'))

    # Violet: HMA(20) cross（i-1,2,3,5,8,13,21 均在下）
    import numpy as np

    def wma(s, n):
        w = np.arange(1, n + 1)
        return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)
    hma20 = wma(2 * wma(c, 10) - wma(c, 20), 4)
    checks = [1, 2, 3, 5, 8, 13, 21]
    for i in range(22, len(df)):
        if pd.notna(hma20.iloc[i]):
            if c.iloc[i] > hma20.iloc[i] and all(c.iloc[i - j] < hma20.iloc[i - j] for j in checks):
                sigs['Violet'].append((i, 'bullish'))
            if c.iloc[i] < hma20.iloc[i] and all(c.iloc[i - j] > hma20.iloc[i - j] for j in checks):
                sigs['Violet'].append((i, 'bearish'))
    return sigs


def main():
    ap = argparse.ArgumentParser(description="Rainbow 七色指标检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=200)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    if not name or name == code:
        name = resolve_name(code)
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])

    sigs = rainbow_signals(df)
    recent = {k: [(i, t) for i, t in v if i >= len(df) - 90] for k, v in sigs.items()}
    total = sum(len(v) for v in recent.values())
    bulls = sum(1 for v in recent.values() for _, t in v if t == 'bullish')
    bears = total - bulls

    if args.json:
        print(json.dumps({"code": code, "name": name, "bullish": bulls, "bearish": bears,
                          "signals": {k: [(df['date'].iloc[i].strftime('%Y-%m-%d'), t) for i, t in v] for k, v in recent.items()}},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) Rainbow 七色指标（kaabar ch03，公式已核对作者仓库）===")
    for k in ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Indigo', 'Violet']:
        v = recent[k]
        if v:
            print(f"  {k:7s} 近90日 {len(v)} 信号: " + " ".join(
                f"{df['date'].iloc[i].strftime('%m-%d')}{'▲' if t == 'bullish' else '▼'}" for i, t in v[-6:]))
        else:
            print(f"  {k:7s} 近90日无信号")
    print(f"\n汇总: {total} 个信号（看涨 {bulls} / 看跌 {bears}）")
    if bulls >= 3 and bears <= 1:
        print("📌 结论: 七色看涨共振（多指标去相关确认）")
    elif bears >= 3 and bulls <= 1:
        print("📌 结论: 七色看跌共振")
    else:
        print(f"📌 结论: 信号{'偏多' if bulls > bears else '偏空' if bears > bulls else '中性'}（低频特性，单信号谨慎）")

    # 图
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    import numpy as np

    seg = df.tail(90).copy()
    seg['x'] = mdates.date2num(seg['date'])
    r14 = rsi_series(df['close'], 14)
    r14_seg = r14[-90:]
    colors = {'Red': '#e03131', 'Orange': '#f59f00', 'Yellow': '#fcc419', 'Green': '#2f9e44',
              'Blue': '#1971c2', 'Indigo': '#7048e8', 'Violet': '#c2255c'}
    markers = {'Red': 'o', 'Orange': 's', 'Yellow': 'D', 'Green': '^', 'Blue': 'v', 'Indigo': 'P', 'Violet': 'X'}

    fig, (ax, axr) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                  gridspec_kw={'height_ratios': [2.6, 1], 'hspace': 0.1})
    for _, r in seg.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(r['x'], r['low'], r['high'], color=color, lw=1)
        ax.add_patch(Rectangle((r['x'] - 0.32, min(r['open'], r['close'])), 0.64,
                               max(abs(r['close'] - r['open']), 0.02), facecolor=color, alpha=0.9, edgecolor=color))
    idx0 = len(df) - 90
    for k, v in recent.items():
        for i, t in v:
            row = df.iloc[i]
            y = row['high'] + 1 if t == 'bullish' else row['low'] - 1
            ax.scatter(mdates.date2num(row['date']), y, marker=markers[k], s=70,
                       color=colors[k], edgecolor='white', lw=0.5, zorder=6)
    axr.plot(seg['x'], r14_seg, color='#7048e8', lw=1.2, label='RSI14')
    axr.axhline(70, color='#e03131', ls='--', lw=0.7, alpha=0.5)
    axr.axhline(30, color='#2f9e44', ls='--', lw=0.7, alpha=0.5)
    ax.set_title(f"{name} ({code}) Rainbow 七色 ｜ 近90日 {total} 信号（多{ bulls}空{bears}）", fontsize=12, fontweight='bold')
    handles = [plt.Line2D([0], [0], marker=markers[k], color='w', markerfacecolor=colors[k],
                          markersize=9, label=k) for k in colors]
    ax.legend(handles=handles, loc='upper left', fontsize=8, ncol=4)
    axr.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.25); axr.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    out = Path(f"/tmp/rainbow_{code}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
