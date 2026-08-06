#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pattern-detect: 个股 K 线形态检测 + 结论 + 可视化（kaabar ch07 规则化方法）。

用法:
  python3 pattern-detect.py <股票代码> [--days 60] [--out 路径] [--json]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402

import pandas as pd  # noqa: E402


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def detect_patterns(df):
    """规则化形态检测（kaabar ch07）。返回 df + patterns 列。"""
    df = df.copy()
    df['body'] = (df['close'] - df['open']).abs()
    df['rng'] = (df['high'] - df['low']).replace(0, 1e-9)
    df['body_ratio'] = df['body'] / df['rng']
    df['up_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
    df['dn_wick'] = df[['open', 'close']].min(axis=1) - df['low']
    df['pattern'] = ""

    for i in range(1, len(df)):
        r, p = df.iloc[i], df.iloc[i - 1]
        body, rng, upw, dnw = r['body'], r['rng'], r['up_wick'], r['dn_wick']
        bull = r['close'] > r['open']
        bear = r['close'] < r['open']
        if body / rng < 0.15:
            df.at[i, 'pattern'] = 'Doji'
        elif dnw >= 2 * body and upw <= body * 0.3 and body > 0:
            df.at[i, 'pattern'] = 'Hammer'
        elif upw >= 2 * body and dnw <= body * 0.3 and body > 0:
            df.at[i, 'pattern'] = 'ShootingStar'
        elif (bull and p['close'] < p['open'] and body > p['body'] * 1.2
              and r['open'] <= p['close'] and r['close'] >= p['open']):
            df.at[i, 'pattern'] = 'BullEngulf'
        elif (bear and p['close'] > p['open'] and body > p['body'] * 1.2
              and r['open'] >= p['close'] and r['close'] <= p['open']):
            df.at[i, 'pattern'] = 'BearEngulf'
        elif body / rng > 0.9:
            df.at[i, 'pattern'] = 'Marubozu'
    return df


PATTERN_MEANING = {
    'Doji': ('犹豫', '下跌后=看涨警示 / 上涨后=看跌警示'),
    'Hammer': ('看涨', '下跌后=看涨警示'),
    'ShootingStar': ('看跌', '上涨后=看跌警示'),
    'BullEngulf': ('看涨', '下跌后=看涨警示'),
    'BearEngulf': ('看跌', '上涨后=看跌警示'),
    'Marubozu': ('趋势', '强趋势延续（方向看颜色）'),
}


def make_conclusion(df, code, name):
    """上下文 + 警示 + 确认 + 综合结论。返回 (结论文本, 近期警示列表)。"""
    df['ma20'] = df['close'].rolling(20).mean()
    df['ret5'] = df['close'].pct_change(5) * 100
    df['above_ma'] = df['close'] > df['ma20']
    alerts = []
    for i in range(max(1, len(df) - 10), len(df)):
        if df['pattern'].iloc[i] and df['pattern'].iloc[i] != 'Marubozu':
            p = df['pattern'].iloc[i]
            bearish_loc = df['above_ma'].iloc[i] and (df['ret5'].iloc[i] or 0) > 0
            bullish_loc = not df['above_ma'].iloc[i] and (df['ret5'].iloc[i] or 0) < 0
            side = '看跌' if ('Bear' in p or p == 'ShootingStar') else '看涨'
            # 上下文匹配度
            if (side == '看涨' and bullish_loc) or (side == '看跌' and bearish_loc):
                tag = '匹配(顺势)'
            elif (side == '看涨' and bearish_loc) or (side == '看跌' and bullish_loc):
                tag = '⚠️逆势'
            else:
                tag = '中性'
            alerts.append({
                'date': df['date'].iloc[i], 'pattern': p,
                'close': round(df['close'].iloc[i], 2),
                'side': side, 'tag': tag,
                'above_ma': bool(df['above_ma'].iloc[i]),
                'ret5': round(df['ret5'].iloc[i], 1),
            })
    # 确认：警示后次日方向
    for a in alerts:
        i = df.index[df['date'] == a['date']][0]
        if i + 1 < len(df):
            nxt = df['close'].iloc[i + 1] - df['close'].iloc[i]
            a['confirm'] = '已确认' if (nxt > 0) == (a['side'] == '看涨') else '未确认'
        else:
            a['confirm'] = '待确认(明日)'
    # 综合结论
    last = df.iloc[-1]
    if alerts:
        latest = alerts[-1]
        if latest['confirm'] == '待确认(明日)':
            action = (f"最新形态: {latest['date']} {latest['pattern']}（{latest['side']}警示, "
                      f"{latest['tag']}）→ 明日确认规则: 收盘{'跌破' if latest['side']=='看跌' else '站上'} "
                      f"{latest['close']} 则{'看跌' if latest['side']=='看跌' else '看涨'}确认")
        else:
            action = f"最近确认的形态: {latest['date']} {latest['pattern']} {latest['side']}警示 {latest['confirm']}"
    else:
        action = "近 10 日无有效形态警示"
    trend = "多头(站上MA20)" if last['above_ma'] else "空头(MA20下方)"
    conclusion = (f"{name}({code}) ｜ 趋势: {trend} ｜ 收盘 {last['close']:.2f} "
                  f"(5日 {last['ret5']:+.1f}%) ｜ {action}")
    return conclusion, alerts


def visualize(df, code, name, alerts, out, conclusion):
    """K线 + MA20 + 形态标记 + 量能 + 叙事标注。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False

    df = df.tail(30).copy()
    df['x'] = mdates.date2num(pd.to_datetime(df['date']))
    MARK = {'Doji': ('o', '#f59f00'), 'Hammer': ('^', '#2f9e44'), 'ShootingStar': ('v', '#e03131'),
            'BullEngulf': ('D', '#2f9e44'), 'BearEngulf': ('D', '#e03131'), 'Marubozu': ('s', '#1971c2')}

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(13, 8), sharex=True,
                                  gridspec_kw={'height_ratios': [3.2, 1], 'hspace': 0.08})
    for _, r in df.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(r['x'], r['low'], r['high'], color=color, linewidth=1)
        body_b = min(r['open'], r['close']); body_h = max(abs(r['close'] - r['open']), 0.02)
        ax.add_patch(Rectangle((r['x'] - 0.32, body_b), 0.64, body_h, facecolor=color, alpha=0.9, edgecolor=color))
    ax.plot(df['x'], df['ma20'], color='#1971c2', lw=1.6, label='MA20')

    # 形态标记（近 10 日）
    for _, r in df.tail(10).iterrows():
        if r.get('pattern'):
            mk, mc = MARK.get(r['pattern'], ('o', '#888'))
            ax.scatter(r['x'], r['high'] + 0.6, marker=mk, s=70, facecolor='none', edgecolor=mc,
                       linewidths=2, zorder=5)

    # 叙事标注（警示形态）
    for a in alerts[-3:]:
        row = df[df['date'] == a['date']]
        if row.empty:
            continue
        r = row.iloc[0]
        color = '#e03131' if a['side'] == '看跌' else '#2f9e44'
        ax.annotate(f"{a['pattern']} {a['side']} {a['tag']}\n{a['confirm']}",
                    xy=(r['x'], r['close']), xytext=(r['x'], r['high'] + 3),
                    fontsize=8.5, color=color, ha='center', fontweight='bold',
                    arrowprops=dict(arrowstyle='-', color=color, lw=0.8))

    # 量能
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    for _, r in df.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        vr = r['volume'] / r['vol_ma20'] if r['vol_ma20'] else 1
        axv.bar(r['x'], r['volume'] / 1e6, color=color, alpha=0.4 if vr < 0.7 else (0.9 if vr > 1.5 else 0.65), width=0.6)

    ax.set_title(f"{name} ({code}) ｜ K线形态检测（kaabar ch07）｜ {conclusion[:60]}…", fontsize=11.5, fontweight='bold')
    ax.legend(loc='upper left'); ax.grid(alpha=0.25); axv.grid(alpha=0.25)
    axv.set_ylabel('量(百万股)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)


def resolve_name(code):
    """通过东方财富 suggest 接口补股票名称（东财行情被限流时仍可用）。失败返回 code。"""
    import requests
    try:
        r = requests.get("https://searchapi.eastmoney.com/api/suggest/get",
                         params={"input": code, "type": "14", "count": "1",
                                 "token": "D43BF722C8E33BDC906FB84D85E326E8"},
                         timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        d = r.json().get("QuotationCodeTable") or {}
        rows = d.get("Data") or []
        for x in rows:
            if str(x.get("Code")).zfill(6) == code:
                return str(x.get("Name") or code)
    except Exception:
        pass
    return code


def main():
    ap = argparse.ArgumentParser(description="K 线形态检测 + 结论 + 可视化")
    ap.add_argument("code", help="6 位股票代码")
    ap.add_argument("--days", type=int, default=60, help="检测窗口（默认 60）")
    ap.add_argument("--out", "-o", default="", help="PNG 输出路径")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, pts = fetch_kline(code, lmt=max(args.days, 60))
    if not pts:
        sys.exit(f"❌ 无法获取 {code} K 线（东财/新浪均失败）")
    if not name or name == code:
        name = resolve_name(code)

    df = pd.DataFrame(pts)
    df = detect_patterns(df)
    conclusion, alerts = make_conclusion(df, code, name)

    if args.json:
        print(json.dumps({"code": code, "name": name, "conclusion": conclusion,
                          "alerts": alerts}, ensure_ascii=False, indent=2))
        return

    print(f"=== {name} ({code}) ｜ 近 {len(df)} 日形态检测（kaabar ch07 规则化）===")
    pat_counts = df['pattern'].value_counts().drop('', errors='ignore')
    if not pat_counts.empty:
        print("形态统计: " + "  ".join(f"{k}×{v}" for k, v in pat_counts.items()))
    else:
        print("形态统计: 窗口内无规则化形态")
    print()
    print(pad("日期", 12) + pad("收盘", 9, "right") + pad("5日%", 8, "right") + pad("MA20位", 8, "right") + " 形态")
    for _, r in df.tail(10).iterrows():
        side = "多头" if r.get('above_ma') else "空头"
        print(pad(r['date'], 12) + pad(f"{r['close']:.2f}", 9, "right")
              + pad(f"{r['ret5']:+.1f}", 8, "right") + pad(side, 8, "right") + " " + (r['pattern'] or ""))
    if alerts:
        print("\n警示清单:")
        for a in alerts:
            print(f"  {a['date']} {a['pattern']:12s} {a['side']}警示 {a['tag']:8s} "
                  f"({a['confirm']})  收{a['close']}")
    print(f"\n📌 结论: {conclusion}")

    out = Path(args.out) if args.out else Path(f"/tmp/pattern_{code}.png")
    visualize(df, code, name, alerts, str(out), conclusion)
    print(f"\n📊 图表: {out}")
    subprocess.Popen(["open", str(out)])


if __name__ == "__main__":
    main()
