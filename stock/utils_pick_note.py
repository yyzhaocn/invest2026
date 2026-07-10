"""分组选股说明：Markdown 生成与读写。"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd

PICK_NOTES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'shared',
    'pick_notes',
)


def _ensure_notes_dir() -> str:
    os.makedirs(PICK_NOTES_DIR, exist_ok=True)
    return PICK_NOTES_DIR


def _note_filename(group_name: str) -> str:
    digest = hashlib.sha1(group_name.encode('utf-8')).hexdigest()[:12]
    safe = re.sub(r'[^\w\u4e00-\u9fff\-]+', '_', group_name).strip('_')[:48]
    return f'{safe}_{digest}.md' if safe else f'group_{digest}.md'


def pick_note_path(group_name: str) -> str:
    return os.path.join(_ensure_notes_dir(), _note_filename(group_name))


def get_group_pick_note(group_name: str) -> Optional[str]:
    path = pick_note_path(group_name)
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read().strip()
    return text or None


def set_group_pick_note(group_name: str, content: str) -> str:
    path = pick_note_path(group_name)
    _ensure_notes_dir()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content.rstrip() + '\n')
    return path


def delete_group_pick_note(group_name: str) -> bool:
    path = pick_note_path(group_name)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def _is_code_column(col_name: str) -> bool:
    c = str(col_name or '').strip()
    cl = c.lower()
    return cl in ('code', '代码', '股票代码') or c.endswith('代码') or c.endswith('Code')


def _sanitize_cell(text: str) -> str:
    return str(text).replace('|', '\\|').replace('\n', ' ')


def _is_news_blob_column(col_name: str) -> bool:
    c = str(col_name or '')
    return '资讯' in c or '关键词' in c


def _format_display_value(value: Any, col_name: str = '') -> str:
    """表格单元格：数值 round(,2)；大数用万/亿；科学计数法转中文单位。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''

    if _is_code_column(col_name):
        s = str(value).strip()
        if re.fullmatch(r'\d+\.0+', s):
            s = s.split('.')[0]
        return _sanitize_cell(s)

    s = str(value).strip()
    if not s or s.lower() in ('--', 'none', 'nan'):
        return _sanitize_cell(s)

    if _is_news_blob_column(col_name):
        try:
            try:
                from stock.utils_iwencai import decode_iwencai_blob
            except ImportError:
                from utils_iwencai import decode_iwencai_blob
            decoded = decode_iwencai_blob(s)
            if decoded:
                return _sanitize_cell(decoded)
        except Exception:
            pass

    num = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        num = float(value)
    else:
        try:
            try:
                from stock.utils_iwencai import decode_iwencai_blob, _looks_like_b64_json
            except ImportError:
                from utils_iwencai import decode_iwencai_blob, _looks_like_b64_json
            if _looks_like_b64_json(s):
                decoded = decode_iwencai_blob(s)
                if decoded:
                    return _sanitize_cell(decoded)
        except Exception:
            pass
        try:
            num = float(s)
        except (TypeError, ValueError):
            return _sanitize_cell(s)

    if pd.isna(num):
        return ''

    abs_num = abs(num)
    if abs_num >= 1e8:
        return f'{num / 1e8:.2f}亿'
    if abs_num >= 1e4:
        return f'{num / 1e4:.2f}万'
    return f'{num:.2f}'


def _pick_note_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """选股说明表格：去掉与 code 重复的列。"""
    out = df.copy()
    cols = [str(c) for c in out.columns]
    drop = []
    if 'code' in cols and '股票代码' in cols:
        drop.append('股票代码')
    if drop:
        out = out.drop(columns=drop, errors='ignore')
    return out


