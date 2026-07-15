#!/usr/bin/env python3
"""S1–S5 策略选股：基于 zjlx + flow，写入自选股分组。

策略（624→625 回测验证）：
- S1 防御强资金：航空/券商/银行等低波动 + 大流入
- S2 科技大流入：半导体/电子等 + 主力 ≥1 亿
- S3 战术 2.0：低振幅 + 静默 + 大流入
- S4 资金加速科技：早/收双快照，主力加速（需当日早盘 zjlx）
- S5 超大单突击：超大单净占比高 + 温和上涨 + 适度换手
"""
from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from module_cache_policy import strategy_pick_csv_basename, strategy_pick_group_name
from repo_paths import GENERATED_EM
from utils_favorites import get_favorites_manager
from utils_reem import find_latest_zjlx_zlb_file

DEFENSE_INDUSTRIES = frozenset({
    '航空机场', '证券Ⅱ', '银行', '保险', '铁路公路', '航运港口',
})
TECH_INDUSTRIES = frozenset({
    '半导体', '电子元件', '光学光电子', '通信设备', '计算机设备', '消费电子',
})
BAD_INDUSTRIES = frozenset({'能源金属', '小金属'})

NUM_COLS = (
    '最新价', '今日涨跌幅', '换手率', '主力净流入', '主力净占比', '超大单净流入', '超大单净占比',
    '开盘价', '最高价', '最低价', '昨收价', '振幅',
)


def _find_flow_for_zlb(zlb_path: str) -> Optional[str]:
    folder = os.path.dirname(zlb_path)
    base = os.path.basename(zlb_path)
    suffix = base.replace('zjlx_zlb_', '')
    candidate = os.path.join(folder, f'flow_{suffix}')
    if os.path.isfile(candidate):
        return candidate
    flows = glob.glob(os.path.join(folder, 'flow_*.csv'))
    return max(flows, key=os.path.getmtime) if flows else None


def _find_morning_zlb(close_path: str) -> Optional[str]:
    folder = os.path.dirname(close_path)
    files = glob.glob(os.path.join(folder, 'zjlx_zlb_*.csv'))
    close_name = os.path.basename(close_path)
    others = [p for p in files if os.path.basename(p) != close_name]
    if not others:
        return None
    for pat in ('1004', '0956', '1030', '1100'):
        matched = [p for p in others if pat in os.path.basename(p)]
        if matched:
            return max(matched, key=os.path.getmtime)
    return min(others, key=os.path.getmtime)


