"""星图 quote 文件缓存策略。

- 交易时段：距上次更新不足 5 分钟则复用缓存（避免每 5 分钟落一份新 CSV）
- 盘后：每个交易日 15:05 后仅拉取/落盘一次（quote_{dte}_close.csv）
- 盘中：覆盖写入 quote_{dte}_latest.csv
- 非交易日：不请求 API，读取最近一个交易日的收盘快照
"""

from __future__ import annotations

import glob
import os
import re
from datetime import datetime, timedelta, time
from typing import Dict, Optional, Tuple

import pandas as pd

from trading_calendar import is_trading_day

TRADING_REFRESH_MINUTES = 5
POST_CLOSE_TIME = time(15, 5)
PRE_MARKET_CUTOFF = time(9, 25)


def _stock_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _em_base() -> str:
    return os.path.join(os.path.dirname(_stock_dir()), 'generated', 'em')


def _is_trading_time(now: Optional[datetime] = None) -> bool:
    from utils_reem import is_trading_time as _utils_is_trading_time

    return _utils_is_trading_time()


def previous_trading_day(from_dt: Optional[datetime] = None, max_lookback: int = 40):
    """Return date object for the previous trading day before from_dt."""
    cur = (from_dt or datetime.now()).date()
    for _ in range(max_lookback):
        cur = cur - timedelta(days=1)
        if is_trading_day(cur):
            return cur
    return None


def effective_quote_date_short(now: Optional[datetime] = None) -> str:
    """yymmdd folder to read quotes from (today on trading days, else last close day)."""
    now = now or datetime.now()
    if is_trading_day(now):
        return now.strftime('%y%m%d')
    prev = previous_trading_day(now)
    if prev:
        return prev.strftime('%y%m%d')
    return now.strftime('%y%m%d')


def _quote_dir(date_short: str) -> str:
    return os.path.join(_em_base(), date_short)


def _post_close_marker_path(day: Optional[datetime] = None) -> str:
    day = day or datetime.now()
    dte_short = day.strftime('%y%m%d')
    os.makedirs(_quote_dir(dte_short), exist_ok=True)
    return os.path.join(_quote_dir(dte_short), f'.quote_post_close_{day.strftime("%Y%m%d")}.flag')


def _candidate_quote_paths(date_short: str) -> list:
    base = _quote_dir(date_short)
    if not os.path.isdir(base):
        return []
    patterns = [
        os.path.join(base, f'quote_{date_short}_close.csv'),
        os.path.join(base, f'quote_{date_short}_latest.csv'),
        os.path.join(base, 'quote_*.csv'),
    ]
    files: list = []
    seen = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            if path not in seen and os.path.isfile(path):
                seen.add(path)
                files.append(path)
    return files


def _quote_csv_looks_corrupt(path: str) -> bool:
    """Detect star-map CSV saved with a broken pipe parser."""
    try:
        df = pd.read_csv(path, dtype={'股票代码': str})
    except (OSError, pd.errors.ParserError, ValueError):
        return True
    if df.empty or '股票代码' not in df.columns or '当前价' not in df.columns:
        return True

    codes = df['股票代码'].astype(str).str.zfill(6)
    prices = pd.to_numeric(df['当前价'], errors='coerce')
    indexed = pd.Series(prices.values, index=codes.values)

    # Spot-check well-known tickers whose parser glitches produce 10x+ prices.
    for code, (lo, hi) in (('600522', (20, 120)), ('000001', (5, 30)), ('600519', (800, 2500))):
        if code in indexed.index:
            price = float(indexed[code])
            if price < lo or price > hi:
                return True

    turns = pd.to_numeric(df['换手率'], errors='coerce').dropna() if '换手率' in df.columns else pd.Series(dtype=float)
    if not turns.empty and turns.median() > 80:
        return True
    rates = pd.to_numeric(df['涨跌幅'], errors='coerce').dropna() if '涨跌幅' in df.columns else pd.Series(dtype=float)
    if not rates.empty and rates.abs().median() > 15:
        return True
    return False


def _quote_csv_row_count(path: str) -> int:
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return max(sum(1 for _ in fh) - 1, 0)
    except OSError:
        return 0


def _pick_best_quote_file(candidates: list, min_rows: int = 50) -> Optional[str]:
    def _rank(path: str):
        name = os.path.basename(path)
        if name.endswith('_close.csv'):
            tier = 0
        elif name.endswith('_latest.csv'):
            tier = 1
        else:
            tier = 2
        m = re.search(r'quote_(\d{10,12})', name)
        ts = int(m.group(1)) if m else 0
        # tier 越小越优先；同 tier 取较新时间戳/文件
        return (tier, -ts, -os.path.getmtime(path))

    ranked = sorted(candidates, key=_rank)
    for path in ranked:
        if _quote_csv_row_count(path) < min_rows:
            continue
        if not _quote_csv_looks_corrupt(path):
            return path
    for path in ranked:
        if _quote_csv_row_count(path) >= min_rows:
            return path
    return None


