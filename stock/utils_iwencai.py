"""同花顺问财（爱问财）选股查询。"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

IWENCAI_PREFIX_RE = re.compile(r'^(?:\?|？)\s*(.+)$', re.DOTALL)
IWENCAI_ROBOT_URL = 'https://www.iwencai.com/customized/chart/get-robot-data'
IWENCAI_COOKIE_PROBE_QUERY = '沪深300'
IWENCAI_LOGIN_COOKIE_KEYS = ('THSSESSID', 'u_ukey')


class IwencaiCaptchaError(Exception):
    """问财要求验证码校验（未登录 / 会话被风控 / 请求过快时触发）。"""

_cookie_refresh_lock = threading.Lock()
_cookie_watcher_started = False


def _clean_b64(text: str) -> str:
    """问财字段里的 Base64 常带换行，需去掉空白再解码。"""
    return re.sub(r'\s+', '', str(text or '').strip())


def _looks_like_b64_json(text: str) -> bool:
    s = _clean_b64(text)
    return (
        len(s) >= 40
        and re.fullmatch(r'[A-Za-z0-9+/=]+', s) is not None
        and s.startswith(('W3si', 'W3s', 'eyJ', 'W10'))
    )


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', str(text or '')).strip()


def _extract_news_title(item: Dict[str, Any]) -> str:
    for key in (
        'PageRawTitll', 'PageRawTitle', 'pageRawTitll', 'pageRawTitle',
        'PageTitle', 'pageTitle', 'title', 'Title', 'newsTitle', 'NewsTitle',
        'rawTitle', 'digest', 'summary', 'content', 'keyword', 'Keyword',
        'showTitle', 'ShowTitle',
    ):
        val = item.get(key)
        if val is None:
            continue
        text = _strip_html(str(val).strip())
        if text:
            return text
    for key, val in item.items():
        kl = str(key).lower()
        if not any(tag in kl for tag in ('titll', 'title', 'digest', 'summary', 'content', 'keyword', '资讯')):
            continue
        text = _strip_html(str(val).strip())
        if text and text not in ('--', 'null', 'None'):
            return text
    return ''


def _flatten_iwencai_news(data: Any) -> str:
    titles: List[str] = []
    seen = set()

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            title = _extract_news_title(node)
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
            for val in node.values():
                if isinstance(val, (list, dict)):
                    _walk(val)
        elif isinstance(node, str):
            text = _strip_html(node.strip())
            if text and text not in seen:
                seen.add(text)
                titles.append(text)

    _walk(data)
    return '；'.join(titles)


def decode_iwencai_blob(value: Any) -> Optional[str]:
    """解码问财 Base64 JSON 字段（如「关键词资讯」）为可读标题列表。"""
    s = _clean_b64(value)
    if not s or not _looks_like_b64_json(s):
        return None
    try:
        raw = base64.b64decode(s, validate=False)
        text = raw.decode('utf-8')
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    flattened = _flatten_iwencai_news(data)
    return flattened or None


def parse_iwencai_query(text: str) -> Optional[str]:
    """若文本以 ? / ？ 开头，返回问财问句。"""
    if not text:
        return None
    m = IWENCAI_PREFIX_RE.match(str(text).strip())
    return m.group(1).strip() if m else None


def _iwencai_cookie_paths() -> List[str]:
    return [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'shared', 'iwencai_cookie.txt'),
        os.path.join(os.path.dirname(__file__), 'shared', 'iwencai_cookie.txt'),
    ]


def _primary_iwencai_cookie_path() -> str:
    return _iwencai_cookie_paths()[0]


def _auto_chrome_cookie_enabled() -> bool:
    return os.environ.get('IWENCAI_AUTO_CHROME', '1').strip().lower() not in ('0', 'false', 'no')


def _cookie_max_age_seconds() -> int:
    try:
        hours = float(os.environ.get('IWENCAI_COOKIE_MAX_AGE_HOURS', '12'))
    except (TypeError, ValueError):
        hours = 12.0
    return max(int(hours * 3600), 300)


def _cookie_refresh_interval_seconds() -> int:
    try:
        hours = float(os.environ.get('IWENCAI_COOKIE_REFRESH_HOURS', '6'))
    except (TypeError, ValueError):
        hours = 6.0
    return max(int(hours * 3600), 600)


def _cookie_file_is_stale() -> bool:
    path = _primary_iwencai_cookie_path()
    if not os.path.isfile(path):
        return True
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return True
    return age > _cookie_max_age_seconds()


def _load_iwencai_cookie_from_file() -> Optional[str]:
    cookie = os.environ.get('IWENCAI_COOKIE', '').strip()
    if cookie:
        return cookie
    for path in _iwencai_cookie_paths():
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    text = fh.read().strip()
                    if text:
                        return text
            except OSError:
                pass
    return None


def fetch_iwencai_cookie_from_chrome(profile: Optional[str] = None) -> Optional[str]:
    """从本机 Chrome 读取 iwencai.com 登录 Cookie（需已在 Chrome 登录爱问财）。"""
    try:
        import browser_cookie3
    except ImportError:
        return None

    kwargs: Dict[str, Any] = {}
    profile_name = (profile or os.environ.get('IWENCAI_CHROME_PROFILE') or '').strip()
    if profile_name:
        kwargs['profile'] = profile_name

    seen: Dict[str, str] = {}
    for domain in ('iwencai.com', '.iwencai.com'):
        try:
            jar = browser_cookie3.chrome(domain_name=domain, **kwargs)
            for item in jar:
                seen[item.name] = item.value
        except Exception:
            continue

    if not seen:
        return None
    if not any(k in seen for k in ('v', 'other_uid', 'u_ukey', 'THSSESSID')):
        return None
    return '; '.join(f'{k}={v}' for k, v in seen.items())


def _cookie_has_login(cookie: Optional[str]) -> bool:
    """判断 Cookie 是否含登录态字段（无登录态的访客 Cookie 易触发验证码）。"""
    if not cookie:
        return False
    return any(k in cookie for k in IWENCAI_LOGIN_COOKIE_KEYS)


def save_iwencai_cookie(cookie: str) -> str:
    path = _primary_iwencai_cookie_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(cookie.strip())
    return path


def sync_iwencai_cookie_from_chrome(save: bool = True, profile: Optional[str] = None) -> Dict[str, Any]:
    """从 Chrome 同步 Cookie，可选写入 shared/iwencai_cookie.txt 并用问财 API 校验。"""
    cookie = fetch_iwencai_cookie_from_chrome(profile=profile)
    if not cookie:
        return {
            'success': False,
            'error': (
                '未能从 Chrome 读取爱问财 Cookie。请先在 Chrome 打开 iwencai.com 并登录；'
                '若使用非默认配置文件，可设置 IWENCAI_CHROME_PROFILE=Profile 1'
            ),
        }

    if not _cookie_has_login(cookie):
        return {
            'success': False,
            'error': (
                'Chrome 中 iwencai.com 仅有访客 Cookie（未登录，缺少 THSSESSID/u_ukey）。'
                '请先在 Chrome 打开 https://www.iwencai.com 登录同花顺账号并完成验证码，'
                '再重新运行本命令同步 Cookie'
            ),
            'cookie_fields': len(cookie.split(';')),
        }

    try:
        df = _fetch_iwencai_via_https(IWENCAI_COOKIE_PROBE_QUERY, cookie)
    except IwencaiCaptchaError as exc:
        return {
            'success': False,
            'error': (
                f'问财要求验证码校验（{exc}）。请在 Chrome 打开 iwencai.com '
                '完成验证后重新同步 Cookie'
            ),
            'cookie_fields': len(cookie.split(';')),
        }
    if df is None or df.empty:
        return {
            'success': False,
            'error': '已读取 Cookie，但问财校验失败，请确认账号已登录且未过期',
        }

    path = None
    if save:
        path = save_iwencai_cookie(cookie)
    return {
        'success': True,
        'path': path,
        'cookie_fields': len(cookie.split(';')),
        'sample_count': len(df),
        'has_login': True,
    }


def auto_refresh_iwencai_cookie(force: bool = False) -> Dict[str, Any]:
    """Cookie 过期或 force 时，从 Chrome 拉取并写入 shared/iwencai_cookie.txt。"""
    if not _auto_chrome_cookie_enabled():
        return {'success': False, 'skipped': True, 'reason': 'IWENCAI_AUTO_CHROME disabled'}

    if not force and not _cookie_file_is_stale():
        cookie = _load_iwencai_cookie_from_file()
        if cookie:
            return {
                'success': True,
                'skipped': True,
                'reason': 'cookie still fresh',
                'path': _primary_iwencai_cookie_path(),
            }

    with _cookie_refresh_lock:
        if not force and not _cookie_file_is_stale():
            cookie = _load_iwencai_cookie_from_file()
            if cookie:
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'cookie still fresh',
                    'path': _primary_iwencai_cookie_path(),
                }
        try:
            return sync_iwencai_cookie_from_chrome(save=True)
        except IwencaiCaptchaError as exc:
            return {
                'success': False,
                'error': f'问财要求验证码校验（{exc}），请在 Chrome 登录 iwencai.com 后重试',
            }


def _load_iwencai_cookie() -> Optional[str]:
    if os.environ.get('IWENCAI_COOKIE', '').strip():
        return _load_iwencai_cookie_from_file()

    cookie = _load_iwencai_cookie_from_file()
    if cookie and not _cookie_file_is_stale():
        return cookie

    if _auto_chrome_cookie_enabled():
        result = auto_refresh_iwencai_cookie(force=not cookie)
        if result.get('success') and not result.get('skipped'):
            refreshed = _load_iwencai_cookie_from_file()
            if refreshed:
                return refreshed
        cookie = _load_iwencai_cookie_from_file()
        if cookie:
            return cookie
        live = fetch_iwencai_cookie_from_chrome()
        if live:
            try:
                save_iwencai_cookie(live)
            except OSError:
                pass
            return live
    return cookie


def _refresh_iwencai_cookie_from_chrome() -> Optional[str]:
    if not _auto_chrome_cookie_enabled():
        return None
    result = sync_iwencai_cookie_from_chrome(save=True)
    if not result.get('success'):
        return None
    return _load_iwencai_cookie_from_file()


def start_iwencai_cookie_auto_update() -> None:
    """启动时及定期从 Chrome 同步问财 Cookie（daemon 线程）。"""
    global _cookie_watcher_started
    if _cookie_watcher_started or not _auto_chrome_cookie_enabled():
        return
    _cookie_watcher_started = True

    def _loop() -> None:
        auto_refresh_iwencai_cookie(force=False)
        while True:
            time.sleep(_cookie_refresh_interval_seconds())
            try:
                auto_refresh_iwencai_cookie(force=True)
            except Exception:
                pass

    threading.Thread(target=_loop, name='iwencai-cookie-auto-update', daemon=True).start()


def _normalize_iwencai_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in list(out.columns):
        c = str(col)
        if '资讯' in c or '关键词' in c or out[col].dtype == object:
            sample = out[col].dropna().astype(str).head(5)
            if len(sample) and any(_looks_like_b64_json(x) for x in sample):
                out[col] = out[col].apply(
                    lambda v: (decode_iwencai_blob(v) or v) if pd.notna(v) else v
                )
    if 'code' in out.columns:
        out['股票代码'] = (
            out['code'].astype(str)
            .str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
            .str.replace(r'\.0$', '', regex=True)
            .str.zfill(6)
        )
    rename = {}
    for col in out.columns:
        c = str(col)
        if c in ('code', '代码') or (c.endswith('股票代码') and c != '股票代码'):
            continue
        elif c in ('name', '名称', '股票名称') or ('股票简称' in c and c != '股票简称'):
            rename[col] = '股票简称'
    if rename:
        out = out.rename(columns=rename)
    if '股票代码' not in out.columns:
        for col in out.columns:
            if '代码' in str(col):
                out['股票代码'] = (
                    out[col].astype(str)
                    .str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
                    .str.replace(r'\.0$', '', regex=True)
                    .str.zfill(6)
                )
                break
    elif out['股票代码'].dtype == object:
        out['股票代码'] = (
            out['股票代码'].astype(str)
            .str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
            .str.replace(r'\.0$', '', regex=True)
            .str.zfill(6)
        )
    return out


def _df_to_raw_text(query: str, df: pd.DataFrame) -> str:
    """问财结果：问句 + Markdown 表格（供选股说明 / 导入文本框）。"""
    try:
        from stock.utils_pick_note import dataframe_to_markdown_table, _pick_note_display_df
    except ImportError:
        from utils_pick_note import dataframe_to_markdown_table, _pick_note_display_df

    display_df = _pick_note_display_df(df)
    lines = [f'问财选股：{query}', '', '## 选股结果', '']
    table = dataframe_to_markdown_table(display_df)
    if table:
        lines.append(table)
        return '\n'.join(lines)

    code_col = '股票代码' if '股票代码' in df.columns else None
    name_col = '股票简称' if '股票简称' in df.columns else None
    if not code_col:
        for c in df.columns:
            if '代码' in str(c):
                code_col = c
                break
    if not name_col:
        for c in df.columns:
            if '简称' in str(c) or '名称' in str(c):
                name_col = c
                break
    for _, row in df.iterrows():
        if code_col:
            code = str(row[code_col]).zfill(6)
            name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else ''
            lines.append(f'{code} {name}'.strip())
    return '\n'.join(lines)


def _build_result_from_df(query: str, df: pd.DataFrame) -> Dict[str, Any]:
    df = _normalize_iwencai_df(df)
    if '股票代码' not in df.columns:
        return {'success': False, 'error': '问财结果中未找到股票代码列'}

    raw_text = _df_to_raw_text(query, df)
    stocks = []
    for _, row in df.iterrows():
        code = str(row['股票代码']).zfill(6)
        name = ''
        if '股票简称' in df.columns and pd.notna(row.get('股票简称')):
            name = str(row['股票简称']).strip()
        stocks.append({'code': code, 'name': name})

    return {
        'success': True,
        'query': query,
        'count': len(stocks),
        'stocks': stocks,
        'raw_text': raw_text,
        'dataframe': df,
    }


def _fetch_iwencai_via_https(query: str, cookie: str) -> Optional[pd.DataFrame]:
    """通过 HTTPS 直连问财 robot-data（pywencai 默认走 HTTP，易失败）。"""
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        ),
        'Content-Type': 'application/json',
        'Referer': 'https://www.iwencai.com/unifiedwap/result',
        'Origin': 'https://www.iwencai.com',
        'Cookie': cookie,
    }
    payload = {
        'source': 'Ths_iwencai_Xuangu',
        'version': '2.0',
        'add_info': (
            '{"urp":{"scene":1,"company":1,"business":1},'
            '"contentType":"json","searchInfo":true}'
        ),
        'question': query,
        'perpage': 100,
        'page': 1,
        'secondary_intent': 'stock',
        'log_info': '{"input_type":"typewrite"}',
    }
    try:
        resp = requests.post(IWENCAI_ROBOT_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code in (401, 403):
            raise IwencaiCaptchaError(f'HTTP {resp.status_code}')
        resp.raise_for_status()
        body = resp.json()
    except IwencaiCaptchaError:
        raise
    except Exception:
        return None

    if not isinstance(body, dict):
        return None
    if (body.get('data') or {}).get('captcha_url'):
        raise IwencaiCaptchaError('账号触发验证码风控')

    if body.get('status_code') == 0 or body.get('code') == 0:
        data = body.get('data') or {}
    else:
        return None

    components = (
        (((data.get('answer') or [{}])[0].get('txt') or [{}])[0].get('content') or {})
        .get('components')
        or []
    )
    for comp in components:
        rows = (comp.get('data') or {}).get('datas')
        if isinstance(rows, list) and rows:
            return pd.DataFrame.from_records(rows)
    return None


def fetch_iwencai_results(query: str) -> Dict[str, Any]:
    """查询问财并返回解析后的股票列表与原文。"""
    query = str(query or '').strip()
    if not query:
        return {'success': False, 'error': '问财问句不能为空'}

    cookie = _load_iwencai_cookie()
    df = None

    try:
        if cookie:
            df = _fetch_iwencai_via_https(query, cookie)

        if df is None and _auto_chrome_cookie_enabled():
            refreshed = _refresh_iwencai_cookie_from_chrome()
            if refreshed:
                cookie = refreshed
                df = _fetch_iwencai_via_https(query, cookie)

        if df is None:
            try:
                import pywencai
            except ImportError:
                return {
                    'success': False,
                    'error': '未安装 pywencai，请在 venv 中执行: pip install pywencai',
                }

            kwargs = {'query': query, 'loop': True}
            if cookie:
                kwargs['cookie'] = cookie
            try:
                df = pywencai.get(**kwargs)
            except Exception:
                df = None
    except IwencaiCaptchaError as exc:
        if cookie and not _cookie_has_login(cookie):
            return {
                'success': False,
                'error': (
                    f'问财要求验证码校验（{exc}），且当前 Cookie 仅为访客态（未登录）。\n'
                    '更新步骤：\n'
                    '1. 在 Chrome 打开 https://www.iwencai.com 登录同花顺账号并完成验证码；\n'
                    '2. 重新同步 Cookie：cd stock && source venv/bin/activate && '
                    'python -m stock.utils_iwencai（从项目根目录运行）\n'
                    '3. 或手动将浏览器 DevTools 里的 Cookie 写入 shared/iwencai_cookie.txt，'
                    '或设置环境变量 IWENCAI_COOKIE；\n'
                    '4. 若刚完成多次查询，等待几分钟再试（问财限流）'
                ),
            }
        return {
            'success': False,
            'error': (
                f'问财要求验证码校验（{exc}）。'
                '请在 Chrome 打开 https://www.iwencai.com 完成验证后，'
                '运行 python -m stock.utils_iwencai 重新同步 Cookie'
            ),
        }

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        if not cookie:
            return {
                'success': False,
                'error': (
                    '问财查询失败：需要登录 Cookie。'
                    '请在浏览器登录 iwencai.com 后，将 Cookie 写入 '
                    'shared/iwencai_cookie.txt 或设置环境变量 IWENCAI_COOKIE'
                ),
            }
        if cookie and not _cookie_has_login(cookie):
            return {
                'success': False,
                'error': (
                    '问财未返回结果，且当前 Cookie 仅为访客态（未登录，缺少 THSSESSID/u_ukey）。\n'
                    '请在 Chrome 打开 https://www.iwencai.com 登录同花顺账号并完成验证码，'
                    '然后运行 python -m stock.utils_iwencai 重新同步 Cookie'
                ),
            }
        return {'success': False, 'error': f'问财未返回结果，请检查问句或更新 Cookie: {query}'}

    if not isinstance(df, pd.DataFrame):
        return {'success': False, 'error': '问财返回格式异常（非表格）'}

    return _build_result_from_df(query, df)


def resolve_iwencai_import_text(text: str) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    若 text 为爱问财触发格式，查询问财并返回 (替换后的原文, meta)。
    否则返回 (原文, None)。
    """
    query = parse_iwencai_query(text)
    if not query:
        return text, None
    result = fetch_iwencai_results(query)
    if not result.get('success'):
        raise ValueError(result.get('error') or '问财查询失败')
    return result['raw_text'], result


