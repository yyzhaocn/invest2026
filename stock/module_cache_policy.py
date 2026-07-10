"""Module 1 缓存过期策略：下一交易日 16:30 过期，非交易日不刷新。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

EXPIRE_AT = time(16, 30)
STOCKCOMMENT_UPDATE_AT = time(17, 0)

HOLIDAYS = {
    '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04',
    '2025-10-05', '2025-10-06', '2025-10-07', '2025-10-08',
}


def is_trading_calendar_day(dt: Optional[datetime] = None) -> bool:
    dt = dt or datetime.now()
    if dt.weekday() >= 5:
        return False
    return dt.strftime('%Y-%m-%d') not in HOLIDAYS


def next_trading_day(d: date) -> date:
    cur = d
    for _ in range(366):
        if is_trading_calendar_day(datetime.combine(cur, time(12, 0))):
            return cur
        cur += timedelta(days=1)
    return d


def cache_expires_at(file_mtime: datetime) -> datetime:
    """过期时间为缓存日之后的下一交易日 16:30。"""
    anchor = file_mtime.date() + timedelta(days=1)
    expire_day = next_trading_day(anchor)
    return datetime.combine(expire_day, EXPIRE_AT)


def is_cache_expired(file_mtime: datetime, now: Optional[datetime] = None) -> bool:
    """非交易日不判定过期；交易日超过下一交易日 16:30 则过期。"""
    now = now or datetime.now()
    if not is_trading_calendar_day(now):
        return False
    return now > cache_expires_at(file_mtime)


def cache_policy_summary() -> str:
    return '下一交易日 16:30 过期 · 非交易日不刷新'


def previous_trading_day(d: date) -> date:
    cur = d - timedelta(days=1)
    for _ in range(366):
        if is_trading_calendar_day(datetime.combine(cur, time(12, 0))):
            return cur
        cur -= timedelta(days=1)
    return d


def stockcomment_expected_batch_cutoff(now: Optional[datetime] = None) -> datetime:
    """
    stockcomment 每日 17:00 更新一批。
    返回当前时刻应已具备的最新批次时间戳（当日或上一交易日 17:00）。
    """
    now = now or datetime.now()
    today = now.date()
    if is_trading_calendar_day(now) and now.time() >= STOCKCOMMENT_UPDATE_AT:
        batch_day = today
    else:
        batch_day = previous_trading_day(today)
    return datetime.combine(batch_day, STOCKCOMMENT_UPDATE_AT)


def is_stockcomment_cache_fresh(file_mtime: datetime, now: Optional[datetime] = None) -> bool:
    """文件生成时间不早于当前应持有的最新 17:00 批次。"""
    return file_mtime >= stockcomment_expected_batch_cutoff(now)


def stockcomment_cache_policy_summary() -> str:
    return '交易日 17:00 更新 · 下一批次前复用缓存'


# pkyd（股票异动）与 stockcomment 共用同一日更批次策略（17:00）
pkyd_expected_batch_cutoff = stockcomment_expected_batch_cutoff
is_pkyd_cache_fresh = is_stockcomment_cache_fresh
pkyd_cache_policy_summary = stockcomment_cache_policy_summary


def rise_prob_session_label(now: Optional[datetime] = None) -> str:
    """
    上涨概率/综合评价日更批次标签。
    交易日 17:00 前为「盘前」（沿用上一批次），17:00 及之后为「盘后」。
    非交易日视为盘前（沿用最近批次）。
    """
    now = now or datetime.now()
    if is_trading_calendar_day(now) and now.time() >= STOCKCOMMENT_UPDATE_AT:
        return '盘后'
    return '盘前'


def rise_prob_pick_group_name(date_tag: Optional[str] = None, now: Optional[datetime] = None) -> str:
    """上涨概率选股分组名：上涨概率选股_{YYYYMMDD}_{盘前|盘后}"""
    now = now or datetime.now()
    tag = date_tag or now.strftime('%Y%m%d')
    return f'上涨概率选股_{tag}_{rise_prob_session_label(now)}'


def rise_prob_pick_csv_basename(count: int = 30, date_tag: Optional[str] = None, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    tag = date_tag or now.strftime('%Y%m%d')
    session = rise_prob_session_label(now)
    return f'rise_prob_picks_{count}_{tag}_{session}.csv'


STRATEGY_PICK_LABELS = {
    's1_defense': '防御强资金选股',
    's2_tech': '科技大流入选股',
    's3_tactical': '战术2.0选股',
    's4_accel': '资金加速科技选股',
    's5_superdeal': '超大单突击选股',
}


def strategy_pick_group_name(strategy_key: str, date_tag: Optional[str] = None, now: Optional[datetime] = None) -> str:
    """策略选股分组名：{策略名}_{YYYYMMDD}"""
    now = now or datetime.now()
    tag = date_tag or now.strftime('%Y%m%d')
    label = STRATEGY_PICK_LABELS.get(strategy_key, strategy_key)
    return f'{label}_{tag}'


def strategy_pick_csv_basename(strategy_key: str, count: int, date_tag: Optional[str] = None, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    tag = date_tag or now.strftime('%Y%m%d')
    return f'{strategy_key}_picks_{count}_{tag}.csv'


def ensure_dated_pick_group_name(
    label: str,
    date_tag: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """选股分组名：{标签}_{YYYYMMDD}（已有日期后缀则不变）。"""
    import re

    name = str(label or '').strip()
    if not name:
        return name
    if re.search(r'_\d{8}$', name):
        return name
    now = now or datetime.now()
    tag = date_tag or now.strftime('%Y%m%d')
    return f'{name}_{tag}'


def iwencai_pick_group_name(
    query_or_label: str,
    date_tag: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """问财选股分组名：由问句/标签 + 当前日期。"""
    import re

    text = str(query_or_label or '').strip()
    aliases = {
        '同花顺人气排行股票': '同花顺热股榜',
        '同花顺热股榜': '同花顺热股榜',
        '底部反转，底背离': '底部反转底背离',
        '底部反转,底背离': '底部反转底背离',
    }
    label = aliases.get(text, re.sub(r'[，,。；;、\s]+', '', text) or text)
    return ensure_dated_pick_group_name(label, date_tag, now)