def find_latest_quote_file(date_short: Optional[str] = None, min_rows: int = 50) -> Optional[str]:
    """Best quote CSV for date_short, or effective trading day if omitted."""
    date_short = date_short or effective_quote_date_short()
    effective_short = effective_quote_date_short()
    allow_lookback = date_short == effective_short

    for _ in range(40):
        candidates = _candidate_quote_paths(date_short)
        if candidates:
            picked = _pick_best_quote_file(candidates, min_rows=min_rows)
            if picked:
                return picked

        if not allow_lookback:
            return None

        try:
            base_dt = datetime.strptime(date_short, '%y%m%d')
        except ValueError:
            return None
        prev = previous_trading_day(base_dt)
        if not prev:
            return None
        prev_short = prev.strftime('%y%m%d')
        if prev_short == date_short:
            return None
        date_short = prev_short

    return None


def should_refresh_quote(force: bool = False, now: Optional[datetime] = None) -> Tuple[bool, str]:
    now = now or datetime.now()

    if force and is_trading_day(now):
        return True, 'force'

    if not is_trading_day(now):
        return False, 'non_trading_day'

    dte_short = now.strftime('%y%m%d')
    latest = find_latest_quote_file(dte_short)
    marker = _post_close_marker_path(now)

    if _is_trading_time(now):
        if not latest:
            return True, 'missing'
        mtime = datetime.fromtimestamp(os.path.getmtime(latest))
        if mtime.date() < now.date():
            return True, 'trading_new_day'
        if now - mtime >= timedelta(minutes=TRADING_REFRESH_MINUTES):
            return True, 'trading_interval'
        return False, 'trading_fresh'

    if os.path.exists(marker):
        return False, 'post_close_done'

    if now.time() >= POST_CLOSE_TIME:
        close_path = os.path.join(_quote_dir(dte_short), f'quote_{dte_short}_close.csv')
        if os.path.exists(close_path):
            return False, 'post_close_cached'
        return True, 'post_close_fetch'

    if now.time() < PRE_MARKET_CUTOFF:
        if latest:
            return False, 'pre_market_use_last_close'
        prev = previous_trading_day(now)
        if prev and find_latest_quote_file(prev.strftime('%y%m%d')):
            return False, 'pre_market_use_last_close'
        return True, 'pre_market_fetch'

    if latest:
        mtime = datetime.fromtimestamp(os.path.getmtime(latest))
        if mtime.date() == now.date():
            return False, 'midday_pause_cached'
    return True, 'midday_fetch'


def quote_save_path(now: Optional[datetime] = None) -> str:
    """Target CSV path for a fresh fetch (latest intraday or post-close snapshot)."""
    now = now or datetime.now()
    dte_short = now.strftime('%y%m%d')
    os.makedirs(_quote_dir(dte_short), exist_ok=True)
    if is_trading_day(now) and now.time() >= POST_CLOSE_TIME and not os.path.exists(_post_close_marker_path(now)):
        return os.path.join(_quote_dir(dte_short), f'quote_{dte_short}_close.csv')
    return os.path.join(_quote_dir(dte_short), f'quote_{dte_short}_latest.csv')


def write_post_close_marker(now: Optional[datetime] = None) -> None:
    marker = _post_close_marker_path(now)
    with open(marker, 'w', encoding='utf-8') as fh:
        fh.write((now or datetime.now()).isoformat())


def load_realtime_quote_from_csv(quote_csv: str) -> Dict:
    """Rebuild getRealtimeQuote()-shaped dict from a saved quote CSV."""
    df = pd.read_csv(quote_csv, dtype={'股票代码': str})
    if '股票代码' in df.columns:
        df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
    stock_data = df.to_dict('records')

    dir_path = os.path.dirname(quote_csv)
    dtestr = os.path.basename(dir_path)
    sector_data = []
    for bk_name in (f'bk_{dtestr}.csv', 'bk.csv'):
        bk_csv = os.path.join(dir_path, bk_name)
        if os.path.exists(bk_csv):
            bk_df = pd.read_csv(bk_csv)
            sector_data = bk_df.to_dict('records')
            break

    mtime = datetime.fromtimestamp(os.path.getmtime(quote_csv))
    return {
        'quotetime': 0,
        'hash': '',
        'stock_data': stock_data,
        'sector_data': sector_data,
        'update_time': mtime.strftime('%Y-%m-%d %H:%M:%S'),
        'quote_file': quote_csv,
        'cached': True,
        'cache_date': dtestr,
    }


def get_cached_realtime_quote(now: Optional[datetime] = None) -> Optional[Dict]:
    path = find_latest_quote_file(effective_quote_date_short(now))
    if not path:
        return None
    result = load_realtime_quote_from_csv(path)
    result['cache_reason'] = effective_quote_date_short(now)
    return result
