#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""divergence-detect: RSI 背离检测（kaabar ch03/ch11 斜率背离）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, rsi  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import pandas as pd  # noqa: E402


def find_extremes(df, win):
    """返回摆动高点/低点列表 [(idx, price)]。"""
    highs, lows = [], []
    for i in range(win, len(df) - win):
        if df['high'].iloc[i] == df['high'].iloc[i - win:i + win + 1].max():
            highs.append((i, df['high'].iloc[i]))
        if df['low'].iloc[i] == df['low'].iloc[i - win:i + win + 1].min():
            lows.append((i, df['low'].iloc[i]))
    return highs, lows


def main():
    ap = argparse.ArgumentParser(description="RSI 背离检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--rsi", type=int, default=14)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])
    rsi_vals = rsi(pts, args.rsi)
    df['rsi'] = [None] * (len(df) - len(rsi_vals)) + rsi_vals if isinstance(rsi_vals, list) else pd.Series(rsi_vals)

    highs, lows = find_extremes(df, args.window)
    divs = []
    if len(highs) >= 2:
        (i1, p1), (i2, p2) = highs[-2], highs[-1]
        r1, r2 = df['rsi'].iloc[i1], df['rsi'].iloc[i2]
        if pd.notna(r1) and pd.notna(r2) and p2 > p1 and r2 < r1:
            divs.append({'type': '顶背离', 'points': [(i1, p1, r1), (i2, p2, r2)], 'bullish': False})
    if len(lows) >= 2:
        (i1, p1), (i2, p2) = lows[-2], lows[-1]
        r1, r2 = df['rsi'].iloc[i1], df['rsi'].iloc[i2]
        if pd.notna(r1) and pd.notna(r2) and p2 < p1 and r2 > r1:
            divs.append({'type': '底背离', 'points': [(i1, p1, r1), (i2, p2, r2)], 'bullish': True})

    if args.json:
        out_d = []
        for d in divs:
            out_d.append({'type': d['type'],
                          'points': [(df['date'].iloc[i].strftime('%Y-%m-%d'), p, round(r, 1)) for i, p, r in d['points']]})
        print(json.dumps({"code": code, "name": name, "divergences": out_d}, ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) RSI 背离检测（kaabar ch03/ch11）===")
    if not divs:
        print("最近摆动高低点无顶/底背离")
    for d in divs:
        (i1, p1, r1), (i2, p2, r2) = d['points']
        print(f"\n🔴 {d['type']}:")
        print(f"  摆动1: {df['date'].iloc[i1].strftime('%Y-%m-%d')} 价格 {p1:.2f} RSI {r1:.1f}")
        print(f"  摆动2: {df['date'].iloc[i2].strftime('%Y-%m-%d')} 价格 {p2:.2f} RSI {r2:.1f}")
        print(f"  价格 {'更高' if p2 > p1 else '更低'} 但 RSI {'更低' if r2 < r1 else '更高'} → "
              f"{'看跌' if not d['bullish'] else '看涨'}反转前兆")

    # 双面板图
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    fig, (ax, axr) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True,
                                  gridspec_kw={'height_ratios': [2.4, 1], 'hspace': 0.1})
    seg = df.tail(60)
    x = mdates.date2num(seg['date'])
    for _, r in seg.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(mdates.date2num(r['date']), r['low'], r['high'], color=color, lw=1)
    ax.plot(x, seg['close'], color='#333', lw=1.2)
    axr.plot(x, seg['rsi'], color='#7048e8', lw=1.3, label=f'RSI{args.rsi}')
    axr.axhline(70, color='#e03131', ls='--', lw=0.8, alpha=0.6)
    axr.axhline(30, color='#2f9e44', ls='--', lw=0.8, alpha=0.6)
    for d in divs:
        (i1, p1, _), (i2, p2, _) = d['points']
        color = '#e03131' if not d['bullish'] else '#2f9e44'
        d1, d2 = mdates.date2num(df['date'].iloc[i1]), mdates.date2num(df['date'].iloc[i2])
        ax.plot([d1, d2], [p1, p2], color=color, lw=2, ls='--')
        axr.plot([d1, d2], [df['rsi'].iloc[i1], df['rsi'].iloc[i2]], color=color, lw=2, ls='--')
        ax.annotate(d['type'], xy=(d2, p2), xytext=(d2, p2 + (max(seg['high']) - min(seg['low'])) * 0.08),
                    fontsize=10, color=color, fontweight='bold', ha='center')
    ax.set_title(f"{name} ({code}) RSI 背离检测 ｜ {'、'.join(d['type'] for d in divs) if divs else '无背离'}", fontsize=12, fontweight='bold')
    ax.grid(alpha=0.25); axr.grid(alpha=0.25); axr.legend(loc='upper left', fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    out = Path(f"/tmp/divergence_{code}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
