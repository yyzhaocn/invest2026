#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""heikin-ashi-viz: Heikin-Ashi 趋势检测与图表（kaabar ch04，公式核对自作者仓库）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import pandas as pd  # noqa: E402


def heikin_ashi(df):
    """公式核对自 master_library.heikin_ashi。"""
    out = pd.DataFrame()
    out['HA_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    out['HA_open'] = 0.0
    out['HA_open'].iloc[0] = df['open'].iloc[0]
    for i in range(1, len(df)):
        out.at[i, 'HA_open'] = (out['HA_open'].iloc[i - 1] + out['HA_close'].iloc[i - 1]) / 2
    out['HA_high'] = df[['high']].join(out[['HA_open', 'HA_close']]).max(axis=1)
    out['HA_low'] = df[['low']].join(out[['HA_open', 'HA_close']]).min(axis=1)
    out['date'] = df['date']
    return out


def trend_read(ha):
    """连阳/连阴计数 + 翻转警示。"""
    bull = ha['HA_close'] >= ha['HA_open']
    streak, streak_type = 0, ''
    for b in reversed(bull.tolist()):
        t = 'bull' if b else 'bear'
        if streak_type == '' or t == streak_type:
            streak += 1
            streak_type = t
        else:
            break
    flip = len(bull) > 1 and bull.iloc[-1] != bull.iloc[-2]
    # 无影线强趋势
    last = ha.iloc[-1]
    no_wick = (abs(last['HA_close'] - last['HA_high']) < 1e-9) if streak_type == 'bull' else \
        (abs(last['HA_close'] - last['HA_low']) < 1e-9)
    return streak, streak_type, flip, no_wick


def main():
    ap = argparse.ArgumentParser(description="Heikin-Ashi 趋势检测")
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
    ha = heikin_ashi(df)

    streak, stype, flip, no_wick = trend_read(ha)
    trend = "多头" if stype == 'bull' else "空头"
    strength = "强(连阳≥5)" if (stype == 'bull' and streak >= 5) else \
        ("强(连阴≥5)" if (stype == 'bear' and streak >= 5) else
         ("确认(≥3)" if streak >= 3 else "初现(<3)"))

    if args.json:
        print(json.dumps({"code": code, "name": name, "trend": trend, "streak": streak,
                          "flip": bool(flip), "no_wick": bool(no_wick), "strength": strength},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) Heikin-Ashi 趋势（kaabar ch04，公式已核对作者仓库）===")
    print(f"当前: {trend}趋势 连{trend}{streak} 根（{strength}）")
    if no_wick:
        print(f"⚠️ 最新 HA 无影线（{'close=high 强多' if stype == 'bull' else 'close=low 强空'}）→ 趋势加速中")
    if flip:
        print(f"⚠️ 颜色翻转（上一根为{'阴' if stype == 'bull' else '阳'}）→ 趋势转折警示")
    last = ha.iloc[-1]
    print(f"最新 HA: open {last['HA_open']:.2f} / close {last['HA_close']:.2f} / "
          f"high {last['HA_high']:.2f} / low {last['HA_low']:.2f}")
    print(f"对照普通K线: 收盘 {df['close'].iloc[-1]:.2f}（{'收阳' if df['close'].iloc[-1] >= df['open'].iloc[-1] else '收阴'}）")

    # 图: HA + 普通 K 双面板
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    seg_ha = ha.tail(40)
    seg_df = df.tail(40)
    fig, (axh, axn) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                   gridspec_kw={'height_ratios': [1, 1], 'hspace': 0.1})
    for ax, src, is_ha in ((axh, seg_ha, True), (axn, seg_df, False)):
        for _, r in src.iterrows():
            if is_ha:
                o, c, h, l = r['HA_open'], r['HA_close'], r['HA_high'], r['HA_low']
            else:
                o, c, h, l = r['open'], r['close'], r['high'], r['low']
            up = c >= o
            color = '#e03131' if up else '#2f9e44'
            x = mdates.date2num(r['date'])
            ax.vlines(x, l, h, color=color, lw=1)
            ax.add_patch(Rectangle((x - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.02),
                                   facecolor=color, alpha=0.9, edgecolor=color))
    axh.set_title(f"{name} ({code}) Heikin-Ashi（上）vs 普通K线（下）｜ {trend}趋势 连{streak}根", fontsize=12, fontweight='bold')
    axn.set_ylabel('普通K线', fontsize=9)
    axh.set_ylabel('Heikin-Ashi', fontsize=9)
    axh.grid(alpha=0.25); axn.grid(alpha=0.25)
    axn.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    out = Path(f"/tmp/ha_{code}.png")
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
