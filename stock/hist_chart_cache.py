"""资金 hist 图表缓存策略（与 quote_cache 对齐）。

- 交易时段（9:30–11:30 / 13:00–15:00）：生成当日图，5 分钟内复用缓存
- 午间休市（11:30–13:00 等）：当日仅更新一次
- 盘后 15:05 后：每个股票每个交易日再更新一次（收盘快照）
- 非交易日：不请求 API，使用最近一个交易日的收盘图
"""

from __future__ import annotations

import glob
import os
import re
from datetime import datetime, time, timedelta
from typing import Optional, Tuple

from quote_cache import (
    POST_CLOSE_TIME,
    PRE_MARKET_CUTOFF,
    TRADING_REFRESH_MINUTES,
    effective_quote_date_short,
    previous_trading_day,
)
from trading_calendar import is_trading_day

_STOCK_DIR = os.path.dirname(os.path.abspath(__file__))

MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)


def is_trading_session(now: Optional[datetime] = None) -> bool:
    """A 股连续竞价时段（不含集合竞价 9:15–9:25）。"""
    now = now or datetime.now()
    if not is_trading_day(now):
        return False
    t = now.time()
    return (MORNING_START <= t <= MORNING_END) or (AFTERNOON_START <= t <= AFTERNOON_END)


def chart_dir() -> str:
    path = os.path.join(_STOCK_DIR, 'generated', 'cache', 'stockd', 'charts')
    os.makedirs(path, exist_ok=True)
    return path


def hist_chart_path(stock_code: str, date_short: Optional[str] = None) -> str:
    date_short = date_short or effective_quote_date_short()
    return os.path.join(chart_dir(), f'hist_flow_{stock_code}_{date_short}.png')


def _post_close_marker_path(stock_code: str, day: Optional[datetime] = None) -> str:
    day = day or datetime.now()
    return os.path.join(chart_dir(), f'.hist_chart_{stock_code}_{day.strftime("%Y%m%d")}_close.flag')


def find_hist_chart(stock_code: str, now: Optional[datetime] = None) -> Optional[str]:
    """Return best cached PNG for display."""
    now = now or datetime.now()
    eff = effective_quote_date_short(now)
    primary = hist_chart_path(stock_code, eff)
    if os.path.isfile(primary):
        return primary

    if is_trading_day(now) and now.time() < PRE_MARKET_CUTOFF:
        prev = previous_trading_day(now)
        if prev:
            prev_path = hist_chart_path(stock_code, prev.strftime('%y%m%d'))
            if os.path.isfile(prev_path):
                return prev_path

    pattern = os.path.join(chart_dir(), f'hist_flow_{stock_code}_*.png')
    files = [p for p in glob.glob(pattern) if not os.path.basename(p).startswith('.')]
    if not files:
        return None

    def _date_key(path: str) -> str:
        match = re.search(r'hist_flow_\d+_(\d{6})\.png$', os.path.basename(path))
        return match.group(1) if match else '000000'

    return max(files, key=_date_key)


def should_refresh_hist_chart(stock_code: str, force: bool = False, now: Optional[datetime] = None) -> Tuple[bool, str]:
    """Whether to regenerate hist PNG for the effective trading day."""
    now = now or datetime.now()
    if force:
        return True, 'force'

    if not is_trading_day(now):
        return False, 'non_trading_day'

    eff = effective_quote_date_short(now)
    target = hist_chart_path(stock_code, eff)

    if is_trading_session(now):
        if not os.path.isfile(target):
            return True, 'trading_missing'
        mtime = datetime.fromtimestamp(os.path.getmtime(target))
        if mtime.date() < now.date():
            return True, 'trading_new_day'
        if now - mtime >= timedelta(minutes=TRADING_REFRESH_MINUTES):
            return True, 'trading_interval'
        return False, 'trading_fresh'

    if now.time() >= POST_CLOSE_TIME:
        if os.path.isfile(_post_close_marker_path(stock_code, now)):
            return False, 'post_close_done'
        return True, 'post_close_fetch'

    if now.time() < PRE_MARKET_CUTOFF:
        if os.path.isfile(target):
            return False, 'pre_market_cached'
        prev = previous_trading_day(now)
        if prev and os.path.isfile(hist_chart_path(stock_code, prev.strftime('%y%m%d'))):
            return False, 'pre_market_use_last_close'
        return True, 'pre_market_fetch'

    # 午间休市 / 集合竞价等非连续竞价时段：当日已有图则不再更新
    if os.path.isfile(target):
        mtime = datetime.fromtimestamp(os.path.getmtime(target))
        if mtime.date() == now.date():
            return False, 'midday_pause_cached'
    return True, 'midday_fetch'


def write_hist_chart_marker(stock_code: str, now: Optional[datetime] = None) -> None:
    """Write post-close marker after 15:05 snapshot generation."""
    now = now or datetime.now()
    if is_trading_day(now) and now.time() >= POST_CLOSE_TIME:
        marker = _post_close_marker_path(stock_code, now)
        with open(marker, 'w', encoding='utf-8') as fh:
            fh.write(now.isoformat())


def is_hist_data_stale_ok(now: Optional[datetime] = None) -> bool:
    """Whether hist CSV may be reused without refetch (non-session on trading day, or holiday)."""
    now = now or datetime.now()
    if not is_trading_day(now):
        return True
    return not is_trading_session(now)


def clear_hist_chart_cache(stock_code: str) -> int:
    """Remove cached PNG/flag files for one stock. Returns number of files removed."""
    removed = 0
    for pattern in (
        os.path.join(chart_dir(), f'hist_flow_{stock_code}_*.png'),
        os.path.join(chart_dir(), f'.hist_chart_{stock_code}_*.flag'),
    ):
        for path in glob.glob(pattern):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    return removed
