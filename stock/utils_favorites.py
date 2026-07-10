"""
自选股管理工具模块
负责自选股的增删改查操作
"""
import os
import re
import glob
import csv
import configparser
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
import sys

# 配置文件路径
FAVORITES_INI = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'shared',
    'favoriteStocks.ini'
)

IMPORT_GROUP = '导入'

_NAME_SUFFIXES = ('股份', '集团', '控股', '有限', '公司', '科技', '发展', '实业', '医药', '生物')
_STOCK_MAP_CACHE: Optional[Dict[str, str]] = None


def _is_valid_stock_code(code: str) -> bool:
    return isinstance(code, str) and len(code) == 6 and code.isdigit() and not code.startswith('9')


def _normalize_stock_code(code_str: str) -> Optional[str]:
    digits = re.sub(r'\D', '', str(code_str).strip())
    if not digits:
        return None
    code = digits[-6:].zfill(6) if len(digits) >= 6 else digits.zfill(6)
    return code if _is_valid_stock_code(code) else None


def _parse_ini_stock_codes(raw: str) -> List[str]:
    """Parse comma-separated stock codes from ini; tolerate list-literal corruption."""
    import ast

    text = str(raw).strip()
    if not text:
        return []

    if text.startswith('['):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (list, tuple)):
                codes: List[str] = []
                for item in parsed:
                    if item is None:
                        continue
                    codes.extend(_parse_ini_stock_codes(str(item)))
                return codes
        except (ValueError, SyntaxError):
            pass

    codes: List[str] = []
    seen: Set[str] = set()
    for part in text.split(','):
        part = part.strip().strip("'\"[]")
        if not part:
            continue
        code = _normalize_stock_code(part)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _parse_ini_int(raw: str) -> int:
    """Parse pin flags from ini; tolerate list-literal corruption like \"['1']\"."""
    import ast

    text = str(raw).strip()
    if text.startswith('['):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, (list, tuple)) and parsed:
                text = str(parsed[0]).strip()
        except (ValueError, SyntaxError):
            pass
    text = text.strip().strip("'\"[] ")
    return int(text) if text.isdigit() else 0


def _normalize_stock_name(name: str) -> str:
    """标准化股票名称：去空格、全角转半角。"""
    name = str(name).strip()
    name = re.sub(r'[\s\u3000]+', '', name)
    chars = []
    for ch in name:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        else:
            chars.append(ch)
    return ''.join(chars)


def _add_to_stock_map(stock_map: Dict[str, str], name: str, code: str) -> None:
    if not _is_valid_stock_code(code):
        return
    name = _normalize_stock_name(name)
    if not name or not re.search(r'[\u4e00-\u9fff]', name):
        return
    stock_map[name] = code
    stock_map[code] = name


def _name_to_flexible_pattern(name: str) -> str:
    """允许名称字符间有空格的宽松匹配模式。"""
    chars = list(_normalize_stock_name(name))
    if not chars:
        return re.escape(name)
    return r'\s*'.join(re.escape(c) for c in chars)


