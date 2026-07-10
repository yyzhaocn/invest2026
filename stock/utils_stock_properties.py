"""
股票属性记忆模块
持久化存储每只股票的标签/属性（如题材、逻辑），供后续策略分类使用。
"""
import os
import json
from typing import Dict, List, Optional

PROPERTIES_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'shared',
    'stockProperties.json',
)


class StockPropertyStore:
    """股票属性存储（单例，内存缓存 + JSON 持久化）。"""

    _instance: Optional['StockPropertyStore'] = None

    def __init__(self, path: str = PROPERTIES_JSON):
        self.path = path
        self._cache: Dict[str, Dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._cache = data
                    return
            except Exception:
                pass
        self._cache = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def _normalize_code(self, code: str) -> str:
        return str(code).strip().zfill(6)

    def add_properties(
        self,
        code: str,
        properties: List[str],
        name: str = '',
    ) -> List[str]:
        """追加属性（去重），返回该股票全部属性。"""
        code = self._normalize_code(code)
        if code not in self._cache:
            self._cache[code] = {'name': name or code, 'properties': []}

        entry = self._cache[code]
        if name:
            entry['name'] = name

        existing = set(entry['properties'])
        for prop in properties:
            prop = str(prop).strip()
            if prop and prop not in existing:
                entry['properties'].append(prop)
                existing.add(prop)

        self._save()
        return list(entry['properties'])

    def get_properties(self, code: str) -> List[str]:
        code = self._normalize_code(code)
        return list(self._cache.get(code, {}).get('properties', []))

    def get_entry(self, code: str) -> Dict:
        code = self._normalize_code(code)
        entry = self._cache.get(code, {})
        return {
            'code': code,
            'name': entry.get('name', code),
            'properties': list(entry.get('properties', [])),
        }

    def get_batch(self, codes: List[str]) -> Dict[str, List[str]]:
        return {self._normalize_code(c): self.get_properties(c) for c in codes}

    def set_group_as_first_property(
        self,
        code: str,
        group_name: str,
        name: str = '',
    ) -> List[str]:
        """将分组名设为第一属性（持久化，已存在则移到首位）。"""
        code = self._normalize_code(code)
        group_name = str(group_name).strip()
        if not group_name:
            return self.get_properties(code)

        if code not in self._cache:
            self._cache[code] = {'name': name or code, 'properties': []}

        entry = self._cache[code]
        if name:
            entry['name'] = name

        props = entry['properties']
        if group_name in props:
            props.remove(group_name)
        props.insert(0, group_name)
        self._save()
        return list(props)

    def rename_group_in_properties(self, old_name: str, new_name: str) -> int:
        """将属性列表中的旧分组名替换为新分组名。"""
        old_name = str(old_name).strip()
        new_name = str(new_name).strip()
        if not old_name or not new_name or old_name == new_name:
            return 0
        updated = 0
        for entry in self._cache.values():
            props = entry.get('properties', [])
            if old_name not in props:
                continue
            entry['properties'] = list(dict.fromkeys(
                new_name if p == old_name else p for p in props
            ))
            updated += 1
        if updated:
            self._save()
        return updated

    def apply_group_and_parsed_stocks(
        self,
        stocks: List[Dict],
        group_name: str,
    ) -> int:
        """写入分组名为第一属性，并追加解析出的其他属性。"""
        added = 0
        group_name = str(group_name).strip()
        for item in stocks:
            code = item.get('code')
            if not code:
                continue
            name = item.get('name', '')
            before = set(self.get_properties(code))

            if group_name:
                self.set_group_as_first_property(code, group_name, name)

            extra = [p for p in (item.get('properties') or []) if p and p != group_name]
            if extra:
                self.add_properties(code, extra, name)

            after = set(self.get_properties(code))
            added += len(after - before)
        return added

    def apply_from_parsed_stocks(self, stocks: List[Dict], group_name: str = '') -> int:
        """兼容旧接口：有 group_name 时走完整逻辑。"""
        if group_name:
            return self.apply_group_and_parsed_stocks(stocks, group_name)
        added = 0
        for item in stocks:
            props = item.get('properties') or []
            if not props:
                continue
            before = len(self.get_properties(item['code']))
            self.add_properties(item['code'], props, item.get('name', ''))
            after = len(self.get_properties(item['code']))
            added += max(0, after - before)
        return added


_store: Optional[StockPropertyStore] = None


def get_stock_property_store() -> StockPropertyStore:
    global _store
    if _store is None:
        _store = StockPropertyStore()
    return _store
