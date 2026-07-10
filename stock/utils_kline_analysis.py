"""日 K 走势分析。"""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


def _fmt_pct(v: float) -> str:
    sign = '+' if v > 0 else ''
    return f'{sign}{v:.2f}%'


def _strip_html(value: Any) -> str:
    return re.sub(r'<[^>]+>', '', str(value or '')).strip()


def _to_float(value: Any) -> Optional[float]:
    text = _strip_html(value).replace(',', '').replace('%', '').replace('+', '').strip()
    if not text or text in ('--', '—', 'None', 'nan'):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _ma_trend(close: float, ma5, ma10, ma20) -> str:
    vals = [v for v in (ma5, ma10, ma20) if pd.notna(v)]
    if len(vals) < 2:
        return '均线数据不足'
    if close > ma5 > ma10 > ma20:
        return '多头排列，趋势偏强'
    if close < ma5 < ma10 < ma20:
        return '空头排列，趋势偏弱'
    if close > ma20:
        return '价格在 MA20 上方，中期偏强'
    if close < ma20:
        return '价格在 MA20 下方，中期偏弱'
    return '均线纠缠，方向待明'


def _macd_comment(macd, signal, hist) -> str:
    if pd.isna(macd) or pd.isna(signal):
        return 'MACD 数据不足'
    parts = []
    if macd > signal:
        parts.append('DIF 在 DEA 上方')
    else:
        parts.append('DIF 在 DEA 下方')
    if pd.notna(hist):
        parts.append('红柱放大' if hist > 0 else '绿柱放大')
    return '，'.join(parts)


def _rsi_comment(rsi) -> str:
    if pd.isna(rsi):
        return 'RSI 数据不足'
    if rsi >= 70:
        return f'RSI={rsi:.1f}，超买区'
    if rsi <= 30:
        return f'RSI={rsi:.1f}，超卖区'
    return f'RSI={rsi:.1f}，中性'


def _period_change(df: pd.DataFrame, days: int) -> Optional[float]:
    if len(df) <= days:
        return None
    start = df.iloc[-1 - days]['收盘价']
    end = df.iloc[-1]['收盘价']
    if not start:
        return None
    return (end - start) / start * 100


def _kline_cache_candidates(code: str) -> List[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    roots = [
        os.environ.get('KLINE_CACHE_ROOT', ''),
        os.path.join(here, 'generated', 'cache', 'stockd'),
        os.path.join(here, 'generated', 'cache', 'stockd1'),
        os.path.join(parent, 'generated', 'cache', 'stockd'),
        os.path.join(parent, 'generated', 'cache', 'stockd1'),
    ]
    paths: List[str] = []
    seen = set()
    for root in roots:
        if not root:
            continue
        exact = os.path.join(root, code, f'kline_{code}.csv')
        if exact not in seen:
            seen.add(exact)
            paths.append(exact)
        for hit in glob.glob(os.path.join(root, '*', f'kline_{code}.csv')):
            if hit not in seen:
                seen.add(hit)
                paths.append(hit)
    return paths


def _load_kline_from_cache(code: str) -> Optional[pd.DataFrame]:
    for path in _kline_cache_candidates(code):
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_csv(path)
            if df is None or df.empty:
                continue
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
            rename = {'开盘': '开盘价', '收盘': '收盘价', '最高': '最高价', '最低': '最低价'}
            df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
            return df.sort_values('日期').reset_index(drop=True)
        except OSError:
            continue
    return None


def _sina_symbol(code: str) -> str:
    if code.startswith(('6', '5', '9')):
        return f'sh{code}'
    if code.startswith(('4', '8')):
        return f'bj{code}'
    return f'sz{code}'


def _normalize_kline_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename = {
        '开盘': '开盘价', '收盘': '收盘价', '最高': '最高价', '最低': '最低价',
        'day': '日期', 'open': '开盘价', 'close': '收盘价', 'high': '最高价',
        'low': '最低价', 'volume': '成交量',
    }
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    for col in ('开盘价', '收盘价', '最高价', '最低价', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率'):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')
    if '日期' in out.columns:
        out['日期'] = pd.to_datetime(out['日期'])
    if '收盘价' in out.columns and '涨跌幅' not in out.columns:
        out['涨跌幅'] = out['收盘价'].pct_change() * 100
        out['涨跌幅'] = out['涨跌幅'].fillna(0)
    return out.sort_values('日期').reset_index(drop=True)


def _kline_cache_path(code: str) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.environ.get(
        'KLINE_CACHE_ROOT',
        os.path.join(here, 'generated', 'cache', 'stockd'),
    )
    cache_dir = os.path.join(root, code)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f'kline_{code}.csv')