def _load_stock_map(limit: int = 3, use_cache: bool = True) -> Dict[str, str]:
    """从 quote / sector / codelist 加载名称/代码双向映射。"""
    global _STOCK_MAP_CACHE
    if use_cache and _STOCK_MAP_CACHE is not None:
        return _STOCK_MAP_CACHE

    stock_map: Dict[str, str] = {}
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    stock_dir = os.path.dirname(os.path.abspath(__file__))

    def load_quote_csv(path: str) -> None:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = _normalize_stock_code(row.get('股票代码', ''))
                    name = row.get('股票名称', '')
                    if code and name:
                        _add_to_stock_map(stock_map, name, code)
        except Exception:
            pass

    def load_sector_csv(path: str) -> None:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pairs = [
                        (row.get('f128', ''), row.get('f140', '')),
                        (row.get('f207', ''), row.get('f208', '')),
                    ]
                    for name, code_raw in pairs:
                        code = _normalize_stock_code(code_raw)
                        if code and name:
                            _add_to_stock_map(stock_map, name, code)
        except Exception:
            pass

    codelist_path = os.path.join(stock_dir, 'eastmoney_stock_codes_api.csv')
    if os.path.exists(codelist_path):
        try:
            with open(codelist_path, 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    code = _normalize_stock_code(row.get('code') or row.get('股票代码', ''))
                    name = row.get('name') or row.get('股票名称', '')
                    if code and name:
                        _add_to_stock_map(stock_map, name, code)
        except Exception:
            pass

    quote_files: List[str] = []
    root_quotes = glob.glob(os.path.join(base_dir, 'generated/quote_*.csv'))
    em_quotes = glob.glob(os.path.join(base_dir, 'generated/em/**/quote_*.csv'), recursive=True)
    root_quotes.sort(key=os.path.getmtime, reverse=True)
    em_quotes.sort(key=os.path.getmtime, reverse=True)
    quote_files.extend(root_quotes)
    quote_files.extend(em_quotes)
    seen_paths: Set[str] = set()
    loaded = 0
    for path in quote_files:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        before = len([k for k in stock_map if not k.isdigit()])
        load_quote_csv(path)
        after = len([k for k in stock_map if not k.isdigit()])
        if after > before:
            loaded += 1
        if loaded >= limit:
            break

    for pattern in ('sector_list_industry.csv', 'sector_list_concept.csv'):
        sector_path = os.path.join(base_dir, 'generated/em', pattern)
        if os.path.exists(sector_path):
            load_sector_csv(sector_path)

    _STOCK_MAP_CACHE = stock_map
    return stock_map


def _extract_explicit_code(token: str) -> Optional[str]:
    """仅识别明确的 6 位代码 token（不做短数字补零）。"""
    token = str(token).strip()
    m = re.match(r'^(?:SH|SZ|sh|sz)?([0-8]\d{5})$', token)
    if m:
        return m.group(1)
    return None


def _resolve_name_to_code(name: str, full_lookup: Dict[str, str], token_lookup: Dict[str, str]) -> Optional[str]:
    norm = _normalize_stock_name(name)
    if norm in full_lookup:
        return full_lookup[norm]
    if norm in token_lookup:
        return token_lookup[norm]
    return None


def _clean_property_text(text: str) -> str:
    """清洗属性描述文本。"""
    text = str(text).strip()
    text = re.sub(r'^[\s"\'""「『]+|[\s"\'""」』]+$', '', text)
    text = re.sub(r'[\s\u3000]+', ' ', text).strip()
    return text


def _extract_list_entries(content: str) -> List[Tuple[str, int, Optional[str]]]:
    """从「1、旭光电子----氮化铝…」等清单行提取 (名称, 位置, 属性)。"""
    results: List[Tuple[str, int, Optional[str]]] = []
    line_pattern = re.compile(
        r'(?:^|\n)\s*(\d+\s*[、.．)\]]\s*.+?)(?=\n\s*\d+\s*[、.．)\]]|\Z)',
        re.MULTILINE,
    )
    name_pattern = re.compile(
        r'^\d+\s*[、.．)\]]\s*'
        r'([\*ST\u4e00-\u9fff][\*ST\u4e00-\u9fffA-Za-z]{1,11})'
    )
    for m in line_pattern.finditer(content):
        line = m.group(1).strip()
        prop_text: Optional[str] = None
        name_part = line
        split_match = re.split(r'\s*[-—–|｜/\\]{2,}\s*', line, maxsplit=1)
        if len(split_match) == 2:
            name_part = split_match[0].strip()
            prop_text = _clean_property_text(split_match[1])
            if not prop_text:
                prop_text = None
        nm = name_pattern.match(name_part.strip())
        if not nm:
            continue
        name = _normalize_stock_name(nm.group(1))
        if len(name) >= 2:
            offset = m.start(1) + name_part.find(nm.group(1))
            results.append((name, offset, prop_text))
    return results


def _extract_parenthesized_codes(content: str) -> List[Tuple[str, int, str]]:
    """提取括号内的明确代码，如 贵州茅台(600519)。"""
    results: List[Tuple[str, int, str]] = []
    for m in re.finditer(
        r'([\u4e00-\u9fff\*ST][\u4e00-\u9fffA-Za-z\*ST]{1,11})?\s*[（(]\s*(?:SH|SZ|sh|sz)?([0-8]\d{5})\s*[)）]',
        content,
    ):
        name = _normalize_stock_name(m.group(1) or '')
        results.append((m.group(2), m.start(), name))
    return results


def _build_name_lookup(stock_map: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    构建两个查找表：
    - full_lookup: 仅完整名称，用于全文子串匹配
    - token_lookup: 含去后缀变体，用于 token 精确匹配
    """
    full_lookup: Dict[str, str] = {}
    token_lookup: Dict[str, str] = {}
    names = [k for k in stock_map.keys() if not k.isdigit()]
    for name in names:
        code = stock_map[name]
        full_lookup[name] = code
        token_lookup[name] = code
        for suffix in _NAME_SUFFIXES:
            if name.endswith(suffix) and len(name) > len(suffix) + 1:
                short = name[:-len(suffix)]
                if len(short) >= 2 and short not in token_lookup:
                    token_lookup[short] = code
    return full_lookup, token_lookup


def parse_stocks_detail_from_text(
    text: str,
    stock_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """
    从文本解析股票，返回去重后的列表（按首次出现顺序）。
    每项: {code, name, source}，source 为 list / code / name / pattern。
    """
    if not text or not str(text).strip():
        return []

    if stock_map is None:
        stock_map = _load_stock_map()

    content = str(text).strip()
    full_lookup, token_lookup = _build_name_lookup(stock_map)
    hits: List[Tuple[str, int, str, str]] = []
    code_properties: Dict[str, List[str]] = {}

    def add_property(code: str, prop: Optional[str]) -> None:
        if not code or not prop:
            return
        props = code_properties.setdefault(code, [])
        if prop not in props:
            props.append(prop)

    def add_hit(code: Optional[str], pos: int, source: str, matched: str = '') -> None:
        if not code or not _is_valid_stock_code(code):
            return
        name = stock_map.get(code, '')
        if isinstance(name, str) and name.isdigit():
            name = matched or code
        hits.append((code, pos, source, matched or name))

    for name, pos, prop in _extract_list_entries(content):
        code = _resolve_name_to_code(name, full_lookup, token_lookup)
        if code:
            add_hit(code, pos, 'list', name)
            add_property(code, prop)

    for code, pos, name in _extract_parenthesized_codes(content):
        add_hit(code, pos, 'name', name or stock_map.get(code, code))

    for m in re.finditer(r'(?:SH|SZ|sh|sz)([0-8]\d{5})', content):
        add_hit(m.group(1), m.start(), 'code', m.group(0))

    for m in re.finditer(
        r'(?:SH|SZ|sh|sz)?([0-8]\d{5})\s*[：:\-—]\s*([\u4e00-\u9fff\*ST][\u4e00-\u9fffA-Za-z\*ST]{1,11})',
        content,
    ):
        add_hit(m.group(1), m.start(), 'pattern', _normalize_stock_name(m.group(2)))

    for line in re.split(r'[\r\n]+', content):
        line = line.strip()
        if not line or re.match(r'^\d+\s*[、.．)\]]', line):
            continue
        line_names = sorted(full_lookup.keys(), key=len, reverse=True)
        for name in line_names:
            if len(name) < 3:
                continue
            patterns = [re.escape(name), _name_to_flexible_pattern(name)]
            seen_patterns: Set[str] = set()
            for pattern in patterns:
                if pattern in seen_patterns:
                    continue
                seen_patterns.add(pattern)
                try:
                    for m in re.finditer(pattern, line):
                        add_hit(full_lookup[name], m.start(), 'name', name)
                except re.error:
                    continue

    tokens = re.split(r'[\s,，;；、|。\t\r\n/\\]+', content)
    for token in tokens:
        token = token.strip()
        if not token or re.fullmatch(r'\d{1,2}', token):
            continue
        pos = content.find(token)
        code = _extract_explicit_code(token)
        if code:
            add_hit(code, pos, 'code', token)
            continue
        norm_token = _normalize_stock_name(token)
        if norm_token in token_lookup:
            add_hit(token_lookup[norm_token], pos, 'name', norm_token)
            continue
        for suffix in (')', '）', ']', '】', '>', '》'):
            if norm_token.endswith(suffix):
                trimmed = norm_token.rstrip(suffix)
                if trimmed in token_lookup:
                    add_hit(token_lookup[trimmed], pos, 'name', trimmed)

    hits.sort(key=lambda x: x[1])

    seen_codes: Set[str] = set()
    result: List[Dict[str, str]] = []
    for code, _pos, source, matched in hits:
        if code in seen_codes:
            continue
        seen_codes.add(code)
        name = stock_map.get(code, matched)
        if isinstance(name, str) and name.isdigit():
            name = matched if matched and not matched.isdigit() else code
        result.append({
            'code': code,
            'name': name,
            'source': source,
            'properties': list(code_properties.get(code, [])),
        })
    return result


def parse_stocks_from_text(text: str, stock_map: Optional[Dict[str, str]] = None) -> List[str]:
    """从粘贴文本中解析股票代码（去重，保留首次出现顺序）。"""
    return [item['code'] for item in parse_stocks_detail_from_text(text, stock_map)]


def _get_property_store():
    try:
        from stock.utils_stock_properties import get_stock_property_store
    except ImportError:
        from utils_stock_properties import get_stock_property_store
    return get_stock_property_store()


def get_import_stock_map() -> Dict[str, str]:
    """合并本地 quote 映射与 utils_reem 映射，供导入解析使用。"""
    stock_map = dict(_load_stock_map())
    try:
        from stock.utils_reem import load_stock_name_code_map
        name_map = load_stock_name_code_map()
        for name, code in name_map.items():
            code_str = str(code).strip()
            if len(code_str) == 6 and code_str.isdigit() and not code_str.startswith('9'):
                _add_to_stock_map(stock_map, name, code_str)
    except Exception:
        pass
    return stock_map


class FavoritesManager:
    """自选股管理器"""
    
    def __init__(self, ini_path: str = FAVORITES_INI):
        self.ini_path = ini_path
        self.config = configparser.ConfigParser()
        self._ensure_file_exists()
        self._load()
    
    def _ensure_file_exists(self):
        """确保INI文件存在"""
        if not os.path.exists(self.ini_path):
            os.makedirs(os.path.dirname(self.ini_path), exist_ok=True)
            with open(self.ini_path, 'w', encoding='utf-8') as f:
                f.write('[默认]\n')
    
    def _backup_ini(self, tagged_suffix: Optional[str] = None) -> Optional[str]:
        """覆盖写入 .bak；删除等操作可额外保留带后缀的历史副本。"""
        if not os.path.exists(self.ini_path):
            return None
        bak_path = self.ini_path + '.bak'
        tagged_path = None
        try:
            import shutil
            shutil.copy2(self.ini_path, bak_path)
            if tagged_suffix:
                tagged_path = f'{self.ini_path}.bak.{tagged_suffix}'
                shutil.copy2(self.ini_path, tagged_path)
                self._prune_tagged_backups(max_keep=50)
        except Exception:
            return None
        return tagged_path

    def _prune_tagged_backups(self, max_keep: int = 50) -> None:
        pattern = self.ini_path + '.bak.delete_*'
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        for old in files[max_keep:]:
            try:
                os.remove(old)
            except OSError:
                pass

    def _try_restore_from_backup(self) -> bool:
        """Restore from .bak when the live ini was truncated to empty defaults."""
        bak_path = self.ini_path + '.bak'
        if not os.path.exists(bak_path):
            return False
        bak = configparser.ConfigParser()
        bak.read(bak_path, encoding='utf-8')
        if len(bak.sections()) <= 2:
            return False
        if len(self.config.sections()) > 2:
            return False
        self.config = bak
        for group in ('默认', IMPORT_GROUP):
            if group not in self.config.sections():
                self.config.add_section(group)
        return True

    def _load(self):
        """加载配置文件"""
        self.config = configparser.ConfigParser()
        existed = os.path.exists(self.ini_path)
        if existed:
            self.config.read(self.ini_path, encoding='utf-8')
            self._try_restore_from_backup()
        changed = False
        for group in ('默认', IMPORT_GROUP):
            if group not in self.config.sections():
                self.config.add_section(group)
                changed = True
        # 仅新建文件时落盘，避免 reload 时用内存空配置覆盖磁盘
        if changed and not existed:
            self._save()

    def _reload_from_disk(self):
        """从磁盘重新加载，使外部写入的分组/股票对运行中的服务可见。"""
        self._load()
    
    def _sanitize_ini(self) -> bool:
        """Rewrite corrupted list-literal values to plain comma-separated codes / ints."""
        changed = False
        for group_name in self.config.sections():
            for key in list(self.config.options(group_name)):
                raw = self.config.get(group_name, key)
                if key.startswith('_') and not key.startswith('_pin_'):
                    continue
                if key.startswith('_pin_'):
                    clean = str(_parse_ini_int(raw))
                    if raw.strip() != clean:
                        self.config.set(group_name, key, clean)
                        changed = True
                else:
                    codes = _parse_ini_stock_codes(raw)
                    clean = ','.join(codes)
                    if raw.strip() != clean:
                        if clean:
                            self.config.set(group_name, key, clean)
                        else:
                            self.config.remove_option(group_name, key)
                        changed = True
        return changed

    def _save(self):
        """保存配置文件"""
        self._backup_ini()
        self._sanitize_ini()
        with open(self.ini_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def get_all_groups(self) -> List[str]:
        """获取所有分组"""
        self._reload_from_disk()
        return self.config.sections()
    
    def create_group(self, group_name: str) -> bool:
        """创建新分组"""
        self._reload_from_disk()
        if group_name in self.config.sections():
            return False
        self.config.add_section(group_name)
        self._save()
        return True
    
    def delete_group(self, group_name: str) -> Tuple[bool, Optional[str]]:
        """删除分组（不允许删除默认分组）。删除前备份 .bak 及带时间戳副本。"""
        self._reload_from_disk()
        if group_name == '默认':
            return False, None
        if group_name not in self.config.sections():
            return False, None

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe = re.sub(r'[^\w\u4e00-\u9fff]+', '_', group_name).strip('_')[:48] or 'group'
        backup_path = self._backup_ini(tagged_suffix=f'delete_{safe}_{ts}')

        self.config.remove_section(group_name)
        self._save()
        try:
            try:
                from stock.utils_pick_note import delete_group_pick_note
            except ImportError:
                from utils_pick_note import delete_group_pick_note
            delete_group_pick_note(group_name)
        except Exception:
            pass
        return True, backup_path

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """重命名分组（保留股票列表与置顶标记）。"""
        self._reload_from_disk()
        if old_name not in self.config.sections():
            return False
        if new_name in self.config.sections():
            return False
        if old_name == '默认' or new_name == '默认':
            return False
        self.config.add_section(new_name)
        for key, value in self.config.items(old_name):
            self.config.set(new_name, key, value)
        self.config.remove_section(old_name)
        self._save()
        return True
    
    def add_stock(self, stock_code: str, group_name: str = '默认') -> bool:
        """
        添加股票到指定分组
        以当前日期为key，股票代码为value
        组内不允许重复
        """
        if group_name not in self.config.sections():
            self.config.add_section(group_name)
        
        today = datetime.now().strftime('%Y-%m-%d')

        stock_code = _normalize_stock_code(stock_code) or stock_code
        if not _is_valid_stock_code(stock_code):
            return False
        
        # 获取当前组内所有股票
        existing_stocks = self.get_stocks_in_group(group_name)
        
        # 检查是否已存在
        if stock_code in existing_stocks:
            return False

        # 添加或更新
        if self.config.has_option(group_name, today):
            stock_list = _parse_ini_stock_codes(self.config.get(group_name, today))
            if stock_code in stock_list:
                return False
            stock_list.append(stock_code)
            self.config.set(group_name, today, ','.join(stock_list))
        else:
            self.config.set(group_name, today, stock_code)
        
        self._save()
        self._remember_group_property(stock_code, group_name)
        return True

    def _remember_group_property(self, stock_code: str, group_name: str, name: str = '') -> None:
        try:
            _get_property_store().set_group_as_first_property(stock_code, group_name, name)
        except Exception:
            pass
    
    def remove_stock(self, stock_code: str, group_name: str = '默认') -> bool:
        """从指定分组删除股票"""
        self._reload_from_disk()
        if group_name not in self.config.sections():
            return False
        
        # 遍历该分组的所有日期，删除指定股票
        modified = False
        for date_key in self.config.options(group_name):
            if date_key.startswith('_pin_'):
                continue
            stocks = self.config.get(group_name, date_key)
            stock_list = _parse_ini_stock_codes(stocks)
            
            if stock_code in stock_list:
                stock_list.remove(stock_code)
                modified = True
                
                if stock_list:
                    self.config.set(group_name, date_key, ','.join(stock_list))
                else:
                    self.config.remove_option(group_name, date_key)
        
        if modified:
            for pin_type in ('pinned', 'top_pinned'):
                pin_key = f'_pin_{pin_type}_{stock_code}'
                if self.config.has_option(group_name, pin_key):
                    self.config.remove_option(group_name, pin_key)

            has_stock_keys = any(
                not key.startswith('_')
                for key in self.config.options(group_name)
            )
            if not has_stock_keys and not self.config.has_option(group_name, '_empty'):
                self.config.set(group_name, '_empty', '1')

            self._save()
        return modified
    
    def get_stocks_in_group(self, group_name: str = '默认') -> Set[str]:
        """获取指定分组内的所有股票（去重）"""
        self._reload_from_disk()
        if group_name not in self.config.sections():
            return set()
        
        all_stocks = set()
        for date_key in self.config.options(group_name):
            if date_key.startswith('_'):
                continue
            stocks = self.config.get(group_name, date_key)
            for code in _parse_ini_stock_codes(stocks):
                all_stocks.add(code)
        
        return all_stocks
    
    def get_stocks_with_dates(self, group_name: str = '默认') -> List[Dict]:
        """
        获取指定分组内的股票及其添加日期
        返回格式: [{'code': 'xxx', 'date': 'yyyy-mm-dd', 'pinned': 0, 'top_pinned': 0}, ...]
        """
        self._reload_from_disk()
        if group_name not in self.config.sections():
            return []
        
        result = []
        for date_key in self.config.options(group_name):
            if date_key.startswith('_'):
                continue
            
            stocks = self.config.get(group_name, date_key)
            stock_list = _parse_ini_stock_codes(stocks)
            
            for stock in stock_list:
                # 检查置顶状态
                pinned = self._get_pin_status(group_name, stock, 'pinned')
                top_pinned = self._get_pin_status(group_name, stock, 'top_pinned')
                
                result.append({
                    'code': stock,
                    'date': date_key,
                    'pinned': pinned,
                    'top_pinned': top_pinned
                })
        
        # 排序：固顶 > 置顶 > 日期降序
        result.sort(key=lambda x: (
            -x['top_pinned'],
            -x['pinned'],
            x['date']
        ), reverse=True)
        
        return result
    
    def _get_pin_status(self, group_name: str, stock_code: str, pin_type: str) -> int:
        """获取置顶状态"""
        key = f'_pin_{pin_type}_{stock_code}'
        if self.config.has_option(group_name, key):
            return _parse_ini_int(self.config.get(group_name, key))
        return 0
    
    def set_pin(self, stock_code: str, group_name: str = '默认', 
                pin_type: str = 'pinned', value: int = 1) -> bool:
        """
        设置置顶状态
        pin_type: 'pinned' (置顶) 或 'top_pinned' (固顶)
        value: 1 (置顶) 或 0 (取消置顶)
        """
        if group_name not in self.config.sections():
            return False
        
        # 确保股票在该组内
        if stock_code not in self.get_stocks_in_group(group_name):
            return False
        
        key = f'_pin_{pin_type}_{stock_code}'
        
        if value == 1:
            self.config.set(group_name, key, '1')
        else:
            if self.config.has_option(group_name, key):
                self.config.remove_option(group_name, key)
        
        self._save()
        return True
    
    def get_all_stocks_across_groups(self) -> List[Dict]:
        """获取所有分组内的股票（去重），附带所属分组列表。"""
        stock_groups: Dict[str, List[str]] = {}
        for group in self.get_all_groups():
            for code in self.get_stocks_in_group(group):
                code = str(code).zfill(6)
                stock_groups.setdefault(code, [])
                if group not in stock_groups[code]:
                    stock_groups[code].append(group)
        return [
            {'code': code, 'groups': groups}
            for code, groups in sorted(stock_groups.items())
        ]

    def is_stock_in_group(self, stock_code: str, group_name: str = '默认') -> bool:
        """检查股票是否在指定分组中"""
        return stock_code in self.get_stocks_in_group(group_name)

    def get_group_pick_note(self, group_name: str) -> Optional[str]:
        try:
            try:
                from stock.utils_pick_note import get_group_pick_note as _get
            except ImportError:
                from utils_pick_note import get_group_pick_note as _get
            return _get(group_name)
        except Exception:
            return None

    def set_group_pick_note(self, group_name: str, content: str) -> Optional[str]:
        try:
            try:
                from stock.utils_pick_note import set_group_pick_note as _set
            except ImportError:
                from utils_pick_note import set_group_pick_note as _set
            return _set(group_name, content)
        except Exception:
            return None

    def import_stocks_from_text(
        self,
        text: str,
        group_name: str = IMPORT_GROUP,
        create_group: bool = False,
        stock_map: Optional[Dict[str, str]] = None,
        save_pick_note: bool = True,
    ) -> Dict:
        """
        从文本批量导入股票到指定分组。
        返回: {group_name, parsed, added, skipped, added_codes, skipped_codes, pick_note_path}
        """
        group_name = (group_name or IMPORT_GROUP).strip() or IMPORT_GROUP

        if create_group and group_name not in ('默认',):
            try:
                try:
                    from stock.module_cache_policy import ensure_dated_pick_group_name
                except ImportError:
                    from module_cache_policy import ensure_dated_pick_group_name
                group_name = ensure_dated_pick_group_name(group_name)
            except Exception:
                pass

        if create_group or group_name not in self.config.sections():
            if group_name not in self.config.sections():
                self.config.add_section(group_name)
                self._save()

        stocks = parse_stocks_detail_from_text(text, stock_map)
        codes = [s['code'] for s in stocks]
        added_codes: List[str] = []
        skipped_codes: List[str] = []

        for code in codes:
            if self.add_stock(code, group_name):
                added_codes.append(code)
            else:
                skipped_codes.append(code)

        properties_added = 0
        try:
            properties_added = _get_property_store().apply_group_and_parsed_stocks(
                stocks, group_name
            )
        except Exception:
            pass

        pick_note_path = None
        if save_pick_note and str(text or '').strip():
            try:
                try:
                    from stock.utils_pick_note import (
                        build_import_pick_note_markdown,
                        set_group_pick_note,
                    )
                except ImportError:
                    from utils_pick_note import (
                        build_import_pick_note_markdown,
                        set_group_pick_note,
                    )
                note_md = build_import_pick_note_markdown(
                    group_name,
                    text,
                    parsed_count=len(codes),
                    added=len(added_codes),
                    skipped=len(skipped_codes),
                )
                pick_note_path = set_group_pick_note(group_name, note_md)
            except Exception:
                pass

        return {
            'group_name': group_name,
            'parsed': codes,
            'stocks': stocks,
            'added': len(added_codes),
            'skipped': len(skipped_codes),
            'added_codes': added_codes,
            'skipped_codes': skipped_codes,
            'properties_added': properties_added,
            'pick_note_path': pick_note_path,
        }


# 全局实例
_favorites_manager = None


def get_favorites_manager() -> FavoritesManager:
    """获取自选股管理器实例（单例）"""
    global _favorites_manager
    if _favorites_manager is None:
        _favorites_manager = FavoritesManager()
    return _favorites_manager


if __name__ == '__main__':
    # 测试代码
    manager = FavoritesManager()
    
    print("所有分组:", manager.get_all_groups())
    
    # 添加测试股票
    manager.add_stock('000001', '默认')
    manager.add_stock('600000', '默认')
    manager.add_stock('002916', '默认')
    
    print("默认分组股票:", manager.get_stocks_in_group('默认'))
    
    # 创建新分组
    manager.create_group('科技股')
    manager.add_stock('000001', '科技股')
    
    print("科技股分组:", manager.get_stocks_in_group('科技股'))
    
    # 测试置顶
    manager.set_pin('000001', '默认', 'top_pinned', 1)
    manager.set_pin('600000', '默认', 'pinned', 1)
    
    print("默认分组股票（含排序）:", manager.get_stocks_with_dates('默认'))
