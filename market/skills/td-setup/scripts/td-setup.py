#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""td-setup: TD Setup + Fibonacci timing 计数检测（kaabar ch09，公式核对自作者仓库）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import pandas as pd  # noqa: E402


def td_setup(df, final_step=9, difference=4, perfected=False):
    """公式核对自 master_library.td_setup。返回 (buy_counts, sell_counts, signals)。"""
    c = df['close']
    buy, sell = [0] * len(df), [0] * len(df)
    sig = [0] * len(df)
    for i in range(difference, len(df)):
        if c.iloc[i] < c.iloc[i - difference]:
            buy[i] = buy[i - 1] + 1 if buy[i - 1] < final_step else 0
        else:
            buy[i] = 0
        if c.iloc[i] > c.iloc[i - difference]:
            sell[i] = sell[i - 1] + 1 if sell[i - 1] < final_step else 0
        else:
            sell[i] = 0
    for i in range(difference, len(df)):
        if buy[i] == final_step:
            if not perfected or (df['low'].iloc[i] < df['low'].iloc[i - 2]
                                 and df['low'].iloc[i] < df['low'].iloc[i - 3]):
                if i + 1 < len(df):
                    sig[i + 1] = 1
        elif sell[i] == final_step:
            if not perfected or (df['high'].iloc[i] > df['high'].iloc[i - 2]
                                 and df['high'].iloc[i] > df['high'].iloc[i - 3]):
                if i + 1 < len(df):
                    sig[i + 1] = -1
    return buy, sell, sig


def fib_timing(df, final_step=8, d1=5, d2=21):
    """Fibonacci timing pattern（master_library.fibonacci_timing_pattern）。"""
    c = df['close']
    buy, sell = [0] * len(df), [0] * len(df)
    sig = [0] * len(df)
    for i in range(d2, len(df)):
        if c.iloc[i] < c.iloc[i - d1] and c.iloc[i - d1] < c.iloc[i - d2]:
            buy[i] = buy[i - 1] + 1 if buy[i - 1] < final_step else 0
        else:
            buy[i] = 0
        if c.iloc[i] > c.iloc[i - d1] and c.iloc[i - d1] > c.iloc[i - d2]:
            sell[i] = sell[i - 1] + 1 if sell[i - 1] < final_step else 0
        else:
            sell[i] = 0
    for i in range(d2, len(df)):
        if buy[i] == final_step and i + 1 < len(df):
            sig[i + 1] = 1
        elif sell[i] == final_step and i + 1 < len(df):
            sig[i + 1] = -1
    return buy, sell, sig


def main():
    ap = argparse.ArgumentParser(description="TD Setup 计数检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--perfected", action="store_true", help="只显示 perfected 确认信号")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    if not name or name == code:
        name = resolve_name(code)
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])

    buy, sell, sig = td_setup(df, perfected=args.perfected)
    fb, fs, fsig = fib_timing(df)

    b_now, s_now = buy[-1], sell[-1]
    signals = [(i, s) for i, s in enumerate(sig) if s != 0]
    fib_sigs = [(i, s) for i, s in enumerate(fsig) if s != 0]
    ma20 = df['close'].rolling(20).mean()
    regime = "震荡" if abs(df['close'].iloc[-1] / ma20.iloc[-1] - 1) < 0.03 else \
        ("多头" if df['close'].iloc[-1] > ma20.iloc[-1] else "空头")

    if args.json:
        print(json.dumps({"code": code, "name": name,
                          "buy_count": b_now, "sell_count": s_now,
                          "regime": regime,
                          "td_signals": [(df['date'].iloc[i].strftime('%Y-%m-%d'), 'bullish' if s == 1 else 'bearish') for i, s in signals],
                          "fib_timing_signals": [(df['date'].iloc[i].strftime('%Y-%m-%d'), 'bullish' if s == 1 else 'bearish') for i, s in fib_sigs]},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) TD Setup 检测（kaabar ch09，公式已核对作者仓库）===")
    print(f"当前计数: 看涨 {b_now} / 看跌 {s_now}（目标 9）{'✅已完成!' if b_now == 9 or s_now == 9 else ''}")
    print(f"Regime: {regime}（{'✅ 震荡市 → TD 有效' if regime == '震荡' else '⚠️ 趋势市 → TD 可能失效（书 ch09）'}）")
    if signals:
        print("TD 9 信号（近 60 日）:")
        for i, s in signals[-6:]:
            if i >= len(df) - 60:
                print(f"  {df['date'].iloc[i].strftime('%Y-%m-%d')} {'🔴看涨' if s == 1 else '🟢看跌'}")
    else:
        print("近 60 日无 TD 9 信号（计数未完成）")
    if fib_sigs:
        print("Fibonacci timing 信号:", "  ".join(
            f"{df['date'].iloc[i].strftime('%m-%d')}{'多' if s == 1 else '空'}" for i, s in fib_sigs[-5:]))

    # 图：计数徽章
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    seg = df.tail(40).copy()
    seg['x'] = mdates.date2num(seg['date'])
    seg['ma20'] = seg['close'].rolling(20).mean()
    idx0 = len(df) - 40
    fig, ax = plt.subplots(figsize=(13, 6.5))
    for _, r in seg.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(r['x'], r['low'], r['high'], color=color, lw=1)
        ax.add_patch(Rectangle((r['x'] - 0.32, min(r['open'], r['close'])), 0.64,
                               max(abs(r['close'] - r['open']), 0.02), facecolor=color, alpha=0.9, edgecolor=color))
    ax.plot(seg['x'], seg['ma20'], color='#1971c2', lw=1.4, label='MA20')
    # 计数徽章
    for i in range(idx0, len(df)):
        x = seg['x'].iloc[i - idx0]
        b, s = buy[i], sell[i]
        if b > 0:
            ax.text(x, df['low'].iloc[i] - 1.2, f"B{b}", fontsize=7.5, ha='center',
                    color='#e03131', fontweight='bold' if b == 9 else 'normal')
        if s > 0:
            ax.text(x, df['low'].iloc[i] - 2.6, f"S{s}", fontsize=7.5, ha='center',
                    color='#2f9e44', fontweight='bold' if s == 9 else 'normal')
    for i, s in signals:
        if idx0 <= i < len(df):
            color = '#e03131' if s == 1 else '#2f9e44'
            ax.annotate('9!', xy=(seg['x'].iloc[i - idx0], df['high'].iloc[i]),
                        xytext=(seg['x'].iloc[i - idx0], df['high'].iloc[i] + 1),
                        fontsize=12, color=color, ha='center', fontweight='bold')
    ax.set_title(f"{name} ({code}) TD Setup ｜ 计数 B{b_now}/S{s_now} ｜ {regime}市 ｜ "
                 f"{'perfected' if args.perfected else 'unperfected+perfected'}", fontsize=12, fontweight='bold')
    ax.legend(loc='upper left', fontsize=9); ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    out = Path(f"/tmp/td_{code}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