def save_kline_cache(code: str, df: pd.DataFrame) -> str:
    path = _kline_cache_path(code)
    out = _normalize_kline_columns(df)
    out.to_csv(path, index=False, encoding='utf-8')
    return path


def _fetch_kline_via_sina(code: str, datalen: int = 500) -> Optional[pd.DataFrame]:
    """新浪日 K 备用源（东财 API 不可用时）。"""
    symbol = _sina_symbol(code)
    url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
    try:
        resp = requests.get(
            url,
            params={'symbol': symbol, 'scale': 240, 'ma': 'no', 'datalen': datalen},
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'},
            timeout=15,
        )
        resp.raise_for_status()
        rows = json.loads(resp.text)
        if not rows:
            return None
        df = pd.DataFrame(rows)
        return _normalize_kline_columns(df)
    except Exception:
        return None


def download_kline_cache(stock_code: str, datalen: int = 500) -> Dict[str, Any]:
    """下载并保存日 K 到 kline_{code}.csv。"""
    code = str(stock_code).zfill(6)
    df = _fetch_kline_via_sina(code, datalen=datalen)
    if df is None or df.empty:
        df = _fetch_kline_remote(code)
    if df is None or df.empty:
        return {'success': False, 'error': f'无法下载 {code} 日 K 数据'}
    path = save_kline_cache(code, df)
    return {
        'success': True,
        'stock_code': code,
        'path': path,
        'count': len(df),
    }


def _fetch_kline_remote(code: str) -> Optional[pd.DataFrame]:
    if code.startswith(('6', '9')):
        secid = f'1.{code}'
    else:
        secid = f'0.{code}'

    try:
        from utils_reem import _requests_session_no_proxy, parse_kline
    except ImportError:
        from stock.utils_reem import _requests_session_no_proxy, parse_kline

    session = _requests_session_no_proxy()
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        ),
        'Referer': f'https://quote.eastmoney.com/{("sh" if secid.startswith("1.") else "sz")}{code}.html',
    }
    params = {
        'secid': secid,
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',
        'fqt': '1',
        'beg': '0',
        'end': '20500101',
        'lmt': '120',
    }

    for url in (
        'https://push2.eastmoney.com/api/qt/stock/kline/get',
        'https://push2his.eastmoney.com/api/qt/stock/kline/get',
    ):
        try:
            resp = session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            if url.endswith('push2.eastmoney.com/api/qt/stock/kline/get') and resp.text.startswith('{'):
                import json
                payload = resp.json()
                klines = (payload.get('data') or {}).get('klines') or []
                if not klines:
                    continue
                rows = []
                for kline in klines:
                    parts = kline.split(',')
                    if len(parts) >= 11:
                        rows.append({
                            '日期': parts[0],
                            '开盘价': float(parts[1] or 0),
                            '收盘价': float(parts[2] or 0),
                            '最高价': float(parts[3] or 0),
                            '最低价': float(parts[4] or 0),
                            '成交量': float(parts[5] or 0),
                            '成交额': float(parts[6] or 0),
                            '振幅': float(parts[7] or 0),
                            '涨跌幅': float(parts[8] or 0),
                            '涨跌额': float(parts[9] or 0),
                            '换手率': float(parts[10] or 0),
                        })
                if rows:
                    df = pd.DataFrame(rows)
                    df['日期'] = pd.to_datetime(df['日期'])
                    return df.sort_values('日期').reset_index(drop=True)
            else:
                df = parse_kline(resp.text)
                if df is not None and not df.empty:
                    return df.sort_values('日期').reset_index(drop=True)
        except Exception:
            continue
    return None


def _latest_kline_date(df: Optional[pd.DataFrame]) -> Optional[pd.Timestamp]:
    if df is None or df.empty or '日期' not in df.columns:
        return None
    return pd.to_datetime(df['日期']).max()


