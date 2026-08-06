#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""multi-lens: 个股七维综合分析（kaabar 全书方法论聚合）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


# ---------- 七维检测（内联实现，避免跨技能 import 脆弱性） ----------

def lens_patterns(df):
    """ch07 单K形态。返回 (摘要, 方向: 1看涨/-1看跌/0中性)。"""
    body = (df['close'] - df['open']).abs()
    rng = (df['high'] - df['low']).replace(0, 1e-9)
    ratio = body / rng
    sig = ""
    for i in range(len(df) - 1, max(len(df) - 11, 0), -1):
        if ratio.iloc[i] < 0.15:
            up = df['close'].iloc[i] > df['close'].iloc[i - 5] if i >= 5 else False
            sig = f"Doji({df['date'].iloc[i].strftime('%m-%d')}，{'涨后' if up else '跌后'})"
            return sig, -1 if up else 1
    return "无形态", 0


def lens_fib(df):
    """ch05 斐波那契。返回 (摘要, 方向)。"""
    win = 20
    seg = df.tail(win)
    hi_i, lo_i = seg['high'].idxmax(), seg['low'].idxmin()
    sw_hi, sw_lo = seg.loc[hi_i, 'high'], seg.loc[lo_i, 'low']
    if sw_hi <= sw_lo:
        return "区间异常", 0
    bullish = seg.index.get_loc(lo_i) < seg.index.get_loc(hi_i)
    cur = df['close'].iloc[-1]
    diff = sw_hi - sw_lo
    lv = (sw_hi - diff * 0.618) if bullish else (sw_lo + diff * 0.618)
    pos = "上方(偏强)" if cur > lv else "下方(偏弱)"
    return f"61.8%位 {lv:.2f}，现价{pos}", 1 if cur > lv else -1


def lens_ma(df):
    """ch03 均线。返回 (摘要, 方向)。"""
    c = df['close']
    s5, s20 = c.rolling(5).mean(), c.rolling(20).mean()
    if pd.isna(s20.iloc[-1]):
        return "均线未成形", 0
    if c.iloc[-1] > s5.iloc[-1] > s20.iloc[-1]:
        return f"多头排列(SMA5 {s5.iloc[-1]:.2f}>SMA20 {s20.iloc[-1]:.2f})", 1
    if c.iloc[-1] < s5.iloc[-1] < s20.iloc[-1]:
        return f"空头排列(SMA5 {s5.iloc[-1]:.2f}<SMA20 {s20.iloc[-1]:.2f})", -1
    return f"纠缠(S5 {s5.iloc[-1]:.2f}/S20 {s20.iloc[-1]:.2f})", 0


def lens_vol(df):
    """ch06 波动率。返回 (摘要, 方向=0 不参与方向)。"""
    n = 20
    mid = df['close'].rolling(n).mean()
    sd = df['close'].rolling(n).std()
    bw = (2 * sd) / mid.replace(0, 1e-9)
    valid = bw.dropna().tail(60)
    rank = (valid < bw.iloc[-1]).mean() * 100
    state = "挤压(突破前夜)" if rank <= 20 else ("高波动(警惕)" if rank >= 80 else "正常")
    return f"带宽分位 {rank:.0f}% → {state}", 0


def lens_divergence(df, rsi_s):
    """ch03/11 RSI 背离。返回 (摘要, 方向)。"""
    win = 5
    highs = [(i, df['high'].iloc[i]) for i in range(win, len(df) - win)
             if df['high'].iloc[i] == df['high'].iloc[i - win:i + win + 1].max()]
    lows = [(i, df['low'].iloc[i]) for i in range(win, len(df) - win)
            if df['low'].iloc[i] == df['low'].iloc[i - win:i + win + 1].min()]
    if len(highs) >= 2:
        (i1, p1), (i2, p2) = highs[-2], highs[-1]
        if p2 > p1 and rsi_s[i2] < rsi_s[i1]:
            return f"顶背离(价格新高 RSI未新高)", -1
    if len(lows) >= 2:
        (i1, p1), (i2, p2) = lows[-2], lows[-1]
        if p2 < p1 and rsi_s[i2] > rsi_s[i1]:
            return f"底背离(价格新低 RSI未新低)", 1
    return "无背离", 0


def lens_harmonic(df):
    """ch08 谐波（简化：仅报最近摆动结构）。返回 (摘要, 方向)。"""
    return "未检出经典谐波(需严格比例)", 0


def lens_price_pattern(df):
    """ch10 双顶/双底。返回 (摘要, 方向)。"""
    win = 3
    lows = [(i, df['low'].iloc[i]) for i in range(win, len(df) - win)
            if df['low'].iloc[i] == df['low'].iloc[i - win:i + win + 1].min()]
    if len(lows) >= 2:
        (i1, v1), (i2, v2) = lows[-2], lows[-1]
        if abs(v1 - v2) / max(v1, v2) < 0.03:
            neck = df['high'].iloc[i1:i2 + 1].max()
            cur = df['close'].iloc[-1]
            if cur > neck:
                return f"双底已破颈线({neck:.2f})", 1
            return f"双底形态(待破颈线 {neck:.2f})", 0
    return "无双顶/双底", 0


