#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harmonic-detect: 谐波形态检测（kaabar ch08）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402
import pandas as pd  # noqa: E402


def find_pivots(df, window=3):
    highs, lows = [], []
    for i in range(window, len(df) - window):
        hi = df['high'].iloc[i]
        lo = df['low'].iloc[i]
        if hi == df['high'].iloc[i - window:i + window + 1].max() and hi > df['low'].iloc[i - window:i + window + 1].max():
            highs.append(i)
        if lo == df['low'].iloc[i - window:i + window + 1].min() and lo < df['high'].iloc[i - window:i + window + 1].min():
            lows.append(i)
    piv = sorted(set(highs + lows))
    out = []
    for i in piv:
        out.append((i, df['high'].iloc[i] if i in highs else df['low'].iloc[i],
                    'H' if i in highs else 'L'))
    return out


def detect_harmonic(df, pivots):
    patterns = []
    for n in range(len(pivots) - 4):
        (iX, X, _), (iA, A, tA), (iB, B, tB), (iC, C, tC), (iD, D, tD) = pivots[n:n + 5]
        if not (tA == 'L' and tB == 'H' and tC == 'L' and tD == 'H'):  # 熊形 XABCD
            continue
        if not (iX < iA < iB < iC < iD):
            continue
        XA, AB, BC, CD = abs(A - X), abs(B - A), abs(C - B), abs(D - C)
        if XA <= 0 or BC <= 0:
            continue
        rAB_XA, rBC_AB, rCD_BC = AB / XA, BC / AB, CD / BC
        rD_XA = abs(D - X) / XA
        name = None
        if abs(rBC_AB - 0.618) < 0.1 and abs(rCD_BC - 1.272) < 0.12:
            name = 'ABCD'
        elif abs(rAB_XA - 0.618) < 0.08 and abs(rD_XA - 0.786) < 0.05:
            name = 'Gartley'
        elif abs(rAB_XA - 0.382) < 0.08 and abs(rD_XA - 0.886) < 0.05:
            name = 'Bat'
        elif abs(rAB_XA - 0.786) < 0.08 and abs(rD_XA - 1.272) < 0.08:
            name = 'Butterfly'
        elif abs(rAB_XA - 0.382) < 0.08 and abs(rD_XA - 1.618) < 0.08:
            name = 'Crab'
        if name:
            patterns.append({'name': name, 'points': [('X', iX, X), ('A', iA, A), ('B', iB, B),
                                                       ('C', iC, C), ('D', iD, D)],
                             'ratios': {'AB/XA': round(rAB_XA, 3), 'BC/AB': round(rBC_AB, 3),
                                        'CD/BC': round(rCD_BC, 3), 'D/XA': round(rD_XA, 3)}})
    return patterns[-1] if patterns else None


def main():
    ap = argparse.ArgumentParser(description="谐波形态检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])
    pivots = find_pivots(df, window=3)
    pat = detect_harmonic(df, pivots)

    if not pat:
        if args.json:
            print(json.dumps({"code": code, "name": name, "pattern": None}, ensure_ascii=False))
            return
        print(f"{name} ({code}) ｜ 近 120 日未识别到合格谐波形态（Gartley/Bat/Crab/Butterfly/ABCD）")
        print("提示: 摆动点窗口 3，可调整或等待形态成形")
        return

    pts_ = pat['points']
    D_price = pts_[-1][2]
    stop = D_price * 0.98 if pts_[0][2] < D_price else D_price * 1.02  # 熊形止损在上方
    if args.json:
        print(json.dumps({"code": code, "name": name, "pattern": pat, "stop": round(stop, 2)},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) 谐波形态检测（kaabar ch08）===")
    print(f"识别形态: {pat['name']}（熊形，D 为反转高点）")
    for label, i, v in pts_:
        print(f"  {label}: {df['date'].iloc[i].strftime('%Y-%m-%d')} @ {v:.2f}")
    print("比例校验:", "  ".join(f"{k}={v}" for k, v in pat['ratios'].items()))
    print(f"D 点反转位: {D_price:.2f} ｜ 建议止损: {stop:.2f} ｜ 目标: A 点 {pts_[1][2]:.2f} 回测")

    from chart import render_candlestick
    out = Path(f"/tmp/harmonic_{code}.png")
    dxs = [df['date'].iloc[i] for _, i, _ in pts_]
    dys = [v for _, _, v in pts_]
    render_candlestick(df, str(out), f"{name} ({code}) 谐波 {pat['name']} ｜ D={D_price:.2f} 止损 {stop:.2f}",
                       overlays=[{'x': dxs, 'y': dys, 'color': '#7048e8', 'label': 'XABCD', 'lw': 2}],
                       annotations=[{'x': df['date'].iloc[i], 'y': v, 'text': l, 'dy': 4} for l, i, v in pts_],
                       hlines=[{'y': stop, 'color': '#e03131', 'label': '止损'}],
                       markers=[{'x': dxs[-1], 'y': D_price, 'marker': 'X', 'color': '#e03131', 'size': 120}])
    print(f"📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