def _apply_live_quote_to_df(
    df: pd.DataFrame,
    quote: Optional[Dict[str, Any]],
) -> pd.DataFrame:
    """用表格实时价补全或追加当日 K 线（缓存/接口略滞后时）。"""
    if df is None or df.empty or not quote:
        return df
    price = _to_float(quote.get('当前价格') or quote.get('price'))
    change = _to_float(quote.get('涨跌幅') or quote.get('change_percent'))
    if price is None:
        return df

    out = df.copy()
    last_idx = out.index[-1]
    last_date = pd.to_datetime(out.at[last_idx, '日期']).date()
    today = datetime.now().date()

    if last_date == today:
        out.at[last_idx, '收盘价'] = price
        if change is not None:
            out.at[last_idx, '涨跌幅'] = change
        elif last_idx > 0:
            prev = _to_float(out.at[last_idx - 1, '收盘价'])
            if prev:
                out.at[last_idx, '涨跌幅'] = (price - prev) / prev * 100
        return out

    if last_date < today:
        prev_close = _to_float(out.at[last_idx, '收盘价'])
        chg = change
        if chg is None and prev_close:
            chg = (price - prev_close) / prev_close * 100
        new_row: Dict[str, Any] = {col: None for col in out.columns}
        new_row['日期'] = pd.Timestamp(today)
        new_row['开盘价'] = price
        new_row['收盘价'] = price
        new_row['最高价'] = price
        new_row['最低价'] = price
        new_row['成交量'] = 0
        new_row['涨跌幅'] = chg if chg is not None else 0
        out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
        return out.sort_values('日期').reset_index(drop=True)
    return out


def _load_daily_kline_df(code: str) -> Optional[pd.DataFrame]:
    cached = _load_kline_from_cache(code)
    cached = _normalize_kline_columns(cached) if cached is not None and not cached.empty else None

    remote = _fetch_kline_via_sina(code, datalen=500)
    if remote is not None and not remote.empty:
        cached_ts = _latest_kline_date(cached)
        remote_ts = _latest_kline_date(remote)
        if cached_ts is None or remote_ts is None or remote_ts >= cached_ts:
            try:
                save_kline_cache(code, remote)
            except OSError:
                pass
            return remote

    if cached is not None and not cached.empty:
        return cached

    try:
        from utils_reem import get_kline
    except ImportError:
        from stock.utils_reem import get_kline

    for loader in (get_kline, _fetch_kline_remote):
        try:
            raw = loader(code)
            if raw is None or raw.empty:
                continue
            df = _normalize_kline_columns(raw)
            try:
                save_kline_cache(code, df)
            except OSError:
                pass
            return df
        except Exception:
            continue
    return None


def _analyze_from_quote_snapshot(
    code: str,
    name: str,
    quote: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    quote = quote or {}
    price = _to_float(quote.get('当前价格') or quote.get('price'))
    change = _to_float(quote.get('涨跌幅') or quote.get('change_percent'))
    turnover = _to_float(quote.get('换手率'))
    volume_ratio = _to_float(quote.get('量比'))
    amount = _to_float(quote.get('成交额(亿)'))
    market_cap = _to_float(quote.get('流通市值(亿)'))

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'### {name} ({code}) · 行情快照',
        f'**更新时间** {now}',
        '',
        '> 日 K 历史暂不可用（网络或缓存缺失），以下为当前行情快照解读。',
        '',
    ]
    if price is not None:
        lines.append(f'**现价** {price:.2f}' + (f'　**涨跌** {_fmt_pct(change)}' if change is not None else ''))
    elif change is not None:
        lines.append(f'**涨跌幅** {_fmt_pct(change)}')

    hints = []
    if change is not None:
        if change >= 5:
            hints.append('当日涨幅较大，注意追高风险')
        elif change <= -5:
            hints.append('当日跌幅较大，留意支撑与量能')
        elif change > 0:
            hints.append('当日收阳')
        elif change < 0:
            hints.append('当日收阴')
    if volume_ratio is not None:
        if volume_ratio >= 1.5:
            hints.append(f'量比 {volume_ratio:.2f}，成交活跃')
        elif volume_ratio <= 0.7:
            hints.append(f'量比 {volume_ratio:.2f}，成交偏淡')
    if turnover is not None:
        hints.append(f'换手率 {turnover:.2f}%')
    if amount is not None:
        hints.append(f'成交额 {amount:.2f} 亿')
    if market_cap is not None:
        hints.append(f'流通市值 {market_cap:.2f} 亿')

    if hints:
        lines.extend(['', '**观察** ' + '；'.join(hints)])

    summary = '；'.join(hints[:3]) if hints else '仅有有限行情字段，建议稍后重试日 K 分析'
    lines.extend(['', f'**小结** {summary}'])

    markdown = '\n'.join(lines)
    return {
        'success': True,
        'stock_code': code,
        'stock_name': name,
        'date': now,
        'close': price,
        'change_percent': change,
        'summary': summary,
        'markdown': markdown,
        'mode': 'quote_snapshot',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
    }


