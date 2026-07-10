"""东方财富条件选股（xuangu.eastmoney.com）查询。"""

from __future__ import annotations

import random
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

XUANGU_PREFIX_RE = re.compile(r'^#\s*(.+)$', re.DOTALL)
XUANGU_SEARCH_URL = (
    'https://np-tjxg-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code'
)
XUANGU_RESULT_URL = 'https://xuangu.eastmoney.com/Result?type=stock&color=w&id={xc_id}'
XUANGU_HOT_URL = 'https://np-ipick.eastmoney.com/recommend/stock/heat/ranking'
XUANGU_PAGE_URL = 'https://xuangu.eastmoney.com/?color=w&type=stock'
XUANGU_PAGE_SIZE = 200

_SKIP_COLUMN_KEYS = {'SERIAL', 'IN_OPTIONAL', 'MARKET_NUM'}


def parse_xuangu_query(text: str) -> Optional[str]:
    """若文本以 # 开头，返回东财选股问句。"""
    if not text:
        return None
    m = XUANGU_PREFIX_RE.match(str(text).strip())
    return m.group(1).strip() if m else None


def _xuangu_headers() -> Dict[str, str]:
    return {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://xuangu.eastmoney.com/',
        'Origin': 'https://xuangu.eastmoney.com',
        'Content-Type': 'application/json',
    }


def _build_search_payload(query: str, page_no: int, page_size: int) -> Dict[str, Any]:
    return {
        'keywordNew': query,
        'pageSize': page_size,
        'pageNo': page_no,
        'fingerprint': uuid.uuid4().hex,
        'matchWord': '',
        'timestamp': int(time.time() * 1000),
        'shareToGuba': False,
        'calcAvgChg': True,
        'requestId': uuid.uuid4().hex,
        'dynamicType': 'COMMON',
        'allCode': True,
        'ownSelectAll': False,
        'client': 'WEB',
        'biz': 'web_ai_select_stocks',
        'ignoreRightsField': False,
        'needAmbiguousSuggest': False,
        'notExecuteCompute': False,
    }


def _extract_conditions(data: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for item in data.get('responseConditionList') or []:
        desc = str(item.get('describe') or '').strip()
        if desc:
            out.append(desc)
    total = (data.get('result') or {}).get('meta') or {}
    if isinstance(total, dict):
        desc = str(total.get('describe') or '').strip()
        if desc and desc not in out:
            out.append(desc)
    return out


def _rows_to_dataframe(result: Dict[str, Any]) -> pd.DataFrame:
    columns = result.get('columns') or []
    col_map = {
        str(c.get('key')): str(c.get('title') or c.get('key') or '')
        for c in columns
        if c.get('key')
    }
    rows: List[Dict[str, Any]] = []
    for item in result.get('dataList') or []:
        row: Dict[str, Any] = {}
        for key, value in item.items():
            if key in _SKIP_COLUMN_KEYS:
                continue
            title = col_map.get(key, key)
            if title in ('序号',):
                continue
            row[title] = value
        if row:
            rows.append(row)
    return pd.DataFrame(rows)


def _normalize_xuangu_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename = {}
    for col in out.columns:
        c = str(col)
        if c in ('代码', '股票代码', 'SECURITY_CODE'):
            rename[col] = '股票代码'
        elif c in ('名称', '股票简称', 'SECURITY_SHORT_NAME'):
            rename[col] = '股票简称'
    if rename:
        out = out.rename(columns=rename)

    if '股票代码' in out.columns:
        out['股票代码'] = (
            out['股票代码'].astype(str)
            .str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
            .str.replace(r'\.0$', '', regex=True)
            .str.zfill(6)
        )
    elif '代码' in out.columns:
        out['股票代码'] = (
            out['代码'].astype(str)
            .str.replace(r'\.(SH|SZ|BJ)$', '', regex=True)
            .str.replace(r'\.0$', '', regex=True)
            .str.zfill(6)
        )
    if '股票简称' not in out.columns and '名称' in out.columns:
        out['股票简称'] = out['名称']
    return out


def _df_to_raw_text(query: str, df: pd.DataFrame, *, result_url: Optional[str] = None) -> str:
    try:
        from stock.utils_pick_note import dataframe_to_markdown_table, _pick_note_display_df
    except ImportError:
        from utils_pick_note import dataframe_to_markdown_table, _pick_note_display_df

    display_df = _pick_note_display_df(df)
    lines = [f'东财选股：{query}', '']
    if result_url:
        lines.extend([f'结果页：{result_url}', ''])
    lines.extend(['## 选股结果', ''])
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


def _build_result_from_df(
    query: str,
    df: pd.DataFrame,
    *,
    conditions: Optional[List[str]] = None,
    xc_id: Optional[str] = None,
    total: Optional[int] = None,
) -> Dict[str, Any]:
    df = _normalize_xuangu_df(df)
    if '股票代码' not in df.columns:
        return {'success': False, 'error': '东财选股结果中未找到股票代码列'}

    result_url = XUANGU_RESULT_URL.format(xc_id=xc_id) if xc_id else None
    raw_text = _df_to_raw_text(query, df, result_url=result_url)
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
        'count': total if total is not None else len(stocks),
        'stocks': stocks,
        'raw_text': raw_text,
        'dataframe': df,
        'conditions': conditions or [],
        'xc_id': xc_id,
        'result_url': result_url,
    }


