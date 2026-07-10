"""
Stock Analysis Web Application
Provides comprehensive stock analysis for any given stock code
"""
import os
import re
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from typing import Dict, Optional
import sys
import json
from datetime import datetime, timedelta
import time
import pandas as pd
import numpy as np


# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock.utils_favorites import (
    get_favorites_manager,
    parse_stocks_from_text,
    parse_stocks_detail_from_text,
    get_import_stock_map,
    IMPORT_GROUP,
)
from stock.utils_stock_properties import get_stock_property_store
from stock.bk_flow_cache import ensure_bk_flow_fresh, find_latest_bk_flow_file
from stock.module_cache_policy import cache_expires_at, is_cache_expired, cache_policy_summary, is_trading_calendar_day

try:
    from stock.utils_reem import (
        get_stockcomment,
        get_zjlx_complete,
        get_zjlx_zlb_all,
        find_latest_zjlx_zlb_file,
        get_quote,
        getRealtimeQuote,
    )
    from stock.proto_pkyd import get_pkyd, find_latest_pkyd_file
    from stock.utils_cmts import StockCommentApp
    from stock.app_buysell import buysell_bp
    
    # Initialize stock comment app (with built-in caching)
    stock_app = StockCommentApp()
    
    REAL_DATA_AVAILABLE = True
    print("✓ Real stock data utilities loaded successfully")
    print("✓ Stock Comment App initialized with built-in caching")
except ImportError as e:
    print(f"Warning: Could not import stock utilities. Using mock data. Error: {e}")
    get_stockcomment = None
    get_zjlx_complete = None
    get_zjlx_zlb_all = None
    find_latest_zjlx_zlb_file = None
    getRealtimeQuote = None
    get_quote = None
    get_pkyd = None
    find_latest_pkyd_file = None
    stock_app = None
    buysell_bp = None
    REAL_DATA_AVAILABLE = False

try:
    favorites_mgr = get_favorites_manager()
    stock_property_store = get_stock_property_store()
    print("✓ Favorites Manager initialized")
    print("✓ Stock Property Store initialized")
except Exception as e:
    print(f"Warning: Favorites manager not available. Error: {e}")
    favorites_mgr = None
    stock_property_store = None

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
CORS(app)

# Register buysell blueprint if available
if buysell_bp:
    app.register_blueprint(buysell_bp)
    print("✓ Buysell submodule registered successfully")

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

try:
    try:
        from utils_iwencai import start_iwencai_cookie_auto_update
    except ImportError:
        from stock.utils_iwencai import start_iwencai_cookie_auto_update
    start_iwencai_cookie_auto_update()
    print('✓ Iwencai cookie auto-update enabled')
except Exception as e:
    print(f'⚠ Iwencai cookie auto-update not started: {e}')


@app.errorhandler(404)
def handle_api_not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': f'接口不存在: {request.path}，请重启应用后重试',
        }), 404
    return 'Not Found', 404


@app.errorhandler(500)
def handle_api_server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': '服务器内部错误，请重启应用后重试',
        }), 500
    return 'Internal Server Error', 500


def fetch_module_data(stock_code: str, module_num: int) -> Dict:
    """
    Fetch data for a specific module (caching handled by StockCommentApp)
    
    Args:
        stock_code: Stock code
        module_num: Module number (1-8)
    
    Returns:
        Module data dict
    """
    if not REAL_DATA_AVAILABLE or not stock_app:
        return {"error": "Data fetching not available"}
    
    try:
        print(f"⬇ Fetching data for {stock_code} module_{module_num}")
        module_func = getattr(stock_app, f'run_module_{module_num}', None)
        
        if not module_func:
            return {"error": f"Module {module_num} not found"}
        
        # StockCommentApp handles caching internally
        return module_func(stock_code)
        
    except Exception as e:
        print(f"⚠ Error fetching module_{module_num} for {stock_code}: {e}")
        return {"error": str(e)}


def fetch_all_modules(stock_code: str) -> Dict:
    """
    Fetch data for all 8 modules (caching handled by StockCommentApp)
    
    Args:
        stock_code: Stock code
    
    Returns:
        Dict with all module data
    """
    all_data = {}
    
    for i in range(1, 9):  # 8 modules total
        all_data[f"module_{i}"] = fetch_module_data(stock_code, i)
    
    return all_data


def _read_module1_cache_raw(stock_code: str) -> Optional[Dict]:
    """Read module_1 cache file even when expired."""
    if not REAL_DATA_AVAILABLE or not stock_app:
        return None
    code = str(stock_code).zfill(6)
    cache_file = stock_app._get_cache_file(code, '1')
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠ Module1 cache read failed for {code}: {e}")
        return None


def _normalize_turnover_rate(value) -> float:
    """Normalize turnover to percentage for display (e.g. 2.86 means 2.86%)."""
    if value is None or value == '':
        return 0.0
    raw = str(value).strip()
    had_pct = '%' in raw
    try:
        rate = float(raw.replace('%', '').replace(',', ''))
    except (TypeError, ValueError):
        return 0.0
    if rate < 0:
        return 0.0
    if had_pct or rate > 1:
        return round(rate, 4)
    if rate == 0:
        return 0.0
    # Ambiguous (0, 1]: 0.0286 (fraction) vs 0.84 (percent literal)
    as_pct_if_fraction = rate * 100
    if as_pct_if_fraction > 20:
        return round(rate, 4)
    return round(as_pct_if_fraction, 4)


def _header_quote_updated_at(trade_date=None, fallback_mtime=None) -> str:
    """Display timestamp for header quote — market close after hours, not cache write time."""
    now = datetime.now()
    close_today = now.replace(hour=15, minute=0, second=0, microsecond=0)

    try:
        from utils_cap import is_trading_time as _cap_is_trading_time
        trading = _cap_is_trading_time()
    except ImportError:
        trading = False

    if trading:
        return now.strftime('%Y-%m-%d %H:%M:%S')

    if now.weekday() < 5 and now >= close_today:
        return close_today.strftime('%Y-%m-%d %H:%M:%S')

    if trade_date not in (None, ''):
        day = str(trade_date).strip().replace('T', ' ')[:10]
        try:
            datetime.strptime(day, '%Y-%m-%d')
            return f'{day} 15:00:00'
        except ValueError:
            pass

    if fallback_mtime is not None:
        return datetime.fromtimestamp(fallback_mtime).strftime('%Y-%m-%d %H:%M:%S')
    return now.strftime('%Y-%m-%d %H:%M:%S')


def _quote_from_push2delay(stock_code: str) -> Optional[Dict]:
    """Lightweight live quote via push2delay when get_quote fails."""
    try:
        import time as _time
        from utils_cap import _requests_session_no_proxy

        code = str(stock_code).zfill(6)
        prefix = '1' if code.startswith(('6', '9')) else '0'
        secid = f'{prefix}.{code}'
        params = {
            'invt': '2',
            'fltt': '1',
            'fields': 'f58,f43,f169,f170,f168',
            'secid': secid,
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            '_': int(_time.time() * 1000),
        }
        resp = _requests_session_no_proxy().get(
            'https://push2delay.eastmoney.com/api/qt/stock/get',
            params=params,
            timeout=10,
        )
        payload = resp.json()
        if payload.get('rc') != 0 or not payload.get('data'):
            return None
        d = payload['data']
        price = float(d.get('f43', 0)) / 100
        change_pct = float(d.get('f169', 0)) / 100
        change_amt = float(d.get('f170', 0)) / 100
        return {
            'code': code,
            'name': str(d.get('f58') or code),
            'price': price,
            'change': change_amt,
            'change_percent': change_pct,
            'turnover_rate': _normalize_turnover_rate(float(d.get('f168', 0)) / 100),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
    except Exception as e:
        print(f'⚠ push2delay quote failed for {stock_code}: {e}')
        return None


def _quote_from_module1_cache(stock_code: str) -> Optional[Dict]:
    """Header quote from comprehensive evaluation cache (matches module pages)."""
    data = _read_module1_cache_raw(stock_code)
    if not data or data.get('error'):
        return None

    inner = data.get('data') or {}
    summary = inner.get('evaluation_summary') or {}
    key_metrics = summary.get('key_metrics') or {}
    close_price = key_metrics.get('close_price')
    if close_price in (None, '', 0):
        return None

    pk_rows = ((inner.get('pk_ranking_analysis') or {}).get('result') or {}).get('data') or []
    pk = pk_rows[0] if pk_rows else {}
    name = pk.get('SECURITY_NAME_ABBR') or str(stock_code).zfill(6)

    price = float(close_price)
    change_rate = float(key_metrics.get('change_rate') or pk.get('CHANGE_RATE') or 0)
    prev_close = price / (1 + change_rate / 100) if change_rate != -100 else price
    change = round(price - prev_close, 2)

    cache_file = stock_app._get_cache_file(str(stock_code).zfill(6), '1')
    trade_date = pk.get('TRADE_DATE')
    updated_at = _header_quote_updated_at(
        trade_date=trade_date,
        fallback_mtime=cache_file.stat().st_mtime,
    )

    return {
        'code': str(stock_code).zfill(6),
        'name': str(name),
        'price': price,
        'change': change,
        'change_percent': round(change_rate, 2),
        'pe_ratio': float(key_metrics.get('pe_ratio') or 0),
        'turnover_rate': _normalize_turnover_rate(key_metrics.get('turnover_rate')),
        'trade_date': trade_date,
        'updated_at': updated_at,
    }


def _stockhotmap_display_name(stock_code: str, row_name) -> str:
    """Resolve stock name when starmap pipe format stores code in 股票名称."""
    code = str(stock_code).zfill(6)
    name = str(row_name or '').strip()
    if name and name.zfill(6) != code and name != code:
        return name
    try:
        base = _fetch_quote_base_data()
        hy = (base.get('stock_hy') or {}).get(code)
        if hy and hy.get('name'):
            return str(hy['name'])
    except Exception:
        pass
    return code


def _quote_from_stockhotmap(stock_code: str, force_fresh: bool = False) -> Optional[Dict]:
    """Header quote from stockhotmap getquotedata (CSV cache or live fetch)."""
    try:
        from quote_cache import get_cached_realtime_quote, should_refresh_quote

        code = str(stock_code).zfill(6)
        payload = None

        if force_fresh and REAL_DATA_AVAILABLE and getRealtimeQuote:
            need, _reason = should_refresh_quote(force=True)
            cached = get_cached_realtime_quote()
            if need or not cached:
                payload = getRealtimeQuote(force=True)
            else:
                payload = cached
        else:
            payload = get_cached_realtime_quote()
            if payload is None and REAL_DATA_AVAILABLE and getRealtimeQuote:
                payload = getRealtimeQuote(force=False)

        if not payload:
            return None

        row = next(
            (
                s for s in (payload.get('stock_data') or [])
                if str(s.get('股票代码', '')).zfill(6) == code
            ),
            None,
        )
        if not row:
            return None

        price = float(row.get('当前价') or 0)
        if price <= 0:
            return None

        change_pct = float(row.get('涨跌幅') or 0)
        change_raw = row.get('涨跌额')
        if change_raw in (None, ''):
            prev_close = price / (1 + change_pct / 100) if change_pct != -100 else price
            change_amt = round(price - prev_close, 2)
        else:
            change_amt = float(change_raw)

        quote_file = payload.get('quote_file')
        fallback_mtime = (
            os.path.getmtime(quote_file)
            if quote_file and os.path.exists(quote_file)
            else None
        )
        updated_at = _header_quote_updated_at(fallback_mtime=fallback_mtime)
        try:
            from utils_cap import is_trading_time as _cap_is_trading_time
            if _cap_is_trading_time() and payload.get('update_time'):
                updated_at = str(payload['update_time'])
        except ImportError:
            pass

        return {
            'code': code,
            'name': _stockhotmap_display_name(code, row.get('股票名称')),
            'price': price,
            'change': round(change_amt, 2),
            'change_percent': round(change_pct, 2),
            'turnover_rate': _normalize_turnover_rate(row.get('换手率')),
            'updated_at': updated_at,
        }
    except Exception as e:
        print(f'⚠ stockhotmap quote failed for {stock_code}: {e}')
        return None


def _quote_from_stockcomment_cache(stock_code: str) -> Optional[Dict]:
    """Fallback header quote from latest stockcommentC CSV."""
    try:
        import pandas as pd
        if not get_stockcomment:
            return None
        from stock.utils_reem import find_latest_stockcomment_files
        _, compact_file = find_latest_stockcomment_files()
        if not compact_file or not os.path.exists(compact_file):
            return None

        df = pd.read_csv(compact_file, dtype={'股票代码': str})
        code = str(stock_code).zfill(6)
        df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
        matched = df[df['股票代码'] == code]
        if matched.empty:
            return None

        row = matched.iloc[0]
        price = float(row['最新价'])
        change_pct = float(str(row['涨跌幅']).replace('%', '').strip())
        prev_close = price / (1 + change_pct / 100) if change_pct != -100 else price
        change = price - prev_close

        pe_ratio = 0.0
        if '市盈率' in row and pd.notna(row['市盈率']):
            pe_ratio = float(row['市盈率'])

        updated_at = _header_quote_updated_at(
            fallback_mtime=os.path.getmtime(compact_file),
        )

        turnover_rate = 0.0
        if '换手率' in row and pd.notna(row['换手率']):
            turnover_rate = _normalize_turnover_rate(str(row['换手率']).strip())

        return {
            'code': code,
            'name': str(row['名称']),
            'price': price,
            'change': round(change, 2),
            'change_percent': change_pct,
            'pe_ratio': pe_ratio,
            'turnover_rate': turnover_rate,
            'updated_at': updated_at,
        }
    except Exception as e:
        print(f"⚠ Stockcomment quote fallback failed for {stock_code}: {e}")
        return None


def _should_prefer_live_favorite_quotes(explicit_live: bool, latest_file: Optional[str]) -> bool:
    """Prefer live API when forced, in trading session, or when CSV is unavailable."""
    if explicit_live:
        return True
    try:
        from favorites_quote_cache import _is_trading_session
        if _is_trading_session():
            return True
    except ImportError:
        try:
            from stock.utils_reem import is_trading_time
        except ImportError:
            is_trading_time = lambda: False  # type: ignore
        if is_trading_time():
            return True
    if not latest_file or not os.path.exists(latest_file):
        return True
    return False


def _ensure_market_quote_csv(force: bool = False) -> Optional[str]:
    """Ensure a market-wide quote CSV exists; refresh when missing or stale."""
    try:
        from quote_cache import find_latest_quote_file, should_refresh_quote
    except ImportError:
        return None

    latest = find_latest_quote_file()
    need, _reason = should_refresh_quote(force=force)
    if latest and not need and not force:
        return latest

    if (not latest or need or force) and REAL_DATA_AVAILABLE and getRealtimeQuote:
        try:
            getRealtimeQuote(force=force or need)
        except Exception as e:
            print(f"⚠ ensure market quote csv: {e}")
    return find_latest_quote_file()


def _glob_pkyd_files() -> list:
    import glob

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(parent_dir, "generated/em/**/pkyd_*.csv")
    files = glob.glob(pattern, recursive=True)
    stock_pattern = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pkyd_*.csv")
    return files + glob.glob(stock_pattern)


def _ensure_pkyd_data(force: bool = False) -> Dict:
    """Ensure pkyd CSV exists; refresh using same cache policy as stockcomment."""
    result: Dict = {'pkyd_file': None, 'cached': False, 'reason': '', 'fetched': False}
    if REAL_DATA_AVAILABLE and get_pkyd:
        try:
            result = get_pkyd(force_refetch=force) or result
            result['fetched'] = bool(not result.get('cached') or force)
        except Exception as exc:
            print(f"⚠ ensure pkyd data: {exc}")
            result['reason'] = str(exc)
    if not result.get('pkyd_file'):
        files = _glob_pkyd_files()
        if files:
            result['pkyd_file'] = max(files, key=os.path.getmtime)
            result.setdefault('reason', '使用本地最新文件')
    if result.get('pkyd_file'):
        result.update(_raw_batch_cache_meta(result['pkyd_file']))
    return result


def _raw_batch_cache_meta(file_path: Optional[str], now: Optional[datetime] = None) -> Dict:
    """17:00 batch cache metadata (same policy as stockcomment / pkyd)."""
    from stock.module_cache_policy import (
        is_stockcomment_cache_fresh,
        is_trading_calendar_day,
        stockcomment_cache_policy_summary,
    )

    now = now or datetime.now()
    if not file_path or not os.path.exists(file_path):
        return {
            'cache_fresh': False,
            'cached': False,
            'stale': False,
            'should_fetch': is_trading_calendar_day(now),
            'reason': '无缓存文件',
        }
    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    if is_stockcomment_cache_fresh(mtime, now):
        return {
            'cache_fresh': True,
            'cached': True,
            'stale': False,
            'should_fetch': False,
            'reason': f'缓存有效 · {stockcomment_cache_policy_summary()}',
        }
    if not is_trading_calendar_day(now):
        return {
            'cache_fresh': False,
            'cached': True,
            'stale': True,
            'should_fetch': False,
            'reason': '非交易日复用最近批次',
        }
    return {
        'cache_fresh': False,
        'cached': True,
        'stale': False,
        'should_fetch': True,
        'reason': '缓存已过期，需重新拉取',
    }


def _normalize_raw_stock_code(raw) -> Optional[str]:
    text = str(raw or '').strip().upper()
    match = re.search(r'(\d{6})', text)
    return match.group(1) if match else None


def _raw_row_stock_code(row: Dict) -> Optional[str]:
    for key in ('股票代码', '代码', 'SECURITY_CODE', 'code', 'SecuCode', 'secucode'):
        if key in row and row[key] not in (None, '', '-'):
            code = _normalize_raw_stock_code(row[key])
            if code:
                return code
    return None


def _enrich_raw_records(records: list) -> list:
    enriched = []
    for item in records:
        row = dict(item)
        code = _raw_row_stock_code(row)
        if code:
            row['_chart_code'] = code
            row['mini_quote_url'] = _mini_quote_chart_url(code)
            row['intraday_url'] = _intraday_chart_url(code)
            row['kline_url'] = _kline_daily_chart_url(code)
        enriched.append(row)
    return enriched


def _glob_stockcomment_files(file_type: str = 'stockcomment') -> list:
    import glob

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if file_type == 'stockcommentC':
        pattern = os.path.join(parent_dir, "generated/em/*/stockcommentC_*.csv")
    else:
        pattern = os.path.join(parent_dir, "generated/em/*/stockcomment_*.csv")
    return glob.glob(pattern)


def _ensure_stockcomment_data(force: bool = False) -> Dict:
    """Ensure stockcomment CSV; refresh when batch cache expired (同 get_stockcomment)."""
    result: Dict = {'stockcomment_file': None, 'cached': False, 'reason': '', 'fetched': False}
    if REAL_DATA_AVAILABLE and get_stockcomment:
        try:
            before = _glob_stockcomment_files()
            before_mtime = max((os.path.getmtime(p) for p in before), default=0)
            payload = get_stockcomment(force_refetch=force) or {}
            result.update(payload)
            after_file = payload.get('stockcomment_file')
            if after_file and os.path.exists(after_file):
                if force or os.path.getmtime(after_file) > before_mtime + 0.5:
                    result['fetched'] = not payload.get('cached', False) or force
        except Exception as exc:
            print(f"⚠ ensure stockcomment data: {exc}")
            result['reason'] = str(exc)
    if not result.get('stockcomment_file'):
        files = _glob_stockcomment_files()
        if files:
            result['stockcomment_file'] = max(files, key=os.path.getmtime)
            result.setdefault('reason', '使用本地最新文件')
    if result.get('stockcomment_file'):
        result.update(_raw_batch_cache_meta(result['stockcomment_file']))
    return result


def _glob_zjlx_files(file_type: str = 'zjlx') -> list:
    import glob

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if file_type == 'flow':
        pattern = os.path.join(parent_dir, "generated/em/*/flow_*.csv")
    else:
        pattern = os.path.join(parent_dir, "generated/em/*/zjlx_*.csv")
    return glob.glob(pattern)


def _ensure_stockflows_data(force: bool = False, file_type: str = 'zjlx') -> Dict:
    """Ensure zjlx/flow CSV; auto-fetch on trading day when batch cache expired."""
    result: Dict = {'zjlx_file': None, 'cached': False, 'reason': '', 'fetched': False, 'file_type': file_type}
    latest = None
    if file_type == 'zjlx' and find_latest_zjlx_zlb_file:
        latest = find_latest_zjlx_zlb_file(prefer_today=False)
    if not latest:
        files = _glob_zjlx_files(file_type)
        latest = max(files, key=os.path.getmtime) if files else None

    meta = _raw_batch_cache_meta(latest)
    need_fetch = force or (meta.get('should_fetch') and REAL_DATA_AVAILABLE)
    if need_fetch and file_type == 'zjlx' and get_zjlx_zlb_all:
        try:
            before_mtime = os.path.getmtime(latest) if latest and os.path.exists(latest) else 0
            get_zjlx_zlb_all()
            latest = find_latest_zjlx_zlb_file(prefer_today=False) if find_latest_zjlx_zlb_file else None
            if not latest:
                files = _glob_zjlx_files(file_type)
                latest = max(files, key=os.path.getmtime) if files else None
            if latest and os.path.exists(latest) and os.path.getmtime(latest) > before_mtime + 0.5:
                result['fetched'] = True
                result['cached'] = False
                result['reason'] = '已重新拉取'
            elif latest:
                result['cached'] = True
                result['reason'] = meta.get('reason', '')
        except Exception as exc:
            print(f"⚠ ensure stockflows data: {exc}")
            result['reason'] = str(exc)
    elif latest:
        result['cached'] = True
        result['reason'] = meta.get('reason', '')

    result['zjlx_file'] = latest
    if latest:
        result.update(_raw_batch_cache_meta(latest))
    return result


def _pick_latest_stockflows_file(file_type: str = 'zjlx') -> Optional[str]:
    """Return newest zjlx or flow CSV path."""
    if file_type == 'zjlx' and find_latest_zjlx_zlb_file:
        path = find_latest_zjlx_zlb_file(prefer_today=True)
        if path:
            return path
    files = _glob_zjlx_files(file_type)
    return max(files, key=os.path.getmtime) if files else None


def _ensure_quotes_data(force: bool = False, file_type: str = 'quote') -> Dict:
    """Ensure quote CSV via quote_cache policy."""
    import glob

    result: Dict = {'quote_file': None, 'cached': False, 'reason': '', 'fetched': False, 'file_type': file_type}
    if file_type != 'quote':
        files = glob.glob(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "generated/em/*/q_report_*.csv",
        ))
        if files:
            result['quote_file'] = max(files, key=os.path.getmtime)
        return result

    try:
        from quote_cache import find_latest_quote_file, should_refresh_quote
    except ImportError:
        find_latest_quote_file = None
        should_refresh_quote = None

    before = find_latest_quote_file() if find_latest_quote_file else None
    before_mtime = os.path.getmtime(before) if before and os.path.exists(before) else 0
    need, reason = should_refresh_quote(force=force) if should_refresh_quote else (force, 'force')
    if need or force or not before:
        path = _ensure_market_quote_csv(force=force or need)
        if path and os.path.exists(path) and os.path.getmtime(path) > before_mtime + 0.5:
            result['fetched'] = True
            result['cached'] = False
            result['reason'] = f'已刷新 · {reason}'
        else:
            result['cached'] = True
            result['reason'] = reason or '使用缓存'
        result['quote_file'] = path
    else:
        result['quote_file'] = before
        result['cached'] = True
        result['cache_fresh'] = True
        result['should_fetch'] = False
        result['reason'] = f'缓存有效 · {reason}'
    if not result.get('quote_file') and find_latest_quote_file:
        result['quote_file'] = find_latest_quote_file()
    return result