def analyze_daily_kline(
    stock_code: str,
    stock_name: str = '',
    quote: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """基于日 K 或行情快照生成走势分析。"""
    code = str(stock_code).zfill(6)
    name = (stock_name or code).strip()

    try:
        from utils_cap import calculate_technical_indicators
    except ImportError:
        from stock.utils_cap import calculate_technical_indicators

    df = _load_daily_kline_df(code)
    if df is None or df.empty:
        if quote and any(_to_float(quote.get(k)) is not None for k in (
            '当前价格', 'price', '涨跌幅', 'change_percent', '量比', '换手率',
        )):
            return _analyze_from_quote_snapshot(code, name, quote)
        return {
            'success': False,
            'error': '日 K 数据暂不可用，请稍后重试或检查网络',
        }

    df = _apply_live_quote_to_df(df, quote)
    df = calculate_technical_indicators(df)
    latest = df.iloc[-1]

    close = float(latest['收盘价'])
    change = float(latest.get('涨跌幅', 0) or 0)
    date_str = pd.to_datetime(latest['日期']).strftime('%Y-%m-%d')

    ma5 = latest.get('MA5')
    ma10 = latest.get('MA10')
    ma20 = latest.get('MA20')
    rsi = latest.get('RSI')
    macd = latest.get('MACD')
    signal = latest.get('MACD_Signal')
    hist = latest.get('MACD_Histogram')

    recent_high = df.tail(20)['最高价'].max()
    recent_low = df.tail(20)['最低价'].min()
    vol = float(latest.get('成交量', 0) or 0)
    vol_ma5 = df.tail(5)['成交量'].mean()
    vol_ratio = (vol / vol_ma5) if vol_ma5 else None

    chg5 = _period_change(df, 5)
    chg20 = _period_change(df, 20)
    chg60 = _period_change(df, 60)

    lines: List[str] = [
        f'### {name} ({code}) · 日 K 走势',
        f'**日期** {date_str}　**收盘** {close:.2f}　**涨跌** {_fmt_pct(change)}',
        '',
        '**均线** ' + _ma_trend(close, ma5, ma10, ma20),
    ]
    if pd.notna(ma5):
        lines.append(f'- MA5={ma5:.2f}　MA10={ma10:.2f}　MA20={ma20:.2f}')
    lines.extend([
        '',
        '**MACD** ' + _macd_comment(macd, signal, hist),
        '**RSI** ' + _rsi_comment(rsi),
        '',
        '**区间** 近20日高 {:.2f} / 低 {:.2f}'.format(recent_high, recent_low),
    ])

    period_parts = []
    if chg5 is not None:
        period_parts.append(f'5日 {_fmt_pct(chg5)}')
    if chg20 is not None:
        period_parts.append(f'20日 {_fmt_pct(chg20)}')
    if chg60 is not None:
        period_parts.append(f'60日 {_fmt_pct(chg60)}')
    if period_parts:
        lines.append('**阶段涨幅** ' + '　'.join(period_parts))

    if vol_ratio is not None:
        vol_desc = '放量' if vol_ratio > 1.2 else ('缩量' if vol_ratio < 0.8 else '平量')
        lines.append(f'**量能** 较5日均量 {vol_ratio:.2f} 倍（{vol_desc}）')

    summary_bits = []
    if change > 0 and pd.notna(ma5) and close > ma5:
        summary_bits.append('当日收阳且站上 MA5')
    elif change < 0 and pd.notna(ma5) and close < ma5:
        summary_bits.append('当日收阴且跌破 MA5')
    if pd.notna(hist):
        summary_bits.append('MACD 红柱' if hist > 0 else 'MACD 绿柱')
    if chg20 is not None:
        summary_bits.append(f'20日{_fmt_pct(chg20)}')
    summary = '；'.join(summary_bits) if summary_bits else '暂无显著信号'

    lines.extend(['', f'**小结** {summary}'])

    markdown = '\n'.join(lines)
    return {
        'success': True,
        'stock_code': code,
        'stock_name': name,
        'date': date_str,
        'close': close,
        'change_percent': change,
        'summary': summary,
        'markdown': markdown,
        'mode': 'daily_kline',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
    }
