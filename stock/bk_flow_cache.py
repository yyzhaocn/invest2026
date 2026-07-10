"""概念板块资金流向 (bk_flow) 缓存与刷新策略。

- 交易时段：数据超过 10 分钟则重新拉取
- 盘后：每个交易日仅拉取一次（15:00 后首次触发）
"""

from __future__ import annotations

import glob
import os
from datetime import datetime, timedelta, time
from typing import Dict, Optional, Tuple

from utils_reem import is_trading_time

TRADING_REFRESH_MINUTES = 10
POST_CLOSE_HOUR = 15


def _stock_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _em_glob_pattern() -> str:
    parent_dir = os.path.dirname(_stock_dir())
    return os.path.join(parent_dir, 'generated', 'em', '*', 'bk_flow_*.csv')


def _post_close_marker_path(day: Optional[datetime] = None) -> str:
    day = day or datetime.now()
    dte_short = day.strftime('%y%m%d')
    parent_dir = os.path.dirname(_stock_dir())
    em_dir = os.path.join(parent_dir, 'generated', 'em', dte_short)
    os.makedirs(em_dir, exist_ok=True)
    return os.path.join(em_dir, f'.bk_flow_post_close_{day.strftime("%Y%m%d")}.flag')


def _is_trading_day(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    holidays = {
        '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04',
        '2025-10-05', '2025-10-06', '2025-10-07', '2025-10-08',
    }
    return now.strftime('%Y-%m-%d') not in holidays


def find_latest_bk_flow_file() -> Optional[str]:
    files = glob.glob(_em_glob_pattern())
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _write_post_close_marker() -> None:
    marker = _post_close_marker_path()
    with open(marker, 'w', encoding='utf-8') as fh:
        fh.write(datetime.now().isoformat())


def should_refresh_bk_flow(force: bool = False) -> Tuple[bool, str]:
    """Return (need_refresh, reason)."""
    if force:
        return True, 'force'

    now = datetime.now()
    latest = find_latest_bk_flow_file()
    if not latest:
        return True, 'missing'

    mtime = datetime.fromtimestamp(os.path.getmtime(latest))

    if is_trading_time():
        if mtime.date() < now.date():
            return True, 'trading_new_day'
        if now - mtime >= timedelta(minutes=TRADING_REFRESH_MINUTES):
            return True, 'trading_interval'
        return False, 'trading_fresh'

    today_marker = _post_close_marker_path(now)
    if os.path.exists(today_marker):
        return False, 'post_close_done'

    if _is_trading_day(now) and now.time() >= time(POST_CLOSE_HOUR, 0):
        return True, 'post_close_fetch'

    return False, 'off_hours_cached'


def ensure_bk_flow_fresh(force: bool = False) -> Dict:
    """Refresh bk_flow CSV when policy requires it; return status metadata."""
    need, reason = should_refresh_bk_flow(force=force)
    fetched = False
    error = None

    if need:
        try:
            from utils_reem import get_capreal_bk
            get_capreal_bk()
            fetched = True
            if reason == 'post_close_fetch':
                _write_post_close_marker()
        except Exception as exc:
            error = str(exc)

    latest = find_latest_bk_flow_file()
    refreshed_at = None
    if latest:
        refreshed_at = datetime.fromtimestamp(os.path.getmtime(latest)).isoformat()

    return {
        'fetched': fetched,
        'need_refresh': need,
        'reason': reason,
        'error': error,
        'latest_file': latest,
        'refreshed_at': refreshed_at,
        'is_trading_time': is_trading_time(),
        'cache_policy': {
            'trading_refresh_minutes': TRADING_REFRESH_MINUTES,
            'post_close_once_per_day': True,
        },
    }
