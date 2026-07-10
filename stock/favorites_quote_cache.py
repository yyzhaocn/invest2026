"""动态选股分组行情缓存。

- 交易时段：5 分钟内复用
- 非交易时段（含非交易日）：使用最近交易日数据，不因 TTL 过期
- 无缓存时由 API 先拉取再写入
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, time as dt_time
from typing import Any, Dict, List, Optional, Tuple

from quote_cache import TRADING_REFRESH_MINUTES, previous_trading_day
from trading_calendar import is_trading_day

TRADING_TTL_SECONDS = TRADING_REFRESH_MINUTES * 60
EXTRA_QUOTE_COLS = (
    '换手率', '成交额(亿)', '流通市值(亿)', '量比', '状态',
    '今开', '昨收', '最高', '最低', '涨停价', '跌停价',
    '成交量', '成交额', '总市值', '振幅', '市净率', '市盈率(动)', '市盈率TTM', '涨跌额',
    '东财二级行业', '东财三级行业',
)


def _cache_root() -> str:
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated', 'cache', 'favorites_quotes')
    os.makedirs(root, exist_ok=True)
    return root


def _safe_group_slug(group_name: str) -> str:
    slug = re.sub(r'[^\w\-]+', '_', (group_name or 'default').strip()) or 'default'
    return slug[:80]


def cache_path(group_name: str) -> str:
    return os.path.join(_cache_root(), f'{_safe_group_slug(group_name)}.json')


def _is_trading_session(now: Optional[datetime] = None) -> bool:
    from utils_reem import is_trading_time

    return is_trading_time()


def expected_quote_trade_date(now: Optional[datetime] = None) -> date:
    """当前应展示的最近一个交易日。"""
    now = now or datetime.now()
    today = now.date()
    if not is_trading_day(now):
        prev = previous_trading_day(now)
        return prev or today
    t = now.time()
    if t >= dt_time(15, 0):
        return today
    if _is_trading_session(now):
        return today
    if t < dt_time(9, 30):
        prev = previous_trading_day(now)
        return prev or today
    return today


def _parse_trade_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _codes_match(payload: Dict[str, Any], stock_codes: List[str]) -> bool:
    cached = {str(c).zfill(6) for c in payload.get('stock_codes') or []}
    current = {str(c).zfill(6) for c in stock_codes}
    return cached == current


def _market_quote_mtime(now: Optional[datetime] = None) -> Optional[float]:
    """最新全市场行情 CSV 的 mtime（优先盘后 close 快照）。"""
    try:
        from quote_cache import find_latest_quote_file

        path = find_latest_quote_file()
        if path and os.path.isfile(path):
            return os.path.getmtime(path)
    except Exception:
        pass
    return None


def _cache_quote_ref_mtime(payload: Dict[str, Any]) -> float:
    """缓存所依据的行情文件时间戳（fetched_at 与 csv_path 取较新）。"""
    ref = float(payload.get('fetched_at') or 0)
    csv_path = payload.get('csv_path')
    if csv_path and os.path.isfile(csv_path):
        ref = max(ref, os.path.getmtime(csv_path))
    return ref


def is_cache_valid(payload: Optional[Dict[str, Any]], stock_codes: List[str], now: Optional[datetime] = None) -> bool:
    if not payload or not payload.get('quotes'):
        return False
    if not _codes_match(payload, stock_codes):
        return False

    now = now or datetime.now()
    trade_d = _parse_trade_date(payload.get('trade_date'))
    expected = expected_quote_trade_date(now)
    if trade_d is None or trade_d < expected:
        return False

    if _is_trading_session(now):
        fetched_at = float(payload.get('fetched_at') or 0)
        return (time.time() - fetched_at) < TRADING_TTL_SECONDS

    # 盘外：若全市场行情 CSV 已更新（如盘后 close 快照），则使分组缓存失效
    market_mtime = _market_quote_mtime(now)
    if market_mtime is not None and market_mtime > _cache_quote_ref_mtime(payload) + 1:
        return False

    return True


def should_use_cache(
    group_name: str,
    stock_codes: List[str],
    force: bool = False,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if force:
        return False, None, 'force'
    payload = load_cache(group_name)
    if not payload:
        return False, None, 'missing'
    if is_cache_valid(payload, stock_codes):
        return True, payload, 'hit'
    return False, payload, 'stale'


def load_cache(group_name: str) -> Optional[Dict[str, Any]]:
    path = cache_path(group_name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(group_name: str, payload: Dict[str, Any]) -> str:
    path = cache_path(group_name)
    tmp = f'{path}.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def build_cache_payload(
    group_name: str,
    stock_codes: List[str],
    quotes: Dict[str, Dict[str, Any]],
    file_info: Dict[str, Any],
    csv_path: Optional[str] = None,
    source: str = 'mixed',
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now()
    trade_date = expected_quote_trade_date(now)
    update_time = file_info.get('update_time')
    if update_time:
        parsed = _parse_trade_date(str(update_time).replace(' ', 'T')[:10])
        if parsed and parsed >= trade_date:
            trade_date = parsed

    return {
        'group_name': group_name,
        'stock_codes': sorted({str(c).zfill(6) for c in stock_codes}),
        'fetched_at': time.time(),
        'trade_date': trade_date.isoformat(),
        'source': source,
        'quotes': quotes,
        'file_info': file_info,
        'csv_path': csv_path,
    }


def extract_quotes_from_rows(result_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    quotes: Dict[str, Dict[str, Any]] = {}
    for row in result_rows:
        code = str(row.get('_code') or '').zfill(6)
        if not code:
            continue
        name = row.get('股票名称') or code
        if isinstance(name, str) and '<' in name:
            match = re.search(r'>([^<]+)<', name)
            if match:
                name = match.group(1)
        extras = {col: row[col] for col in EXTRA_QUOTE_COLS if col in row and row[col] not in (None, '', '--')}
        quotes[code] = {
            'name': name,
            'price': row.get('当前价格'),
            'change_percent': row.get('涨跌幅'),
            'extras': extras,
        }
    return quotes


def cache_policy_summary(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    if _is_trading_session(now):
        return f'交易时段 · {TRADING_REFRESH_MINUTES} 分钟缓存'
    expected = expected_quote_trade_date(now)
    if is_trading_day(now):
        return f'非交易时段 · 使用 {expected.isoformat()} 最近行情'
    return f'非交易日 · 使用 {expected.isoformat()} 收盘行情'
