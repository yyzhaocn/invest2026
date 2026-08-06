#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享 K 线图表渲染 (harmonic/fibonacci/price-pattern/ma-signal/volatility/divergence 共用)。

render_candlestick(df, out, title, ...) 绘制红涨绿跌 K 线 + MA20 + 量能，
支持叠加线/水平线/标记/标注/底色区。
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle


def _fonts():
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Hiragino Sans GB', 'Arial Unicode MS', 'STHeiti']
    plt.rcParams['axes.unicode_minus'] = False


def render_candlestick(df, out, title,
                       ma20=True, volume=True,
                       overlays=None, hlines=None, markers=None,
                       annotations=None, highlight=None, days=30):
    """绘制 K 线图。

    df: date/open/high/low/close/volume (+ ma20 可选)
    overlays: [{'x': [dates], 'y': [vals], 'color', 'label', 'lw'}]
    hlines:   [{'y', 'color', 'label', 'style'}]
    markers:  [{'x', 'y', 'marker', 'color', 'size'}]
    annotations: [{'x', 'y', 'text', 'color', 'dy'}]
    highlight: [{'x0', 'x1', 'color', 'alpha'}]  纵向底色区
    """
    _fonts()
    import pandas as pd
    df = df.tail(days).copy()
    df['x'] = mdates.date2num(pd.to_datetime(df['date']))

    n_sub = 2 if volume else 1
    fig, axs = plt.subplots(n_sub, 1, figsize=(13, 8 if volume else 6.5),
                            sharex=True, gridspec_kw={'height_ratios': [3.2, 1] if volume else [1],
                                                      'hspace': 0.08})
    ax = axs[0] if volume else axs
    axv = axs[1] if volume else None

    for _, r in df.iterrows():
        up = r['close'] >= r['open']
        color = '#e03131' if up else '#2f9e44'
        ax.vlines(r['x'], r['low'], r['high'], color=color, linewidth=1)
        body_b = min(r['open'], r['close'])
        body_h = max(abs(r['close'] - r['open']), 0.02)
        ax.add_patch(Rectangle((r['x'] - 0.32, body_b), 0.64, body_h,
                               facecolor=color, alpha=0.9, edgecolor=color))

    if ma20 and 'ma20' in df.columns:
        ax.plot(df['x'], df['ma20'], color='#1971c2', lw=1.4, label='MA20')

    for hl in highlight or []:
        ax.axvspan(mdates.date2num(pd.to_datetime(hl['x0'])),
                   mdates.date2num(pd.to_datetime(hl['x1'])),
                   color=hl.get('color', '#f59f00'), alpha=hl.get('alpha', 0.12))

    for o in overlays or []:
        xs = [mdates.date2num(pd.to_datetime(x)) for x in o['x']]
        ax.plot(xs, o['y'], color=o.get('color', '#7048e8'), lw=o.get('lw', 1.4),
                label=o.get('label'), alpha=o.get('alpha', 1))

    for h in hlines or []:
        ax.axhline(h['y'], color=h.get('color', '#f59f00'), linestyle=h.get('style', '--'),
                   lw=1.2, alpha=0.8, label=h.get('label'))

    for m in markers or []:
        ax.scatter(mdates.date2num(pd.to_datetime(m['x'])), m['y'],
                   marker=m.get('marker', 'o'), s=m.get('size', 60), facecolor='none',
                   edgecolor=m.get('color', '#f59f00'), linewidths=2, zorder=6)

    for a in annotations or []:
        ax.annotate(a['text'], xy=(mdates.date2num(pd.to_datetime(a['x'])), a['y']),
                    xytext=(mdates.date2num(pd.to_datetime(a['x'])), a['y'] + a.get('dy', 3)),
                    fontsize=8.5, color=a.get('color', '#333'), ha='center', fontweight='bold',
                    arrowprops=dict(arrowstyle='-', color=a.get('color', '#333'), lw=0.8))

    if axv is not None:
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        for _, r in df.iterrows():
            up = r['close'] >= r['open']
            color = '#e03131' if up else '#2f9e44'
            vr = r['volume'] / r['vol_ma20'] if r['vol_ma20'] else 1
            axv.bar(r['x'], r['volume'] / 1e6, color=color,
                    alpha=0.4 if vr < 0.7 else (0.9 if vr > 1.5 else 0.65), width=0.6)
        axv.set_ylabel('量(百万股)')

    ax.set_title(title, fontsize=12, fontweight='bold')
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc='upper left', fontsize=9)
    ax.grid(alpha=0.25)
    if axv is not None:
        axv.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out