IWENCAI_SCREENER_URL = 'https://www.iwencai.com/screener'
IWENCAI_GATEWAY_BASE = 'https://www.iwencai.com/gateway/iwc-web-business-center'
IWENCAI_UNIFIEDWAP_BASE = 'https://www.iwencai.com/unifiedwap'

IWENCAI_SCOPE_TYPES: List[Dict[str, str]] = [
    {'value': 'stock', 'label': 'A股'},
    {'value': 'azhishu', 'label': 'A股指数'},
    {'value': 'fund', 'label': '基金产品'},
    {'value': 'fundmanager', 'label': '基金经理'},
    {'value': 'fundcompany', 'label': '基金公司'},
    {'value': 'hkstock', 'label': '港股'},
    {'value': 'hkzhishu', 'label': '港股指数'},
    {'value': 'usstock', 'label': '美股'},
    {'value': 'uszhishu', 'label': '美股指数'},
    {'value': 'threeboard', 'label': '新三板'},
    {'value': 'conbond', 'label': '可转债'},
    {'value': 'insurance', 'label': '保险'},
    {'value': 'futures', 'label': '期货'},
    {'value': 'lccp', 'label': '理财'},
    {'value': 'foreign_exchange', 'label': '外汇'},
    {'value': 'macro', 'label': '宏观'},
    {'value': 'law', 'label': '法律法规'},
]