def _json_raw_file_payload(file_path: str, df, extra: Optional[Dict] = None) -> Dict:
    from datetime import datetime as dt

    file_mtime = os.path.getmtime(file_path)
    file_datetime = dt.fromtimestamp(file_mtime)
    payload = {
        'success': True,
        'filename': os.path.basename(file_path),
        'total_records': len(df),
        'timestamp': file_mtime * 1000,
        'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
        'data': _enrich_raw_records(df.head(100).to_dict(orient='records')),
    }
    if extra:
        payload.update(extra)
    return payload


def _build_favorite_rows_from_quote_cache(stocks_data, pin_info: Dict, payload: Dict) -> list:
    import pandas as pd

    quotes = payload.get('quotes') or {}
    live_map = {
        code: {
            'name': q.get('name', code),
            'price': q.get('price'),
            'change_percent': q.get('change_percent'),
        }
        for code, q in quotes.items()
    }

    df, code_col = None, None
    csv_path = payload.get('csv_path')
    try:
        from quote_cache import find_latest_quote_file

        latest_quote = find_latest_quote_file()
        if latest_quote and os.path.exists(latest_quote):
            if not csv_path or not os.path.exists(csv_path):
                csv_path = latest_quote
            elif os.path.getmtime(latest_quote) > os.path.getmtime(csv_path):
                csv_path = latest_quote
    except Exception:
        pass
    if csv_path and os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            code_col = next((c for c in ('代码', '股票代码', 'code') if c in df.columns), None)
            if code_col:
                df[code_col] = df[code_col].astype(str).str.zfill(6)
        except Exception:
            df, code_col = None, None

    result = []
    seen_codes = set()
    for stock in stocks_data:
        code = stock['code'].zfill(6)
        if code in seen_codes:
            continue
        seen_codes.add(code)
        row = _build_favorite_row(
            code, pin_info[code], df, code_col,
            prefer_live=True,
            live_quote_map=live_map,
        )
        extras = (quotes.get(code) or {}).get('extras') or {}
        for key, value in extras.items():
            if value not in (None, '', '--'):
                row[key] = value
        _apply_industry_fields_to_row(row, code)
        result.append(row)

    result.sort(key=lambda x: (
        -x.get('_top_pinned', 0),
        -x.get('_pinned', 0),
    ))
    return result


def _favorites_pick_note_payload(group_name: str) -> Dict:
    pick_note = favorites_mgr.get_group_pick_note(group_name)
    pick_note_html = None
    if pick_note:
        try:
            try:
                from stock.utils_pick_note import markdown_to_html
            except ImportError:
                from utils_pick_note import markdown_to_html
            pick_note_html = markdown_to_html(pick_note)
        except Exception:
            pick_note_html = None
    return {'pick_note': pick_note, 'pick_note_html': pick_note_html}


def _em_secid(stock_code: str) -> str:
    code = str(stock_code).zfill(6)
    if code.startswith('6'):
        return f'1.{code}'
    return f'0.{code}'


def _fetch_em_ulist_live_quotes(stock_codes) -> Dict[str, Dict]:
    """Batch fetch live price/change from East Money ulist (no proxy)."""
    result: Dict[str, Dict] = {}
    codes = [str(c).zfill(6) for c in stock_codes if str(c).strip()]
    if not codes:
        return result

    try:
        from stock.utils_reem import _requests_session_no_proxy
    except ImportError:
        from utils_reem import _requests_session_no_proxy

    session = _requests_session_no_proxy()
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}

    for i in range(0, len(codes), 80):
        chunk = codes[i:i + 80]
        secids = ','.join(_em_secid(c) for c in chunk)
        for attempt in range(3):
            try:
                resp = session.get(
                    'https://push2.eastmoney.com/api/qt/ulist.np/get',
                    params={
                        'fltt': 2,
                        'secids': secids,
                        'fields': 'f12,f14,f2,f3,f4',
                        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                    },
                    headers=headers,
                    timeout=20,
                )
                resp.raise_for_status()
                for item in (resp.json().get('data') or {}).get('diff') or []:
                    code = str(item.get('f12', '')).zfill(6)
                    price = item.get('f2')
                    if price in (None, '-'):
                        continue
                    result[code] = {
                        'name': str(item.get('f14', code)),
                        'price': float(price),
                        'change_percent': float(item.get('f3', 0) or 0),
                    }
                break
            except Exception as e:
                if attempt == 2:
                    print(f"⚠ EM ulist batch quote failed ({i}-{i + len(chunk)}): {e}")
    return result


def _load_iwencai_group_quotes(group_name: str) -> Dict[str, Dict]:
    """Load price/name snapshot saved when importing iwencai picks."""
    import glob
    import pandas as pd

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exact = os.path.join(parent_dir, 'generated', 'em', '*', f'iwencai_{group_name}.csv')
    paths = sorted(glob.glob(exact), key=os.path.getmtime, reverse=True)
    if not paths:
        label = group_name.rsplit('_', 1)[0] if '_' in group_name else group_name
        paths = sorted(
            [p for p in glob.glob(os.path.join(parent_dir, 'generated', 'em', '*', 'iwencai_*.csv'))
             if label in os.path.basename(p)],
            key=os.path.getmtime,
            reverse=True,
        )
    if not paths:
        return {}

    try:
        df = pd.read_csv(paths[0], dtype={'代码': str})
    except Exception as e:
        print(f"⚠ iwencai csv read failed: {e}")
        return {}

    code_col = next((c for c in ('代码', 'code', '股票代码') if c in df.columns), None)
    name_col = next((c for c in ('名称', 'name', '股票名称', '股票简称') if c in df.columns), None)
    price_col = next((c for c in ('现价', '当前价格', 'price', '最新价') if c in df.columns), None)
    chg_col = next((c for c in ('涨跌幅', '涨跌幅:前复权', 'change_percent') if c in df.columns), None)
    if not code_col:
        return {}

    out: Dict[str, Dict] = {}
    for _, row in df.iterrows():
        code = str(row[code_col]).zfill(6)
        item: Dict = {}
        if name_col and pd.notna(row.get(name_col)):
            item['name'] = str(row[name_col])
        if price_col and pd.notna(row.get(price_col)):
            try:
                item['price'] = float(row[price_col])
            except (TypeError, ValueError):
                pass
        if chg_col and pd.notna(row.get(chg_col)):
            try:
                item['change_percent'] = float(str(row[chg_col]).replace('%', ''))
            except (TypeError, ValueError):
                pass
        if item:
            out[code] = item
    return out


def _find_best_quote_file(files, min_rows=50):
    """Pick a quote CSV with enough rows; skip tiny per-stock cache files."""
    if not files:
        return None

    ranked = []
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                row_count = max(sum(1 for _ in fh) - 1, 0)
            ranked.append((path, row_count, os.path.getmtime(path)))
        except OSError:
            continue

    if not ranked:
        return max(files, key=os.path.getmtime)

    ranked.sort(key=lambda item: item[2], reverse=True)
    for path, row_count, _ in ranked:
        if row_count >= min_rows:
            return path

    return max(ranked, key=lambda item: item[1])[0]


def _fetch_favorite_quote_info(stock_code: str) -> Optional[Dict]:
    """Fetch latest name/price for a favorite stock."""
    code = str(stock_code).zfill(6)

    if REAL_DATA_AVAILABLE and get_quote:
        try:
            quote_data = get_quote(code)
            if quote_data:
                return {
                    'name': quote_data.get('股票名称', code),
                    'price': quote_data.get('当前价格'),
                    'change_percent': quote_data.get('涨跌幅'),
                }
        except Exception as e:
            print(f"⚠ Quote fetch failed for favorite {code}: {e}")

    cached = _quote_from_stockcomment_cache(code)
    if cached:
        return {
            'name': cached['name'],
            'price': cached['price'],
            'change_percent': cached['change_percent'],
        }

    try:
        import requests
        response = requests.get(
            'https://searchadapter.eastmoney.com/api/suggest/get',
            params={
                'input': code,
                'type': '14',
                'token': 'D43BF722C8E33BDC906FB84D85E326E8',
                'count': 5,
            },
            timeout=5,
        )
        response.raise_for_status()
        for item in response.json().get('QuotationCodeTable', {}).get('Data') or []:
            if str(item.get('Code', '')).zfill(6) == code:
                return {
                    'name': item.get('Name') or code,
                    'price': None,
                    'change_percent': None,
                }
    except Exception as e:
        print(f"⚠ Search fallback failed for favorite {code}: {e}")

    return None


def _stock_code_link(code: str) -> str:
    code = str(code).zfill(6)
    return (
        f'<a href="/analysis/{code}" '
        f'style="color: #2196F3; text-decoration: none;">{code}</a>'
    )


def _find_csv_row_for_code(df, code_col: str, stock_code: str):
    """Find a quote CSV row by code, with fallback when code is stored in name column."""
    import pandas as pd

    code = str(stock_code).zfill(6)
    if df is None or df.empty:
        return None

    code_series = df[code_col].astype(str).str.replace(r'\.0$', '', regex=True)
    matched = df[code_series.str.fullmatch(r'\d{6}') & (code_series == code)]
    if not matched.empty:
        return matched.iloc[0]

    name_col = '股票名称' if '股票名称' in df.columns else None
    if name_col:
        name_series = df[name_col].astype(str)
        matched = df[name_series == code]
        if not matched.empty:
            return matched.iloc[0]

    return None


