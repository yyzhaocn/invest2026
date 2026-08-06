#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""price-pattern-detect: 价格结构形态检测（kaabar ch10）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402
import pandas as pd  # noqa: E402


def find_pivots(df, window=3):
    out = []
    for i in range(window, len(df) - window):
        hi, lo = df['high'].iloc[i], df['low'].iloc[i]
        if hi == df['high'].iloc[i - window:i + window + 1].max():
            out.append((i, hi, 'H'))
        if lo == df['low'].iloc[i - window:i + window + 1].min():
            out.append((i, lo, 'L'))
    return out


def detect(df, pivots, tol):
    for n in range(len(pivots) - 2):
        (i1, v1, t1), (i2, v2, t2), (i3, v3, t3) = pivots[n:n + 3]
        if t1 != t3 or t1 == t2:
            continue
        if abs(v1 - v3) / max(v1, v3) > tol:
            continue
        neck = df['high'].iloc[i1:i3 + 1].max() if t1 == 'L' else df['low'].iloc[i1:i3 + 1].min()
        cur = df['close'].iloc[-1]
        if t1 == 'L':  # 双底
            if cur > neck:
                target = neck + (neck - min(v1, v3))
                return {'name': 'DoubleBottom', 'points': [('L1', i1, v1), ('N', i1 + (i2 - i1) // 2, neck), ('L2', i3, v3)],
                        'neck': neck, 'target': target, 'confirmed': True, 'bullish': True}
            return {'name': 'DoubleBottom', 'points': [('L1', i1, v1), ('N', i1 + (i2 - i1) // 2, neck), ('L2', i3, v3)],
                    'neck': neck, 'target': neck + (neck - min(v1, v3)), 'confirmed': False, 'bullish': True}
        else:  # 双顶
            if cur < neck:
                target = neck - (max(v1, v3) - neck)
                return {'name': 'DoubleTop', 'points': [('H1', i1, v1), ('N', i1 + (i2 - i1) // 2, neck), ('H2', i3, v3)],
                        'neck': neck, 'target': target, 'confirmed': True, 'bullish': False}
            return {'name': 'DoubleTop', 'points': [('H1', i1, v1), ('N', i1 + (i2 - i1) // 2, neck), ('H2', i3, v3)],
                    'neck': neck, 'target': neck - (max(v1, v3) - neck), 'confirmed': False, 'bullish': False}
    return None


def main():
    ap = argparse.ArgumentParser(description="价格结构形态检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--tol", type=float, default=0.03, help="相似度容差，默认 0.03")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])
    pat = detect(df, find_pivots(df), args.tol)

    if not pat:
        print(f"{name} ({code}) ｜ 近 120 日未识别到双顶/双底结构（容差 {args.tol:.0%}）")
        return
    if args.json:
        print(json.dumps({"code": code, "name": name, **pat,
                          "points": [(l, df['date'].iloc[i].strftime('%Y-%m-%d'), v) for l, i, v in pat['points']]},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) 价格形态检测（kaabar ch10）===")
    print(f"识别: {pat['name']}（{'看涨' if pat['bullish'] else '看跌'}反转）")
    for l, i, v in pat['points']:
        print(f"  {l}: {df['date'].iloc[i].strftime('%Y-%m-%d')} @ {v:.2f}")
    print(f"颈线: {pat['neck']:.2f} ｜ 量度目标: {pat['target']:.2f}")
    print(f"确认: {'✅ 已破颈线（形态成立）' if pat['confirmed'] else '⏳ 未破颈线（待确认）'}")
    cur = df['close'].iloc[-1]
    print(f"当前: {cur:.2f} ｜ 距目标 {'%+.1f%%' % ((pat['target']/cur-1)*100)}")

    from chart import render_candlestick
    out = Path(f"/tmp/price_{code}.png")
    dxs = [df['date'].iloc[i] for _, i, _ in pat['points']]
    dys = [v for _, _, v in pat['points']]
    color = '#2f9e44' if pat['bullish'] else '#e03131'
    render_candlestick(df, str(out), f"{name} ({code}) {pat['name']} ｜ 目标 {pat['target']:.2f}",
                       overlays=[{'x': dxs, 'y': dys, 'color': color, 'label': pat['name'], 'lw': 2}],
                       hlines=[{'y': pat['neck'], 'color': '#7048e8', 'label': '颈线'},
                               {'y': pat['target'], 'color': color, 'label': '量度目标'}],
                       annotations=[{'x': df['date'].iloc[-1], 'y': cur, 'text': '当前', 'dy': 3, 'color': '#333'}])
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
