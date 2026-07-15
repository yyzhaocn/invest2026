#!/usr/bin/env python3
"""上涨概率选股：全市场 RPT_STOCK_CHANGERATE，写入自选股分组。

分组命名：上涨概率选股_{YYYYMMDD}_{盘前|盘后}
- 交易日 17:00 前：盘前（上一批次）
- 交易日 17:00 后：盘后（当日批次）
"""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime
from typing import Dict, List

import pandas as pd
import requests

from module_cache_policy import rise_prob_pick_csv_basename, rise_prob_pick_group_name
from repo_paths import GENERATED_EM, em_glob
from utils_favorites import get_favorites_manager
from utils_reem import find_latest_stockcomment_files


def _fetch_rise_page(page: int = 1, page_size: int = 50) -> List[Dict]:
    url = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
    params = {
        'reportName': 'RPT_STOCK_CHANGERATE',
        'columns': 'ALL',
        'source': 'WEB',
        'client': 'WEB',
        'pageSize': page_size,
        'pageNumber': page,
        'sortColumns': 'RISE_1_PROBABILITY',
        'sortTypes': '-1',
    }
    r = requests.get(url, params=params, timeout=20)
    text = r.text.strip()
    if '(' in text:
        text = text[text.index('(') + 1:]
        if text.endswith(');'):
            text = text[:-2]
        elif text.endswith(')'):
            text = text[:-1]
    data = json.loads(text)
    return (data.get('result') or {}).get('data') or []


def screen_rise_prob_picks(top_n: int = 30, max_pages: int = 6) -> pd.DataFrame:
    zlb_files = em_glob('*/zjlx_zlb_*.csv')
    if not zlb_files:
        raise FileNotFoundError(f'未找到 zjlx_zlb CSV（目录: {GENERATED_EM}）')
    zlb_path = max(zlb_files, key=os.path.getmtime)
    zlb = pd.read_csv(zlb_path)
    zlb['代码'] = zlb['代码'].astype(str).str.zfill(6)
    ind_map = dict(zip(zlb['代码'], zlb.get('所属行业', pd.Series([''] * len(zlb)))))

    sc_path, _ = find_latest_stockcomment_files()
    if not sc_path:
        raise FileNotFoundError('未找到 stockcomment CSV')
    sc = pd.read_csv(sc_path)
    sc['代码'] = sc['SECURITY_CODE'].astype(str).str.zfill(6)
    score_map = dict(zip(sc['代码'], pd.to_numeric(sc['TOTALSCORE'], errors='coerce')))
    rank_map = dict(zip(sc['代码'], pd.to_numeric(sc['RANK'], errors='coerce')))

    candidates: List[Dict] = []
    for page in range(1, max_pages + 1):
        for row in _fetch_rise_page(page):
            code = str(row.get('SECURITY_CODE', '')).strip().zfill(6)
            name = str(row.get('SECURITY_NAME_ABBR', '')).strip()
            if not code.isdigit() or len(code) != 6 or code.startswith('9'):
                continue
            if re.search(r'ST|退', name):
                continue
            candidates.append({
                '代码': code,
                '名称': name,
                '次日上涨概率': round(float(row.get('RISE_1_PROBABILITY') or 0), 2),
                '五日上涨概率': round(float(row.get('RISE_5_PROBABILITY') or 0), 2),
                '概率总分': round(float(row.get('TOTAL_SCORE') or 0), 2),
                '综合得分': score_map.get(code),
                '综合排名': int(rank_map[code]) if code in rank_map and pd.notna(rank_map[code]) else None,
                '所属行业': ind_map.get(code, ''),
            })

    selected: List[Dict] = []
    seen_ind: Dict[str, int] = {}
    for row in candidates:
        ind = row['所属行业'] or '未知'
        if seen_ind.get(ind, 0) >= 3:
            continue
        selected.append(row)
        seen_ind[ind] = seen_ind.get(ind, 0) + 1
        if len(selected) >= top_n:
            break
    if len(selected) < top_n:
        codes = {r['代码'] for r in selected}
        for row in candidates:
            if row['代码'] in codes:
                continue
            selected.append(row)
            codes.add(row['代码'])
            if len(selected) >= top_n:
                break
    return pd.DataFrame(selected)


def save_rise_prob_picks(df: pd.DataFrame, top_n: int = 30, now: datetime | None = None) -> Dict:
    now = now or datetime.now()
    date_tag = now.strftime('%Y%m%d')
    date_key = now.strftime('%Y-%m-%d')
    group = rise_prob_pick_group_name(date_tag, now)

    em_dirs = glob.glob(os.path.join(GENERATED_EM, '*/'))
    em_dir = max(em_dirs, key=os.path.getmtime) if em_dirs else GENERATED_EM
    csv_path = os.path.join(em_dir.rstrip('/'), rise_prob_pick_csv_basename(top_n, date_tag, now))
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    mgr = get_favorites_manager()
    mgr._reload_from_disk()
    if group not in mgr.config.sections():
        mgr.create_group(group)
    codes = df['代码'].astype(str).str.zfill(6).tolist()
    mgr.config.set(group, date_key, ','.join(codes))
    for _, r in df.iterrows():
        try:
            mgr._remember_group_property(str(r['代码']).zfill(6), group, str(r['名称']))
        except Exception:
            pass
    mgr._save()
    return {'group': group, 'csv': csv_path, 'count': len(df)}


def main():
    df = screen_rise_prob_picks(30)
    result = save_rise_prob_picks(df, 30)
    print(f"=== {result['group']} ({result['count']} 只) ===")
    print(f"CSV: {result['csv']}")
    for i, r in enumerate(df.itertuples(), 1):
        print(f"{i:2}. {r.代码} {r.名称:8} 次日{r.次日上涨概率:.2f}% 五日{r.五日上涨概率:.2f}%")


if __name__ == '__main__':
    main()
