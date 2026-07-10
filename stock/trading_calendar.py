#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股交易日历：排除周末及法定节假日
数据来源：沪深北交易所休市安排公告
"""

from datetime import datetime

# A股休市日期及名称 (YYYY-MM-DD -> 节假日名称)
# 每年需根据交易所公告更新
CN_HOLIDAY_NAMES = {
    # 2025 国庆节
    '2025-10-01': '国庆节', '2025-10-02': '国庆节', '2025-10-03': '国庆节',
    '2025-10-04': '国庆节', '2025-10-05': '国庆节', '2025-10-06': '国庆节',
    '2025-10-07': '国庆节', '2025-10-08': '国庆节',
    # 2026 元旦
    '2026-01-01': '元旦', '2026-01-02': '元旦', '2026-01-03': '元旦',
    # 2026 春节
    '2026-02-15': '春节', '2026-02-16': '春节', '2026-02-17': '春节',
    '2026-02-18': '春节', '2026-02-19': '春节', '2026-02-20': '春节',
    '2026-02-21': '春节', '2026-02-22': '春节', '2026-02-23': '春节',
    # 2026 清明节
    '2026-04-04': '清明节', '2026-04-05': '清明节', '2026-04-06': '清明节',
    # 2026 劳动节
    '2026-05-01': '劳动节', '2026-05-02': '劳动节', '2026-05-03': '劳动节',
    '2026-05-04': '劳动节', '2026-05-05': '劳动节',
    # 2026 端午节
    '2026-06-19': '端午节', '2026-06-20': '端午节', '2026-06-21': '端午节',
    # 2026 中秋节
    '2026-09-25': '中秋节', '2026-09-26': '中秋节', '2026-09-27': '中秋节',
    # 2026 国庆节
    '2026-10-01': '国庆节', '2026-10-02': '国庆节', '2026-10-03': '国庆节',
    '2026-10-04': '国庆节', '2026-10-05': '国庆节', '2026-10-06': '国庆节',
    '2026-10-07': '国庆节',
}
CN_HOLIDAYS = frozenset(CN_HOLIDAY_NAMES.keys())


def is_trading_day(date=None):
    """
    检查是否为交易日（排除周末及法定节假日）
    Args:
        date: datetime 或 date 对象，默认 today
    Returns:
        bool
    """
    d = date if date is not None else datetime.now()
    if hasattr(d, 'date'):
        d = d.date()
    # 周末
    if d.weekday() >= 5:
        return False
    # 节假日
    date_str = d.strftime('%Y-%m-%d')
    return date_str not in CN_HOLIDAYS


def is_holiday(date=None):
    """检查是否为休市日（周末或节假日）"""
    return not is_trading_day(date)


def get_non_trading_reason(date=None):
    """
    获取非交易日原因，用于日志提示
    Args:
        date: datetime 或 date 对象，默认 today
    Returns:
        str: "周末"、"春节"、"国庆节" 等，若为交易日则返回 None
    """
    d = date if date is not None else datetime.now()
    if hasattr(d, 'date'):
        d = d.date()
    if d.weekday() >= 5:
        return "周末"
    date_str = d.strftime('%Y-%m-%d')
    return CN_HOLIDAY_NAMES.get(date_str)  # 非节假日返回 None