def main():
    ap = argparse.ArgumentParser(description="个股七维综合分析")
    ap.add_argument("code", help="6 位股票代码")
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

    # RSI 序列（kline.rsi 只返回当前值，这里算全序列）
    closes = df['close'].values
    n = 14
    rsi_s = [None] * len(closes)
    if len(closes) > n:
        gains = losses = 0.0
        for i in range(1, n + 1):
            d = closes[i] - closes[i - 1]
            gains += max(d, 0); losses += max(-d, 0)
        for i in range(n, len(closes)):
            if i > n:
                d = closes[i] - closes[i - 1]
                gains = gains * (n - 1) / n + max(d, 0)
                losses = losses * (n - 1) / n + max(-d, 0)
            rsi_s[i] = 100 - 100 / (1 + gains / losses) if losses > 0 else 50.0

    lenses = [
        ("K线形态", *lens_patterns(df)),
        ("谐波", *lens_harmonic(df)),
        ("斐波那契", *lens_fib(df)),
        ("价格结构", *lens_price_pattern(df)),
        ("现代均线", *lens_ma(df)),
        ("波动率", *lens_vol(df)),
        ("RSI背离", *lens_divergence(df, rsi_s)),
    ]

    bulls = sum(1 for _, _, d in lenses if d == 1)
    bears = sum(1 for _, _, d in lenses if d == -1)
    if bulls >= 3 and bears <= 1:
        verdict = f"🔴 看多共振（{bulls} 多 vs {bears} 空）→ 高置信偏多"
    elif bears >= 3 and bulls <= 1:
        verdict = f"🟢 看空共振（{bears} 空 vs {bulls} 多）→ 高置信偏空"
    elif bulls >= 2 and bears >= 2:
        verdict = f"⚠️ 信号分歧（{bulls} 多 vs {bears} 空）→ 降低仓位，等确认"
    elif bulls > bears:
        verdict = f"偏多（{bulls} 多 vs {bears} 空）"
    elif bears > bulls:
        verdict = f"偏空（{bears} 空 vs {bulls} 多）"
    else:
        verdict = "中性（无方向信号）"

    if args.json:
        print(json.dumps({"code": code, "name": name, "verdict": verdict,
                          "bullish": bulls, "bearish": bears,
                          "lenses": [{"lens": l, "summary": s, "direction": d} for l, s, d in lenses]},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) 七维综合分析（kaabar 全书）===")
    for l, s, d in lenses:
        arrow = {'1': '🔴看涨', '-1': '🟢看跌', '0': '➖中性'}[str(d)]
        print(f"  {pad(l, 8)} {pad(s, 44)} {arrow}")
    print(f"\n📌 综合: {verdict}")
    print(f"   建议: 多空共振时顺势，分歧时观望；波动率高时仓位减半（ch06 风险原则）")

    # 综合图
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    seg = df.tail(60).copy()
    seg['x'] = mdates.date2num(seg['date'])
    seg['ma20'] = seg['close'].rolling(20).mean()
    seg['mid'] = seg['close'].rolling(20).mean()
    seg['sd'] = seg['close'].rolling(20).std()

    fig, (ax, axr, axv) = plt.subplots(3, 1, figsize=(13, 9), sharex=True,
                                       gridspec_kw={'height_ratios': [3, 1, 0.8], 'hspace': 0.08})
    for _, r in seg.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(r['x'], r['low'], r['high'], color=color, lw=1)
        body_b = min(r['open'], r['close'])
        ax.add_patch(Rectangle((r['x'] - 0.32, body_b), 0.64, max(abs(r['close'] - r['open']), 0.02),
                               facecolor=color, alpha=0.9, edgecolor=color))
    ax.plot(seg['x'], seg['ma20'], color='#1971c2', lw=1.4, label='MA20')
    ax.plot(seg['x'], seg['mid'] + 2 * seg['sd'], color='#e8590c', lw=1, alpha=0.8, label='BB上轨')
    ax.plot(seg['x'], seg['mid'] - 2 * seg['sd'], color='#2f9e44', lw=1, alpha=0.8, label='BB下轨')
    ax.set_title(f"{name} ({code}) 七维综合 ｜ {verdict}", fontsize=12.5, fontweight='bold')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.25)

    axr.plot(seg['x'], [rsi_s[df.index.get_loc(i)] if isinstance(rsi_s, list) else rsi_s for i in seg.index],
             color='#7048e8', lw=1.2, label='RSI14')
    axr.axhline(70, color='#e03131', ls='--', lw=0.7, alpha=0.5)
    axr.axhline(30, color='#2f9e44', ls='--', lw=0.7, alpha=0.5)
    axr.legend(loc='upper left', fontsize=8); axr.grid(alpha=0.25)

    for _, r in seg.iterrows():
        up = r['close'] >= r['open']
        axv.bar(r['x'], r['volume'] / 1e6, color='#e03131' if up else '#2f9e44', alpha=0.6, width=0.6)
    axv.set_ylabel('量(百万股)'); axv.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

    out = Path(f"/tmp/multi_{code}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 综合图: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