def _load_zjlx(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df['代码'] = df['代码'].astype(str).str.zfill(6)
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.drop_duplicates('代码', keep='first')


def load_universe() -> Tuple[pd.DataFrame, str, Optional[str], str, str]:
    zlb_path = find_latest_zjlx_zlb_file(prefer_today=True)
    if not zlb_path:
        raise FileNotFoundError(f'未找到 zjlx_zlb CSV（目录: {GENERATED_EM}）')
    flow_path = _find_flow_for_zlb(zlb_path)
    if not flow_path:
        raise FileNotFoundError(f'未找到 flow CSV（zjlx: {zlb_path}）')

    folder = os.path.basename(os.path.dirname(zlb_path))
    if len(folder) == 6 and folder.isdigit():
        data_date_tag = '20' + folder
        data_date_key = f'20{folder[:2]}-{folder[2:4]}-{folder[4:6]}'
    else:
        data_date_tag = datetime.now().strftime('%Y%m%d')
        data_date_key = datetime.now().strftime('%Y-%m-%d')

    z_close = _load_zjlx(zlb_path)
    flow = pd.read_csv(flow_path)
    flow['代码'] = flow['股票代码'].astype(str).str.zfill(6)
    flow['市值分位'] = pd.to_numeric(flow['市值分位'], errors='coerce')
    flow['流通市值'] = pd.to_numeric(flow['流通市值'], errors='coerce')

    df = z_close.rename(columns={'最新价': '入池价', '今日涨跌幅': '入池涨跌'})
    keep = [
        '代码', '名称', '入池价', '入池涨跌', '换手率', '主力净流入', '主力净占比',
        '超大单净流入', '超大单净占比', '所属行业', '开盘价', '最高价', '最低价', '昨收价', '振幅',
    ]
    df = df[[c for c in keep if c in df.columns]]
    df = df.merge(flow[['代码', '市值分位', '流通市值']].drop_duplicates('代码'), on='代码', how='left')
    df['流通市值_亿'] = np.where(df['流通市值'].fillna(0) > 1e6, df['流通市值'] / 1e8, df['流通市值'])

    rng = (df['最高价'] - df['最低价']).replace(0, np.nan)
    df['收盘强度'] = ((df['入池价'] - df['最低价']) / rng).fillna(0.5)
    df['上影比'] = ((df['最高价'] - df['入池价']) / rng).fillna(0)

    morn_path = _find_morning_zlb(zlb_path)
    if morn_path:
        zm = _load_zjlx(morn_path)[['代码', '今日涨跌幅', '主力净流入']].rename(columns={
            '今日涨跌幅': '早涨跌', '主力净流入': '早主力',
        })
        df = df.merge(zm, on='代码', how='left')
        df['主力加速'] = df['主力净流入'] - df['早主力']
        df['涨跌加速'] = df['入池涨跌'] - df['早涨跌']

    em_dir = os.path.dirname(zlb_path)
    return df, em_dir, morn_path, data_date_tag, data_date_key


def base_mask(df: pd.DataFrame) -> pd.Series:
    return (
        ~df['名称'].astype(str).str.contains('ST|退', na=False, regex=True)
        & ~df['代码'].str.startswith('9')
        & (df['流通市值_亿'].fillna(0) >= 15)
        & ~df['所属行业'].isin(BAD_INDUSTRIES)
    )


def pick_top(
    df: pd.DataFrame,
    sort_col: str = '主力净流入',
    top_n: int = 15,
    industry_cap: int = 2,
) -> pd.DataFrame:
    if df.empty:
        return df
    sub = df.sort_values(sort_col, ascending=False)
    picked: List[pd.Series] = []
    seen_ind: Dict[str, int] = {}
    codes: set = set()
    for _, row in sub.iterrows():
        if row['代码'] in codes:
            continue
        ind = str(row.get('所属行业') or '未知')
        if seen_ind.get(ind, 0) >= industry_cap:
            continue
        picked.append(row)
        codes.add(row['代码'])
        seen_ind[ind] = seen_ind.get(ind, 0) + 1
        if len(picked) >= top_n:
            break
    if len(picked) < top_n:
        for _, row in sub.iterrows():
            if row['代码'] in codes:
                continue
            picked.append(row)
            codes.add(row['代码'])
            if len(picked) >= top_n:
                break
    return pd.DataFrame(picked)


def screen_s1_defense(u: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    cond = (
        u['所属行业'].isin(DEFENSE_INDUSTRIES)
        & (u['主力净流入'] >= 8e7)
        & u['入池涨跌'].between(-1, 3)
        & (u['振幅'].fillna(99) <= 6)
    )
    out = pick_top(u[cond], top_n=top_n, industry_cap=2)
    if len(out) < max(3, top_n // 2):
        cond = (
            u['所属行业'].isin(DEFENSE_INDUSTRIES)
            & (u['主力净流入'] >= 5e7)
            & u['入池涨跌'].between(-1, 4)
            & (u['振幅'].fillna(99) <= 6)
        )
        out = pick_top(u[cond], top_n=top_n, industry_cap=2)
    return out.assign(策略='S1防御强资金', 策略标签='防御+大流入+低振幅')


def screen_s2_tech(u: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    cond = (
        u['所属行业'].isin(TECH_INDUSTRIES)
        & (u['主力净流入'] >= 1e8)
        & u['入池涨跌'].between(0, 7)
        & (u['上影比'].fillna(1) <= 0.35)
    )
    return pick_top(u[cond], top_n=top_n, industry_cap=2).assign(
        策略='S2科技大流入', 策略标签='科技+大流入+低上影',
    )


def screen_s3_tactical(u: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    tiers = [
        ((u['主力净流入'] >= 8e7) & u['入池涨跌'].between(-1, 2.5) & (u['主力净占比'] >= 10) & (u['振幅'].fillna(99) <= 5)),
        ((u['主力净流入'] >= 5e7) & u['入池涨跌'].between(-1, 3) & (u['主力净占比'] >= 8) & (u['振幅'].fillna(99) <= 6)),
    ]
    for cond in tiers:
        out = pick_top(u[cond], top_n=top_n, industry_cap=2)
        if len(out) >= max(3, top_n // 2):
            return out.assign(策略='S3战术2.0', 策略标签='静默+大流入+低振幅')
    return pick_top(u[tiers[-1]], top_n=top_n, industry_cap=2).assign(
        策略='S3战术2.0', 策略标签='静默+大流入+低振幅',
    )


def screen_s4_accel(u: pd.DataFrame, top_n: int = 12) -> pd.DataFrame:
    if '主力加速' not in u.columns:
        return pd.DataFrame()
    cond = (
        u['所属行业'].isin(TECH_INDUSTRIES)
        & (u['主力加速'] >= 8e7)
        & u['入池涨跌'].between(1, 6)
        & (u['收盘强度'] >= 0.65)
    )
    return pick_top(u[cond], sort_col='主力加速', top_n=top_n, industry_cap=2).assign(
        策略='S4资金加速', 策略标签='科技+主力加速+收强',
    )


def screen_s5_superdeal(u: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    tiers = [
        (
            (u['超大单净占比'] >= 10)
            & u['入池涨跌'].between(0, 5)
            & u['换手率'].between(2, 8)
            & (u['主力净流入'] >= 2e7)
            & (u['主力净占比'] > 0)
        ),
        (
            (u['超大单净占比'] >= 8)
            & u['入池涨跌'].between(0, 5)
            & u['换手率'].between(1.5, 10)
            & (u['主力净流入'] >= 1e7)
            & (u['主力净占比'] > 0)
        ),
    ]
    for cond in tiers:
        out = pick_top(u[cond], sort_col='超大单净占比', top_n=top_n, industry_cap=2)
        if len(out) >= max(3, top_n // 2):
            return out.assign(策略='S5超大单突击', 策略标签='超大单高占比+温和上涨+放量')
    return pick_top(u[tiers[-1]], sort_col='超大单净占比', top_n=top_n, industry_cap=2).assign(
        策略='S5超大单突击', 策略标签='超大单高占比+温和上涨+放量',
    )


STRATEGIES: List[Tuple[str, Callable[..., pd.DataFrame], int]] = [
    ('s1_defense', screen_s1_defense, 10),
    ('s2_tech', screen_s2_tech, 15),
    ('s3_tactical', screen_s3_tactical, 10),
    ('s4_accel', screen_s4_accel, 12),
    ('s5_superdeal', screen_s5_superdeal, 15),
]

OUTPUT_COLS = [
    '代码', '名称', '入池价', '入池涨跌', '主力净流入', '主力净占比', '超大单净占比', '换手率',
    '所属行业', '收盘强度', '上影比', '策略', '策略标签',
]


def _export_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in OUTPUT_COLS if c in df.columns]
    extra = [c for c in ('主力加速', '涨跌加速') if c in df.columns]
    return df[cols + extra].copy()


def save_strategy_picks(
    strategy_key: str,
    df: pd.DataFrame,
    em_dir: str,
    date_tag: str,
    date_key: str,
) -> Dict:
    group = strategy_pick_group_name(strategy_key, date_tag)
    csv_name = strategy_pick_csv_basename(strategy_key, len(df), date_tag)
    csv_path = os.path.join(em_dir, csv_name)
    _export_cols(df).to_csv(csv_path, index=False, encoding='utf-8-sig')

    mgr = get_favorites_manager()
    mgr._reload_from_disk()
    if group not in mgr.config.sections():
        mgr.create_group(group)
    codes = df['代码'].astype(str).str.zfill(6).tolist()
    mgr.config.set(group, date_key, ','.join(codes))
    for _, row in df.iterrows():
        try:
            mgr._remember_group_property(str(row['代码']).zfill(6), group, str(row['名称']))
        except Exception:
            pass
    mgr._save()
    return {'group': group, 'csv': csv_path, 'count': len(df), 'date_tag': date_tag}


def run_all(only: Optional[List[str]] = None) -> List[Dict]:
    df, em_dir, morn_path, date_tag, date_key = load_universe()
    u = df[base_mask(df)].copy()
    results: List[Dict] = []

    strategies = STRATEGIES
    if only:
        only_set = set(only)
        strategies = [s for s in STRATEGIES if s[0] in only_set]
        unknown = only_set - {s[0] for s in strategies}
        if unknown:
            raise ValueError(f'未知策略: {", ".join(sorted(unknown))}')

    for key, fn, top_n in strategies:
        picks = fn(u, top_n=top_n)
        if picks.empty:
            print(f'[{key}] 无符合条件的标的（早盘 zjlx: {morn_path or "无"}）')
            continue
        info = save_strategy_picks(key, picks, em_dir, date_tag, date_key)
        info['strategy_key'] = key
        info['picks'] = picks
        results.append(info)
    return results


def _print_results(results: List[Dict]) -> None:
    if not results:
        print('未生成任何策略选股')
        return
    for info in results:
        picks: pd.DataFrame = info['picks']
        print(f"\n=== {info['group']} ({info['count']} 只) ===")
        print(f"CSV: {info['csv']}")
        for _, row in picks.iterrows():
            yi = row['主力净流入'] / 1e8
            ch = row['入池涨跌']
            sd = row.get('超大单净占比', float('nan'))
            sd_txt = f' 超大单{sd:.1f}%' if pd.notna(sd) else ''
            print(
                f"  {row['代码']} {row['名称']:8s} 涨{ch:+.1f}% 主力{yi:.2f}亿{sd_txt}  {row.get('策略标签', '')}"
            )


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description='zjlx 策略选股并写入自选股分组')
    parser.add_argument(
        '--only',
        nargs='+',
        metavar='KEY',
        help='仅运行指定策略，如 s5_superdeal（默认运行全部）',
    )
    args = parser.parse_args(argv)
    results = run_all(only=args.only)
    _print_results(results)


if __name__ == '__main__':
    main()
