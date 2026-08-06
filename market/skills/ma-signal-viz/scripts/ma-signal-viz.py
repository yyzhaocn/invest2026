#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ma-signal-viz: 现代均线信号可视化（kaabar ch03）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402


def wma(s, n):
    w = np.arange(1, n + 1)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def iwma(s, n):
    w = np.arange(1, n + 1)[::-1]
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s, n=20):
    return wma(2 * wma(s, max(2, n // 2)) - wma(s, n), int(np.sqrt(n)))


def kama(s, n=10, fast=2, slow=30):
    er = (s - s.shift(n)).abs() / s.diff().abs().rolling(n).sum()
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    k = s.copy(); k.iloc[:n] = s.iloc[:n]
    for i in range(n, len(s)):
        k.iloc[i] = k.iloc[i - 1] + sc.iloc[i] * (s.iloc[i] - k.iloc[i - 1])
    return k


def crosses(a, b):
    """返回金叉(True)/死叉(False)索引列表。"""
    out = []
    for i in range(1, len(a)):
        if pd.notna(a[i]) and pd.notna(a[i - 1]) and pd.notna(b[i]) and pd.notna(b[i - 1]):
            if a[i - 1] <= b[i - 1] and a[i] > b[i]:
                out.append((i, 'golden'))
            if a[i - 1] >= b[i - 1] and a[i] < b[i]:
                out.append((i, 'death'))
    return out


def main():
    ap = argparse.ArgumentParser(description="现代均线信号可视化")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--lookback", type=int, default=20, help="均线周期，默认 20")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])
    c = df['close']
    n = args.lookback
    df['SMA5'], df['SMA20'] = c.rolling(5).mean(), c.rolling(n).mean()
    df['WMA'], df['IWMA'] = wma(c, n), iwma(c, n)
    df['HMA'], df['KAMA'] = hma(c, n), kama(c, min(10, n))

    events = crosses(df['SMA5'].values, df['SMA20'].values) + crosses(df['WMA'].values, df['IWMA'].values)
    events.sort()
    recent = [(df['date'].iloc[i], t) for i, t in events if i >= len(df) - 10]

    last = df.iloc[-1]
    if pd.notna(last['SMA5']) and pd.notna(last['SMA20']):
        if last['SMA5'] > last['SMA20']:
            if last['close'] > last['SMA5']:
                state = "多头排列（价格>SMA5>SMA20）"
            else:
                state = "偏多（SMA5>SMA20，价格在SMA5下方）"
        else:
            if last['close'] < last['SMA5']:
                state = "空头排列（价格<SMA5<SMA20）"
            else:
                state = "偏空（SMA5<SMA20，价格在SMA5上方）"
    else:
        state = "均线未成形"
    wma_bull = last['WMA'] > last['IWMA'] if pd.notna(last['WMA']) and pd.notna(last['IWMA']) else None

    if args.json:
        print(json.dumps({"code": code, "name": name, "state": state,
                          "wma_iwma_bullish": wma_bull,
                          "values": {k: round(float(last[k]), 2) for k in ['SMA5', 'SMA20', 'WMA', 'IWMA', 'HMA', 'KAMA']},
                          "recent_events": [{"date": d.strftime('%Y-%m-%d'), "type": t} for d, t in recent]},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) 现代均线信号（kaabar ch03, lookback={n}）===")
    print("五线最新值:")
    for k in ['SMA5', 'SMA20', 'WMA', 'IWMA', 'HMA', 'KAMA']:
        v = last[k]
        print(f"  {k:6s} {v:.2f}" if pd.notna(v) else f"  {k:6s} --")
    print(f"\n状态: {state}")
    if wma_bull is not None:
        print(f"WMA/IWMA 单参数交叉: {'多头(WMA>IWMA)' if wma_bull else '空头(WMA<IWMA)'}")
    if recent:
        print("近 10 日交叉事件:")
        for d, t in recent:
            print(f"  {d.strftime('%Y-%m-%d')} {'🔴金叉' if t == 'golden' else '🟢死叉'}")

    from chart import render_candlestick
    out = Path(f"/tmp/ma_{code}.png")
    # 多空底色: 价格在SMA20上方为多头区
    seg = df.tail(60)
    bullish_days = seg[seg['close'] > seg['SMA20']]
    hl = []
    if not bullish_days.empty:
        groups = (bullish_days['date'] != bullish_days['date'].shift(1) + pd.Timedelta(days=1)).cumsum() if False else None
        # 简单: 连续多头区间
        seg2 = seg.copy()
        seg2['bull'] = seg2['close'] > seg2['SMA20']
        start = None
        for _, r in seg2.iterrows():
            if r['bull'] and start is None:
                start = r['date']
            elif not r['bull'] and start is not None:
                hl.append({'x0': start, 'x1': r['date'], 'color': '#e03131', 'alpha': 0.08})
                start = None
        if start is not None:
            hl.append({'x0': start, 'x1': seg2['date'].iloc[-1], 'color': '#e03131', 'alpha': 0.08})
    overlays = [
        {'x': seg['date'], 'y': seg['SMA5'], 'color': '#f59e0b', 'label': 'SMA5', 'lw': 1.2},
        {'x': seg['date'], 'y': seg['SMA20'], 'color': '#1971c2', 'label': f'SMA{n}', 'lw': 1.4},
        {'x': seg['date'], 'y': seg['WMA'], 'color': '#2f9e44', 'label': 'WMA', 'lw': 1.2},
        {'x': seg['date'], 'y': seg['IWMA'], 'color': '#e8590c', 'label': 'IWMA', 'lw': 1.0},
        {'x': seg['date'], 'y': seg['HMA'], 'color': '#7048e8', 'label': 'HMA', 'lw': 1.6},
        {'x': seg['date'], 'y': seg['KAMA'], 'color': '#c2255c', 'label': 'KAMA', 'lw': 1.3},
    ]
    markers = [{'x': df['date'].iloc[i], 'y': df['SMA5'].iloc[i], 'marker': '^' if t == 'golden' else 'v',
                'color': '#e03131' if t == 'golden' else '#2f9e44', 'size': 90}
               for i, t in events if i >= len(df) - 60]
    render_candlestick(df, str(out), f"{name} ({code}) 现代均线 ｜ {state}", overlays=overlays,
                       highlight=hl, markers=markers, ma20=False)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
