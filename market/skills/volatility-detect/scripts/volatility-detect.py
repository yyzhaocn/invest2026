#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""volatility-detect: 波动率检测与可视化（kaabar ch06）。"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, resolve_name  # noqa: E402
import pandas as pd  # noqa: E402


def atr(df, n=14):
    tr = pd.concat([df['high'] - df['low'],
                    (df['high'] - df['close'].shift(1)).abs(),
                    (df['low'] - df['close'].shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def main():
    ap = argparse.ArgumentParser(description="波动率检测")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--window", type=int, default=20)
    ap.add_argument("--k", type=float, default=2.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=120)
    if not name or name == code:
        name = resolve_name(code)
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线")
    df = pd.DataFrame(pts)
    df['date'] = pd.to_datetime(df['date'])
    n, k = args.window, args.k
    df['mid'] = df['close'].rolling(n).mean()
    df['sd'] = df['close'].rolling(n).std()
    df['upper'] = df['mid'] + k * df['sd']
    df['lower'] = df['mid'] - k * df['sd']
    df['bw'] = (df['upper'] - df['lower']) / df['mid'].replace(0, 1e-9)
    df['atr'] = atr(df)
    df['atr_pct'] = df['atr'] / df['close'] * 100

    valid = df.dropna(subset=['bw']).tail(60)
    cur_bw = df['bw'].iloc[-1]
    pct_rank = (valid['bw'] < cur_bw).mean() * 100
    squeeze = pct_rank <= 20
    high_vol = pct_rank >= 80
    atr_v = df['atr_pct'].iloc[-1]
    atr_grade = '低(<2%)' if atr_v < 2 else ('中(2-4%)' if atr_v <= 4 else '高(>4%)')

    last = df.iloc[-1]
    break_dir = '向上' if last['close'] > last['mid'] else '向下'

    if args.json:
        print(json.dumps({"code": code, "name": name, "bandwidth_pct_rank": round(pct_rank, 1),
                          "squeeze": bool(squeeze), "high_vol": bool(high_vol),
                          "atr_pct": round(atr_v, 2), "atr_grade": atr_grade,
                          "break_direction": break_dir, "current": round(last['close'], 2),
                          "upper": round(last['upper'], 2), "lower": round(last['lower'], 2)},
                         ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) 波动率检测（kaabar ch06, BB{n}/{k}σ）===")
    print(f"带宽分位: {pct_rank:.0f}%（近 60 日） ｜ 布林带 {last['lower']:.2f} ~ {last['upper']:.2f}（中轨 {last['mid']:.2f}）")
    if squeeze:
        print(f"状态: 🔴 挤压中（带宽处于近 60 日最低 {pct_rank:.0f}%）→ 突破前夜，关注方向")
    elif high_vol:
        print(f"状态: 🟡 高波动（带宽 {pct_rank:.0f}% 分位）→ 警惕追高/剧烈波动")
    else:
        print(f"状态: 🟢 正常波动（{pct_rank:.0f}% 分位）")
    print(f"ATR14: {df['atr'].iloc[-1]:.2f}（{atr_v:.1f}% 价格）→ 波动率{atr_grade}")
    print(f"当前位置: 收盘 {last['close']:.2f} 在中轨{'上方（偏强）' if last['close'] > last['mid'] else '下方（偏弱）'}，近期倾向{break_dir}")

    from chart import render_candlestick
    out = Path(f"/tmp/volatility_{code}.png")
    seg = df.tail(60)
    # 挤压区间高亮
    squeeze_bands = valid[valid['bw'] <= valid['bw'].quantile(0.2)]
    hl = []
    if not squeeze_bands.empty:
        dts = squeeze_bands['date'].tolist()
        # 连续段
        segs, s = [], dts[0]
        for a, b in zip(dts, dts[1:]):
            if (b - a).days > 5:
                segs.append((s, a)); s = b
        segs.append((s, dts[-1]))
        hl = [{'x0': a, 'x1': b, 'color': '#f59f00', 'alpha': 0.15} for a, b in segs if (b - a).days >= 2]
    overlays = [{'x': seg['date'], 'y': seg['upper'], 'color': '#e8590c', 'label': f'上轨 {k}σ', 'lw': 1.1},
                {'x': seg['date'], 'y': seg['lower'], 'color': '#2f9e44', 'label': f'下轨 {k}σ', 'lw': 1.1},
                {'x': seg['date'], 'y': seg['mid'], 'color': '#1971c2', 'label': '中轨', 'lw': 1.2}]
    render_candlestick(df, str(out), f"{name} ({code}) 波动率 ｜ 带宽分位 {pct_rank:.0f}% ｜ ATR {atr_v:.1f}%",
                       overlays=overlays, highlight=hl, ma20=False)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