IWENCAI_TAB_LABELS = {
    'technical': '技术面',
    'funding': '资金面',
    'basic': '基本面',
}

IWENCAI_TYPE_KEYWORDS: Dict[str, List[str]] = {
    'hkstock': ['港股', 'HK'],
    'hkzhishu': ['港股', 'HK', '指数'],
    'usstock': ['美股', 'US'],
    'uszhishu': ['美股', '指数'],
    'fund': ['基金'],
    'fundmanager': ['基金经理'],
    'fundcompany': ['基金公司', '基金company'],
    'conbond': ['可转债'],
    'threeboard': ['新三板'],
    'insurance': ['保险'],
    'futures': ['期货'],
    'lccp': ['理财'],
    'foreign_exchange': ['外汇'],
    'macro': ['宏观', 'GDP'],
    'law': ['法律法规', '法规'],
    'azhishu': ['指数', 'A股指数'],
}


def _iwencai_public_headers() -> Dict[str, str]:
    return {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        ),
        'Referer': IWENCAI_SCREENER_URL,
    }


def _hot_query_label(question: str, max_len: int = 40) -> str:
    label = str(question or '').split(';')[0].strip()
    label = label.replace('\n', ' ').strip()
    if len(label) > max_len:
        return label[: max_len - 1] + '…'
    return label