def _json_safe(value):
    """将 NaN/Inf 等不可 JSON 序列化的值转为 None。"""
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        if pd.isna(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _valid_stock_display_name(name, code: str) -> Optional[str]:
    """Reject numeric/broken names from quote CSV (e.g. 2475.0)."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return None
    text = str(name).strip()
    if not text or text == code:
        return None
    if re.fullmatch(r'\d+\.?\d*', text):
        return None
    return text


def _resolve_favorite_display_name(code: str) -> str:
    """Resolve human-readable stock name from multiple local/remote sources."""
    code = str(code).zfill(6)

    cached = _quote_from_stockcomment_cache(code)
    if cached:
        name = _valid_stock_display_name(cached.get('name'), code)
        if name:
            return name

    try:
        from utils_favorites import _load_stock_map
        stock_map = _load_stock_map()
        if code in stock_map:
            name = _valid_stock_display_name(stock_map[code], code)
            if name:
                return name
    except Exception:
        pass

    try:
        import glob
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        zjlx_files = glob.glob(os.path.join(parent_dir, 'generated/em/*/zjlx_zlb_*.csv'))
        if zjlx_files:
            import pandas as pd
            zjlx = pd.read_csv(max(zjlx_files, key=os.path.getmtime), usecols=['代码', '名称'], dtype={'代码': str})
            zjlx['代码'] = zjlx['代码'].astype(str).str.zfill(6)
            matched = zjlx[zjlx['代码'] == code]
            if not matched.empty:
                name = _valid_stock_display_name(matched.iloc[0]['名称'], code)
                if name:
                    return name
    except Exception:
        pass

    if REAL_DATA_AVAILABLE and get_quote:
        try:
            quote_data = get_quote(code)
            if quote_data:
                name = _valid_stock_display_name(quote_data.get('股票名称'), code)
                if name:
                    return name
        except Exception:
            pass

    try:
        import requests
        response = requests.get(
            'https://searchadapter.eastmoney.com/api/suggest/get',
            params={
                'input': code,
                'type': '14',
                'token': 'D43BF722C8E33BDC906FB84D85E326E8',
                'count': 5,
            },
            timeout=5,
        )
        response.raise_for_status()
        for item in response.json().get('QuotationCodeTable', {}).get('Data') or []:
            if str(item.get('Code', '')).zfill(6) == code:
                name = _valid_stock_display_name(item.get('Name'), code)
                if name:
                    return name
    except Exception:
        pass

    return code


def _quote_fields_from_csv_row(csv_row) -> Dict:
    """Extract price/change/name from a quote CSV row."""
    out: Dict = {}
    if csv_row is None:
        return out
    if '当前价' in csv_row.index and pd.notna(csv_row['当前价']):
        price = _json_safe(csv_row['当前价'])
        if price is not None:
            out['price'] = price
    if '涨跌幅' in csv_row.index and pd.notna(csv_row['涨跌幅']):
        change = _json_safe(csv_row['涨跌幅'])
        if change is not None:
            out['change_percent'] = change
    for name_col in ('股票名称', '名称'):
        if name_col in csv_row.index and pd.notna(csv_row[name_col]):
            name = _valid_stock_display_name(csv_row[name_col], '')
            if name:
                out['name'] = name
                break
    return out


_stock_bk_industry_maps: Optional[Dict[int, Dict[str, str]]] = None


def _bk_name_from_stock_hy(stock_hy: Dict, level: int) -> Dict[str, str]:
    bk_key = f'bk{level}'
    mapping: Dict[str, str] = {}
    for stock_code, info in (stock_hy or {}).items():
        name = (info.get(bk_key) or {}).get('name') or ''
        if name:
            mapping[str(stock_code).zfill(6)] = name
    return mapping


def _load_bk_industry_maps() -> Dict[int, Dict[str, str]]:
    """Load stock code -> East Money bk2/bk3 industry names (local cache first)."""
    global _stock_bk_industry_maps
    if _stock_bk_industry_maps:
        return _stock_bk_industry_maps

    import glob
    import json

    maps: Dict[int, Dict[str, str]] = {2: {}, 3: {}}
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in sorted(glob.glob(os.path.join(parent_dir, 'generated/em/*/quote_base.json')), reverse=True):
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                cached = json.load(fh)
            stock_hy = cached.get('stock_hy') or {}
            maps[2].update(_bk_name_from_stock_hy(stock_hy, 2))
            maps[3].update(_bk_name_from_stock_hy(stock_hy, 3))
            if len(maps[3]) > 1000:
                break
        except (OSError, json.JSONDecodeError, TypeError):
            continue

    if len(maps[3]) < 1000:
        quote_base = _fetch_quote_base_data()
        stock_hy = quote_base.get('stock_hy') or {}
        maps[2].update(_bk_name_from_stock_hy(stock_hy, 2))
        maps[3].update(_bk_name_from_stock_hy(stock_hy, 3))

    if len(maps[3]) < 1000:
        for code, name in _load_sector_constituent_map().items():
            maps[3].setdefault(code, name)
        for code, name in _load_performers_stock_sector_map().items():
            maps[3].setdefault(code, name)

    if maps[2] or maps[3]:
        _stock_bk_industry_maps = maps
    return maps


def _load_bk3_industry_map() -> Dict[str, str]:
    return _load_bk_industry_maps().get(3, {})


def _lookup_bk2_industry(code: str) -> str:
    return _load_bk_industry_maps().get(2, {}).get(str(code).zfill(6), '')


def _lookup_bk3_industry(code: str) -> str:
    return _load_bk_industry_maps().get(3, {}).get(str(code).zfill(6), '')


def _stock_hy_industry_info(code: str) -> Dict:
    """East Money bk1/bk2/bk3 names and sector-pick link target for header."""
    code = str(code).zfill(6)
    chain: list = []
    level_items: list = []
    try:
        hy = (_fetch_quote_base_data().get('stock_hy') or {}).get(code) or {}
        for level in (1, 2, 3):
            bk = hy.get(f'bk{level}') or {}
            name = str(bk.get('name') or '').strip()
            bk_code = str(bk.get('code') or '').strip()
            if name and (not chain or name != chain[-1]):
                chain.append(name)
                level_items.append({'level': level, 'name': name, 'code': bk_code})
    except Exception:
        chain = []
        level_items = []

    if len(chain) < 2:
        maps = _load_bk_industry_maps()
        for level, name in ((2, maps.get(2, {}).get(code, '')), (3, maps.get(3, {}).get(code, ''))):
            name = str(name or '').strip()
            if name and (not chain or name != chain[-1]):
                chain.append(name)
                level_items.append({'level': level, 'name': name, 'code': ''})

    link_level = None
    link_code = None
    for item in reversed(level_items):
        if item.get('code'):
            link_level = item['level']
            link_code = item['code']
            break

    return {
        'industry_chain': chain,
        'industry_text': '｜'.join(chain) if chain else '',
        'industry_levels': level_items,
        'industry_hy_level': link_level,
        'industry_hy_code': link_code,
    }


def _stock_hy_industry_chain(code: str) -> list:
    """East Money bk1/bk2/bk3 industry names for compact header display."""
    return _stock_hy_industry_info(code).get('industry_chain') or []


def _apply_industry_fields_to_row(row: Dict, code: str) -> None:
    """Fill 东财二级/三级行业 on a favorites table row."""
    code = str(code).zfill(6)
    bk2 = _lookup_bk2_industry(code)
    if bk2:
        row['东财二级行业'] = bk2
    bk3 = _lookup_bk3_industry(code)
    if bk3:
        row['东财三级行业'] = bk3


def _enrich_favorite_stocks_industry(stocks: list) -> list:
    """Ensure each favorites row has 东财二级/三级行业."""
    if not stocks:
        return stocks
    maps = _load_bk_industry_maps()
    bk2_map = maps.get(2) or {}
    bk3_map = maps.get(3) or {}
    if not bk2_map and not bk3_map:
        return stocks
    for row in stocks:
        code = str(row.get('_code') or _extract_stock_code_from_cell(row.get('股票代码')) or '').zfill(6)
        if not code:
            continue
        if code in bk2_map:
            row['东财二级行业'] = bk2_map[code]
        if code in bk3_map:
            row['东财三级行业'] = bk3_map[code]
    return stocks


def _build_favorite_row(
    stock_code: str,
    pin_meta: Dict,
    df=None,
    code_col: Optional[str] = None,
    prefer_live: bool = False,
    live_quote_map: Optional[Dict[str, Dict]] = None,
    iwencai_quote_map: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """Build one favorites table row with reliable name/quote fields."""
    code = str(stock_code).zfill(6)
    row = {
        '股票代码': _stock_code_link(code),
        '股票名称': code,
        '当前价格': '--',
        '涨跌幅': '--',
        'mini_quote_url': _mini_quote_chart_url(code),
        'intraday_url': _intraday_chart_url(code),
        'kline_url': _kline_daily_chart_url(code),
        'macd_url': _kline_macd_chart_url(code),
        '_code': code,
        '_pinned': pin_meta.get('pinned', 0),
        '_top_pinned': pin_meta.get('top_pinned', 0),
        '_add_date': pin_meta.get('add_date', ''),
        '_properties': [],
    }

    if stock_property_store:
        row['_properties'] = stock_property_store.get_properties(code)

    csv_row = _find_csv_row_for_code(df, code_col, code) if df is not None and code_col else None
    csv_quote = _quote_fields_from_csv_row(csv_row)

    quote_info: Optional[Dict] = None
    has_fresh_live = False
    quote_from_iwencai = False
    if live_quote_map and code in live_quote_map:
        batch = live_quote_map[code]
        quote_info = {
            'name': batch.get('name', code),
            'price': batch.get('price'),
            'change_percent': batch.get('change_percent'),
        }
        has_fresh_live = quote_info.get('price') not in (None, '')

    if not has_fresh_live and iwencai_quote_map and code in iwencai_quote_map:
        snap = iwencai_quote_map[code]
        quote_info = {
            'name': snap.get('name', code),
            'price': snap.get('price'),
            'change_percent': snap.get('change_percent'),
        }
        has_fresh_live = quote_info.get('price') not in (None, '')
        quote_from_iwencai = has_fresh_live

    if not has_fresh_live and prefer_live and live_quote_map is None and REAL_DATA_AVAILABLE and get_quote:
        try:
            live = get_quote(code)
            if live:
                quote_info = {
                    'name': live.get('股票名称', code),
                    'price': live.get('当前价格'),
                    'change_percent': live.get('涨跌幅'),
                }
                has_fresh_live = quote_info.get('price') not in (None, '')
        except Exception as e:
            print(f"⚠ Live quote failed for favorite {code}: {e}")

    if quote_info is None:
        quote_info = {}

    if not has_fresh_live:
        if quote_info.get('price') in (None, '') and csv_quote.get('price') not in (None, ''):
            quote_info['price'] = csv_quote['price']
        if quote_info.get('change_percent') in (None, '') and csv_quote.get('change_percent') not in (None, ''):
            quote_info['change_percent'] = csv_quote['change_percent']

    if not quote_info.get('name'):
        quote_info['name'] = csv_quote.get('name')

    if quote_info.get('price') in (None, '') or (
        quote_info.get('change_percent') in (None, '') and not quote_from_iwencai
    ):
        if live_quote_map is not None:
            cached = _quote_from_stockcomment_cache(code)
            if cached:
                if quote_info.get('price') in (None, ''):
                    quote_info['price'] = cached.get('price')
                if quote_info.get('change_percent') in (None, '') and not quote_from_iwencai:
                    quote_info['change_percent'] = cached.get('change_percent')
                if not quote_info.get('name'):
                    quote_info['name'] = cached.get('name')
        else:
            fallback = _fetch_favorite_quote_info(code)
            if fallback:
                if quote_info.get('price') in (None, ''):
                    quote_info['price'] = fallback.get('price')
                if quote_info.get('change_percent') in (None, ''):
                    quote_info['change_percent'] = fallback.get('change_percent')
                if not quote_info.get('name'):
                    quote_info['name'] = fallback.get('name')

    name = _valid_stock_display_name(quote_info.get('name'), code)
    if not name:
        quote_info['name'] = _resolve_favorite_display_name(code)

    if quote_info:
        _apply_quote_info_to_row(row, code, quote_info)
    else:
        _apply_quote_info_to_row(row, code, {'name': _resolve_favorite_display_name(code)})

    if csv_row is not None:
        extra_cols = [
            '换手率', '成交额(亿)', '流通市值(亿)', '量比', '状态',
            '今开', '昨收', '最高', '最低', '涨停价', '跌停价',
            '成交量', '成交额', '总市值', '振幅', '市净率', '市盈率(动)', '市盈率TTM', '涨跌额',
        ]
        for col in extra_cols:
            if col in csv_row.index and pd.notna(csv_row[col]):
                value = _json_safe(csv_row[col])
                if value is not None:
                    row[col] = value

    _apply_industry_fields_to_row(row, code)

    return {k: _json_safe(v) if not isinstance(v, str) or not v.startswith('<a ') else v for k, v in row.items()}


def _extract_stock_code_from_cell(value) -> str:
    if value is None:
        return ''
    text = str(value)
    if '<' in text:
        match = re.search(r'>(\d{6})<', text)
        if match:
            return match.group(1)
    digits = re.sub(r'\D', '', text)
    return digits.zfill(6)[-6:] if digits else text.zfill(6)


def _apply_quote_info_to_row(record: Dict, code: str, quote_info: Dict) -> None:
    name = _valid_stock_display_name(quote_info.get('name'), code) or _resolve_favorite_display_name(code)
    record['股票名称'] = (
        f'<a href="https://data.eastmoney.com/stockcomment/stock/{code}.html" '
        f'target="_blank" style="color: #2196F3; text-decoration: none;">{name}</a>'
    )
    if quote_info.get('price') not in (None, ''):
        record['当前价格'] = quote_info['price']
    if quote_info.get('change_percent') not in (None, ''):
        record['涨跌幅'] = quote_info['change_percent']


def preprocess_stockcomment_dataframe(df):
    """
    Preprocess stockcomment dataframe before display:
    1. Disable columns: ['SECURITY_INNER_CODE','SECUCODE','TRADE_MARKET_CODE','SECURITY_TYPE_CODE','LISTING_STATE']
    2. Rename SECURITY_CODE as CODE and format as f'{:06d}'
    3. Rename SECURITY_NAME_ABBR as NAME
    """
    import pandas as pd
    
    # Create a copy to avoid modifying original
    processed_df = df.copy()
    
    # 1. Disable specified columns (drop them)
    columns_to_disable = ['SECURITY_INNER_CODE', 'SECUCODE', 'TRADE_MARKET_CODE', 'SECURITY_TYPE_CODE', 'LISTING_STATE','TRADE_DATE']
    for col in columns_to_disable:
        if col in processed_df.columns:
            processed_df = processed_df.drop(columns=[col])
    
    # 2. Rename SECURITY_CODE as CODE and format as 6-digit string
    if 'SECURITY_CODE' in processed_df.columns:
        processed_df = processed_df.rename(columns={'SECURITY_CODE': 'CODE'})
        # Format CODE column as 6-digit string
        processed_df['CODE'] = processed_df['CODE'].astype(str).str.zfill(6)
    
    # 3. Rename SECURITY_NAME_ABBR as NAME
    if 'SECURITY_NAME_ABBR' in processed_df.columns:
        processed_df = processed_df.rename(columns={'SECURITY_NAME_ABBR': 'NAME'})
    
    return processed_df


def format_dataframe(df, add_favorites_button=False):
    """
    Format dataframe for display:
    1. Format stock codes to 6-digit format and make them clickable links
    2. Format stock names to make them clickable links
    3. Format flow numbers (divide by 1E8, round to 2 decimals)
    4. Optionally add favorites button column
    """
    
    # Create a copy to avoid modifying original
    formatted_df = df.copy()
    input_cols = formatted_df.columns.tolist()

    # Remove columns that should not be displayed
    columns_to_remove = ['Tme', '市场类型', 'F206','主力净流入最大股']
    drop_cols = [col for col in columns_to_remove if col in formatted_df.columns]
    if drop_cols:
        formatted_df = formatted_df.drop(columns=drop_cols)

    
    # Find stock code and name columns first
    stock_code_col = None
    stock_name_col = None
    
    for col in formatted_df.columns:
        if '股票代码' in col or col == 'CODE' or col == '代码':
            stock_code_col = col
        if '股票名称' in col or col == 'NAME' or col == '名称':
            stock_name_col = col
    
    # Format stock names first (using original stock codes)
    if stock_name_col and stock_code_col:
        # Create a mapping function that uses the stock code for the URL
        def create_name_link(row):
            stock_code = str(row[stock_code_col]).zfill(6)
            stock_name = row[stock_name_col]
            
            # return f'<a href="http://data.eastmoney.com/zjlx/{stock_code}.html" target="_blank" style="color: #2196F3; text-decoration: none;">{stock_name}</a>'
            return f'<a href="https://data.eastmoney.com/stockcomment/stock/{stock_code}.html" target="_blank" style="color: #2196F3; text-decoration: none;">{stock_name}</a>'
        
        formatted_df[stock_name_col] = formatted_df.apply(create_name_link, axis=1)
    
    # Format stock codes (assuming column names contain '代码' or '股票代码')
    for col in formatted_df.columns:
        if '股票代码' in col or col == 'CODE':
            # Convert to string and pad with zeros to 6 digits, then make clickable
            formatted_df[col] = formatted_df[col].astype(str).str.zfill(6)
            
            # Create different links based on column type
            if col == 'CODE':
                # For CODE column, link to internal analysis page
                def create_analysis_link(code):
                    return f'<a href="/analysis/{code}" style="color: #2196F3; text-decoration: none;">{code}</a>'
                formatted_df[col] = formatted_df[col].apply(create_analysis_link)
            else:
                # For other code columns, link to external quote.eastmoney.com
                # Use sz for codes starting with 0, 2, 3 (Shenzhen) and sh for codes starting with 6 (Shanghai)
                def create_stock_code_link(code):
                    if code.startswith(('0', '2', '3')):
                        exchange = 'sz'
                    elif code.startswith('6'):
                        exchange = 'sh'
                    else:
                        exchange = 'sz'  # Default to sz for other codes
                    return f'<a href="https://quote.eastmoney.com/{exchange}{code}.html" target="_blank" style="color: #2196F3; text-decoration: none;">{code}</a>'
                
                formatted_df[col] = formatted_df[col].apply(create_stock_code_link)
    
    # Format flow numbers (columns that might contain flow data)
    flow_columns = []
    for col in formatted_df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ['flow', 'inflow', 'outflow', '净流入', '流入', '流出', '资金']):
            flow_columns.append(col)
    
    for col in flow_columns:
        try:
            # Convert to numeric, handle errors
            numeric_values = pd.to_numeric(formatted_df[col], errors='coerce')
            # Divide by 1E8 and round to 2 decimals
            formatted_df[col] = (numeric_values / 1e8).round(2)
        except:
            # If conversion fails, keep original values
            pass
    
    # Add favorites button column if requested
    if add_favorites_button and stock_code_col:
        # Create a copy of the original dataframe to get clean stock codes
        original_df = df.copy()
        
        # Get the original stock codes before formatting
        if stock_code_col in original_df.columns:
            # Format original codes to 6-digit strings
            original_codes = original_df[stock_code_col].astype(str).str.zfill(6)
            
            def create_favorite_button(code):
                return f'<button onclick="addToFavoritesQuick(\'{code}\')" style="padding: 4px 10px; background: #f39c12; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px;">⭐ 加自选</button>'
            
            # Insert as the first column using original codes
            formatted_df.insert(0, '操作', original_codes.apply(create_favorite_button))
    
    # Reorder columns to move stock name to the front and stock code to the end (if not adding favorites button)
    if not add_favorites_button:
        ordered_cols = list(formatted_df.columns)

        if stock_name_col and stock_name_col in ordered_cols:
            ordered_cols.remove(stock_name_col)
            ordered_cols.insert(0, stock_name_col)

        if stock_code_col and stock_code_col in ordered_cols:
            ordered_cols.remove(stock_code_col)
            ordered_cols.append(stock_code_col)

        board_col = '板块代码'
        change_col = '今日涨跌幅'
        if board_col in ordered_cols and change_col in ordered_cols:
            idx_board = ordered_cols.index(board_col)
            idx_change = ordered_cols.index(change_col)
            ordered_cols[idx_board], ordered_cols[idx_change] = ordered_cols[idx_change], ordered_cols[idx_board]

        formatted_df = formatted_df[ordered_cols]
    
    return formatted_df


def format_dataframe_bk_flow(df):
    """
    Format dataframe for bk_flow display:
    1. Format stock codes to 6-digit format and make them clickable links
    2. Format stock names to make them clickable links
    3. DO NOT divide flow numbers by 1E8 since bk_flow data is already in 亿元
    """
    import pandas as pd
    import numpy as np
    
    # Create a copy to avoid modifying original
    formatted_df = df.copy()
    input_cols = formatted_df.columns.tolist()
    print(input_cols)
    # Remove columns that should not be displayed
    columns_to_remove = ['Tme', '市场类型', 'F206','主力净流入最大股']
    drop_cols = [col for col in columns_to_remove if col in formatted_df.columns]
    if drop_cols:
        formatted_df = formatted_df.drop(columns=drop_cols)


    # Find stock code and name columns first
    stock_code_col = None
    stock_name_col = None
    
    for col in formatted_df.columns:
        if '股票代码' in col or col == 'CODE' or col == '代码':
            stock_code_col = col
        if '股票名称' in col or col == 'NAME' or col == '名称':
            stock_name_col = col
        if '板块代码' in col:
            # Make sector codes clickable
            def create_sector_code_link(code):
                code_str = str(code).strip()
                return f'<a href="https://data.eastmoney.com/bkzj/{code_str}.html" target="_blank" style="color: #2196F3; text-decoration: none;">{code_str}</a>'
            formatted_df[col] = formatted_df[col].apply(create_sector_code_link)
    
    # Format stock names first (using original stock codes)
    if stock_name_col and stock_code_col:
        # Create a mapping function that uses the stock code for the URL
        def create_name_link(row):
            stock_code = str(row[stock_code_col]).zfill(6)
            stock_name = row[stock_name_col]
            return f'<a href="https://data.eastmoney.com/stockcomment/stock/{stock_code}.html" target="_blank" style="color: #2196F3; text-decoration: none;">{stock_name}</a>'
        
        formatted_df[stock_name_col] = formatted_df.apply(create_name_link, axis=1)
    
    # Format stock codes (assuming column names contain '代码' or '股票代码')
    for col in formatted_df.columns:
        if '股票代码' in col or col == 'CODE':
            # Convert to string and pad with zeros to 6 digits, then make clickable
            formatted_df[col] = formatted_df[col].astype(str).str.zfill(6)
            
            # Create different links based on column type
            if col == 'CODE':
                # For CODE column, link to internal analysis page
                def create_analysis_link(code):
                    return f'<a href="/analysis/{code}" style="color: #2196F3; text-decoration: none;">{code}</a>'
                formatted_df[col] = formatted_df[col].apply(create_analysis_link)
            else:
                # For other code columns, link to external quote.eastmoney.com
                def create_stock_code_link(code):
                    if code.startswith(('0', '2', '3')):
                        exchange = 'sz'
                    elif code.startswith('6'):
                        exchange = 'sh'
                    else:
                        exchange = 'sz'  # Default to sz for other codes
                    return f'<a href="https://quote.eastmoney.com/{exchange}{code}.html" target="_blank" style="color: #2196F3; text-decoration: none;">{code}</a>'
                
                formatted_df[col] = formatted_df[col].apply(create_stock_code_link)
    
    # DO NOT divide flow numbers by 1E8 for bk_flow data
    # Flow amounts are already in 亿元 format
    # Just round to 2 decimals
    flow_columns = []
    for col in formatted_df.columns:
        col_lower = col.lower()
        if any(keyword in col_lower for keyword in ['净流入', '流入', '占比']):
            flow_columns.append(col)
    
    for col in flow_columns:
        try:
            # Convert to numeric and round to 2 decimals
            numeric_values = pd.to_numeric(formatted_df[col], errors='coerce')
            # Round to 2 decimals without dividing
            formatted_df[col] = numeric_values.round(2)
        except:
            # If conversion fails, keep original values
            pass
    
    # Reorder columns to move stock name to the front and stock code to the end
    ordered_cols = list(formatted_df.columns)

    if stock_name_col and stock_name_col in ordered_cols:
        ordered_cols.remove(stock_name_col)
        ordered_cols.insert(0, stock_name_col)

    if stock_code_col and stock_code_col in ordered_cols:
        ordered_cols.remove(stock_code_col)
        ordered_cols.append(stock_code_col)

    board_col = '板块代码'
    change_col = '今日涨跌幅'
    if board_col in ordered_cols and change_col in ordered_cols:
        idx_board = ordered_cols.index(board_col)
        idx_change = ordered_cols.index(change_col)
        ordered_cols[idx_board], ordered_cols[idx_change] = ordered_cols[idx_change], ordered_cols[idx_board]

    formatted_df = formatted_df[ordered_cols]
    
    return formatted_df


@app.route('/')
def index():
    """Main landing page with stock code input"""
    return render_template('index.html')


@app.route('/analysis/<stock_code>')
def analysis(stock_code):
    """Default stock analysis — live quote + four analysis panels."""
    return render_template('instant_analysis.html', stock_code=stock_code)


@app.route('/full-analysis/<stock_code>')
def full_analysis(stock_code):
    """Full tabbed analysis dashboard (opened as popup from default analysis page)."""
    return render_template('dashboard.html', stock_code=stock_code)


@app.route('/instant/<stock_code>')
def instant_analysis(stock_code):
    """Legacy URL — redirect to default analysis page."""
    return redirect(f'/analysis/{stock_code}')


@app.route('/api/stock/<stock_code>/info')
def get_stock_info(stock_code):
    """Get basic stock information"""
    try:
        stock_info = None
        source = 'unknown'
        force_fresh = request.args.get('fresh', '0') in ('1', 'true', 'yes')

        module_info = _quote_from_module1_cache(stock_code)
        quote_info = None
        hotmap_info = None

        if REAL_DATA_AVAILABLE and get_quote:
            try:
                print(f"Fetching real data for stock: {stock_code}")
                quote_data = get_quote(stock_code, force_refetch=force_fresh)
                if quote_data:
                    quote_info = {
                        'code': stock_code,
                        'name': quote_data.get('股票名称', f'股票{stock_code}'),
                        'price': float(quote_data.get('当前价格', 0)),
                        'change': float(quote_data.get('涨跌额', 0)),
                        'change_percent': float(quote_data.get('涨跌幅', 0)),
                        'market_cap': f"{quote_data.get('总市值', 0):.2f}亿",
                        'pe_ratio': float(quote_data.get('市盈率(动)', 0)),
                        'pb_ratio': float(quote_data.get('市净率', 0)),
                        'volume': quote_data.get('成交量', 0),
                        'turnover': quote_data.get('成交额', 0),
                        'high': quote_data.get('最高', 0),
                        'low': quote_data.get('最低', 0),
                        'open': quote_data.get('今开', 0),
                        'turnover_rate': _normalize_turnover_rate(quote_data.get('换手率', 0)),
                        'updated_at': quote_data.get('更新时间') or _header_quote_updated_at(),
                    }
            except Exception as e:
                print(f"⚠ Error fetching quote data: {e}. Trying fallback.")

        try:
            from utils_cap import is_trading_time as _cap_is_trading_time
            is_trading = _cap_is_trading_time()
        except ImportError:
            is_trading = bool(stock_app and stock_app._is_trading_time())

        if quote_info is None and force_fresh and is_trading:
            quote_info = _quote_from_push2delay(stock_code)
            if quote_info:
                print(f"✓ push2delay quote for {stock_code}")

        if quote_info is None:
            hotmap_info = _quote_from_stockhotmap(stock_code, force_fresh=force_fresh)
            if hotmap_info:
                print(f"✓ stockhotmap quote for {stock_code}")

        if quote_info:
            stock_info = quote_info
            source = 'quote'
        elif hotmap_info:
            stock_info = hotmap_info
            source = 'stockhotmap'
        elif module_info:
            stock_info = module_info
            source = 'module1'
        else:
            stock_info = None
            source = 'unknown'

        if stock_info is None:
            return jsonify({
                'success': False,
                'error': '无法获取行情数据',
                'data': {'code': stock_code, 'name': f'股票{stock_code}'}
            }), 502

        # Overlay live quote fields when available (e.g. fresher price during trading)
        if quote_info and stock_info is not quote_info:
            for key in (
                'name', 'price', 'change', 'change_percent',
                'turnover_rate', 'updated_at',
            ):
                if quote_info.get(key) not in (None, ''):
                    stock_info[key] = quote_info[key]
        if stock_info.get('turnover_rate') in (None, ''):
            stock_info['turnover_rate'] = 0.0

        industry_info = _stock_hy_industry_info(stock_code)
        stock_info['industry_chain'] = industry_info.get('industry_chain') or []
        stock_info['industry_text'] = industry_info.get('industry_text') or ''
        stock_info['industry_levels'] = industry_info.get('industry_levels') or []
        stock_info['industry_hy_level'] = industry_info.get('industry_hy_level')
        stock_info['industry_hy_code'] = industry_info.get('industry_hy_code')

        return jsonify({
            'success': True,
            'data': stock_info,
            'source': source,
            'is_trading': is_trading,
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/realtime-flow')
def get_realtime_flow_api(stock_code):
    """Minute-level capital flow — live during trading, cached otherwise."""
    try:
        from utils_cap import (
            get_realtime_flow,
            get_flow_distribution,
            is_trading_time,
            load_realtime_cached_data,
            get_realtime_cache_path,
        )

        code = str(stock_code).zfill(6)
        force = request.args.get('force', '0') in ('1', 'true', 'yes')
        trading = is_trading_time()

        if trading and force:
            df = get_realtime_flow(code, use_cache=False)
            cached = False
        elif trading:
            df = get_realtime_flow(code, use_cache=True)
            cached = load_realtime_cached_data(code) is not None
        else:
            df = load_realtime_cached_data(code, allow_stale=True)
            if df is None or df.empty:
                df = get_realtime_flow(code, use_cache=False)
            cached = load_realtime_cached_data(code) is not None

        distribution = None
        dist_cached = cached or not trading
        try:
            if trading and force:
                distribution = get_flow_distribution(code, use_cache=False)
            elif trading:
                distribution = get_flow_distribution(code, use_cache=True)
            else:
                distribution = get_flow_distribution(code, use_cache=True)
        except Exception as e:
            print(f"⚠ 成交分布获取失败: {e}")

        if df is None or df.empty:
            return jsonify({
                'success': False,
                'error': '暂无实时资金流向数据',
                'is_trading': trading,
                'cached': cached,
            }), 404

        cache_path = get_realtime_cache_path(code)
        updated_at = None
        if os.path.exists(cache_path):
            updated_at = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime('%Y-%m-%d %H:%M:%S')

        series = []
        for _, row in df.iterrows():
            t = row['时间']
            time_str = t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[-5:]
            series.append({
                'time': time_str,
                'main_net': round(float(row['主力净流入']), 4),
                'super_net': round(float(row['超大单净流入']), 4),
                'big_net': round(float(row['大单净流入']), 4),
                'mid_net': round(float(row['中单净流入']), 4),
                'small_net': round(float(row['小单净流入']), 4),
            })

        return jsonify({
            'success': True,
            'stock_code': code,
            'is_trading': trading,
            'cached': cached or not trading,
            'updated_at': updated_at,
            'data': series,
            'distribution': distribution,
            'distribution_cached': dist_cached,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# 东财 suggest：AStock=沪深主板/创业板，23=科创板
_SEARCH_ALLOWED_CLASSIFY = frozenset({None, 'AStock', '23'})


def _local_stock_search(query: str, limit: int = 10) -> list:
    """本地名称/代码/拼音前缀匹配（含科创板）。"""
    try:
        from utils_favorites import get_import_stock_map
    except ImportError:
        from stock.utils_favorites import get_import_stock_map

    q = query.strip()
    if not q:
        return []

    stock_map = get_import_stock_map()
    upper = q.upper()
    hits = []

    # 6 位代码精确匹配
    if re.fullmatch(r'\d{6}', q):
        name = stock_map.get(q)
        if name and not str(name).isdigit():
            return [{'code': q, 'name': name, 'pinyin': ''}]

    seen = set()
    for key, val in stock_map.items():
        if key.isdigit():
            code, name = key, val
        elif val.isdigit():
            code, name = val, key
        else:
            continue
        if len(code) != 6 or code in seen:
            continue
        if not (code.startswith(('00', '30', '60', '68', '92')) and not code.startswith('9')):
            continue
        name = str(name)
        if q in code or q in name or name.startswith(q) or upper in name.upper():
            seen.add(code)
            hits.append({'code': code, 'name': name, 'pinyin': ''})
            if len(hits) >= limit:
                break
    return hits


@app.route('/api/stock/search')
def search_stock():
    """Search A-share stocks by code, name, or pinyin initials."""
    query = request.args.get('q', '').strip()
    try:
        limit = min(max(int(request.args.get('limit', 10)), 1), 20)
    except (TypeError, ValueError):
        limit = 10

    if not query:
        return jsonify({'success': True, 'data': [], 'query': query})

    results = []
    seen_codes = set()

    def _append(item):
        code = item['code']
        if code in seen_codes:
            return
        seen_codes.add(code)
        results.append(item)

    try:
        import requests

        response = requests.get(
            'https://searchadapter.eastmoney.com/api/suggest/get',
            params={
                'input': query,
                'type': '14',
                'token': 'D43BF722C8E33BDC906FB84D85E326E8',
                'count': limit + 5,
            },
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()

        for item in payload.get('QuotationCodeTable', {}).get('Data') or []:
            code = str(item.get('Code', '')).strip()
            if len(code) != 6 or not code.isdigit():
                continue
            if item.get('Classify') not in _SEARCH_ALLOWED_CLASSIFY:
                continue
            _append({
                'code': code,
                'name': item.get('Name', ''),
                'pinyin': item.get('PinYin', ''),
            })
            if len(results) >= limit:
                break

        if len(results) < limit:
            for item in _local_stock_search(query, limit):
                _append(item)
                if len(results) >= limit:
                    break

        return jsonify({'success': True, 'data': results[:limit], 'query': query})
    except Exception as e:
        local = _local_stock_search(query, limit)
        if local:
            return jsonify({'success': True, 'data': local[:limit], 'query': query})
        return jsonify({'success': False, 'error': str(e), 'query': query}), 502


@app.route('/api/stock/<stock_code>/comprehensive')
def get_comprehensive_data(stock_code):
    """Get comprehensive evaluation data"""
    try:
        # Fetch Module 1 data with caching
        module_data = fetch_module_data(stock_code, 1)
        
        # Get cache file path
        cache_file_path = None
        if REAL_DATA_AVAILABLE and stock_app:
            try:
                cache_file = stock_app._get_cache_file(stock_code, "1")
                if cache_file.exists():
                    cache_file_path = str(cache_file)
            except Exception as e:
                print(f"Warning: Could not get cache file path: {e}")
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 1,
            'module_name': 'comprehensive',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'cache_file_path': cache_file_path,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/institutional')
def get_institutional_data(stock_code):
    """Get institutional participation data (Module 2)"""
    try:
        # Fetch Module 2 data with caching
        module_data = fetch_module_data(stock_code, 2)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 2,
            'module_name': 'institutional',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/sentiment')
def get_sentiment_data(stock_code):
    """Get sentiment monitoring data (Module 3)"""
    try:
        # Fetch Module 3 data with caching
        module_data = fetch_module_data(stock_code, 3)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 3,
            'module_name': 'sentiment',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/market-heat')
def get_market_heat_data(stock_code):
    """Get market heat data (Module 4)"""
    try:
        # Fetch Module 4 data with caching
        module_data = fetch_module_data(stock_code, 4)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 4,
            'module_name': 'market-heat',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/capital-flow')
def get_capital_flow_data(stock_code):
    """Get capital flow data (Module 6)"""
    try:
        # Fetch Module 6 data with caching
        module_data = fetch_module_data(stock_code, 6)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 6,
            'module_name': 'capital-flow',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/financial')
def get_financial_data(stock_code):
    """Get financial evaluation data (Module 7)"""
    try:
        # Fetch Module 7 data with caching
        module_data = fetch_module_data(stock_code, 7)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 7,
            'module_name': 'financial',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/trend')
def get_trend_data(stock_code):
    """Get trend analysis data (Module 5)"""
    try:
        # Fetch Module 5 data with caching
        module_data = fetch_module_data(stock_code, 5)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'module': 5,
            'module_name': 'trend',
            'data': module_data,
            'source': 'module_cache' if REAL_DATA_AVAILABLE and 'timestamp' in module_data else 'module_fresh' if REAL_DATA_AVAILABLE else 'mock',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/module/<module_name>/<stock_code>')
def serve_module(module_name, stock_code):
    """Serve individual module pages with stock code parameter"""
    
    # Map module names to numbers
    module_mapping = {
        'comprehensive': 1,
        'institutional': 2,
        'sentiment': 3,
        'market': 4,
        'trend': 5,
        'capital': 6,
        'financial': 7
    }
    
    module_num = module_mapping.get(module_name)
    if not module_num:
        return "Module not found", 404
    
    # Check if generated HTML exists
    generated_file = f"generated/html/{stock_code}_module_{module_num}_{module_name}.html"
    if os.path.exists(generated_file):
        print(f"✓ Serving generated HTML: {generated_file}")
        with open(generated_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    # Fallback to template files
    module_files = {
        'comprehensive': 'comprehensive_evaluation.html',
        'institutional': 'institutional_participation.html',
        'sentiment': 'sentiment_monitoring.html',
        'market': 'market_heat.html',
        'trend': 'trend_analysis.html',
        'capital': 'capital_flow.html',
        'financial': 'financial_evaluation.html'
    }
    
    template_file = module_files.get(module_name)
    if template_file:
        print(f"✓ Serving template: {template_file}")
        
        # Determine market code for Eastmoney charts
        def get_market_code(code):
            if code.startswith('60') or code.startswith('68'):
                return '1.'
            else:  # Shenzhen stocks (00xxxx, 30xxxx, etc.)
                return '0.'
        
        market_code = get_market_code(stock_code)
        embed = request.args.get('embed', '').lower() in ('1', 'true', 'yes')
        return render_template(template_file, stock_code=stock_code, market_code=market_code, embed=embed)
    else:
        return "Module not found", 404


@app.route('/api/generate-flow-chart/<stock_code>', methods=['POST'])
def generate_flow_chart(stock_code):
    """Generate historical capital flow chart for the given stock"""
    try:
        from utils_cap import plot_hist_flow
        from hist_chart_cache import (
            clear_hist_chart_cache,
            find_hist_chart,
            hist_chart_path,
            should_refresh_hist_chart,
            write_hist_chart_marker,
        )
        from quote_cache import effective_quote_date_short
        
        force = request.args.get('force', '').lower() in ('1', 'true', 'yes')
        if request.args.get('clear', '').lower() in ('1', 'true', 'yes'):
            clear_hist_chart_cache(stock_code)
            force = True

        need, reason = should_refresh_hist_chart(stock_code, force=force)
        if not need:
            cached_path = find_hist_chart(stock_code)
            if cached_path and os.path.isfile(cached_path):
                relative_path = os.path.relpath(cached_path, 'generated')
                return jsonify({
                    'success': True,
                    'message': f'Using cached chart for {stock_code} ({reason})',
                    'chart_path': relative_path,
                    'stock_code': stock_code,
                    'cached': True,
                    'cache_reason': reason,
                    'effective_date': effective_quote_date_short(),
                })

        eff = effective_quote_date_short()
        chart_dir = os.path.join('generated', 'cache', 'stockd', 'charts')
        os.makedirs(chart_dir, exist_ok=True)
        save_path = hist_chart_path(stock_code, eff)

        plot_hist_flow(stock_code, save_path=save_path, use_cache=True)

        if os.path.exists(save_path):
            write_hist_chart_marker(stock_code)
            relative_path = os.path.relpath(save_path, 'generated')
            return jsonify({
                'success': True,
                'message': f'Chart generated successfully for {stock_code} ({reason})',
                'chart_path': relative_path,
                'stock_code': stock_code,
                'cached': False,
                'cache_reason': reason,
                'effective_date': eff,
            })
        return jsonify({
            'success': False,
            'error': 'Failed to generate chart',
            'stock_code': stock_code,
        }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error generating chart: {str(e)}',
            'stock_code': stock_code
        }), 500


@app.route('/generated/<path:filename>')
def serve_generated_files(filename):
    """Serve generated files (charts, data files, etc.)"""
    try:
        # Construct the full path
        full_path = os.path.join('generated', filename)
        
        if os.path.exists(full_path):
            # Determine the directory and filename
            directory = os.path.dirname(full_path)
            file_name = os.path.basename(filename)
            
            # Serve the file
            return send_from_directory(directory, file_name)
        else:
            return "File not found", 404
            
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return "Internal server error", 500


@app.route('/api/stock/<stock_code>/fetch-all-modules')
def fetch_all_modules_endpoint(stock_code):
    """Fetch all 8 modules data for a stock (caching handled by StockCommentApp)"""
    try:
        print(f"📦 Fetching all modules for {stock_code}")
        all_data = fetch_all_modules(stock_code)
        
        success_count = sum(1 for data in all_data.values() if "error" not in data)
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'modules_fetched': success_count,
            'total_modules': 7,
            'data': all_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stock/<stock_code>/cache-info')
def get_cache_info_endpoint(stock_code):
    """Get cache information for a stock"""
    try:
        if not stock_app:
            return jsonify({
                'success': False,
                'error': 'Stock app not available'
            })
        
        info = stock_app.get_cache_info(stock_code)
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'cache_info': info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_endpoint():
    """Clear all cache"""
    try:
        if not stock_app:
            return jsonify({
                'success': False,
                'error': 'Stock app not available'
            })
        
        stock_code = request.json.get('stock_code') if request.json else None
        stock_app.clear_cache(stock_code)
        
        return jsonify({
            'success': True,
            'message': f'Cache cleared for {stock_code}' if stock_code else 'All cache cleared'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/stockcomments')
def show_stockcomments():
    """Display latest stockcomment file as a table"""
    import glob
    import pandas as pd
    from pathlib import Path
    
    # Get query parameters
    file_type = request.args.get('type', 'stockcomment')  # 'stockcomment' or 'stockcommentC'
    page = int(request.args.get('page', 1))
    per_page_param = request.args.get('per_page', '50')
    per_page = int(per_page_param) if per_page_param != 'all' else None
    sort_column = request.args.get('sort_column', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    sort_column = request.args.get('sort_column', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    try:
        # Find latest CSV file based on type
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if file_type == 'stockcommentC':
            pattern = os.path.join(parent_dir, "generated/em/*/stockcommentC_*.csv")
        else:
            pattern = os.path.join(parent_dir, "generated/em/*/stockcomment_*.csv")
            
        files = glob.glob(pattern)
        
        if not files:
            return render_template('stockcomments.html', 
                error=f"No {file_type} files found. Please run get_stockcomment() to generate data.",
                table_html=None,
                file_info=None,
                file_type=file_type,
                pagination=None)
        
        # Get the most recent file by modification time
        latest_file = max(files, key=os.path.getmtime)
        
        # Read CSV
        df = pd.read_csv(latest_file)

        # Apply exclude list (bk_exclude.tsv)
        try:
            exclude_path = os.path.join(os.path.dirname(__file__), 'bk_exclude.tsv')
            if os.path.exists(exclude_path):
                exdf = pd.read_csv(exclude_path, sep='\t', comment='#')
                # 标准化列名
                exdf.columns = [c.strip() for c in exdf.columns]
                name_col = '名称' if '名称' in exdf.columns else exdf.columns[0]
                flag_col = '排除显示' if '排除显示' in exdf.columns else exdf.columns[1]
                # 取需要排除的名称集合（排除显示==1）
                to_exclude = set(exdf[exdf[flag_col].astype(str).str.strip() == '1'][name_col].astype(str).str.strip())
                if '板块名称' in df.columns and to_exclude:
                    df = df[~df['板块名称'].astype(str).str.strip().isin(to_exclude)]
        except Exception as _e:
            # 过滤失败不影响后续渲染
            pass
        
        # Preprocess the dataframe for stockcomment files
        df = preprocess_stockcomment_dataframe(df)
        
        # Format the dataframe
        df = format_dataframe(df)
        
        # Apply sorting if specified
        if sort_column:
            # Try to find matching column by name or index
            sort_col = None
            if sort_column in df.columns:
                sort_col = sort_column
            else:
                # Try to find by partial match or common column names
                for col in df.columns:
                    if sort_column.lower() in col.lower() or col.lower() in sort_column.lower():
                        sort_col = col
                        break
            
            if sort_col:
                df = df.sort_values(by=sort_col, ascending=(sort_direction == 'asc'))
                # Update sort_column to the actual column name
                sort_column = sort_col
        
        # Calculate pagination
        total_rows = len(df)
        if per_page is None:  # Show all records
            total_pages = 1
            start_idx = 0
            end_idx = total_rows
            page_df = df
        else:
            total_pages = (total_rows + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_df = df.iloc[start_idx:end_idx]
        
        # Convert to HTML table with escape=False to render HTML links
        table_html = page_df.to_html(classes=['table', 'table-striped', 'table-hover'], 
                                   index=False,
                                   border=0,
                                   table_id='dataTable',
                                   escape=False)
        
        from datetime import datetime
        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)
        
        file_info = {
            'filename': os.path.basename(latest_file),
            'rows': total_rows,
            'timestamp': file_mtime,
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Create pagination info
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'per_page': per_page if per_page is not None else total_rows,
            'total_rows': total_rows,
            'start_row': start_idx + 1,
            'end_row': min(end_idx, total_rows)
        }
        
        return render_template('stockcomments.html', 
                             table_html=table_html,
                             file_info=file_info,
                             file_type=file_type,
                             pagination=pagination,
                             error=None)
    
    except Exception as e:
        return render_template('stockcomments.html',
                             error=str(e),
                             file_type=file_type,
                             data=None)


@app.route('/api/stockcomments/latest')
def get_latest_stockcomments():
    """API endpoint for latest stockcomment data (auto-fetch if batch cache expired)."""
    import pandas as pd

    file_type = request.args.get('type', 'stockcomment')

    try:
        meta = _ensure_stockcomment_data(force=request.args.get('force') == '1')
        latest_file = meta.get('stockcomment_file')
        if not latest_file and file_type == 'stockcommentC':
            files = _glob_stockcomment_files('stockcommentC')
            latest_file = max(files, key=os.path.getmtime) if files else None
        elif not latest_file:
            files = _glob_stockcomment_files(file_type)
            latest_file = max(files, key=os.path.getmtime) if files else None
        if file_type == 'stockcommentC' and latest_file and 'stockcommentC' not in os.path.basename(latest_file):
            files = _glob_stockcomment_files('stockcommentC')
            if files:
                latest_file = max(files, key=os.path.getmtime)

        if not latest_file:
            return jsonify({'success': False, 'error': f'No {file_type} files found'})

        df = pd.read_csv(latest_file)
        return jsonify(_json_raw_file_payload(latest_file, df, {
            'file_type': file_type,
            'cached': meta.get('cached'),
            'stale': meta.get('stale'),
            'cache_fresh': meta.get('cache_fresh'),
            'should_fetch': meta.get('should_fetch'),
            'cache_reason': meta.get('reason'),
            'fetched': meta.get('fetched'),
        }))
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stockcomments/refresh', methods=['POST'])
def refresh_stockcomments():
    """Fetch fresh stockcomment data from East Money and save new CSV files."""
    if not REAL_DATA_AVAILABLE or not get_stockcomment:
        return jsonify({
            'success': False,
            'error': 'Stockcomment utilities not available'
        }), 503

    try:
        result = get_stockcomment(force_refetch=True)
        if not result or not result.get('stockcomment_file'):
            return jsonify({
                'success': False,
                'error': 'Failed to fetch stockcomment data'
            }), 500

        stockcomment_file = result['stockcomment_file']
        file_mtime = os.path.getmtime(stockcomment_file)
        file_datetime = datetime.fromtimestamp(file_mtime)

        return jsonify({
            'success': True,
            'filename': os.path.basename(stockcomment_file),
            'stockcomment_file': stockcomment_file,
            'stockcommentC_file': result.get('stockcommentC_file'),
            'cached': result.get('cached', False),
            'reason': result.get('reason'),
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': file_mtime * 1000
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/stockflows')
def show_stockflows():
    """Display latest zjlx_/flow_ file as a table"""
    import pandas as pd
    from pathlib import Path
    
    # Get query parameters
    file_type = request.args.get('type', 'zjlx')  # 'zjlx' or 'flow'
    page = int(request.args.get('page', 1))
    per_page_param = request.args.get('per_page', '50')
    per_page = int(per_page_param) if per_page_param != 'all' else None
    sort_column = request.args.get('sort_column', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    try:
        _ensure_stockflows_data(
            force=request.args.get('force') in ('1', 'true', 'yes'),
            file_type='zjlx',
        )
        latest_file = _pick_latest_stockflows_file(file_type)
        
        if not latest_file:
            return render_template('stockflows.html', 
                error=f"No {file_type} files found. Please run data generation to create files.",
                table_html=None,
                file_info=None,
                file_type=file_type,
                pagination=None)
        
        # Read CSV
        df = pd.read_csv(latest_file)
        df.rename(columns={'代码': 'CODE'}, inplace=True)

        # Format the dataframe
        df = format_dataframe(df)
        
        # Apply sorting if specified
        if sort_column:
            # Try to find matching column by name or index
            sort_col = None
            if sort_column in df.columns:
                sort_col = sort_column
            else:
                # Try to find by partial match or common column names
                for col in df.columns:
                    if sort_column.lower() in col.lower() or col.lower() in sort_column.lower():
                        sort_col = col
                        break
            
            if sort_col:
                df = df.sort_values(by=sort_col, ascending=(sort_direction == 'asc'))
                # Update sort_column to the actual column name
                sort_column = sort_col
        
        # Calculate pagination
        total_rows = len(df)
        if per_page is None:  # Show all records
            total_pages = 1
            start_idx = 0
            end_idx = total_rows
            page_df = df
        else:
            total_pages = (total_rows + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_df = df.iloc[start_idx:end_idx]
        
        # Convert to HTML table with escape=False to render HTML links
        table_html = page_df.to_html(classes=['table', 'table-striped', 'table-hover'], 
                                   index=False,
                                   border=0,
                                   table_id='dataTable',
                                   escape=False)
        
        from datetime import datetime
        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)
        
        file_info = {
            'filename': os.path.basename(latest_file),
            'rows': total_rows,
            'timestamp': file_mtime,
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Create pagination info
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'per_page': per_page if per_page is not None else total_rows,
            'total_rows': total_rows,
            'start_row': start_idx + 1,
            'end_row': min(end_idx, total_rows)
        }
        
        return render_template('stockflows.html', 
                             table_html=table_html,
                             file_info=file_info,
                             file_type=file_type,
                             pagination=pagination,
                             sort_column=sort_column,
                             sort_direction=sort_direction,
                             error=None)
    
    except Exception as e:
        return render_template('stockflows.html',
                             error=str(e),
                             file_type=file_type,
                             sort_column='',
                             sort_direction='asc',
                             data=None)


@app.route('/api/stockflows/latest')
def get_latest_stockflows():
    """API endpoint for latest stockflows data (auto-fetch if batch cache expired)."""
    import pandas as pd

    file_type = request.args.get('type', 'zjlx')

    try:
        meta = _ensure_stockflows_data(force=request.args.get('force') == '1', file_type=file_type)
        latest_file = _pick_latest_stockflows_file(file_type) or meta.get('zjlx_file')
        if not latest_file:
            files = _glob_zjlx_files(file_type)
            if files:
                latest_file = max(files, key=os.path.getmtime)
        if not latest_file:
            return jsonify({'success': False, 'error': f'No {file_type} files found'})

        df = pd.read_csv(latest_file)
        return jsonify(_json_raw_file_payload(latest_file, df, {
            'file_type': file_type,
            'cached': meta.get('cached'),
            'stale': meta.get('stale'),
            'cache_fresh': meta.get('cache_fresh'),
            'should_fetch': meta.get('should_fetch'),
            'cache_reason': meta.get('reason'),
            'fetched': meta.get('fetched'),
        }))
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stockflows/refresh', methods=['POST'])
def refresh_stockflows():
    """Fetch fresh zjlx/flow data from East Money and save new CSV files."""
    if not REAL_DATA_AVAILABLE or not get_zjlx_zlb_all:
        return jsonify({
            'success': False,
            'error': 'Stockflows utilities not available',
        }), 503

    try:
        meta = _ensure_stockflows_data(force=True, file_type='zjlx')
        latest_file = _pick_latest_stockflows_file('zjlx') or meta.get('zjlx_file')
        if not latest_file or not os.path.exists(latest_file):
            return jsonify({
                'success': False,
                'error': 'Failed to fetch stockflows data',
            }), 500

        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)
        flow_file = _pick_latest_stockflows_file('flow')

        return jsonify({
            'success': True,
            'filename': os.path.basename(latest_file),
            'zjlx_file': latest_file,
            'flow_file': flow_file,
            'cached': meta.get('cached', False),
            'fetched': meta.get('fetched', True),
            'reason': meta.get('reason'),
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': file_mtime * 1000,
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


def _sector_mapping_from_industry_ext(csv_path: str) -> Dict:
    """Build star-map style sector index mapping from industry_ext snapshot."""
    import pandas as pd

    df = pd.read_csv(csv_path)
    ordered_items = []
    seen_names = set()

    for prefer_name in ('银行', '房地产开发'):
        row = df[df['板块名称'] == prefer_name]
        if not row.empty:
            ordered_items.append({
                'name': prefer_name,
                'code': str(row.iloc[0].get('板块代码', '')),
            })
            seen_names.add(prefer_name)

    for _, row in df.iterrows():
        name = str(row.get('板块名称', '')).strip()
        code = str(row.get('板块代码', '')).strip()
        if not name or name in seen_names:
            continue
        ordered_items.append({'name': name, 'code': code})
        seen_names.add(name)

    return {idx: item for idx, item in enumerate(ordered_items)}


def load_sector_mapping():
    """Load the latest bk_ file and create sector mapping with 0-based index.
    
    Rules:
    - Use 0-based sector index to match quote files' "板块序号"
    - Force specific leading order:
      0 -> 银行 (BK0475)
      1 -> 房地产开发 (BK0451)
    - Other sectors follow the order in the latest bk_*.csv
    """
    import glob
    import pandas as pd
    import os
    
    try:
        # Find latest bk_ file (exclude bk_flow_ files)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pattern = os.path.join(parent_dir, "generated/em/*/bk_*.csv")
        all_files = glob.glob(pattern)
        # Filter out bk_flow_ files
        files = [f for f in all_files if not os.path.basename(f).startswith('bk_flow_')]
        
        if not files:
            # Fallback: industry_ext snapshot (star-map bk list unavailable after hours)
            ext_pattern = os.path.join(parent_dir, "generated/em/*/industry_ext_*.csv")
            ext_files = glob.glob(ext_pattern)
            if ext_files:
                return _sector_mapping_from_industry_ext(max(ext_files, key=os.path.getmtime))
            return {}
        
        # Get the most recent file
        latest_file = max(files, key=os.path.getmtime)
        
        # Read CSV
        df = pd.read_csv(latest_file)
        
        # Create ordered list starting with preferred sectors
        ordered_items = []
        seen_codes = set()
        
        # 1. Add 银行 (BK0475) as index 0
        bank_row = df[df['板块名称'] == '银行']
        if not bank_row.empty:
            bank_data = bank_row.iloc[0]
            ordered_items.append({
                'name': bank_data.get('板块名称', ''),
                'code': bank_data.get('板块代码', '')
            })
            seen_codes.add(bank_data.get('板块代码', ''))
        
        # 2. Add 房地产开发 (BK0451) as index 1
        real_estate_row = df[df['板块名称'] == '房地产开发']
        if not real_estate_row.empty:
            real_estate_data = real_estate_row.iloc[0]
            ordered_items.append({
                'name': real_estate_data.get('板块名称', ''),
                'code': real_estate_data.get('板块代码', '')
            })
            seen_codes.add(real_estate_data.get('板块代码', ''))
        
        # 3. Add remaining sectors in original order
        for _, row in df.iterrows():
            code = row.get('板块代码', '')
            name = row.get('板块名称', '')
            
            # Skip if already added
            if code in seen_codes or name in ['银行', '房地产开发']:
                continue
                
            ordered_items.append({
                'name': name,
                'code': code
            })
            seen_codes.add(code)
        
        # Build 0-based mapping
        sector_mapping = {idx: item for idx, item in enumerate(ordered_items)}
        
        return sector_mapping
        
    except Exception as e:
        print(f"Error loading sector mapping: {e}")
        return {}


@app.route('/quotes')
def show_quotes():
    """Display latest quote_ file as a table"""
    import glob
    import pandas as pd
    from pathlib import Path
    import numpy as np
    
    # Get query parameters
    file_type = request.args.get('type', 'quote')  # 'quote' or 'q_report'
    page = int(request.args.get('page', 1))
    per_page_param = request.args.get('per_page', '50')
    per_page = int(per_page_param) if per_page_param != 'all' else None
    sort_column = request.args.get('sort_column', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    # Filter parameters
    sector_filter = request.args.get('sector', '')
    market_cap_percentile_filter = request.args.get('market_cap_percentile', '')
    turnover_rate_filter = request.args.get('turnover_rate', '')
    
    try:
        # Find latest CSV file based on type
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if file_type == 'q_report':
            pattern = os.path.join(parent_dir, "generated/em/*/q_report_*.csv")
        else:
            pattern = os.path.join(parent_dir, "generated/em/*/quote_*.csv")
            
        files = glob.glob(pattern)
        
        if not files:
            return render_template('quotes.html', 
                error=f"No {file_type} files found. Please run data generation to create files.",
                table_html=None,
                file_info=None,
                file_type=file_type,
                pagination=None)
        
        # Get the most recent file by modification time
        latest_file = max(files, key=os.path.getmtime)
        
        # Read CSV
        df = pd.read_csv(latest_file)
        
        # Add market cap percentile column
        if '总市值(亿)' in df.columns:
            # Convert to numeric, handle errors
            df['总市值(亿)'] = pd.to_numeric(df['总市值(亿)'], errors='coerce')
            # Calculate percentile (0-100)
            df['市值分位'] = df['总市值(亿)'].rank(pct=True) * 100
            df['市值分位'] = df['市值分位'].round(1)
        else:
            df['市值分位'] = 0
        
        # Load sector mapping and replace sector index with sector name
        sector_mapping = load_sector_mapping()
        
        if '板块序号' in df.columns and sector_mapping:
            # Replace sector index with sector name
            df['板块名称'] = df['板块序号'].map(lambda x: sector_mapping.get(x, {}).get('name', f'板块{x}'))
            
            # Add sector code column
            df['板块代码'] = df['板块序号'].map(lambda x: sector_mapping.get(x, {}).get('code', ''))
            
            # Reorder columns to put sector name and code after sector index
            cols = list(df.columns)
            sector_index_pos = cols.index('板块序号')
            
            # Remove sector name and code from their current positions if they exist
            if '板块名称' in cols:
                cols.remove('板块名称')
            if '板块代码' in cols:
                cols.remove('板块代码')
            if '市值分位' in cols:
                cols.remove('市值分位')
            
            # Insert sector name, code, and market cap percentile after sector index
            cols.insert(sector_index_pos + 1, '板块名称')
            cols.insert(sector_index_pos + 2, '板块代码')
            cols.insert(sector_index_pos + 3, '市值分位')
            
            df = df[cols]

            # Get unique sectors for filter dropdown (before applying filters)
            unique_sectors = []
            sector_names = set()
            for _, row in df.iterrows():
                sector_idx = row.get('板块序号', 0)
                if sector_idx in sector_mapping:
                    sector_name = sector_mapping[sector_idx].get('name', f'板块{sector_idx}')
                    sector_names.add(sector_name)
            unique_sectors = sorted(list(sector_names))

            # Convert sector name to link and hide sector code column
            if '板块名称' in df.columns and '板块代码' in df.columns:
                def _create_sector_link(row):
                    sector_code = row.get('板块代码', '')
                    sector_name = row.get('板块名称', '')
                    if isinstance(sector_code, str) and sector_code:
                        return f'<a href="https://data.eastmoney.com/bkzj/{sector_code}.html" onclick="openSectorModal(this.href); return false;" style="color: #2196F3; text-decoration: none; cursor: pointer;">{sector_name}</a>'
                    return sector_name
                df['板块名称'] = df.apply(_create_sector_link, axis=1)
                # Drop the sector code column from display
                df = df.drop(columns=['板块代码'])
        else:
            unique_sectors = []
        
        # Apply filters
        if sector_filter:
            # Support multiple sectors separated by comma
            if ',' in sector_filter:
                sectors = sector_filter.split(',')
                # Create a mask for any of the sectors
                mask = pd.Series([False] * len(df), index=df.index)
                for sector in sectors:
                    mask |= df['板块名称'].str.contains(sector.strip(), na=False)
                df = df[mask]
            else:
                df = df[df['板块名称'].str.contains(sector_filter, na=False)]
        
        if market_cap_percentile_filter:
            # Support multiple market cap ranges separated by comma
            if ',' in market_cap_percentile_filter:
                ranges = market_cap_percentile_filter.split(',')
                mask = pd.Series([False] * len(df), index=df.index)
                for range_str in ranges:
                    try:
                        min_percentile, max_percentile = map(float, range_str.strip().split('-'))
                        mask |= ((df['市值分位'] >= min_percentile) & (df['市值分位'] <= max_percentile))
                    except:
                        pass
                df = df[mask]
            else:
                try:
                    min_percentile, max_percentile = map(float, market_cap_percentile_filter.split('-'))
                    df = df[(df['市值分位'] >= min_percentile) & (df['市值分位'] <= max_percentile)]
                except:
                    pass  # Invalid filter format, ignore
        
        if turnover_rate_filter:
            try:
                min_turnover, max_turnover = map(float, turnover_rate_filter.split('-'))
                df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
                df = df[(df['换手率'] >= min_turnover) & (df['换手率'] <= max_turnover)]
            except:
                pass  # Invalid filter format, ignore
        
        # Format the dataframe (with favorites button for quotes page)
        df = format_dataframe(df, add_favorites_button=True)
        
        # Apply sorting if specified
        if sort_column:
            # Try to find matching column by name or index
            sort_col = None
            if sort_column in df.columns:
                sort_col = sort_column
            else:
                # Try to find by partial match or common column names
                for col in df.columns:
                    if sort_column.lower() in col.lower() or col.lower() in sort_column.lower():
                        sort_col = col
                        break
            
            if sort_col:
                df = df.sort_values(by=sort_col, ascending=(sort_direction == 'asc'))
                # Update sort_column to the actual column name
                sort_column = sort_col
        
        # Calculate pagination
        total_rows = len(df)
        if per_page is None:  # Show all records
            total_pages = 1
            start_idx = 0
            end_idx = total_rows
            page_df = df
        else:
            total_pages = (total_rows + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_df = df.iloc[start_idx:end_idx]
        
        # Convert to HTML table with escape=False to render HTML links
        table_html = page_df.to_html(classes=['table', 'table-striped', 'table-hover'], 
                                   index=False,
                                   border=0,
                                   table_id='dataTable',
                                   escape=False)
        
        from datetime import datetime
        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)
        
        file_info = {
            'filename': os.path.basename(latest_file),
            'rows': total_rows,
            'timestamp': file_mtime,
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Create pagination info
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'per_page': per_page if per_page is not None else total_rows,
            'total_rows': total_rows,
            'start_row': start_idx + 1,
            'end_row': min(end_idx, total_rows)
        }
        
        
        return render_template('quotes.html', 
                             table_html=table_html,
                             file_info=file_info,
                             file_type=file_type,
                             pagination=pagination,
                             sort_column=sort_column,
                             sort_direction=sort_direction,
                             unique_sectors=unique_sectors,
                             sector_filter=sector_filter,
                             market_cap_percentile_filter=market_cap_percentile_filter,
                             turnover_rate_filter=turnover_rate_filter,
                             error=None)
    
    except Exception as e:
        return render_template('quotes.html',
                             error=str(e),
                             file_type=file_type,
                             sort_column='',
                             sort_direction='asc',
                             data=None)


@app.route('/pkyd')
def show_pkyd():
    """Display latest pkyd_ file as a table"""
    import glob
    import pandas as pd
    from pathlib import Path
    
    # Get query parameters
    page = int(request.args.get('page', 1))
    per_page_param = request.args.get('per_page', '50')
    per_page = int(per_page_param) if per_page_param != 'all' else None
    sort_column = request.args.get('sort_column', '')
    sort_direction = request.args.get('sort_direction', 'asc')
    
    # Get filter parameters
    filter_type = request.args.get('filter_type', '')
    filter_stock = request.args.get('filter_stock', '').strip().upper()
    
    try:
        import os
        pkyd_meta = _ensure_pkyd_data(force=request.args.get('force') == '1')
        latest_file = pkyd_meta.get('pkyd_file')
        all_files = _glob_pkyd_files() if not latest_file else [latest_file]
        
        if not all_files:
            return render_template('pkyd.html', 
                                 error="No pkyd files found. Please run get_pkyd() to generate data.",
                                 table_html=None,
                                 file_info=None,
                                 pagination=None,
                                 filter_type='',
                                 filter_stock='',
                                 available_types=[],
                                 cache_meta=pkyd_meta)
        
        if not latest_file:
            latest_file = max(all_files, key=os.path.getmtime)
        
        # Read CSV
        df = pd.read_csv(latest_file)
        
        # Get available types for filter dropdown (before filtering)
        available_types = []
        if '异动类型' in df.columns:
            available_types = sorted(df['异动类型'].unique().tolist())
        
        # Store total rows before filtering
        total_rows_before_filter = len(df)
        
        # Apply filters
        if filter_type and '异动类型' in df.columns:
            df = df[df['异动类型'] == filter_type]
        
        if filter_stock and '股票代码' in df.columns:
            # Support partial matching for stock code
            df = df[df['股票代码'].str.contains(filter_stock, case=False, na=False)]
        
        # Format the dataframe
        df = format_dataframe(df)
        
        # Apply sorting if specified
        if sort_column:
            # Try to find matching column by name or index
            sort_col = None
            if sort_column in df.columns:
                sort_col = sort_column
            elif sort_column.isdigit() and 0 <= int(sort_column) < len(df.columns):
                sort_col = df.columns[int(sort_column)]
            
            if sort_col:
                ascending = sort_direction == 'asc'
                df = df.sort_values(by=sort_col, ascending=ascending)
        
        # Apply pagination
        total_rows = len(df)
        if per_page:
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_df = df.iloc[start_idx:end_idx]
        else:
            paginated_df = df
        
        # Convert to HTML table
        table_html = paginated_df.to_html(
            classes='table table-striped table-hover',
            table_id='pkyd-table',
            escape=False,
            index=False
        )
        
        # File information
        file_stat = os.stat(latest_file)
        from datetime import datetime
        file_info = {
            'filename': os.path.basename(latest_file),
            'filepath': latest_file,
            'size': file_stat.st_size,
            'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'update_time': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'total_rows': total_rows,
            'total_rows_before_filter': total_rows_before_filter,
            'start_row': start_idx + 1 if per_page else 1,
            'end_row': min(end_idx, total_rows) if per_page else total_rows,
            'cache_reason': pkyd_meta.get('reason'),
            'cache_cached': pkyd_meta.get('cached'),
            'cache_stale': pkyd_meta.get('stale'),
        }
        
        # Pagination info
        pagination = None
        if per_page and total_rows > per_page:
            total_pages = (total_rows + per_page - 1) // per_page
            pagination = {
                'current_page': page,
                'total_pages': total_pages,
                'per_page': per_page,
                'total_rows': total_rows,
                'start_row': start_idx + 1,
                'end_row': min(end_idx, total_rows)
            }
        
        return render_template('pkyd.html', 
                             table_html=table_html,
                             file_info=file_info,
                             pagination=pagination,
                             sort_column=sort_column,
                             sort_direction=sort_direction,
                             filter_type=filter_type,
                             filter_stock=filter_stock,
                             available_types=available_types,
                             cache_meta=pkyd_meta,
                             error=None)
    
    except Exception as e:
        return render_template('pkyd.html',
                             error=str(e),
                             sort_column='',
                             sort_direction='asc',
                             filter_type='',
                             filter_stock='',
                             available_types=[],
                             data=None)


@app.route('/api/quotes/latest')
def get_latest_quotes():
    """API endpoint for latest quotes data (auto-fetch when quote cache stale)."""
    import glob
    import pandas as pd

    file_type = request.args.get('type', 'quote')

    try:
        meta = _ensure_quotes_data(force=request.args.get('force') == '1', file_type=file_type)
        latest_file = meta.get('quote_file')
        if not latest_file:
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if file_type == 'q_report':
                pattern = os.path.join(parent_dir, "generated/em/*/q_report_*.csv")
            else:
                pattern = os.path.join(parent_dir, "generated/em/*/quote_*.csv")
            files = glob.glob(pattern)
            if files:
                latest_file = max(files, key=os.path.getmtime)
        if not latest_file:
            return jsonify({'success': False, 'error': f'No {file_type} files found'})

        df = pd.read_csv(latest_file)
        return jsonify(_json_raw_file_payload(latest_file, df, {
            'file_type': file_type,
            'cached': meta.get('cached'),
            'stale': meta.get('stale'),
            'cache_fresh': meta.get('cache_fresh'),
            'should_fetch': meta.get('should_fetch'),
            'cache_reason': meta.get('reason'),
            'fetched': meta.get('fetched'),
        }))
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/pkyd/latest')
def get_latest_pkyd():
    """API endpoint for latest pkyd data"""
    import pandas as pd
    from datetime import datetime
    
    try:
        pkyd_meta = _ensure_pkyd_data(force=request.args.get('force') == '1')
        latest_file = pkyd_meta.get('pkyd_file')
        if not latest_file:
            files = _glob_pkyd_files()
            if files:
                latest_file = max(files, key=os.path.getmtime)
        if not latest_file:
            return jsonify({
                'success': False,
                'error': 'No pkyd files found'
            })
        
        df = pd.read_csv(latest_file)
        
        # Get file modification time
        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)
        
        # Convert to JSON (first 100 records)
        data = _enrich_raw_records(df.head(100).to_dict(orient='records'))
        
        return jsonify({
            'success': True,
            'filename': os.path.basename(latest_file),
            'total_records': len(df),
            'timestamp': file_mtime * 1000,  # Convert to milliseconds for JavaScript
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'file_type': 'pkyd',
            'cached': pkyd_meta.get('cached'),
            'stale': pkyd_meta.get('stale'),
            'cache_fresh': pkyd_meta.get('cache_fresh'),
            'should_fetch': pkyd_meta.get('should_fetch'),
            'cache_reason': pkyd_meta.get('reason'),
            'fetched': pkyd_meta.get('fetched'),
            'data': data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/pkyd/refresh', methods=['POST'])
def refresh_pkyd():
    """Fetch fresh pkyd data from East Money and save new CSV file."""
    from datetime import datetime

    if not REAL_DATA_AVAILABLE or not get_pkyd:
        return jsonify({
            'success': False,
            'error': 'Pkyd utilities not available'
        }), 503

    try:
        result = get_pkyd(force_refetch=True)
        if not result or not result.get('pkyd_file'):
            return jsonify({
                'success': False,
                'error': 'Failed to fetch pkyd data'
            }), 500

        pkyd_file = result['pkyd_file']
        file_mtime = os.path.getmtime(pkyd_file)
        file_datetime = datetime.fromtimestamp(file_mtime)

        return jsonify({
            'success': True,
            'filename': os.path.basename(pkyd_file),
            'pkyd_file': pkyd_file,
            'cached': result.get('cached', False),
            'stale': result.get('stale'),
            'reason': result.get('reason'),
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': file_mtime * 1000
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


@app.route('/api/cache/cachelist')
def get_cache_list():
    """Get list of cached data with details"""
    try:
        if not REAL_DATA_AVAILABLE or not stock_app:
            return jsonify({
                'success': False,
                'error': 'Data fetching not available',
                'cache_enabled': False
            })
        
        # Get cache information from StockCommentApp
        cache_info = {}
        
        # Try to get cache directory info
        cache_dir = getattr(stock_app, 'cache_dir', None)
        cache_dir_str = str(cache_dir) if cache_dir else None
        
        if cache_dir and os.path.exists(cache_dir):
            cache_files = []
            for file in os.listdir(cache_dir):
                if file.endswith('.json'):
                    file_path = os.path.join(cache_dir, file)
                    stat = os.stat(file_path)
                    cache_files.append({
                        'filename': file,
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'age_minutes': int((time.time() - stat.st_mtime) / 60)
                    })
            
            cache_info = {
                'cache_directory': cache_dir_str,
                'total_files': len(cache_files),
                'files': cache_files
            }
        else:
            cache_info = {
                'cache_directory': cache_dir_str,
                'total_files': 0,
                'files': []
            }
        
        return jsonify({
            'success': True,
            'cache_enabled': True,
            'cache_info': cache_info,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"⚠ Error getting cache list: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/list')
def list_available_apis():
    """List all available API endpoints"""
    try:
        base_url = request.url_root.rstrip('/')
        
        # Define all available API endpoints
        apis = {
            'stock_apis': {
                'description': 'Stock-specific data endpoints',
                'endpoints': [
                    {
                        'path': '/api/stock/{stock_code}/info',
                        'method': 'GET',
                        'description': 'Get basic stock information',
                        'example': f'{base_url}/api/stock/000088/info'
                    },
                    {
                        'path': '/api/stock/{stock_code}/comprehensive',
                        'method': 'GET',
                        'description': 'Get comprehensive evaluation data (Module 1)',
                        'example': f'{base_url}/api/stock/000088/comprehensive'
                    },
                    {
                        'path': '/api/stock/{stock_code}/institutional',
                        'method': 'GET',
                        'description': 'Get institutional participation data (Module 2)',
                        'example': f'{base_url}/api/stock/000088/institutional'
                    },
                    {
                        'path': '/api/stock/{stock_code}/sentiment',
                        'method': 'GET',
                        'description': 'Get sentiment monitoring data (Module 3)',
                        'example': f'{base_url}/api/stock/000088/sentiment'
                    },
                    {
                        'path': '/api/stock/{stock_code}/market-heat',
                        'method': 'GET',
                        'description': 'Get market heat data (Module 4)',
                        'example': f'{base_url}/api/stock/000088/market-heat'
                    },
                    {
                        'path': '/api/stock/{stock_code}/trend',
                        'method': 'GET',
                        'description': 'Get trend analysis data (Module 5)',
                        'example': f'{base_url}/api/stock/000088/trend'
                    },
                    {
                        'path': '/api/stock/{stock_code}/capital-flow',
                        'method': 'GET',
                        'description': 'Get capital flow data (Module 6)',
                        'example': f'{base_url}/api/stock/000088/capital-flow'
                    },
                    {
                        'path': '/api/stock/{stock_code}/financial',
                        'method': 'GET',
                        'description': 'Get financial evaluation data (Module 7)',
                        'example': f'{base_url}/api/stock/000088/financial'
                    },
                    {
                        'path': '/api/stock/{stock_code}/fetch-all-modules',
                        'method': 'GET',
                        'description': 'Fetch all 8 modules data for a stock',
                        'example': f'{base_url}/api/stock/000088/fetch-all-modules'
                    }
                ]
            },
            'module_apis': {
                'description': 'Module page endpoints',
                'endpoints': [
                    {
                        'path': '/module/{module_name}/{stock_code}',
                        'method': 'GET',
                        'description': 'Serve individual module pages',
                        'modules': ['comprehensive', 'institutional', 'sentiment', 'market', 'trend', 'capital', 'financial'],
                        'example': f'{base_url}/module/trend/000088'
                    }
                ]
            },
            'system_apis': {
                'description': 'System and utility endpoints',
                'endpoints': [
                    {
                        'path': '/api/cache/cachelist',
                        'method': 'GET',
                        'description': 'Get list of cached data with details',
                        'example': f'{base_url}/api/cache/cachelist'
                    },
                    {
                        'path': '/api/list',
                        'method': 'GET',
                        'description': 'List all available API endpoints (this endpoint)',
                        'example': f'{base_url}/api/list'
                    },
                    {
                        'path': '/api/stockcomments/latest',
                        'method': 'GET',
                        'description': 'Get latest stock comments',
                        'example': f'{base_url}/api/stockcomments/latest'
                    },
                    {
                        'path': '/api/stockflows/latest',
                        'method': 'GET',
                        'description': 'Get latest stock flows',
                        'example': f'{base_url}/api/stockflows/latest'
                    }
                ]
            },
            'dashboard_apis': {
                'description': 'Dashboard and ranking endpoints',
                'endpoints': [
                    {
                        'path': '/api/rankings/flow',
                        'method': 'GET',
                        'description': 'Get capital flow rankings',
                        'example': f'{base_url}/api/rankings/flow'
                    },
                    {
                        'path': '/api/rankings/comment',
                        'method': 'GET',
                        'description': 'Get comment activity rankings',
                        'example': f'{base_url}/api/rankings/comment'
                    },
                    {
                        'path': '/',
                        'method': 'GET',
                        'description': 'Main dashboard page',
                        'example': f'{base_url}/'
                    }
                ]
            }
        }
        
        return jsonify({
            'success': True,
            'server_info': {
                'base_url': base_url,
                'total_endpoints': sum(len(category['endpoints']) for category in apis.values()),
                'timestamp': datetime.now().isoformat()
            },
            'apis': apis
        })
        
    except Exception as e:
        print(f"⚠ Error listing APIs: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/bk_flow/latest')
def get_latest_bk_flow():
    """API endpoint for latest bk_flow data (板块资金流向)"""
    import pandas as pd
    from datetime import datetime

    try:
        force = request.args.get('force', '0') in ('1', 'true', 'yes')
        refresh_meta = ensure_bk_flow_fresh(force=force)
        latest_file = refresh_meta.get('latest_file') or find_latest_bk_flow_file()

        if not latest_file:
            return jsonify({
                'success': False,
                'error': 'No bk_flow files found',
                'refresh': refresh_meta,
            })

        df = pd.read_csv(latest_file)

        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)

        if '主力净流入' in df.columns:
            df_sorted = df.sort_values('主力净流入', ascending=False)
            top_sectors = df_sorted.head(20)
        else:
            top_sectors = df.head(20)

        data = top_sectors.to_dict(orient='records')

        return jsonify({
            'success': True,
            'filename': os.path.basename(latest_file),
            'total_records': len(df),
            'timestamp': file_mtime * 1000,
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'file_type': 'bk_flow',
            'data': data,
            'refresh': refresh_meta,
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sector/stocks')
def api_sector_stocks():
    """按板块代码返回板块内个股简表（用于前端悬浮卡片）。

    Query params:
    - code: 板块代码，如 BK0475
    - limit: 返回条数，默认 30
    """
    try:
        from flask import jsonify, request
        import requests

        sector_code = request.args.get('code', '').strip()
        limit = int(request.args.get('limit', 30))

        if not sector_code:
            return jsonify({'success': False, 'error': '缺少参数: code'}), 400

        # Eastmoney API：不使用 callback，直接返回 JSON
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1,
            'pz': limit,
            'po': 1,
            'np': 1,
            'fltt': 2,
            'invt': 2,
            'fid': 'f62',  # 按主力净流入排序
            'fs': f'b:{sector_code}',  # 板块筛选
            # 需要的字段：f12代码,f14名称,f2最新价,f3涨跌幅,f168成交量,f8量比,f4涨幅3日,f20流通市值
            # Note: 暂不使用换手率字段（f168是成交量，非换手率）
            'fields': 'f12,f14,f2,f3,f4,f8,f20,f47,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87'
        }

        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        records = []
        try:
            diff = (data or {}).get('data', {}).get('diff', [])
        except Exception:
            diff = []

        # 字段映射
        field_mapping = {
            'f12': '股票代码',
            'f14': '股票名称',
            'f2': '最新价',
            'f3': '涨跌幅',
            'f4': '3日涨幅',
            'f8': '量比',
            'f20': '流通市值',
            'f47': '成交量',
            'f62': '主力净流入',
            'f184': '主力净流入占比',
            'f66': '超大单净流入',
            'f69': '超大单净流入占比',
            'f72': '大单净流入',
            'f75': '大单净流入占比',
            'f78': '中单净流入',
            'f81': '中单净流入占比',
            'f84': '小单净流入',
            'f87': '小单净流入占比'
        }

        for item in diff:
            mapped = {}
            for k, v in item.items():
                mapped[field_mapping.get(k, k)] = v
            records.append(mapped)

        return jsonify({'success': True, 'data': records})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _extract_rise_probabilities(module_data: Optional[Dict]):
    """从综合评价 Module 1 数据提取 1日/5日上涨概率。"""
    if not module_data or module_data.get('error'):
        return None, None
    inner = module_data.get('data') or {}
    change_rate = inner.get('change_rate_analysis') or {}
    if change_rate.get('error'):
        return None, None
    rows = ((change_rate.get('result') or {}).get('data') or [])
    if not rows:
        return None, None
    row = rows[0]

    def _to_float(value):
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return _to_float(row.get('RISE_1_PROBABILITY')), _to_float(row.get('RISE_5_PROBABILITY'))


def _to_float_value(value):
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_value(value):
    if value is None or value == '':
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_pk_ranking_metrics(module_data: Optional[Dict]) -> Dict:
    """从综合评价 Module 1 提取综合得分与市场/行业排名。"""
    empty = {
        'compre_score': None,
        'market_rank': None,
        'industry_rank': None,
        'rank_percentile': None,
        'industry_name': None,
    }
    if not module_data or module_data.get('error'):
        return empty

    inner = module_data.get('data') or {}
    summary = inner.get('evaluation_summary') or {}
    pk_data = inner.get('pk_ranking_analysis') or {}
    if pk_data.get('error'):
        return empty

    rows = ((pk_data.get('result') or {}).get('data') or [])
    if not rows:
        return empty

    row = rows[0]
    ranking_metrics = summary.get('ranking_metrics') or {}
    compre_score = _to_float_value(row.get('COMPRE_SCORE'))
    if compre_score is None:
        compre_score = _to_float_value(summary.get('overall_score'))
    if compre_score is None:
        compre_score = _to_float_value(ranking_metrics.get('comprehensive_score'))

    return {
        'compre_score': compre_score,
        'market_rank': _to_int_value(row.get('MARKET_RANK')) or _to_int_value(ranking_metrics.get('market_rank')),
        'industry_rank': _to_int_value(row.get('INDUSTRY_RANK')) or _to_int_value(ranking_metrics.get('industry_rank')),
        'rank_percentile': _to_float_value(row.get('STOCK_RANK_RATIO')) or _to_float_value(ranking_metrics.get('rank_percentile')),
        'industry_name': row.get('BOARD_NAME') or ranking_metrics.get('industry'),
    }


def _get_module1_data(stock_code: str, fetch_missing: bool = False) -> Optional[Dict]:
    code = str(stock_code).zfill(6)
    if REAL_DATA_AVAILABLE and stock_app:
        cached = stock_app._get_cached_data(code, '1')
        if cached:
            return cached
        if fetch_missing:
            data = fetch_module_data(code, 1)
            if data and not data.get('error'):
                return data
    return None


_STOCKCOMMENT_METRICS_MAP: Optional[Dict[str, Dict]] = None
_STOCKCOMMENT_METRICS_MTIME: float = 0.0


def _load_stockcomment_metrics_map() -> Dict[str, Dict]:
    """Bulk fallback: TOTALSCORE / RANK from latest stockcomment CSV."""
    global _STOCKCOMMENT_METRICS_MAP, _STOCKCOMMENT_METRICS_MTIME
    try:
        from stock.utils_reem import find_latest_stockcomment_files
        sc_path, scc_path = find_latest_stockcomment_files()
        mtime = os.path.getmtime(sc_path) if sc_path and os.path.exists(sc_path) else 0.0
        if _STOCKCOMMENT_METRICS_MAP is not None and mtime == _STOCKCOMMENT_METRICS_MTIME:
            return _STOCKCOMMENT_METRICS_MAP
    except Exception:
        sc_path, scc_path, mtime = None, None, 0.0
        if _STOCKCOMMENT_METRICS_MAP is not None:
            return _STOCKCOMMENT_METRICS_MAP

    metrics: Dict[str, Dict] = {}
    try:
        if sc_path and os.path.exists(sc_path):
            df = pd.read_csv(sc_path)
            code_col = 'SECURITY_CODE' if 'SECURITY_CODE' in df.columns else '股票代码'
            for _, row in df.iterrows():
                code = str(row.get(code_col, '')).strip().zfill(6)
                if not code.isdigit() or len(code) != 6:
                    continue
                metrics[code] = {
                    'compre_score': _to_float_value(row.get('TOTALSCORE')),
                    'market_rank': _to_int_value(row.get('RANK')),
                    'rank_up': _to_int_value(row.get('RANK_UP')),
                    'name': str(row.get('SECURITY_NAME_ABBR') or row.get('名称') or '').strip(),
                }
        if scc_path and os.path.exists(scc_path):
            df = pd.read_csv(scc_path)
            for _, row in df.iterrows():
                code = str(row.get('股票代码', '')).strip().zfill(6)
                if not code.isdigit() or len(code) != 6:
                    continue
                entry = metrics.setdefault(code, {})
                if entry.get('compre_score') is None:
                    entry['compre_score'] = _to_float_value(row.get('综合得分'))
                rank_text = str(row.get('上升/目前排名') or '').strip()
                if entry.get('market_rank') is None and '/' in rank_text:
                    try:
                        entry['market_rank'] = int(rank_text.split('/')[-1])
                    except (TypeError, ValueError):
                        pass
                if not entry.get('name'):
                    entry['name'] = str(row.get('名称') or '').strip()
    except Exception as e:
        print(f"⚠ stockcomment metrics fallback load failed: {e}")

    _STOCKCOMMENT_METRICS_MAP = metrics
    _STOCKCOMMENT_METRICS_MTIME = mtime
    return metrics


def _apply_stockcomment_fallback(cache_status: Dict, code: str) -> None:
    """Fill missing score/rank from stockcomment when module_1 cache is absent."""
    fb = _load_stockcomment_metrics_map().get(str(code).zfill(6))
    if not fb:
        return
    if cache_status.get('compre_score') is None and fb.get('compre_score') is not None:
        cache_status['compre_score'] = fb['compre_score']
        cache_status['score_source'] = 'stockcomment'
    if cache_status.get('market_rank') is None and fb.get('market_rank') is not None:
        cache_status['market_rank'] = fb['market_rank']
        cache_status['rank_source'] = 'stockcomment'
    if cache_status.get('rank_up') is None and fb.get('rank_up') is not None:
        cache_status['rank_up'] = fb['rank_up']


def _apply_module1_payload(cache_status: Dict, module_data: Optional[Dict]) -> None:
    """Extract rise probability and ranking metrics from module_1 payload."""
    if not module_data or module_data.get('error'):
        return
    rise_1, rise_5 = _extract_rise_probabilities(module_data)
    cache_status['rise_1_probability'] = rise_1
    cache_status['rise_5_probability'] = rise_5
    cache_status['has_rise_data'] = rise_1 is not None
    cache_status.update(_extract_pk_ranking_metrics(module_data))
    if cache_status.get('compre_score') is not None:
        cache_status.setdefault('score_source', 'module1')
    if cache_status.get('market_rank') is not None:
        cache_status.setdefault('rank_source', 'module1')


def _resolve_stock_display_name(
    stock_code: str,
    module_data: Optional[Dict] = None,
    allow_quote_fetch: bool = False,
) -> str:
    code = str(stock_code).zfill(6)
    if module_data:
        inner = module_data.get('data') or {}
        pk_rows = ((inner.get('pk_ranking_analysis') or {}).get('result') or {}).get('data') or []
        if pk_rows and pk_rows[0].get('SECURITY_NAME_ABBR'):
            return str(pk_rows[0]['SECURITY_NAME_ABBR'])
    if stock_property_store:
        entry = stock_property_store.get_entry(code)
        name = entry.get('name')
        if name and not str(name).isdigit():
            return name
    if allow_quote_fetch:
        quote = _fetch_favorite_quote_info(code)
        if quote and quote.get('name'):
            return quote['name']
    return code


def _lookup_name_from_map(code: str, name_map: Dict) -> str:
    code = str(code).zfill(6)
    mapped = name_map.get(code)
    if mapped and not str(mapped).isdigit():
        return str(mapped)
    for name, mapped_code in name_map.items():
        if not name.isdigit() and str(mapped_code).zfill(6) == code:
            return name
    return code


def _stock_nid(code: str) -> str:
    """East Money market prefix + 6-digit code."""
    c = str(code).zfill(6)
    prefix = "1" if c.startswith(('6', '9')) else "0"
    return f"{prefix}.{c}"


def _mini_quote_chart_url(code: str) -> str:
    """East Money RJY mini intraday chart for table embed."""
    rnd = int(time.time() * 1000)
    return (
        "https://webquotepic.eastmoney.com/GetPic.aspx"
        f"?nid={_stock_nid(code)}&imageType=RJY"
        "&token=44c9d251add88e27b65ed86506f6e5da"
        f"&rnd={rnd}"
    )


def _intraday_chart_url(code: str) -> str:
    """East Money full intraday chart for multi-stock card embed."""
    rnd = int(time.time() * 1000)
    return (
        "https://webquotepic.eastmoney.com/GetPic.aspx"
        f"?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da"
        f"&nid={_stock_nid(code)}&timespan={rnd}"
    )


def _kline_daily_chart_url(code: str) -> str:
    """East Money daily K-line (star-map hover style, imageType=KL)."""
    rnd = int(time.time() * 1000)
    return (
        "https://webquoteklinepic.eastmoney.com/GetPic.aspx"
        f"?nid={_stock_nid(code)}&type=&unitWidth=-6&ef=&AT=1"
        f"&imageType=KL&timespan={rnd}"
    )


def _kline_macd_chart_url(code: str) -> str:
    """East Money K-line chart with MACD indicator."""
    rnd = int(time.time() * 1000)
    return (
        "https://webquoteklinepic.eastmoney.com/GetPic.aspx"
        f"?nid={_stock_nid(code)}&type=&unitWidth=-6&ef=&formula=MACD"
        f"&AT=1&imageType=KXL&timespan={rnd}"
    )


@app.route('/api/chart-urls/<code>')
def api_chart_urls(code: str):
    """Mini intraday + daily K-line chart URLs for hover popups."""
    norm = _normalize_raw_stock_code(code)
    if not norm:
        return jsonify({'success': False, 'error': 'invalid code'}), 400
    ts = int(time.time() * 1000)
    return jsonify({
        'success': True,
        'code': norm,
        'mini_quote_url': _mini_quote_chart_url(norm) + f'&_={ts}',
        'intraday_url': _intraday_chart_url(norm),
        'kline_url': _kline_daily_chart_url(norm),
    })


def _load_industry_ext_sector_rates() -> Dict[str, Dict]:
    """板块名称 -> {code, change_rate} from latest industry_ext CSV."""
    import glob
    import pandas as pd

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = glob.glob(os.path.join(parent_dir, "generated/em/*/industry_ext_*.csv"))
    if not files:
        return {}

    df = pd.read_csv(max(files, key=os.path.getmtime))
    rates: Dict[str, Dict] = {}
    for _, row in df.iterrows():
        name = str(row.get('板块名称', '')).strip()
        if not name:
            continue
        try:
            change_rate = float(row.get('涨跌幅', 0))
        except (TypeError, ValueError):
            change_rate = 0.0
        rates[name] = {
            'code': str(row.get('板块代码', '')),
            'change_rate': change_rate,
        }
    return rates


def _parse_em_clist_quote(item: Dict) -> Dict[str, float]:
    """Extract price/change from East Money clist row (fltt=2).

    f2/f3/f4 are standard list fields; f43/f169/f170 are detail fields where
    f169=涨跌额 and f170=涨跌幅 (see East Money quote JS).
    """
    def _opt_float(key: str):
        val = item.get(key)
        if val is None or val == '' or val == '-':
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    price = _opt_float('f2') or _opt_float('f43') or 0.0
    change_rate = _opt_float('f3')
    change = _opt_float('f4')
    if change_rate is None:
        change_rate = _opt_float('f170')
    if change is None:
        change = _opt_float('f169')
    return {
        'price': price,
        'change_rate': change_rate if change_rate is not None else 0.0,
        'change': change if change is not None else 0.0,
    }


def _fetch_em_clist_snapshot(use_live: bool = True) -> Dict[str, Dict]:
    """Batch fetch A-share name/industry/quote from East Money clist."""
    if not use_live:
        result: Dict[str, Dict] = {}
        for code, meta in _load_zjlx_stock_meta_map().items():
            result[code] = {
                'name': meta.get('name', code),
                'industry': meta.get('industry', ''),
                'price': _safe_float(meta.get('price')),
                'change_rate': _safe_float(meta.get('change_rate')),
                'change': _safe_float(meta.get('change')),
            }
        if not result:
            result = _fetch_stockcomment_snapshot()
        return result

    import requests

    fields = 'f12,f14,f100,f2,f3,f4,f43,f169,f170'
    fs = 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048'
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
    result: Dict[str, Dict] = {}
    pn = 1
    total = None

    try:
        session = requests.Session()
        session.trust_env = False
        while pn <= 5:
            params = {
                'pn': pn,
                'pz': 5000,
                'po': 1,
                'np': 1,
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'fltt': 2,
                'invt': 2,
                'fid': 'f12',
                'fs': fs,
                'fields': fields,
            }
            resp = session.get(
                'https://push2.eastmoney.com/api/qt/clist/get',
                params=params,
                headers=headers,
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get('data') or {}
            diff = data.get('diff') or []
            total = data.get('total', total)
            for item in diff:
                code = str(item.get('f12', '')).zfill(6)
                industry = str(item.get('f100', '') or '未分类').strip()
                quote = _parse_em_clist_quote(item)
                result[code] = {
                    'name': str(item.get('f14', code)),
                    'industry': industry,
                    **quote,
                }
            if not diff or (total and len(result) >= total):
                break
            pn += 1
    except Exception as e:
        print(f"⚠ clist snapshot failed, fallback to zjlx/stockcomment: {e}")
        result = {}

    if not result:
        for code, meta in _load_zjlx_stock_meta_map().items():
            result[code] = {
                'name': meta.get('name', code),
                'industry': meta.get('industry', ''),
                'price': _safe_float(meta.get('price')),
                'change_rate': _safe_float(meta.get('change_rate')),
                'change': _safe_float(meta.get('change')),
            }
    if not result:
        result = _fetch_stockcomment_snapshot()

    return result


def _dedupe_zjlx_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate stock codes; keep row with industry and larger |主力净流入|."""
    code_col = '代码' if '代码' in df.columns else '股票代码'
    if code_col not in df.columns:
        return df

    work = df.copy()
    work['_code'] = work[code_col].astype(str).str.zfill(6)
    work = work[work['_code'].str.fullmatch(r'\d{6}')]
    if work.empty or not work['_code'].duplicated().any():
        return work.drop(columns=['_code'], errors='ignore')

    if '主力净流入' in work.columns:
        work['_rank_flow'] = pd.to_numeric(work['主力净流入'], errors='coerce').abs().fillna(0)
    else:
        work['_rank_flow'] = 0.0
    if '所属行业' in work.columns:
        work['_rank_ind'] = work['所属行业'].fillna('').astype(str).str.strip().ne('').astype(int)
    else:
        work['_rank_ind'] = 0

    work = work.sort_values(['_rank_ind', '_rank_flow'], ascending=[False, False])
    work = work.drop_duplicates('_code', keep='first')
    return work.drop(columns=['_code', '_rank_flow', '_rank_ind'], errors='ignore')


def _load_zjlx_stock_meta_map() -> Dict[str, Dict]:
    """Stock code -> {name, industry, price, change_rate} from latest zjlx_zlb CSV cache."""
    import glob

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today = datetime.now().strftime('%y%m%d')

    def _read_zjlx_csv(path: str, result: Dict[str, Dict], only_missing: bool = False) -> None:
        try:
            df = pd.read_csv(path, dtype={'代码': str})
        except (OSError, pd.errors.ParserError, ValueError):
            return
        df = _dedupe_zjlx_dataframe(df)
        code_col = '代码' if '代码' in df.columns else '股票代码'
        if code_col not in df.columns:
            return
        for _, row in df.iterrows():
            code = str(row.get(code_col, '')).zfill(6)
            if not code.isdigit() or len(code) != 6:
                continue
            if only_missing and code in result and result[code].get('industry'):
                continue
            industry = str(row.get('所属行业', '') or '').strip()
            name = str(row.get('名称', '') or row.get('股票名称', '') or '').strip()
            try:
                change_rate = _safe_float(str(row.get('今日涨跌幅', row.get('涨跌幅', 0))).replace('%', '').strip())
            except (TypeError, ValueError):
                change_rate = 0.0
            price = _safe_float(row.get('最新价', 0))
            prev = price / (1 + change_rate / 100) if change_rate != -100 and price else price
            entry = result.setdefault(code, {})
            if name:
                entry['name'] = name
            if industry:
                entry['industry'] = industry
            if price:
                entry['price'] = price
            if change_rate:
                entry['change_rate'] = change_rate
                entry['change'] = round(price - prev, 2) if price else 0.0

    zlb_pattern = os.path.join(parent_dir, 'generated/em/*/zjlx_zlb_*.csv')
    zlb_files = glob.glob(zlb_pattern)
    if not zlb_files:
        zlb_files = []

    result: Dict[str, Dict] = {}
    primary = None
    if zlb_files:
        today_files = [p for p in zlb_files if f'/em/{today}/' in p.replace('\\', '/')]
        primary = max(today_files or zlb_files, key=os.path.getmtime)
        _read_zjlx_csv(primary, result)
        if not today_files:
            print(f"⚠ 今日 zjlx_zlb 尚未更新，使用缓存: {os.path.basename(primary)}")

    # 用 zlp 等补充 zlb 中缺失的代码
    supplement_patterns = [
        os.path.join(parent_dir, 'generated/em/*/zjlx_zlp_*.csv'),
        os.path.join(parent_dir, 'generated/zjlx_*.csv'),
    ]
    for pattern in supplement_patterns:
        extras = glob.glob(pattern)
        if not extras:
            continue
        _read_zjlx_csv(max(extras, key=os.path.getmtime), result, only_missing=True)
    return result


def _load_performers_stock_sector_map() -> Dict[str, str]:
    """Stock code -> 板块名称 from all performers_industry CSV snapshots."""
    import glob

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = glob.glob(os.path.join(parent_dir, 'generated/em/*/performers_industry_*.csv'))
    if not files:
        return {}

    mapping: Dict[str, str] = {}
    for path in sorted(files, key=os.path.getmtime):
        try:
            df = pd.read_csv(path, dtype={'股票代码': str})
        except (OSError, pd.errors.ParserError, ValueError):
            continue
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).zfill(6)
            name = str(row.get('板块名称', '')).strip()
            if code.isdigit() and len(code) == 6 and name:
                mapping[code] = name
    return mapping