def dataframe_to_markdown_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ''
    cols = [str(c) for c in df.columns]
    lines = [
        '| ' + ' | '.join(cols) + ' |',
        '| ' + ' | '.join(['---'] * len(cols)) + ' |',
    ]
    for _, row in df.iterrows():
        cells = [_format_display_value(row[c], c) for c in df.columns]
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def build_pick_note_markdown(
    group_name: str,
    df: pd.DataFrame,
    *,
    query: str = '',
    conditions: Optional[List[str]] = None,
    source: str = '问财',
    csv_path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    now = now or datetime.now()
    lines = [
        f'# 选股说明 · {group_name}',
        '',
        f'- **来源**：{source}',
        f'- **生成时间**：{now.strftime("%Y-%m-%d %H:%M:%S")}',
    ]
    if query:
        lines.append(f'- **问句**：{query}')
    if conditions:
        lines.append('- **筛选条件**：')
        for item in conditions:
            lines.append(f'  - {item}')
    if csv_path:
        lines.append(f'- **CSV**：`{csv_path}`')
    lines.extend(['', '## 选股结果', ''])
    table = dataframe_to_markdown_table(_pick_note_display_df(df))
    if table:
        lines.append(table)
    else:
        lines.append('（无表格数据）')
    lines.append('')
    return '\n'.join(lines)


def build_import_pick_note_markdown(
    group_name: str,
    raw_text: str,
    *,
    parsed_count: int = 0,
    added: int = 0,
    skipped: int = 0,
    now: Optional[datetime] = None,
) -> str:
    """批量导入：以粘贴原文作为选股说明。"""
    now = now or datetime.now()
    body = str(raw_text or '').rstrip()
    lines = [
        f'# 选股说明 · {group_name}',
        '',
        '- **来源**：批量导入',
        f'- **导入时间**：{now.strftime("%Y-%m-%d %H:%M:%S")}',
        f'- **识别**：{parsed_count} 只，新增 {added} 只，跳过 {skipped} 只',
        '',
        '## 导入原文',
        '',
        '```',
        body,
        '```',
        '',
    ]
    return '\n'.join(lines)


def markdown_to_html(md: str) -> str:
    """轻量 Markdown → HTML（标题、列表、表格）。"""
    if not md:
        return ''
    lines = md.splitlines()
    out: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('# '):
            out.append(f'<h3>{_esc(line[2:].strip())}</h3>')
            i += 1
            continue
        if line.startswith('## '):
            out.append(f'<h4>{_esc(line[3:].strip())}</h4>')
            i += 1
            continue
        if line.strip().startswith('```'):
            fence = line.strip()
            i += 1
            code_lines: List[str] = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            out.append(f'<pre class="pick-note-pre">{_esc(chr(10).join(code_lines))}</pre>')
            continue
        if line.startswith('| ') and i + 1 < len(lines) and re.match(r'^\|\s*[-:| ]+\|$', lines[i + 1].strip()):
            table_lines = [line]
            i += 2
            while i < len(lines) and lines[i].startswith('| '):
                table_lines.append(lines[i])
                i += 1
            out.append(_md_table_to_html(table_lines))
            continue
        if line.startswith('- '):
            out.append('<ul>')
            while i < len(lines) and lines[i].startswith('- '):
                out.append(f'<li>{_inline_md(lines[i][2:].strip())}</li>')
                i += 1
            out.append('</ul>')
            continue
        if line.startswith('  - '):
            out.append('<ul>')
            while i < len(lines) and (lines[i].startswith('- ') or lines[i].startswith('  - ')):
                text = lines[i].lstrip('- ').strip()
                out.append(f'<li>{_inline_md(text)}</li>')
                i += 1
            out.append('</ul>')
            continue
        out.append(f'<p>{_inline_md(line.strip())}</p>')
        i += 1
    return '\n'.join(out)


def _esc(text: str) -> str:
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def _inline_md(text: str) -> str:
    text = _esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    return text


def _md_table_to_html(rows: List[str]) -> str:
    if len(rows) < 2:
        return ''
    header = [c.strip() for c in rows[0].strip('|').split('|')]
    body_rows = rows[1:]
    html = ['<div class="pick-note-table-wrap"><table class="pick-note-table"><thead><tr>']
    for cell in header:
        html.append(f'<th>{_esc(cell)}</th>')
    html.append('</tr></thead><tbody>')
    for row in body_rows:
        cells = [c.strip() for c in row.strip('|').split('|')]
        html.append('<tr>')
        for cell in cells:
            html.append(f'<td>{_esc(cell)}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
    return ''.join(html)


def save_group_picks_with_note(
    mgr,
    group_name: str,
    df: pd.DataFrame,
    *,
    query: str = '',
    conditions: Optional[List[str]] = None,
    source: str = '问财',
    csv_path: Optional[str] = None,
    date_key: Optional[str] = None,
) -> Dict[str, Any]:
    """写入分组股票 + 选股说明 Markdown。"""
    try:
        try:
            from stock.module_cache_policy import ensure_dated_pick_group_name
        except ImportError:
            from module_cache_policy import ensure_dated_pick_group_name
        group_name = ensure_dated_pick_group_name(group_name)
    except Exception:
        group_name = str(group_name or '').strip()

    now = datetime.now()
    date_key = date_key or now.strftime('%Y-%m-%d')

    mgr._reload_from_disk()
    if group_name not in mgr.config.sections():
        mgr.create_group(group_name)

    code_col = next((c for c in ('代码', 'code', '股票代码') if c in df.columns), None)
    name_col = next((c for c in ('名称', 'name', '股票名称', '股票简称') if c in df.columns), None)
    if not code_col:
        raise ValueError('DataFrame 缺少代码列')

    df = df.copy()
    df[code_col] = (
        df[code_col].astype(str)
        .str.replace(r'\.0$', '', regex=True)
        .str.zfill(6)
    )
    codes = df[code_col].astype(str).str.zfill(6).tolist()
    mgr.config.set(group_name, date_key, ','.join(codes))
    if name_col:
        for _, row in df.iterrows():
            try:
                mgr._remember_group_property(
                    str(row[code_col]).zfill(6),
                    group_name,
                    str(row[name_col]),
                )
            except Exception:
                pass
    mgr._save()

    note_md = build_pick_note_markdown(
        group_name,
        df,
        query=query,
        conditions=conditions,
        source=source,
        csv_path=csv_path,
        now=now,
    )
    note_path = set_group_pick_note(group_name, note_md)
    return {
        'group_name': group_name,
        'date_key': date_key,
        'count': len(codes),
        'csv': csv_path,
        'pick_note_path': note_path,
    }