def _extract_routine_question(item: Dict[str, Any]) -> str:
    add_info = item.get('item_add_info') or {}
    question = str(add_info.get('send_query') or item.get('item_name') or '').strip()
    return question.replace('\n', ' ').strip()


def _fetch_iwencai_routine_multi(name: str) -> Dict[str, List[Dict[str, Any]]]:
    resp = requests.post(
        f'{IWENCAI_GATEWAY_BASE}/recommend/routine/multi/',
        headers={**_iwencai_public_headers(), 'Content-Type': 'application/json'},
        json={'name': name},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if str(body.get('status_code')) != '0':
        return {}
    data = (body.get('result') or {}).get('data') or {}
    return data if isinstance(data, dict) else {}


def _fetch_iwencai_routine_single(name: str) -> List[Dict[str, Any]]:
    resp = requests.post(
        f'{IWENCAI_GATEWAY_BASE}/recommend/routine/single/',
        headers={**_iwencai_public_headers(), 'Content-Type': 'application/json'},
        json={'name': name},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if str(body.get('status_code')) != '0':
        return []
    data = (body.get('result') or {}).get('data') or []
    return data if isinstance(data, list) else []


def _fetch_iwencai_query_hints(querytype: str) -> List[str]:
    resp = requests.post(
        f'{IWENCAI_UNIFIEDWAP_BASE}/suggest/V1/index/query-hint-list',
        headers={
            **_iwencai_public_headers(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data={'querytype': querytype},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get('success'):
        return []
    docs = (body.get('data') or {}).get('docs') or []
    return [str(x).strip() for x in docs if str(x).strip()]


def _fetch_iwencai_hype_concepts() -> List[Dict[str, str]]:
    resp = requests.get(
        f'{IWENCAI_GATEWAY_BASE}/executor/execute/hype_concept/',
        headers=_iwencai_public_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if str(body.get('status_code')) != '0':
        return []
    out: List[Dict[str, str]] = []
    for item in body.get('datas') or []:
        name = str(item.get('index_name') or '').strip()
        if not name:
            continue
        out.append({
            'question': name if '概念' in name else f'{name}概念',
            'label': name,
            'category': '今天炒什么',
        })
    return out


def _fetch_iwencai_lurk_calendar() -> List[Dict[str, str]]:
    resp = requests.get(
        f'{IWENCAI_GATEWAY_BASE}/iwencai_web/home/lurk_calendar_concept/',
        headers=_iwencai_public_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if str(body.get('status_code')) != '0':
        return []
    out: List[Dict[str, str]] = []
    for item in body.get('result') or []:
        name = str(item.get('name') or '').strip()
        title = str(item.get('title') or '').strip()
        if not name:
            continue
        question = name if '概念' in name else f'{name}概念'
        out.append({
            'question': question,
            'label': _hot_query_label(title or name, 36),
            'category': '未来大事',
        })
    return out


def _matches_iwencai_type(question: str, querytype: str) -> bool:
    text = str(question or '')
    if querytype == 'stock':
        exclude = ['港股', '美股', 'US', 'HK', '基金', '可转债', '新三板', '期货', '外汇', '宏观', '理财']
        return not any(kw in text for kw in exclude)
    if querytype == 'azhishu':
        return '指数' in text
    keywords = IWENCAI_TYPE_KEYWORDS.get(querytype) or []
    return any(kw in text for kw in keywords)


def _append_hot_query(
    bucket: List[Dict[str, Any]],
    seen: set,
    *,
    question: str,
    category: str,
    label: Optional[str] = None,
) -> None:
    question = str(question or '').replace('\n', ' ').strip()
    if not question or question in seen:
        return
    seen.add(question)
    bucket.append({
        'question': question,
        'label': label or _hot_query_label(question),
        'category': category,
    })


def fetch_iwencai_hot_queries(querytype: str = 'stock', limit: int = 30) -> Dict[str, Any]:
    """获取问财 screener 热搜问句（按品类）。"""
    querytype = str(querytype or 'stock').strip() or 'stock'
    type_map = {item['value']: item['label'] for item in IWENCAI_SCOPE_TYPES}
    if querytype not in type_map:
        return {'success': False, 'error': f'不支持的问财品类：{querytype}'}

    limit = max(1, min(int(limit or 30), 80))
    groups: List[Dict[str, Any]] = []
    seen: set = set()

    def _add_group(group_id: str, label: str, items: List[Dict[str, Any]]) -> None:
        if items:
            groups.append({'id': group_id, 'label': label, 'queries': items})

    try:
        if querytype == 'stock':
            hype_items: List[Dict[str, Any]] = []
            for item in _fetch_iwencai_hype_concepts():
                _append_hot_query(
                    hype_items,
                    seen,
                    question=item['question'],
                    category=item['category'],
                    label=item.get('label'),
                )
            _add_group('hype', '今天炒什么', hype_items)

            event_items: List[Dict[str, Any]] = []
            for item in _fetch_iwencai_lurk_calendar():
                _append_hot_query(
                    event_items,
                    seen,
                    question=item['question'],
                    category=item['category'],
                    label=item.get('label'),
                )
            _add_group('events', '未来大事', event_items)

        multi = _fetch_iwencai_routine_multi('wi-sr-query-v2')
        for tab_key, items in multi.items():
            category = IWENCAI_TAB_LABELS.get(tab_key, tab_key)
            group_items: List[Dict[str, Any]] = []
            for item in items or []:
                question = _extract_routine_question(item)
                if querytype != 'stock' and not _matches_iwencai_type(question, querytype):
                    continue
                _append_hot_query(group_items, seen, question=question, category=category)
            _add_group(tab_key, category, group_items)

        homepage_items: List[Dict[str, Any]] = []
        for item in _fetch_iwencai_routine_single('wi-hp-query'):
            question = _extract_routine_question(item)
            if not _matches_iwencai_type(question, querytype):
                continue
            _append_hot_query(homepage_items, seen, question=question, category='首页热点')
        _add_group('homepage', '首页热点', homepage_items)

        hint_items: List[Dict[str, Any]] = []
        for doc in _fetch_iwencai_query_hints(querytype):
            _append_hot_query(hint_items, seen, question=doc, category='概念热搜')
        _add_group('hints', '概念热搜', hint_items)
    except requests.RequestException as exc:
        return {'success': False, 'error': f'问财热搜请求失败：{exc}'}

    flat: List[Dict[str, Any]] = []
    for group in groups:
        flat.extend(group['queries'])

    if not flat:
        return {'success': False, 'error': f'问财热搜暂无数据（{type_map[querytype]}）'}

    queries = flat[:limit]
    allowed = {item['question'] for item in queries}
    trimmed_groups: List[Dict[str, Any]] = []
    for group in groups:
        items = [item for item in group['queries'] if item['question'] in allowed]
        if items:
            trimmed_groups.append({**group, 'queries': items})

    return {
        'success': True,
        'querytype': querytype,
        'querytype_label': type_map[querytype],
        'queries': queries,
        'groups': trimmed_groups or [{'id': 'all', 'label': '热搜', 'queries': queries}],
        'types': IWENCAI_SCOPE_TYPES,
        'source_url': IWENCAI_SCREENER_URL,
    }


if __name__ == '__main__':
    import json
    import sys

    profile = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        profile = sys.argv[1]
    out = sync_iwencai_cookie_from_chrome(save=True, profile=profile)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out.get('success') else 1)