def _load_sector_constituent_map() -> Dict[str, str]:
    """Stock code -> sector name from cached industry constituent CSV files."""
    import glob
    import re

    try:
        from stock.sched_performers import get_md_dir
    except ImportError:
        return {}

    store_dir = os.path.join(get_md_dir(), 'sector', 'industry')
    if not os.path.isdir(store_dir):
        return {}

    mapping: Dict[str, str] = {}
    for path in glob.glob(os.path.join(store_dir, '*.csv')):
        basename = os.path.basename(path)
        match = re.match(r'(.+)_(BK\d+)\.csv$', basename)
        if not match:
            continue
        sector_name = match.group(1)
        try:
            df = pd.read_csv(path, dtype={'股票代码': str, 'f12': str})
        except (OSError, pd.errors.ParserError, ValueError):
            continue
        code_col = '股票代码' if '股票代码' in df.columns else 'f12'
        if code_col not in df.columns:
            continue
        for _, row in df.iterrows():
            code = str(row.get(code_col, '')).zfill(6)
            if code.isdigit() and len(code) == 6:
                mapping[code] = sector_name
    return mapping


def _parse_quote_base_payload(payload: Dict) -> Dict:
    """Parse Eastmoney getquotebasedata into bk lists and stock->hy mapping."""

    def _parse_bk(items: list) -> list:
        rows = []
        for line in items or []:
            parts = str(line).split('|')
            if len(parts) < 3:
                continue
            rows.append({'name': parts[0], 'market': parts[1], 'code': parts[2]})
        return rows

    bk1 = _parse_bk(payload.get('bk1'))
    bk2 = _parse_bk(payload.get('bk2'))
    bk3 = _parse_bk(payload.get('bk3'))
    stock_hy: Dict[str, Dict] = {}

    for line in payload.get('baseinfo') or []:
        parts = str(line).split('|')
        if len(parts) < 7:
            continue
        try:
            i1, i2, i3 = int(parts[0]), int(parts[1]), int(parts[2])
        except (TypeError, ValueError):
            continue
        code = str(parts[5]).zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue
        stock_hy[code] = {
            'name': parts[3],
            'bk1': bk1[i1] if 0 <= i1 < len(bk1) else {},
            'bk2': bk2[i2] if 0 <= i2 < len(bk2) else {},
            'bk3': bk3[i3] if 0 <= i3 < len(bk3) else {},
        }

    return {
        'hash': payload.get('hash', ''),
        'bk1': bk1,
        'bk2': bk2,
        'bk3': bk3,
        'stock_hy': stock_hy,
    }


