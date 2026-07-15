#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zjlx / quote / stockcomment 定时调度（invest2026 独立版，不依赖 atime/stock）。"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

import schedule

from bk_flow_cache import ensure_bk_flow_fresh
from proto_pkyd import get_pkyd
from quote_cache import should_refresh_quote
from repo_paths import GENERATED_EM, STOCK_DIR
from trading_calendar import get_non_trading_reason, is_trading_day as _is_trading_day
from utils_reem import (
    getRealtimeQuote,
    get_fund,
    get_quotes,
    get_stockcomment,
    get_zjlx,
    get_zjlx_all,
    get_zjlx_zlb_all,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(STOCK_DIR, 'zjlx_scheduler.log'), encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_ROLLOUT_DEST = os.environ.get('EM_ROLLOUT_DEST', '').strip()
_KEEP_EM_DAYS = int(os.environ.get('EM_KEEP_DAYS', '5'))


def is_trading_time() -> bool:
    now = datetime.now()
    if not _is_trading_day(now):
        return False
    current_time = now.time()
    morning_start = datetime.strptime('09:25', '%H:%M').time()
    morning_end = datetime.strptime('11:35', '%H:%M').time()
    afternoon_start = datetime.strptime('13:00', '%H:%M').time()
    afternoon_end = datetime.strptime('15:05', '%H:%M').time()
    evening_start = datetime.strptime('22:00', '%H:%M').time()
    evening_end = datetime.strptime('23:55', '%H:%M').time()
    return (
        morning_start <= current_time <= morning_end
        or afternoon_start <= current_time <= afternoon_end
        or evening_start <= current_time <= evening_end
    )


def is_trading_day() -> bool:
    return _is_trading_day()


def _run_script(script_name: str) -> bool:
    script_path = os.path.join(STOCK_DIR, script_name)
    if not os.path.isfile(script_path):
        logger.warning('脚本不存在，跳过: %s', script_path)
        return False
    cmd = [sys.executable, script_path]
    logger.info('执行: %s', ' '.join(cmd))
    try:
        result = subprocess.run(cmd, cwd=STOCK_DIR, capture_output=True, text=True)
        if result.stdout:
            logger.info(result.stdout.rstrip())
        if result.returncode != 0:
            logger.error('脚本失败 %s (code=%s): %s', script_name, result.returncode, result.stderr)
            return False
        return True
    except Exception as exc:
        logger.error('执行 %s 异常: %s', script_name, exc)
        return False


def execute_quote_task(force_execute: bool = False) -> None:
    try:
        need, reason = should_refresh_quote(force=force_execute)
        if not need and not force_execute:
            logger.info('quote 缓存有效，跳过拉取 (%s)', reason)
            return

        if force_execute:
            logger.info('启动时执行 getRealtimeQuote…')
        elif is_trading_time():
            logger.info('开始执行 getRealtimeQuote…')
        else:
            logger.info('盘外触发 getRealtimeQuote (%s)…', reason)

        start = time.time()
        getRealtimeQuote(force=force_execute)
        ensure_bk_flow_fresh()
        logger.info('getRealtimeQuote 完成，耗时 %.2fs', time.time() - start)

        if is_trading_day() and (force_execute or is_trading_time()):
            try:
                get_pkyd()
                logger.info('get_pkyd 完成')
            except Exception as exc:
                logger.error('get_pkyd 失败: %s', exc)
    except Exception as exc:
        logger.error('execute_quote_task 错误: %s', exc)


def execute_bk_flow_post_close_task() -> None:
    try:
        meta = ensure_bk_flow_fresh()
        logger.info('盘后 bk_flow: fetched=%s reason=%s', meta.get('fetched'), meta.get('reason'))
    except Exception as exc:
        logger.error('盘后 bk_flow 失败: %s', exc)


def execute_zjlx_task(force_execute: bool = False) -> None:
    try:
        if not (force_execute or is_trading_time()):
            reason = get_non_trading_reason() if not _is_trading_day() else '当前不在交易时间内'
            logger.info('%s，跳过 get_zjlx', reason)
            return
        logger.info('开始执行 get_zjlx…')
        start = time.time()
        get_zjlx()
        logger.info('get_zjlx 完成，耗时 %.2fs', time.time() - start)
    except Exception as exc:
        logger.error('execute_zjlx_task 错误: %s', exc)


def rollout_daily() -> None:
    """可选：复制 generated/em/{YYMMDD} 到 EM_ROLLOUT_DEST，并清理旧目录。"""
    if not _ROLLOUT_DEST:
        return
    if not is_trading_day():
        logger.info('非交易日，跳过 rollout_daily')
        return
    if not os.path.isdir(GENERATED_EM):
        return

    os.makedirs(_ROLLOUT_DEST, exist_ok=True)
    date_dirs = sorted(
        [name for name in os.listdir(GENERATED_EM) if re.fullmatch(r'\d{6}', name)],
        reverse=True,
    )
    copied = 0
    for date_short in date_dirs:
        src = os.path.join(GENERATED_EM, date_short)
        dst = os.path.join(_ROLLOUT_DEST, date_short)
        if not os.path.isdir(dst):
            try:
                shutil.copytree(src, dst)
                copied += 1
                logger.info('rollout: %s -> %s', date_short, _ROLLOUT_DEST)
            except Exception as exc:
                logger.error('rollout 复制 %s 失败: %s', date_short, exc)

    if copied:
        logger.info('rollout_daily: 复制 %d 个目录', copied)

    for date_short in date_dirs[_KEEP_EM_DAYS:]:
        path = os.path.join(GENERATED_EM, date_short)
        try:
            shutil.rmtree(path)
            logger.info('已删除旧目录: %s', date_short)
        except Exception as exc:
            logger.error('删除 %s 失败: %s', date_short, exc)


def execute_zjlx_all_task() -> None:
    if not is_trading_day():
        logger.info('非交易日，跳过 zjlx 全量')
        return
    try:
        start = time.time()
        get_zjlx_all()
        get_zjlx_zlb_all()
        logger.info('zjlx 全量完成，耗时 %.2fs', time.time() - start)
        rollout_daily()
    except Exception as exc:
        logger.error('zjlx 全量任务失败: %s', exc)


def execute_stockcomment_task() -> None:
    if not is_trading_day():
        logger.info('非交易日，跳过 stockcomment')
        return
    try:
        start = time.time()
        get_stockcomment()
        get_quotes(80)
        logger.info('stockcomment 完成，耗时 %.2fs', time.time() - start)
    except Exception as exc:
        logger.error('stockcomment 失败: %s', exc)


def execute_qgqp_task() -> None:
    """盘后：pkyd + stockcomment + fund。"""
    if not is_trading_day():
        logger.info('非交易日，跳过盘后任务')
        return
    try:
        get_pkyd()
        start = time.time()
        get_stockcomment()
        get_quotes(80)
        logger.info('盘后 stockcomment 完成，耗时 %.2fs', time.time() - start)
        get_fund()
        logger.info('get_fund 完成')
    except Exception as exc:
        logger.error('盘后任务失败: %s', exc)


def execute_strategy_picks_task() -> None:
    """收盘后运行上涨概率 + S1–S5 策略选股。"""
    if not is_trading_day():
        return
    _run_script('rise_prob_picks.py')
    _run_script('strategy_picks.py')


def execute_trading_tasks(force_execute: bool = False) -> None:
    if not (force_execute or is_trading_time()):
        reason = get_non_trading_reason() if not _is_trading_day() else '当前不在交易时间内'
        logger.info('%s，跳过交易任务', reason)
        return
    start = time.time()
    execute_quote_task(force_execute)
    execute_zjlx_task(force_execute)
    logger.info('交易任务完成，总耗时 %.2fs', time.time() - start)


def main() -> None:
    logger.info('启动 invest2026 zjlx 调度器 (STOCK_DIR=%s)', STOCK_DIR)

    schedule.every(5).minutes.do(execute_quote_task)
    schedule.every(30).minutes.do(execute_zjlx_task)

    schedule.every().day.at('08:00').do(execute_quote_task)
    schedule.every().day.at('08:05').do(execute_stockcomment_task)
    schedule.every().day.at('12:05').do(execute_stockcomment_task)

    schedule.every().day.at('14:35').do(execute_zjlx_all_task)
    schedule.every().day.at('15:10').do(execute_bk_flow_post_close_task)
    schedule.every().day.at('15:15').do(execute_zjlx_all_task)
    schedule.every().day.at('18:30').do(execute_qgqp_task)
    schedule.every().day.at('17:35').do(execute_strategy_picks_task)

    logger.info('启动时立即执行一次交易任务…')
    execute_trading_tasks(force_execute=True)

    logger.info('按 Ctrl+C 停止')
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        schedule.clear()
        logger.info('调度器已关闭')


if __name__ == '__main__':
    main()
