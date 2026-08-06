#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fibonacci-detect: 斐波那契关键位检测（kaabar ch05）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402
import pandas as pd  # noqa: E402

RATIOS = [(0.236, '23.6%'), (0.382, '38.2%'), (0.5, '50.0%'), (0.618, '61.8%'), (0.786, '78.6%')]


def main():
    ap = argparse.ArgumentParser(description="斐波那契关键位检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--swing", type=int, default=20, help="摆动点回溯窗口，默认 20")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])

    win = args.swing
    seg = df.tail(win)
    hi_i, lo_i = seg['high'].idxmax(), seg['low'].idxmin()
    swing_hi, swing_lo = seg.loc[hi_i, 'high'], seg.loc[lo_i, 'low']
    if swing_hi <= swing_lo:
        sys.exit("摆动区间异常")
    diff = swing_hi - swing_lo
    bullish = seg.index.get_loc(lo_i) < seg.index.get_loc(hi_i)  # 低点在前 → 上升摆动

    levels = []
    for r, label in RATIOS:
        if bullish:
            lv = swing_hi - diff * r
        else:
            lv = swing_lo + diff * r
        levels.append((label, round(lv, 2), r))
    proj = round(swing_hi + diff * 1.618, 2) if bullish else round(swing_lo - diff * 1.618, 2)
    cur = df['close'].iloc[-1]

    # 汇聚区: 相邻级别价差 < 1.5%
    zones = []
    for i in range(len(levels) - 1):
        if abs(levels[i][1] - levels[i + 1][1]) / diff < 0.015:
            zones.append((min(levels[i][1], levels[i + 1][1]), max(levels[i][1], levels[i + 1][1]),
                          f"{levels[i][0]}+{levels[i+1][0]}"))
    # 最近支撑/阻力（统一: 支撑=最近的较低级别, 阻力=最近的较高级别）
    support = max((lv for _, lv, _ in levels if lv < cur), default=None)
    resist = min((lv for _, lv, _ in levels if lv > cur), default=None)

    if args.json:
        print(json.dumps({"code": code, "name": name, "swing_hi": swing_hi, "swing_lo": swing_lo,
                          "bullish": bullish, "levels": levels, "projection": proj,
                          "current": round(cur, 2), "support": support, "resistance": resist,
                          "zones": zones}, ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) 斐波那契检测（kaabar ch05）｜ 摆动 {'上升' if bullish else '下降'} "
          f"{swing_lo:.2f} → {swing_hi:.2f} ===")
    for label, lv, _ in levels:
        tag = ""
        if zones and any(z[0] <= lv <= z[1] for z in zones):
            tag = " ★汇聚"
        print(f"  {label:6s} {lv:8.2f}{tag}")
    print(f"  161.8% 投影 {proj:.2f}（目标位）")
    print(f"\n当前价: {cur:.2f}")
    if support:
        print(f"最近支撑: {support:.2f}")
    if resist:
        print(f"最近阻力: {resist:.2f}")
    if zones:
        print("汇聚区: " + " ｜ ".join(f"{a:.2f}-{b:.2f}({z})" for a, b, z in zones))
    if bullish and cur > swing_hi * 0.99:
        print("💡 23.6% 再整合提示: 价格贴近摆动高点，若回踩 23.6% 不破可低吸（强趋势再整合）")

    from chart import render_candlestick
    out = Path(f"/tmp/fibonacci_{code}.png")
    x0, x1 = df['date'].iloc[-win], df['date'].iloc[-1]
    hl_colors = {'23.6%': '#2f9e44', '38.2%': '#1971c2', '50.0%': '#7048e8',
                 '61.8%': '#f59f00', '78.6%': '#e03131'}
    hlines = [{'y': lv, 'label': f"{label} {lv:.1f}", 'color': hl_colors.get(label, '#888'), 'style': '--'}
              for label, lv, _ in levels]
    hlines.append({'y': proj, 'label': f"161.8% {proj:.1f}", 'color': '#c2255c', 'style': '-'})
    hl = [{'x0': x0, 'x1': x1, 'color': '#f59f00', 'alpha': 0.10} for z in zones]
    render_candlestick(df, str(out), f"{name} ({code}) 斐波那契关键位 ｜ 支撑 {support} / 阻力 {resist}",
                       hlines=hlines, highlight=hl,
                       markers=[{'x': df['date'].iloc[-1], 'y': cur, 'marker': 'o', 'color': '#333', 'size': 50}],
                       annotations=[{'x': df['date'].iloc[-1], 'y': cur, 'text': f"现价 {cur:.2f}", 'dy': 2, 'color': '#333'}])
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