def _fetch_quote_base_data(force: bool = False) -> Dict:
    """Load Eastmoney star-map industry hierarchy (bk1/bk2/bk3 + stock mapping)."""
    import glob
    import json
    import os
    import requests

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(parent_dir, 'generated/em', datetime.now().strftime('%y%m%d'))
    cache_path = os.path.join(cache_dir, 'quote_base.json')

    if not force and os.path.isfile(cache_path):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
            if datetime.now() - mtime < timedelta(hours=6):
                with open(cache_path, 'r', encoding='utf-8') as fh:
                    cached = json.load(fh)
                if cached.get('stock_hy'):
                    return cached
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    headers = {
        'Referer': 'https://quote.eastmoney.com/stockhotmap/',
        'User-Agent': 'Mozilla/5.0',
    }
    cached_hash = ''
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as fh:
                cached_hash = json.load(fh).get('hash', '')
        except (OSError, json.JSONDecodeError, TypeError):
            cached_hash = ''

    try:
        resp = requests.get(
            'https://quote.eastmoney.com/stockhotmap/api/getquotebasedata',
            params={'hash': cached_hash},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get('re'):
            raise ValueError('getquotebasedata re=false')
        parsed = _parse_quote_base_payload(payload)
        if not parsed.get('stock_hy'):
            raise ValueError('empty stock_hy')
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as fh:
            json.dump(parsed, fh, ensure_ascii=False)
        return parsed
    except Exception as exc:
        print(f"⚠ quote base data fetch failed: {exc}")
        for path in sorted(glob.glob(os.path.join(parent_dir, 'generated/em/*/quote_base.json')), reverse=True):
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    cached = json.load(fh)
                if cached.get('stock_hy'):
                    return cached
            except (OSError, json.JSONDecodeError, TypeError):
                continue
        return {'bk1': [], 'bk2': [], 'bk3': [], 'stock_hy': {}}


def _hy_filter_options(quote_base: Dict, hy_level: int) -> list:
    labels = {
        1: '所有东财一级行业',
        2: '所有东财二级行业',
        3: '所有东财三级行业',
    }
    bk_list = quote_base.get(f'bk{hy_level}') or []
    options = [{'code': 'all', 'name': labels.get(hy_level, '全部板块')}]
    options.extend({'code': item['code'], 'name': item['name']} for item in bk_list if item.get('code'))
    return options


def _resolve_bk_sector_name(
    code: str,
    meta: Dict,
    constituent_map: Dict[str, str],
    performers_map: Dict[str, str],
    board_map: Dict[str, str],
) -> str:
    """Prefer Eastmoney bk sector over clist/Shenwan industry labels."""
    return (
        constituent_map.get(code)
        or performers_map.get(code)
        or board_map.get(code)
        or meta.get('industry')
        or ''
    )


def _lookup_bk_sector_meta(sector_name: str, sector_mapping: Dict, industry_rates: Dict[str, Dict]) -> Dict:
    """Resolve sector index/code/rate from bk mapping and industry_ext snapshot."""
    for idx, info in sector_mapping.items():
        if info.get('name') == sector_name:
            ext = industry_rates.get(sector_name, {})
            return {
                'sector_index': idx,
                'sector_code': info.get('code', '') or ext.get('code', ''),
                'change_rate': ext.get('change_rate', 0),
            }
    ext = industry_rates.get(sector_name, {})
    return {
        'sector_index': None,
        'sector_code': ext.get('code', ''),
        'change_rate': ext.get('change_rate', 0),
    }


def _fetch_history_code_sector_map(use_live: bool = True) -> Dict[str, int]:
    """Map stock code -> star-map sector index from latest history snapshot."""
    if not use_live:
        return {}

    import requests

    headers = {
        'Referer': 'https://quote.eastmoney.com/stockhotmap/',
        'User-Agent': 'Mozilla/5.0',
    }
    candidates = []
    today = datetime.now()
    for day_offset in (0, 1, 2):
        day = today - timedelta(days=day_offset)
        date_str = day.strftime('%Y-%m-%d')
        for time_str in ('1500', '1100', '0930'):
            candidates.append((date_str, time_str))

    for date_str, time_str in candidates:
        try:
            url = f'https://quote.eastmoney.com/stockhotmap/api/getquotedata_history/{date_str}/{time_str}'
            resp = requests.get(url, params={'period': 1000}, headers=headers, timeout=20)
            resp.raise_for_status()
            stocks = resp.json().get('result', {}).get('data', {}).get('data') or []
            mapping: Dict[str, int] = {}
            for line in stocks:
                if 'U2FsdGVk' in line:
                    continue
                parts = line.split('|')
                if len(parts) > 1 and parts[1].isdigit() and len(parts[1]) == 6:
                    mapping[parts[1].zfill(6)] = int(parts[0])
            if len(set(mapping.values())) > 50:
                return mapping
        except Exception as exc:
            print(f"⚠ history sector map {date_str}/{time_str} failed: {exc}")
            continue

    return {}


def _load_module1_board_map() -> Dict[str, str]:
    """Load stock -> BOARD_NAME from module_1 cache when available."""
    import glob
    import json

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(parent_dir, 'generated/cache/stockd/*/module_1.json')
    board_map: Dict[str, str] = {}

    def _extract_board(payload: Dict, code: str) -> str:
        target = code.zfill(6)

        def walk(node):
            if isinstance(node, dict):
                sec = str(node.get('SECURITY_CODE', node.get('stock_code', ''))).zfill(6)
                board = str(node.get('BOARD_NAME', '') or '').strip()
                if board and (not sec or sec == target):
                    return board
                for value in node.values():
                    found = walk(value)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = walk(item)
                    if found:
                        return found
            return ''

        return walk(payload)

    for path in glob.glob(pattern):
        code = os.path.basename(os.path.dirname(path))
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                payload = json.load(fh)
            board = _extract_board(payload, code)
            if board:
                board_map[code.zfill(6)] = board
        except (OSError, json.JSONDecodeError, TypeError):
            continue

    return board_map


def _safe_float(value, default: float = 0.0) -> float:
    """Convert to float; map NaN/Inf and bad values to default."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(num) or np.isinf(num):
        return default
    return num


def _sanitize_json_numbers(obj):
    """Recursively replace NaN/Inf floats so jsonify emits valid JSON."""
    if isinstance(obj, dict):
        return {key: _sanitize_json_numbers(val) for key, val in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_numbers(val) for val in obj]
    if isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return 0.0
        return obj
    return obj


def _sanitize_quote_fields(row: Dict, meta: Dict) -> None:
    """Prefer reliable quote/name fields; clamp obvious parser glitches."""
    row['price'] = _safe_float(row.get('price'))
    row['change'] = _safe_float(row.get('change'))
    row['change_rate'] = _safe_float(row.get('change_rate'))
    row['turnover_rate'] = _safe_float(row.get('turnover_rate'))
    row['volume_billion'] = _safe_float(row.get('volume_billion'))

    if meta.get('name') and not str(meta.get('name')).isdigit():
        row['name'] = meta['name']

    parsed_price = _safe_float(row.get('price'))
    meta_price = _safe_float(meta.get('price')) if meta.get('price') else 0.0
    if meta_price and parsed_price:
        if abs(meta_price - parsed_price) / max(parsed_price, 0.01) <= 0.12:
            row['price'] = meta_price
    elif meta_price and not parsed_price:
        row['price'] = meta_price

    parsed_rate = _safe_float(row.get('change_rate'))
    if meta.get('change_rate') is not None:
        meta_rate = _safe_float(meta['change_rate'])
        if abs(meta_rate) <= 30 and (not parsed_rate or abs(meta_rate - parsed_rate) <= 3.0):
            row['change_rate'] = meta_rate
    if meta.get('change') is not None and abs(_safe_float(meta['change'])) <= max(50, row['price'] * 0.35):
        row['change'] = _safe_float(meta['change'])
    elif row['price'] and row['change_rate'] is not None:
        row['change'] = round(row['price'] * row['change_rate'] / 100.0, 2)
    if abs(row['change_rate']) > 30 and not meta.get('change_rate'):
        if row['price'] and row.get('change'):
            row['change_rate'] = round(row['change'] / row['price'] * 100.0, 2)
        else:
            row['change_rate'] = 0.0
    row['change'] = _safe_float(row.get('change'))
    row['change_rate'] = _safe_float(row.get('change_rate'))
    row['price'] = _safe_float(row.get('price'))
    if row['price'] and row['change_rate'] is not None:
        expected_change = round(row['price'] * row['change_rate'] / 100.0, 2)
        if row['change'] is None or row['change'] * row['change_rate'] < 0:
            row['change'] = expected_change
    elif row['price'] and row['change'] is not None and abs(row['change_rate'] or 0) < 0.001:
        row['change_rate'] = round(row['change'] / row['price'] * 100.0, 2)


def _fetch_stockcomment_snapshot() -> Dict[str, Dict]:
    """Fallback quote/name lookup from latest stockcomment compact CSV."""
    import pandas as pd

    try:
        from stock.utils_reem import find_latest_stockcomment_files
        _, compact_file = find_latest_stockcomment_files()
        if not compact_file or not os.path.exists(compact_file):
            return {}

        df = pd.read_csv(compact_file, dtype={'股票代码': str})
        result: Dict[str, Dict] = {}
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).zfill(6)
            if not code.isdigit():
                continue
            try:
                change_rate = _safe_float(str(row.get('涨跌幅', 0)).replace('%', '').strip())
            except (TypeError, ValueError):
                change_rate = 0.0
            price = _safe_float(row.get('最新价', 0))
            prev = price / (1 + change_rate / 100) if change_rate != -100 and price else price
            result[code] = {
                'name': str(row.get('名称', code)),
                'industry': '',
                'price': price,
                'change_rate': change_rate,
                'change': round(price - prev, 2) if price else 0.0,
            }
        return result
    except Exception as e:
        print(f"⚠ stockcomment snapshot failed: {e}")
        return {}


def _normalize_industry_name(name: str) -> str:
    return name.replace('Ⅱ', '').replace('Ⅲ', '').replace(' ', '').strip()


def _match_industry_sector(industry: str, sector_rates: Dict[str, Dict]) -> str:
    """Match clist industry label to industry_ext sector name."""
    if not industry:
        return '未分类'
    if industry in sector_rates:
        return industry
    norm = _normalize_industry_name(industry)
    for name in sector_rates:
        if _normalize_industry_name(name) == norm:
            return name
        if norm and (norm in name or name in norm):
            return name
    return industry


def _starmap_sectors_usable(stocks: list) -> bool:
    from collections import Counter

    idx_counts = Counter()
    for stock in stocks:
        try:
            idx_counts[int(stock.get('板块序号', -999))] += 1
        except (TypeError, ValueError):
            continue
    if len(idx_counts) < 20:
        return False
    top_two = sum(count for _, count in idx_counts.most_common(2))
    return top_two < len(stocks) * 0.5


def _default_sector_pick_group_name() -> str:
    now = datetime.now()
    return f"{now.year}年{now.month}月{now.day}日板块选股"


def _sector_mapping_from_starmap(sector_data: list) -> Dict:
    """Build 0-based sector index mapping from star-map bk list (when bk CSV missing)."""
    if not sector_data:
        return {}

    ordered_items = []
    seen_codes = set()

    for item in sector_data:
        code = item.get('板块代码', '')
        name = item.get('板块名称', '')
        if code and code not in seen_codes:
            ordered_items.append({'name': name, 'code': code})
            seen_codes.add(code)

    # Match load_sector_mapping: 银行 / 房地产开发 first
    reordered = []
    for prefer_name in ('银行', '房地产开发'):
        for i, item in enumerate(ordered_items):
            if item['name'] == prefer_name:
                reordered.append(ordered_items.pop(i))
                break

    reordered.extend(ordered_items)
    return {idx: item for idx, item in enumerate(reordered)}


def _resolve_sector_mapping(quote_result: Dict) -> Dict:
    """Prefer bk CSV mapping; fall back to live star-map sector list or stock indices."""
    mapping = load_sector_mapping()
    if mapping:
        return mapping

    mapping = _sector_mapping_from_starmap(quote_result.get('sector_data') or [])
    if mapping:
        return mapping

    indices = set()
    for stock in quote_result.get('stock_data') or []:
        try:
            indices.add(int(stock.get('板块序号', -1)))
        except (TypeError, ValueError):
            continue

    defaults = {
        0: {'name': '银行', 'code': 'BK0475'},
        1: {'name': '房地产开发', 'code': 'BK0451'},
    }
    fallback = {}
    for idx in sorted(indices):
        fallback[idx] = defaults.get(idx, {'name': f'板块{idx}', 'code': ''})
    return fallback


def _is_starmap_trading_session() -> bool:
    try:
        from utils_cap import is_trading_time
        return bool(is_trading_time())
    except ImportError:
        try:
            from quote_cache import _is_trading_time
            return bool(_is_trading_time())
        except ImportError:
            return False


def _get_starmap_quote_payload(force_refresh: bool = False) -> Dict:
    """Star-map quotes: live during trading; last close CSV cache otherwise."""
    if not REAL_DATA_AVAILABLE or not getRealtimeQuote:
        raise RuntimeError('星图实时数据不可用')

    from quote_cache import get_cached_realtime_quote

    trading = _is_starmap_trading_session()

    if not trading:
        cached = get_cached_realtime_quote()
        if cached:
            out = dict(cached)
            out['cached'] = True
            out['quote_mode'] = 'close_cache'
            return out
        result = getRealtimeQuote(force=False)
        result['quote_mode'] = 'close_cache'
        return result

    if force_refresh:
        result = getRealtimeQuote(force=True)
        result['quote_mode'] = 'live'
        return result

    try:
        from quote_cache import should_refresh_quote
        need, _reason = should_refresh_quote(force=False)
    except ImportError:
        need = False

    if not need:
        cached = get_cached_realtime_quote()
        if cached:
            out = dict(cached)
            out['cached'] = True
            out['quote_mode'] = 'cache'
            return out

    result = getRealtimeQuote(force=False)
    result['quote_mode'] = 'live' if trading else 'close_cache'
    return result


def _build_starmap_sector_groups(
    hy_level: int = 2,
    hy_code: str = 'all',
    force_refresh: bool = False,
) -> Dict:
    """Group star-map realtime quotes by sector; enrich quotes/names from clist."""
    if not REAL_DATA_AVAILABLE or not getRealtimeQuote:
        raise RuntimeError('星图实时数据不可用')

    hy_level = max(1, min(3, int(hy_level or 2)))
    hy_code = (hy_code or 'all').strip() or 'all'

    trading = _is_starmap_trading_session()
    use_live_enrichment = trading and force_refresh

    quote_result = _get_starmap_quote_payload(force_refresh=force_refresh and trading)
    raw_stocks = quote_result.get('stock_data') or []
    quote_base = _fetch_quote_base_data(force=use_live_enrichment)
    use_hy_grouping = bool(quote_base.get('stock_hy'))
    clist = _fetch_em_clist_snapshot(use_live=use_live_enrichment)
    zjlx_meta = _load_zjlx_stock_meta_map()
    board_map = _load_module1_board_map()
    performers_map = _load_performers_stock_sector_map()
    constituent_map = _load_sector_constituent_map()
    history_sector = _fetch_history_code_sector_map(use_live=use_live_enrichment)
    industry_rates = _load_industry_ext_sector_rates()
    sector_mapping = _resolve_sector_mapping(quote_result)
    use_starmap_idx = _starmap_sectors_usable(raw_stocks) and not use_hy_grouping
    use_history_idx = len(set(history_sector.values())) > 50 and not use_hy_grouping
    sector_rates_by_code: Dict[str, Dict] = {}
    for item in quote_result.get('sector_data') or []:
        code = item.get('板块代码', '')
        if code:
            sector_rates_by_code[code] = item

    groups: Dict[int, Dict] = {}
    industry_groups: Dict[str, Dict] = {}
    next_idx = 10000
    seen_codes: set = set()

    for stock in raw_stocks:
        code = str(stock.get('股票代码', '')).zfill(6)
        if not code.isdigit() or len(code) != 6:
            continue
        if code in seen_codes:
            continue
        seen_codes.add(code)

        meta = dict(zjlx_meta.get(code, {}))
        meta.update(clist.get(code, {}))
        row = {
            'code': code,
            'name': meta.get('name') or stock.get('股票名称') or code,
            'price': _safe_float(stock.get('当前价', 0)),
            'change': _safe_float(stock.get('涨跌额', 0)),
            'change_rate': _safe_float(stock.get('涨跌幅', 0)),
            'turnover_rate': _safe_float(stock.get('换手率', 0)),
            'volume_billion': _safe_float(stock.get('成交额(亿)', 0)),
            'mini_quote_url': _mini_quote_chart_url(code),
            'intraday_url': _intraday_chart_url(code),
            'kline_url': _kline_daily_chart_url(code),
            'macd_url': _kline_macd_chart_url(code),
        }
        _sanitize_quote_fields(row, meta)

        if use_hy_grouping:
            hy_info = quote_base['stock_hy'].get(code)
            if not hy_info:
                continue
            bk = hy_info.get(f'bk{hy_level}') or {}
            if hy_code != 'all' and bk.get('code') != hy_code:
                continue
            if not meta.get('name') or str(meta.get('name')).isdigit():
                row['name'] = hy_info.get('name') or row['name']

            sector_name = bk.get('name') or '未分类'
            sector_code = bk.get('code') or ''
            if sector_name not in industry_groups:
                sector_meta = _lookup_bk_sector_meta(sector_name, sector_mapping, industry_rates)
                sector_index = sector_meta['sector_index']
                if sector_index is None:
                    sector_index = next_idx
                    next_idx += 1
                industry_groups[sector_name] = {
                    'sector_index': sector_index,
                    'sector_name': sector_name,
                    'sector_code': sector_code or sector_meta['sector_code'],
                    'change_rate': sector_meta['change_rate'],
                    'stocks': [],
                }
            industry_groups[sector_name]['stocks'].append(row)
        elif use_starmap_idx or use_history_idx:
            try:
                if use_history_idx and code in history_sector:
                    idx = history_sector[code]
                else:
                    idx = int(stock.get('板块序号', -1))
            except (TypeError, ValueError):
                continue
            if idx not in sector_mapping:
                sector_mapping.setdefault(idx, {'name': f'板块{idx}', 'code': ''})
            sector_info = sector_mapping[idx]
            if idx not in groups:
                bk = sector_rates_by_code.get(sector_info['code'], {})
                groups[idx] = {
                    'sector_index': idx,
                    'sector_name': sector_info['name'],
                    'sector_code': sector_info['code'],
                    'change_rate': bk.get('涨跌幅', 0),
                    'stocks': [],
                }
            groups[idx]['stocks'].append(row)
        else:
            industry = _resolve_bk_sector_name(
                code, meta, constituent_map, performers_map, board_map,
            )
            if not industry:
                industry = '未分类'
            industry = _match_industry_sector(industry, industry_rates)
            if industry not in industry_groups:
                sector_meta = _lookup_bk_sector_meta(industry, sector_mapping, industry_rates)
                sector_index = sector_meta['sector_index']
                if sector_index is None:
                    sector_index = next_idx
                    next_idx += 1
                industry_groups[industry] = {
                    'sector_index': sector_index,
                    'sector_name': industry,
                    'sector_code': sector_meta['sector_code'],
                    'change_rate': sector_meta['change_rate'],
                    'stocks': [],
                }
            industry_groups[industry]['stocks'].append(row)

    use_bk_sector_grouping = use_hy_grouping or not (use_starmap_idx or use_history_idx)
    bucket = groups if (use_starmap_idx or use_history_idx) else industry_groups
    sectors = []
    for group in bucket.values():
        if not group['stocks']:
            continue
        rates = [_safe_float(s['change_rate']) for s in group['stocks']]
        rates = [r for r in rates if r is not None]
        if rates:
            group['change_rate'] = sum(rates) / len(rates)
        else:
            group['change_rate'] = _safe_float(group.get('change_rate')) or 0.0
        group['stocks'].sort(key=lambda x: _safe_float(x.get('change_rate')), reverse=True)
        sectors.append(group)

    sectors.sort(key=lambda x: _safe_float(x.get('change_rate')), reverse=True)

    return _sanitize_json_numbers({
        'update_time': quote_result.get('update_time'),
        'default_group_name': _default_sector_pick_group_name(),
        'sectors': sectors,
        'total_stocks': sum(len(s['stocks']) for s in sectors),
        'sector_count': len(sectors),
        'group_mode': 'starmap' if (use_starmap_idx or use_history_idx or use_bk_sector_grouping) else 'industry',
        'hy_level': hy_level,
        'hy_code': hy_code,
        'hy_options': _hy_filter_options(quote_base, hy_level) if use_hy_grouping else [],
        'is_trading': trading,
        'quote_mode': quote_result.get('quote_mode', 'cache'),
        'quote_cached': bool(quote_result.get('cached')),
        'quote_file': quote_result.get('quote_file'),
    })


def _get_module1_cache_status(code: str) -> Dict:
    """Inspect module_1 cache file without fetching."""
    code = str(code).zfill(6)
    result = {
        'status': 'missing',
        'cached': False,
        'valid': False,
        'cached_at': None,
        'expires_at': None,
        'has_rise_data': False,
        'rise_1_probability': None,
        'rise_5_probability': None,
        'compre_score': None,
        'market_rank': None,
        'industry_rank': None,
        'rank_percentile': None,
        'industry_name': None,
    }
    if not REAL_DATA_AVAILABLE or not stock_app or not stock_app.cache_enabled:
        return result

    cache_file = stock_app._get_cache_file(code, '1')
    if not cache_file.exists():
        return result

    result['cached'] = True
    file_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    result['cached_at'] = file_mtime.isoformat()
    result['expires_at'] = cache_expires_at(file_mtime).isoformat()

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        result['status'] = 'error'
        return result

    _apply_module1_payload(result, data)

    if stock_app._is_stale_module_cache('1', data):
        result['status'] = 'stale'
        return result

    if is_cache_expired(file_mtime):
        result['status'] = 'expired'
        return result

    result['valid'] = True
    result['status'] = 'valid'
    return result


def _build_dive_in_stock_rows(entries, fetch_missing: bool = False) -> Dict:
    """Build Dive In stock rows with module_1 cache / probability info."""
    name_map = {}
    try:
        name_map = get_import_stock_map()
    except Exception:
        pass

    rows = []
    stats = {
        'total': 0,
        'valid': 0,
        'expired': 0,
        'missing': 0,
        'stale': 0,
        'error': 0,
        'with_rise_data': 0,
        'with_score_data': 0,
        'with_rank_data': 0,
    }
    latest_cached_at = None
    sc_metrics = _load_stockcomment_metrics_map()

    for entry in entries:
        code = entry['code']
        cache_status = _get_module1_cache_status(code)

        module_data = None
        if fetch_missing and not cache_status['valid']:
            module_data = _get_module1_data(code, fetch_missing=True)
            if module_data:
                _apply_module1_payload(cache_status, module_data)
                cache_status['valid'] = True
                cache_status['status'] = 'valid'
                cache_status['cached'] = True

        _apply_stockcomment_fallback(cache_status, code)

        rise_1 = cache_status.get('rise_1_probability')
        rise_5 = cache_status.get('rise_5_probability')

        status = cache_status['status']
        stats['total'] += 1
        if status in stats:
            stats[status] += 1
        if cache_status.get('has_rise_data'):
            stats['with_rise_data'] += 1
        if cache_status.get('compre_score') is not None:
            stats['with_score_data'] += 1
        if cache_status.get('market_rank') is not None:
            stats['with_rank_data'] += 1

        cached_at = cache_status.get('cached_at')
        if cached_at:
            if not latest_cached_at or cached_at > latest_cached_at:
                latest_cached_at = cached_at

        display_name = _lookup_name_from_map(code, name_map)
        if module_data:
            resolved = _resolve_stock_display_name(code, module_data)
            if resolved != code:
                display_name = resolved
        sc_name = (sc_metrics.get(str(code).zfill(6)) or {}).get('name')
        if sc_name:
            display_name = sc_name
        properties = []
        if stock_property_store:
            properties = stock_property_store.get_properties(code)
            entry_name = stock_property_store.get_entry(code).get('name')
            if entry_name and not str(entry_name).isdigit():
                display_name = entry_name

        rows.append({
            'code': code,
            'name': display_name,
            'groups': entry.get('groups', []),
            'properties': properties,
            'cache_status': status,
            'cached': cache_status.get('cached', False),
            'valid': cache_status.get('valid', False),
            'cached_at': cached_at,
            'expires_at': cache_status.get('expires_at'),
            'has_rise_data': cache_status.get('has_rise_data', False),
            'rise_1_probability': rise_1,
            'rise_5_probability': rise_5,
            'compre_score': cache_status.get('compre_score'),
            'market_rank': cache_status.get('market_rank'),
            'industry_rank': cache_status.get('industry_rank'),
            'rank_percentile': cache_status.get('rank_percentile'),
            'industry_name': cache_status.get('industry_name'),
            'score_source': cache_status.get('score_source'),
            'rank_source': cache_status.get('rank_source'),
        })

    groups_count = len(favorites_mgr.get_all_groups()) if favorites_mgr else 0
    return {
        'stocks': rows,
        'stats': {
            **stats,
            'groups_count': groups_count,
            'is_trading_time': is_trading_calendar_day(),
            'cache_policy': cache_policy_summary(),
            'latest_cached_at': latest_cached_at,
            'data_source': '综合评价 · Module 1',
        },
    }


@app.route('/favorites')
def show_favorites():
    """显示动态选股页面"""
    return render_template('favorites.html')


@app.route('/dive-in/rise-probability')
def show_dive_in_rise_probability():
    """Dive In By 上涨概率"""
    return render_template('dive_in_rise_probability.html')


@app.route('/dive-in/data-overview')
def show_dive_in_data_overview():
    """Dive In 数据概览"""
    return render_template('dive_in_data_overview.html')


@app.route('/dive-in/sector-pick')
def show_dive_in_sector_pick():
    """Dive In 板块分组选股（星图瀑布）"""
    return render_template('dive_in_sector_pick.html')


@app.route('/api/dive-in/sector-pick/starmap')
def get_dive_in_sector_pick_starmap():
    """星图行情按板块分组；非交易时段使用最近收盘缓存，不拉实时 API。"""
    try:
        hy_level = request.args.get('hy_level', 2, type=int)
        hy_code = request.args.get('hy_code', 'all', type=str)
        force = request.args.get('force') in ('1', 'true', 'yes')
        payload = _build_starmap_sector_groups(
            hy_level=hy_level,
            hy_code=hy_code,
            force_refresh=force,
        )
        return jsonify({'success': True, **payload})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dive-in/sector-pick/save', methods=['POST'])
def save_dive_in_sector_pick():
    """将选中股票批量写入板块选股分组。"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500

        data = request.get_json() or {}
        codes = data.get('codes') or []
        group_name = (data.get('group_name') or '').strip() or _default_sector_pick_group_name()

        if not codes:
            return jsonify({'success': False, 'error': '未选择股票'}), 400

        favorites_mgr.create_group(group_name)
        added, skipped = [], []
        for raw_code in codes:
            code = str(raw_code).zfill(6)
            if favorites_mgr.add_stock(code, group_name):
                added.append(code)
            else:
                skipped.append(code)

        return jsonify({
            'success': True,
            'group_name': group_name,
            'added': added,
            'skipped': skipped,
            'message': f'已加入分组「{group_name}」：新增 {len(added)} 支，跳过 {len(skipped)} 支',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dive-in/data-overview')
def get_dive_in_data_overview():
    """Dive In 涉及股票的数据下载与缓存更新情况。"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500

        fetch_missing = request.args.get('fetch_missing', '0') in ('1', 'true', 'yes')
        entries = favorites_mgr.get_all_stocks_across_groups()
        payload = _build_dive_in_stock_rows(entries, fetch_missing=fetch_missing)
        return jsonify({'success': True, **payload})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dive-in/rise-probability')
def get_dive_in_rise_probability():
    """列出所有分组股票的上涨概率（来自综合评价）。"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500

        fetch_missing = request.args.get('fetch_missing', '0') in ('1', 'true', 'yes')
        entries = favorites_mgr.get_all_stocks_across_groups()
        payload = _build_dive_in_stock_rows(entries, fetch_missing=fetch_missing)
        rows = sorted(
            payload['stocks'],
            key=lambda x: (
                x['rise_1_probability'] is None,
                -(x['rise_1_probability'] or 0),
            ),
        )
        with_data = payload['stats']['with_rise_data']

        return jsonify({
            'success': True,
            'stocks': [
                {
                    **row,
                    'has_data': row.get('has_rise_data', False),
                    'mini_quote_url': _mini_quote_chart_url(row['code']),
                    'kline_url': _kline_daily_chart_url(row['code']),
                }
                for row in rows
            ],
            'stats': {
                'total': payload['stats']['total'],
                'with_data': with_data,
                'with_score_data': payload['stats'].get('with_score_data', 0),
                'with_rank_data': payload['stats'].get('with_rank_data', 0),
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks/<stock_code>/properties')
def get_stock_properties(stock_code):
    """获取单只股票的记忆属性"""
    try:
        if not stock_property_store:
            return jsonify({'success': False, 'error': 'Property store not available'}), 500
        entry = stock_property_store.get_entry(stock_code)
        return jsonify({'success': True, **entry})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/groups')
def get_favorite_groups():
    """获取所有自选股分组"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        groups = favorites_mgr.get_all_groups()
        return jsonify({
            'success': True,
            'groups': groups
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/groups/<group_name>', methods=['POST'])
def create_favorite_group(group_name):
    """创建新的自选股分组"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        success = favorites_mgr.create_group(group_name)
        if success:
            return jsonify({'success': True, 'message': f'分组 {group_name} 创建成功'})
        else:
            return jsonify({'success': False, 'error': f'分组 {group_name} 已存在'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/groups/<group_name>', methods=['DELETE'])
def delete_favorite_group(group_name):
    """删除自选股分组"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        success, backup_path = favorites_mgr.delete_group(group_name)
        if success:
            payload = {'success': True, 'message': f'分组 {group_name} 删除成功'}
            if backup_path:
                payload['backup_path'] = backup_path
            return jsonify(payload)
        else:
            return jsonify({'success': False, 'error': f'无法删除分组 {group_name}（不存在或为默认分组）'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/groups/<group_name>/pick-note', methods=['GET', 'POST'])
def favorite_group_pick_note(group_name):
    """读取或更新分组选股说明"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500

        if request.method == 'GET':
            note = favorites_mgr.get_group_pick_note(group_name)
            html = None
            if note:
                try:
                    from stock.utils_pick_note import markdown_to_html
                except ImportError:
                    from utils_pick_note import markdown_to_html
                html = markdown_to_html(note)
            return jsonify({
                'success': True,
                'group_name': group_name,
                'pick_note': note,
                'pick_note_html': html,
            })

        data = request.get_json() or {}
        content = data.get('pick_note', data.get('content', ''))
        if not str(content).strip():
            return jsonify({'success': False, 'error': '选股说明不能为空'}), 400
        path = favorites_mgr.set_group_pick_note(group_name, str(content))
        try:
            from stock.utils_pick_note import markdown_to_html
        except ImportError:
            from utils_pick_note import markdown_to_html
        return jsonify({
            'success': True,
            'group_name': group_name,
            'pick_note_path': path,
            'pick_note': str(content),
            'pick_note_html': markdown_to_html(str(content)),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _resolve_pick_query_import_text(text: str):
    """解析 # 东财选股 / ? 爱问财 触发文本，返回 (text, meta, source_key)。"""
    try:
        try:
            from stock.utils_xuangu import resolve_xuangu_import_text
        except ImportError:
            from utils_xuangu import resolve_xuangu_import_text
        text, xuangu_meta = resolve_xuangu_import_text(text)
        if xuangu_meta:
            return text, xuangu_meta, 'xuangu'
    except ValueError:
        raise

    try:
        try:
            from stock.utils_iwencai import resolve_iwencai_import_text
        except ImportError:
            from utils_iwencai import resolve_iwencai_import_text
        text, iwencai_meta = resolve_iwencai_import_text(text)
        if iwencai_meta:
            return text, iwencai_meta, 'iwencai'
    except ValueError:
        raise

    return text, None, None


@app.route('/api/favorites/xuangu/hot')
def get_xuangu_hot_queries():
    """东财条件选股实时热搜问句。"""
    try:
        limit = request.args.get('limit', 10, type=int)
        try:
            from stock.utils_xuangu import fetch_xuangu_hot_queries
        except ImportError:
            from utils_xuangu import fetch_xuangu_hot_queries
        result = fetch_xuangu_hot_queries(limit=limit)
        if not result.get('success'):
            return jsonify(result), 502
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/iwencai/hot')
def get_iwencai_hot_queries():
    """问财 screener 实时热搜问句。"""
    try:
        querytype = request.args.get('querytype', 'stock', type=str)
        limit = request.args.get('limit', 30, type=int)
        try:
            from stock.utils_iwencai import fetch_iwencai_hot_queries
        except ImportError:
            from utils_iwencai import fetch_iwencai_hot_queries
        result = fetch_iwencai_hot_queries(querytype=querytype, limit=limit)
        if not result.get('success'):
            return jsonify(result), 502
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/import', methods=['POST'])
def import_favorite_stocks():
    """从文本批量导入自选股"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500

        data = request.get_json() or {}
        text = data.get('text', '')
        group_name = data.get('group_name', IMPORT_GROUP)
        create_group = bool(data.get('create_group', False))

        if not text or not str(text).strip():
            return jsonify({'success': False, 'error': '导入内容不能为空'}), 400

        pick_meta = None
        pick_source_key = None
        try:
            text, pick_meta, pick_source_key = _resolve_pick_query_import_text(text)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        if create_group and group_name not in ('默认',):
            from stock.module_cache_policy import ensure_dated_pick_group_name
            group_name = ensure_dated_pick_group_name(group_name)

        stock_map = get_import_stock_map()

        stocks = parse_stocks_detail_from_text(text, stock_map)
        if not stocks:
            return jsonify({
                'success': False,
                'error': '未能从文本中识别到有效股票',
            }), 400

        result = favorites_mgr.import_stocks_from_text(
            text=text,
            group_name=group_name,
            create_group=create_group,
            stock_map=stock_map,
            save_pick_note=bool(data.get('save_pick_note', True)) and not pick_meta,
        )

        saved_pick_note_md = None
        if pick_meta and bool(data.get('save_pick_note', True)):
            try:
                try:
                    from stock.utils_pick_note import build_pick_note_markdown, set_group_pick_note
                except ImportError:
                    from utils_pick_note import build_pick_note_markdown, set_group_pick_note
                pick_source = '东方财富选股' if pick_source_key == 'xuangu' else '问财'
                saved_pick_note_md = build_pick_note_markdown(
                    group_name,
                    pick_meta['dataframe'],
                    query=pick_meta.get('query', ''),
                    conditions=pick_meta.get('conditions') or None,
                    source=pick_source,
                )
                result['pick_note_path'] = set_group_pick_note(group_name, saved_pick_note_md)
            except Exception as e:
                print(f"⚠ pick query pick note save failed: {e}")

        pick_note_html = None
        pick_note_md = saved_pick_note_md
        if saved_pick_note_md:
            try:
                from stock.utils_pick_note import markdown_to_html
            except ImportError:
                from utils_pick_note import markdown_to_html
            pick_note_html = markdown_to_html(saved_pick_note_md)
        elif result.get('pick_note_path'):
            note = favorites_mgr.get_group_pick_note(group_name)
            if note:
                pick_note_md = note
                try:
                    from stock.utils_pick_note import markdown_to_html
                except ImportError:
                    from utils_pick_note import markdown_to_html
                pick_note_html = markdown_to_html(note)

        return jsonify({
            'success': True,
            'message': f"成功导入 {result['added']} 只，跳过 {result['skipped']} 只（已存在）",
            'pick_note_html': pick_note_html,
            'pick_note': pick_note_md,
            'resolved_text': text if pick_meta else None,
            'iwencai': {'query': pick_meta.get('query')} if pick_source_key == 'iwencai' else None,
            'xuangu': {
                'query': pick_meta.get('query'),
                'result_url': pick_meta.get('result_url'),
            } if pick_source_key == 'xuangu' else None,
            **result,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/import/preview', methods=['POST'])
def preview_favorite_import():
    """预览文本中可识别的股票代码（不写入）"""
    try:
        data = request.get_json() or {}
        text = data.get('text', '')
        if not text or not str(text).strip():
            return jsonify({'success': True, 'codes': [], 'stocks': [], 'count': 0})

        pick_meta = None
        pick_source_key = None
        try:
            text, pick_meta, pick_source_key = _resolve_pick_query_import_text(text)
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

        stock_map = get_import_stock_map()
        stocks = parse_stocks_detail_from_text(text, stock_map)
        codes = [s['code'] for s in stocks]
        resp = {
            'success': True,
            'codes': codes,
            'stocks': stocks,
            'count': len(stocks),
        }
        if pick_meta:
            resp['resolved_text'] = text
            resp['raw_text'] = pick_meta.get('raw_text')
            pick_source = '东方财富选股' if pick_source_key == 'xuangu' else '问财'
            if pick_source_key == 'iwencai':
                resp['iwencai'] = {
                    'query': pick_meta.get('query'),
                    'count': pick_meta.get('count'),
                }
            if pick_source_key == 'xuangu':
                resp['xuangu'] = {
                    'query': pick_meta.get('query'),
                    'count': pick_meta.get('count'),
                    'result_url': pick_meta.get('result_url'),
                }
            try:
                try:
                    from stock.utils_pick_note import build_pick_note_markdown, markdown_to_html
                except ImportError:
                    from utils_pick_note import build_pick_note_markdown, markdown_to_html
                note_md = build_pick_note_markdown(
                    '预览',
                    pick_meta['dataframe'],
                    query=pick_meta.get('query', ''),
                    conditions=pick_meta.get('conditions') or None,
                    source=pick_source,
                )
                resp['pick_note_html'] = markdown_to_html(note_md)
                resp['pick_note'] = note_md
            except Exception as e:
                print(f"⚠ pick query preview html failed: {e}")
        return jsonify(resp)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks', methods=['POST'])
def add_favorite_stock():
    """添加股票到自选股"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        data = request.get_json()
        stock_code = data.get('stock_code')
        group_name = data.get('group_name', '默认')
        
        if not stock_code:
            return jsonify({'success': False, 'error': '股票代码不能为空'}), 400
        
        success = favorites_mgr.add_stock(stock_code, group_name)
        if success:
            return jsonify({'success': True, 'message': f'股票 {stock_code} 已添加到 {group_name}'})
        else:
            return jsonify({'success': False, 'error': f'股票 {stock_code} 已存在于 {group_name} 中'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks/<stock_code>', methods=['DELETE'])
def remove_favorite_stock(stock_code):
    """从自选股删除股票"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        data = request.get_json() or {}
        group_name = data.get('group_name', '默认')
        
        success = favorites_mgr.remove_stock(stock_code, group_name)
        if success:
            return jsonify({'success': True, 'message': f'股票 {stock_code} 已从 {group_name} 删除'})
        else:
            return jsonify({'success': False, 'error': f'股票 {stock_code} 不在 {group_name} 中'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks')
def get_favorite_stocks():
    """获取指定分组的所有自选股"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        group_name = request.args.get('group_name', '默认')
        stocks = favorites_mgr.get_stocks_with_dates(group_name)
        
        return jsonify({
            'success': True,
            'group_name': group_name,
            'stocks': stocks
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks/<stock_code>/pin', methods=['POST'])
def set_stock_pin(stock_code):
    """设置股票的置顶状态"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        data = request.get_json()
        group_name = data.get('group_name', '默认')
        pin_type = data.get('pin_type', 'pinned')  # 'pinned' or 'top_pinned'
        value = data.get('value', 1)  # 1 = 置顶, 0 = 取消置顶
        
        if pin_type not in ['pinned', 'top_pinned']:
            return jsonify({'success': False, 'error': '无效的置顶类型'}), 400
        
        success = favorites_mgr.set_pin(stock_code, group_name, pin_type, value)
        if success:
            action = '置顶' if value == 1 else '取消置顶'
            pin_name = '固顶' if pin_type == 'top_pinned' else '置顶'
            return jsonify({'success': True, 'message': f'股票 {stock_code} 已{action}({pin_name})'})
        else:
            return jsonify({'success': False, 'error': f'操作失败，股票可能不在该分组中'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks/<stock_code>/check')
def check_stock_in_group(stock_code):
    """检查股票是否在指定分组中"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500
        
        group_name = request.args.get('group_name', '默认')
        exists = favorites_mgr.is_stock_in_group(stock_code, group_name)
        
        return jsonify({
            'success': True,
            'exists': exists,
            'stock_code': stock_code,
            'group_name': group_name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/stocks/<stock_code>/kline-analysis', methods=['GET', 'POST'])
def favorite_kline_analysis(stock_code):
    """日 K 走势分析（多股同列 / 分时图点击触发）。"""
    try:
        try:
            from stock.utils_kline_analysis import analyze_daily_kline
        except ImportError:
            from utils_kline_analysis import analyze_daily_kline
        payload = request.get_json(silent=True) or {}
        name = (payload.get('name') or request.args.get('name') or '').strip()
        quote = payload.get('quote')
        result = analyze_daily_kline(stock_code, name, quote=quote)
        if not result.get('success'):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stocks/bk-industries')
def get_bk_industries():
    """Batch lookup East Money bk2/bk3 industry names for stock codes."""
    try:
        codes_param = request.args.get('codes', '')
        codes = [str(c).strip().zfill(6) for c in codes_param.split(',') if str(c).strip()]
        if not codes:
            return jsonify({'success': False, 'error': '缺少 codes 参数'}), 400
        maps = _load_bk_industry_maps()
        bk2_map = maps.get(2) or {}
        bk3_map = maps.get(3) or {}
        return jsonify({
            'success': True,
            'bk2': {code: bk2_map.get(code, '') for code in codes},
            'bk3': {code: bk3_map.get(code, '') for code in codes},
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stocks/bk3-industries')
def get_bk3_industries():
    """Batch lookup East Money level-3 industry names for stock codes."""
    try:
        codes_param = request.args.get('codes', '')
        codes = [str(c).strip().zfill(6) for c in codes_param.split(',') if str(c).strip()]
        if not codes:
            return jsonify({'success': False, 'error': '缺少 codes 参数'}), 400
        industry_map = _load_bk3_industry_map()
        return jsonify({
            'success': True,
            'industries': {code: industry_map.get(code, '') for code in codes},
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


try:
    from stock.utils_pi_chat import (
        PiChatError,
        pi_chat_reset,
        pi_chat_send,
        pi_chat_status,
    )
except ImportError:
    from utils_pi_chat import (
        PiChatError,
        pi_chat_reset,
        pi_chat_send,
        pi_chat_status,
    )


@app.route('/api/pi/chat/status')
def pi_chat_status_api():
    try:
        return jsonify({'success': True, **pi_chat_status()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pi/chat', methods=['POST'])
def pi_chat_api():
    try:
        payload = request.get_json(silent=True) or {}
        session_id = (payload.get('session_id') or '').strip()
        message = (payload.get('message') or '').strip()
        if not session_id:
            return jsonify({'success': False, 'error': '缺少 session_id'}), 400
        if not message:
            return jsonify({'success': False, 'error': '消息不能为空'}), 400
        result = pi_chat_send(session_id, message, context=payload.get('context'))
        return jsonify({'success': True, **result})
    except PiChatError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pi/chat/reset', methods=['POST'])
def pi_chat_reset_api():
    try:
        payload = request.get_json(silent=True) or {}
        session_id = (payload.get('session_id') or '').strip()
        if not session_id:
            return jsonify({'success': False, 'error': '缺少 session_id'}), 400
        pi_chat_reset(session_id)
        return jsonify({'success': True})
    except PiChatError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/favorites/quotes')
def get_favorite_quotes():
    """获取自选股报价（独立缓存：交易时段 5 分钟，盘外/非交易日用最近交易日）"""
    try:
        if not favorites_mgr:
            return jsonify({'success': False, 'error': 'Favorites manager not available'}), 500

        import glob
        import pandas as pd
        from datetime import datetime

        try:
            from favorites_quote_cache import (
                build_cache_payload,
                cache_policy_summary,
                extract_quotes_from_rows,
                should_use_cache,
                save_cache,
            )
        except ImportError:
            from stock.favorites_quote_cache import (
                build_cache_payload,
                cache_policy_summary,
                extract_quotes_from_rows,
                should_use_cache,
                save_cache,
            )

        group_name = request.args.get('group_name', '默认')
        explicit_live = request.args.get('live', '0').lower() in ('1', 'true', 'yes')

        stocks_data = favorites_mgr.get_stocks_with_dates(group_name)
        if not stocks_data:
            return jsonify({
                'success': True,
                'group_name': group_name,
                'stocks': [],
                **_favorites_pick_note_payload(group_name),
                'message': '该分组暂无自选股',
            })

        stock_codes = [s['code'] for s in stocks_data]
        pin_info = {
            stock['code'].zfill(6): {
                'pinned': stock['pinned'],
                'top_pinned': stock['top_pinned'],
                'add_date': stock['date'],
            }
            for stock in stocks_data
        }

        use_cache, cached_payload, cache_reason = should_use_cache(
            group_name, stock_codes, force=explicit_live
        )
        if use_cache and cached_payload:
            result_data = _enrich_favorite_stocks_industry(
                _build_favorite_rows_from_quote_cache(stocks_data, pin_info, cached_payload)
            )
            file_info = dict(cached_payload.get('file_info') or {})
            file_info.update({
                'cached': True,
                'cache_reason': cache_reason,
                'cache_policy': cache_policy_summary(),
                'trade_date': cached_payload.get('trade_date'),
                'total_count': len(result_data),
            })
            return jsonify({
                'success': True,
                'group_name': group_name,
                'stocks': result_data,
                **_favorites_pick_note_payload(group_name),
                'file_info': file_info,
            })

        latest_file = None
        try:
            from quote_cache import find_latest_quote_file
            latest_file = find_latest_quote_file()
        except Exception:
            latest_file = None

        if not latest_file:
            latest_file = _ensure_market_quote_csv(force=explicit_live)

        if not latest_file:
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pattern = os.path.join(parent_dir, "generated/em/*/quote_*.csv")
            files = glob.glob(pattern)
            if files:
                latest_file = _find_best_quote_file(files)

        prefer_live = _should_prefer_live_favorite_quotes(explicit_live, latest_file)
        df, code_col = None, None

        if latest_file and os.path.exists(latest_file):
            df = pd.read_csv(latest_file)
            if '代码' in df.columns:
                code_col = '代码'
            elif '股票代码' in df.columns:
                code_col = '股票代码'
            elif 'code' in df.columns:
                code_col = 'code'
            else:
                return jsonify({
                    'success': False,
                    'error': 'quotes文件格式不正确，缺少代码列'
                }), 500
            df[code_col] = df[code_col].astype(str).str.zfill(6)
        elif not prefer_live:
            latest_file = _ensure_market_quote_csv(force=True)
            prefer_live = _should_prefer_live_favorite_quotes(True, latest_file)
            if latest_file and os.path.exists(latest_file):
                df = pd.read_csv(latest_file)
                code_col = next(
                    (c for c in ('代码', '股票代码', 'code') if c in df.columns),
                    None,
                )
                if code_col:
                    df[code_col] = df[code_col].astype(str).str.zfill(6)

        live_quote_map: Dict[str, Dict] = {}
        iwencai_quote_map: Dict[str, Dict] = {}
        if prefer_live:
            live_quote_map = _fetch_em_ulist_live_quotes(stock_codes)
        if len(live_quote_map) < max(len(stock_codes) // 2, 1):
            iwencai_quote_map = _load_iwencai_group_quotes(group_name)

        result_data = []
        seen_codes = set()
        for stock in stocks_data:
            code = stock['code'].zfill(6)
            if code in seen_codes:
                continue
            seen_codes.add(code)
            result_data.append(_build_favorite_row(
                code, pin_info[code], df, code_col,
                prefer_live=prefer_live,
                live_quote_map=live_quote_map,
                iwencai_quote_map=iwencai_quote_map,
            ))

        result_data.sort(key=lambda x: (
            -x.get('_top_pinned', 0),
            -x.get('_pinned', 0),
        ))

        live_hits = len(live_quote_map) if prefer_live else 0
        iwencai_hits = len(iwencai_quote_map)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        csv_stale = False
        if latest_file and os.path.exists(latest_file):
            csv_stale = datetime.fromtimestamp(os.path.getmtime(latest_file)).date() < datetime.now().date()

        if prefer_live and live_hits > 0:
            source = 'live'
            file_info = {
                'filename': '实时报价',
                'update_time': now_str,
                'total_count': len(result_data),
                'live': True,
                'live_count': live_hits,
                'stale': False,
            }
        elif iwencai_hits > 0:
            source = 'iwencai'
            file_info = {
                'filename': '问财选股快照',
                'update_time': now_str,
                'total_count': len(result_data),
                'live': False,
                'iwencai_count': iwencai_hits,
                'stale': csv_stale,
            }
        elif latest_file and os.path.exists(latest_file):
            source = 'csv'
            file_mtime = os.path.getmtime(latest_file)
            file_datetime = datetime.fromtimestamp(file_mtime)
            file_info = {
                'filename': os.path.basename(latest_file),
                'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                'total_count': len(result_data),
                'live': False,
                'stale': csv_stale,
            }
        else:
            source = 'live'
            file_info = {
                'filename': '实时报价',
                'update_time': now_str,
                'total_count': len(result_data),
                'live': prefer_live,
                'stale': True,
            }

        file_info.update({
            'cached': False,
            'cache_reason': cache_reason,
            'cache_policy': cache_policy_summary(),
        })

        quotes_snapshot = extract_quotes_from_rows(result_data)
        cache_payload = build_cache_payload(
            group_name,
            stock_codes,
            quotes_snapshot,
            file_info,
            csv_path=latest_file,
            source=source,
        )
        save_cache(group_name, cache_payload)

        result_data = _enrich_favorite_stocks_industry(result_data)

        return jsonify({
            'success': True,
            'group_name': group_name,
            'stocks': result_data,
            **_favorites_pick_note_payload(group_name),
            'file_info': file_info,
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/bk_flow')
def show_bk_flow():
    """Display latest bk_flow_ file as a table (板块资金流向)"""
    import pandas as pd

    page = int(request.args.get('page', 1))
    per_page_param = request.args.get('per_page', '50')
    per_page = int(per_page_param) if per_page_param != 'all' else None
    sort_column = request.args.get('sort_column', '')
    sort_direction = request.args.get('sort_direction', 'desc')
    force = request.args.get('force', '0') in ('1', 'true', 'yes')

    try:
        refresh_meta = ensure_bk_flow_fresh(force=force)
        latest_file = refresh_meta.get('latest_file') or find_latest_bk_flow_file()

        if not latest_file:
            return render_template('bk_flow.html',
                                 error="No bk_flow files found. Please run data generation to create files.",
                                 table_html=None,
                                 file_info=None,
                                 pagination=None,
                                 refresh_meta=refresh_meta)
        
        # Read CSV
        df = pd.read_csv(latest_file)
        
        # Apply exclude list (bk_exclude.tsv) - BEFORE formatting to preserve column names
        try:
            exclude_path = os.path.join(os.path.dirname(__file__), 'bk_exclude.tsv')
            if os.path.exists(exclude_path):
                exdf = pd.read_csv(exclude_path, sep='\t', comment='#')
                # Get columns
                exdf.columns = [c.strip() for c in exdf.columns]
                name_col = '名称' if '名称' in exdf.columns else exdf.columns[0]
                flag_col = '排除显示' if '排除显示' in exdf.columns else exdf.columns[1]
                # Get names to exclude (排除显示 equals 1)
                to_exclude = set(exdf[exdf[flag_col].fillna(0).astype(float) == 1][name_col].astype(str).str.strip())
                if '板块名称' in df.columns and to_exclude:
                    df = df[~df['板块名称'].astype(str).str.strip().isin(to_exclude)]
        except Exception as e:
            # If filtering fails, continue without it
            print(f"Warning: Failed to apply exclude filter: {e}")
        
        # Format the dataframe (but skip dividing by 1E8 for bk_flow data since it's already in 亿元)
        # Only format stock codes/names, don't re-divide flow amounts
        df = format_dataframe_bk_flow(df)
        
        # Apply sorting if specified, or use default sorting
        if sort_column:
            # Try to find matching column by name or index
            sort_col = None
            if sort_column in df.columns:
                sort_col = sort_column
            else:
                # Try to find by partial match or common column names
                for col in df.columns:
                    if sort_column.lower() in col.lower() or col.lower() in sort_column.lower():
                        sort_col = col
                        break
            
            if sort_col:
                df = df.sort_values(by=sort_col, ascending=(sort_direction == 'asc'))
                # Update sort_column to the actual column name
                sort_column = sort_col
        else:
            # Default sorting: by 主力净流入 in descending order
            if '主力净流入' in df.columns:
                df = df.sort_values(by='主力净流入', ascending=False)
                sort_column = '主力净流入'
                sort_direction = 'desc'
            elif '大单净流入' in df.columns:
                df = df.sort_values(by='大单净流入', ascending=False)
                sort_column = '大单净流入'
                sort_direction = 'desc'
        
        # Calculate pagination
        total_rows = len(df)
        if per_page is None:  # Show all records
            total_pages = 1
            start_idx = 0
            end_idx = total_rows
            page_df = df
        else:
            total_pages = (total_rows + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_df = df.iloc[start_idx:end_idx]
        
        # Convert to HTML table with escape=False to render HTML links
        table_html = page_df.to_html(classes=['table', 'table-striped', 'table-hover'], 
                                   index=False,
                                   border=0,
                                   table_id='dataTable',
                                   escape=False)
        
        from datetime import datetime
        file_mtime = os.path.getmtime(latest_file)
        file_datetime = datetime.fromtimestamp(file_mtime)
        
        file_info = {
            'filename': os.path.basename(latest_file),
            'rows': total_rows,
            'timestamp': file_mtime,
            'update_time': file_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'refresh_reason': refresh_meta.get('reason'),
            'fetched_now': refresh_meta.get('fetched', False),
        }
        
        # Create pagination info
        pagination = {
            'current_page': page,
            'total_pages': total_pages,
            'per_page': per_page if per_page is not None else total_rows,
            'total_rows': total_rows,
            'start_row': start_idx + 1,
            'end_row': min(end_idx, total_rows)
        }
        
        return render_template('bk_flow.html', 
                             table_html=table_html,
                             file_info=file_info,
                             pagination=pagination,
                             sort_column=sort_column,
                             sort_direction=sort_direction,
                             refresh_meta=refresh_meta,
                             error=None)
    
    except Exception as e:
        return render_template('bk_flow.html',
                             error=str(e),
                             sort_column='',
                             sort_direction='desc',
                             data=None)


if __name__ == '__main__':
    # Ensure templates directory exists
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir) 
    
    print("=" * 60)
    print("🚀 Stock Analysis Web App Starting...")
    print("=" * 60)
    print(f"📂 Template directory: {template_dir}")
    print(f"📂 Static directory: {static_dir}")
    print("🌐 Access the app at: http://127.0.0.1:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)



