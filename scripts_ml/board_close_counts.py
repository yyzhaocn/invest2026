#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
收盘按板块(二级行业)统计 涨/跌/平 家数。
用 08-17 全市场收盘快照 + 每板块成分股映射。
"""
import sys, csv, time, json, os
sys.path.insert(0, '/Users/yyz/.agents/skills/stock/_shared')
from boards import fetch_block_stocks, load_boards

SNAP = '/Users/yyz/pydev/invest2026/generated/heatmap_snapshots/snapshot_20260817_1500.csv'

# 1. load close snapshot pct by code
snap = {}
with open(SNAP, encoding='utf-8') as f:
    for r in csv.DictReader(f):
        try:
            snap[r['code']] = float(r['chg_pct'])
        except (ValueError, KeyError):
            continue
print(f'快照载入: {len(snap)} 只')

# 2. load 二级行业 blocks
blocks = [r for r in load_boards('二级行业')]
print(f'二级行业板块: {len(blocks)}')

# 3. for each block, fetch constituents, count up/down/flat
rows_out = []
for i, b in enumerate(blocks):
    code = b['code']; name = b.get('name', code)
    try:
        total, stocks = fetch_block_stocks(code)
    except Exception as e:
        print(f'   [skip] {name} ({code}): {e}')
        time.sleep(2); continue
    up = dn = flat = none = 0
    sumchg = 0.0; cnt = 0
    for s in stocks:
        c = s['code']
        chg = snap.get(c)
        if chg is None:
            none += 1; continue
        cnt += 1; sumchg += chg
        if chg > 0: up += 1
        elif chg < 0: dn += 1
        else: flat += 1
    rows_out.append({
        'name': name, 'code': code, 'member': total,
        'matched': cnt, 'up': up, 'down': dn, 'flat': flat,
        'none': none, 'avg_chg': round(sumchg/cnt, 2) if cnt else None
    })
    time.sleep(0.3)  # rate-limit guard

# 4. sort by avg_chg desc, print
rows_out.sort(key=lambda x: (x['avg_chg'] if x['avg_chg'] is not None else -999), reverse=True)
hdr = '板块(二级行业)    成分  覆盖  涨  跌 平  平均涨跌%'
print('\n' + hdr)
print('-'*len(hdr))
tot = {'up':0,'down':0,'flat':0}
for r in rows_out:
    tot['up']+=r['up']; tot['down']+=r['down']; tot['flat']+=r['flat']
    avg = f"{r['avg_chg']:+.2f}" if r['avg_chg'] is not None else '--'
    print(f"{r['name']:<16s} {r['member']:>4d} {r['matched']:>4d} {r['up']:>3d} {r['down']:>3d} {r['flat']:>2d} {avg:>8s}")
print('-'*len(hdr))
print(f"合计联动     涨停家数: {tot['up']} 下跌: {tot['down']} 平: {tot['flat']}")

# save json
import pathlib
out = '/Users/yyz/pydev/invest2026/generated/board_close_pct_20260817.json'
pathlib.Path(out).write_text(json.dumps(rows_out, ensure_ascii=False, indent=2))
print(f'\n已存: {out}')