def _fetch_xuangu_page(query: str, page_no: int, page_size: int) -> Dict[str, Any]:
    resp = requests.post(
        XUANGU_SEARCH_URL,
        headers=_xuangu_headers(),
        json=_build_search_payload(query, page_no, page_size),
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if str(body.get('code')) != '100':
        msg = body.get('msg') or body.get('message') or '东财选股查询失败'
        raise ValueError(f'{msg}：{query}')
    return body.get('data') or {}


def fetch_xuangu_results(query: str) -> Dict[str, Any]:
    """查询东方财富条件选股并返回解析后的股票列表与原文。"""
    query = str(query or '').strip()
    if not query:
        return {'success': False, 'error': '东财选股问句不能为空'}

    try:
        first = _fetch_xuangu_page(query, page_no=1, page_size=XUANGU_PAGE_SIZE)
    except requests.RequestException as exc:
        return {'success': False, 'error': f'东财选股网络请求失败：{exc}'}
    except ValueError as exc:
        return {'success': False, 'error': str(exc)}

    result = first.get('result') or {}
    total = int(result.get('total') or 0)
    df = _rows_to_dataframe(result)
    if total > len(df):
        page_no = 2
        while len(df) < total:
            try:
                page_data = _fetch_xuangu_page(query, page_no=page_no, page_size=XUANGU_PAGE_SIZE)
            except (requests.RequestException, ValueError):
                break
            page_result = page_data.get('result') or {}
            page_df = _rows_to_dataframe(page_result)
            if page_df.empty:
                break
            df = pd.concat([df, page_df], ignore_index=True)
            page_no += 1
            if page_no > 20:
                break

    if df.empty:
        return {'success': False, 'error': f'东财选股未返回结果，请检查问句：{query}'}

    return _build_result_from_df(
        query,
        df,
        conditions=_extract_conditions(first),
        xc_id=first.get('xcId'),
        total=total or len(df),
    )


def resolve_xuangu_import_text(text: str) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    若 text 为东财选股触发格式（# 问句），查询并返回 (替换后的原文, meta)。
    否则返回 (原文, None)。
    """
    query = parse_xuangu_query(text)
    if not query:
        return text, None
    result = fetch_xuangu_results(query)
    if not result.get('success'):
        raise ValueError(result.get('error') or '东财选股查询失败')
    return result['raw_text'], result


def _hot_query_label(question: str, max_len: int = 40) -> str:
    label = str(question or '').split(';')[0].strip()
    if len(label) > max_len:
        return label[: max_len - 1] + '…'
    return label


def fetch_xuangu_hot_queries(limit: int = 10) -> Dict[str, Any]:
    """获取东财条件选股实时热搜问句。"""
    limit = max(1, min(int(limit or 10), 20))
    try:
        resp = requests.get(
            XUANGU_HOT_URL,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                ),
                'Referer': XUANGU_PAGE_URL,
            },
            params={
                'trace': f'{random.random()}{int(time.time() * 1000)}',
                'client': 'WEB',
                'biz': 'web_smart_tag',
            },
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        return {'success': False, 'error': f'东财热搜请求失败：{exc}'}

    if str(body.get('code')) != '1':
        msg = body.get('message') or body.get('msg') or '东财热搜返回异常'
        return {'success': False, 'error': msg}

    rows = body.get('data') or []
    queries: List[Dict[str, Any]] = []
    for item in sorted(rows, key=lambda x: int(x.get('rank') or 0), reverse=True):
        question = str(item.get('question') or '').strip()
        if not question:
            continue
        queries.append({
            'rank': int(item.get('rank') or 0),
            'question': question,
            'label': _hot_query_label(question),
            'heat_value': item.get('heatValue'),
        })
        if len(queries) >= limit:
            break

    if not queries:
        return {'success': False, 'error': '东财热搜暂无数据'}

    return {
        'success': True,
        'queries': queries,
        'source_url': XUANGU_PAGE_URL,
    }


if __name__ == '__main__':
    import json
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else '今日涨幅2%的股票'
    out = fetch_xuangu_results(q)
    print(json.dumps(
        {
            'success': out.get('success'),
            'query': out.get('query'),
            'count': out.get('count'),
            'result_url': out.get('result_url'),
            'sample': (out.get('stocks') or [])[:5],
            'error': out.get('error'),
        },
        ensure_ascii=False,
        indent=2,
    ))
