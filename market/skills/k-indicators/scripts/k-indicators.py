#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""k-indicators: K's 指标族检测（kaabar ch11，公式核对自作者仓库）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import pandas as pd  # noqa: E402


def macd(s, sw=12, lw=26, sig=9):
    ema_s = s.ewm(span=sw, adjust=False).mean()
    ema_l = s.ewm(span=lw, adjust=False).mean()
    line = ema_s - ema_l
    return line, line.ewm(span=sig, adjust=False).mean()


def k_reversal_I(df):
    """MACD(12,26,9) + BB(100,2σ) 触发。返回 [(idx, 'bullish'|'bearish')]。"""
    line, signal = macd(df['close'])
    mid = df['close'].rolling(100).mean()
    sd = df['close'].rolling(100).std()
    up, lo = mid + 2 * sd, mid - 2 * sd
    sigs = []
    for i in range(1, len(df)):
        if pd.notna(lo.iloc[i]) and pd.notna(line.iloc[i]) and pd.notna(line.iloc[i - 1]):
            if (df['low'].iloc[i] < lo.iloc[i] and df['high'].iloc[i] < mid.iloc[i]
                    and line.iloc[i] > signal.iloc[i] and line.iloc[i - 1] < signal.iloc[i - 1]):
                sigs.append((i, 'bullish'))
            if (df['high'].iloc[i] > up.iloc[i] and df['low'].iloc[i] > mid.iloc[i]
                    and line.iloc[i] < signal.iloc[i] and line.iloc[i - 1] > signal.iloc[i - 1]):
                sigs.append((i, 'bearish'))
    return sigs


def k_reversal_II(df):
    """SMA13 + 21 根 above 状态。"""
    sma13 = df['close'].rolling(13).mean()
    above = (df['close'] > sma13).astype(int)
    pct = above.rolling(21).sum() / 21 * 100
    sigs = []
    for i in range(1, len(df)):
        if pd.notna(pct.iloc[i]) and pd.notna(pct.iloc[i - 1]):
            if pct.iloc[i] == 0 and pct.iloc[i - 1] > 0:
                sigs.append((i, 'bullish'))
            if pct.iloc[i] == 100 and pct.iloc[i - 1] < 100:
                sigs.append((i, 'bearish'))
    return sigs


def rsi_series(s, n=14):
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


def k_rsi2(df):
    """RSI² = RSI(RSI(close,14),14)。"""
    r1 = rsi_series(df['close'])
    return rsi_series(pd.Series(r1), 14)


def main():
    ap = argparse.ArgumentParser(description="K's 指标族检测")
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

    s1 = k_reversal_I(df)
    s2 = k_reversal_II(df)
    r2 = k_rsi2(df)
    r2_now = r2[-1]

    recent = [(i, df['date'].iloc[i], t, 'KRI') for i, t in s1 if i >= len(df) - 60] \
        + [(i, df['date'].iloc[i], t, 'KRII') for i, t in s2 if i >= len(df) - 60]
    recent.sort()

    if args.json:
        print(json.dumps({"code": code, "name": name,
                          "reversal_I_signals": [(df['date'].iloc[i].strftime('%Y-%m-%d'), t) for i, t in s1[-20:]],
                          "reversal_II_signals": [(df['date'].iloc[i].strftime('%Y-%m-%d'), t) for i, t in s2],
                          "rsi2_now": round(r2_now, 1) if r2_now else None},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) K's 指标族检测（kaabar ch11，公式已核对作者仓库）===")
    print(f"K's Reversal I（MACD+BB 100σ2）: 近 60 日 {sum(1 for _, _, t, k in recent if k=='KRI')} 个信号")
    print(f"K's Reversal II（SMA13+21根状态）: 历史共 {len(s2)} 个信号（低频高置信）")
    print(f"K's RSI²: 当前 {r2_now:.1f}（{'超买>70' if r2_now > 70 else '超卖<30' if r2_now < 30 else '中性'}）")
    if recent:
        print("近 60 日信号:")
        for _, d, t, k in recent:
            print(f"  {d.strftime('%Y-%m-%d')} {k} {'🔴看涨' if t=='bullish' else '🟢看跌'}")
    else:
        print("近 60 日无 K's 信号（现代指标低频特性，符合去相关设计）")

    # 图
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    seg = df.tail(80).copy()
    seg['x'] = mdates.date2num(seg['date'])
    seg['sma13'] = seg['close'].rolling(13).mean()
    seg['bbmid'] = seg['close'].rolling(100).mean()
    seg['bbsd'] = seg['close'].rolling(100).std()
    r2_seg = r2[-80:]

    fig, (ax, axr) = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True,
                                  gridspec_kw={'height_ratios': [2.6, 1], 'hspace': 0.1})
    for _, r in seg.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(r['x'], r['low'], r['high'], color=color, lw=1)
        ax.add_patch(Rectangle((r['x'] - 0.32, min(r['open'], r['close'])), 0.64,
                               max(abs(r['close'] - r['open']), 0.02), facecolor=color, alpha=0.9, edgecolor=color))
    ax.plot(seg['x'], seg['sma13'], color='#1971c2', lw=1.3, label='SMA13')
    if seg['bbmid'].notna().any():
        ax.plot(seg['x'], seg['bbmid'], color='#868e96', lw=1, ls='--', label='BB中轨(100)')
        ax.plot(seg['x'], seg['bbmid'] + 2 * seg['bbsd'], color='#e8590c', lw=0.9, alpha=0.7)
        ax.plot(seg['x'], seg['bbmid'] - 2 * seg['bbsd'], color='#2f9e44', lw=0.9, alpha=0.7)
    for i, d, t, k in recent:
        if seg.index[0] <= i <= seg.index[-1]:
            row = df.iloc[i]
            color = '#e03131' if t == 'bullish' else '#2f9e44'
            ax.scatter(mdates.date2num(row['date']), row['low'] - 0.6,
                       marker='^' if t == 'bullish' else 'v', s=110, color=color, zorder=6)
            ax.annotate(k.replace('KRI', 'K1').replace('KRII', 'K2'),
                        xy=(mdates.date2num(row['date']), row['low'] - 0.6),
                        xytext=(mdates.date2num(row['date']), row['low'] - 3),
                        fontsize=8, color=color, ha='center', fontweight='bold')
    axr.plot(seg['x'], r2_seg, color='#7048e8', lw=1.3, label='RSI²')
    axr.axhline(70, color='#e03131', ls='--', lw=0.7, alpha=0.5)
    axr.axhline(30, color='#2f9e44', ls='--', lw=0.7, alpha=0.5)
    ax.set_title(f"{name} ({code}) K's 指标族 ｜ KRI 近期{sum(1 for _, _, t, k in recent if k=='KRI')}信号 ｜ RSI² {r2_now:.0f}",
                 fontsize=12, fontweight='bold')
    ax.legend(loc='upper left', fontsize=8); axr.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.25); axr.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    out = Path(f"/tmp/k_{code}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
