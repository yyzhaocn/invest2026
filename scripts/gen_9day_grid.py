#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""华天科技最近 N 个交易日 3x3 子图（按日期顺序排列）。

用法: python3 gen_9day_grid.py <代码> [--days 9] [--out 路径]
每格 = 一根日K + 开/高/低/收/涨跌/量 标注。
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

ROOT = Path(__file__).resolve().parents[1]


def load_kline(code: str):
    p = ROOT / "generated" / "cache" / "kline" / f"{code}.json"
    if not p.exists():
        sys.exit(f"❌ 无缓存: {p}，请先刷新 K 线")
    d = json.loads(p.read_text(encoding="utf-8"))
    return d.get("name") or code, d.get("points", [])


def main():
    ap = argparse.ArgumentParser(description="最近 N 交易日 3x3 K线子图")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--days", type=int, default=9, help="交易日数（默认 9 = 3x3）")
    ap.add_argument("--out", default="", help="输出路径（默认 /tmp/kline_grid_<code>.png）")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = load_kline(code)
    if not pts:
        sys.exit(f"❌ {code} 无 K 线数据")

    days = pts[-args.days:]
    cols = rows = int(args.days ** 0.5)
    while cols * rows < args.days:
        cols += 1

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.6, rows * 3.0), squeeze=False)
    fig.suptitle(f"{name} ({code}) 最近 {len(days)} 个交易日 ｜ 按日期顺序 ｜ 数据截止 {days[-1]['date']}",
                 fontsize=13, fontweight='bold', y=0.995)

    # 全局价格范围（统一坐标，便于比较）
    lo = min(p['low'] for p in days)
    hi = max(p['high'] for p in days)
    pad = (hi - lo) * 0.12

    for i, p in enumerate(days):
        ax = axes[i // cols][i % cols]
        up = p['close'] >= p['open']
        color = '#e03131' if up else '#2f9e44'
        # 影线
        ax.vlines(0, p['low'], p['high'], color=color, lw=1.5)
        # 实体
        body_b = min(p['open'], p['close'])
        body_h = max(abs(p['close'] - p['open']), 0.02)
        ax.add_patch(Rectangle((-0.28, body_b), 0.56, body_h,
                               facecolor=color, alpha=0.92, edgecolor=color))
        # 标题 = 日期 + 涨跌
        ax.set_title(f"{p['date'][5:]}  {p['pct']:+.2f}%", fontsize=11, fontweight='bold',
                     color='#c92a2a' if up else '#2f9e44')
        # 关键价标注
        ax.text(0.42, p['high'], f"H{p['high']:.2f}", fontsize=7.5, va='bottom', color='#868e96')
        ax.text(0.42, p['low'], f"L{p['low']:.2f}", fontsize=7.5, va='top', color='#868e96')
        ax.text(0, body_b + body_h / 2, f"O{p['open']:.2f} C{p['close']:.2f}",
                fontsize=7.5, ha='center', va='center', color='#495057')
        # 量能条
        vmax = max(p['volume'] for p in days)
        ax.text(0.42, lo - pad * 0.35, f"量{p['volume']/1e6:.0f}M", fontsize=7, color='#adb5bd')
        ax.set_xlim(-0.6, 0.6)
        ax.set_ylim(lo - pad, hi + pad)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color('#dee2e6')

    # 隐藏多余子图
    for i in range(len(days), rows * cols):
        axes[i // cols][i % cols].axis('off')

    out = Path(args.out) if args.out else Path(f"/tmp/kline_grid_{code}.png")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out, dpi=150, bbox_inches='tight')
    print(f"✅ 9日网格图: {out}")

    import subprocess
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
