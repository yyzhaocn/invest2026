# -*- coding: utf-8 -*-
import requests
import json
import os
import time
import re
from pathlib import Path
from fund.config import HEADERS_COMMON, URL_FUND_LIST, URL_FUND_DETAIL_BASE

class FundFetcher:
    def __init__(self, data_dir='fund/data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key):
        return self.data_dir / f"{key}.json"

    def _load_cache(self, key):
        path = self._get_cache_path(key)
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load cache for {key}: {e}")
        return None

    def _save_cache(self, key, data):
        path = self._get_cache_path(key)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save cache for {key}: {e}")

    def fetch_fund_list(self):
        """
        Fetches the complete list of funds from fundcode_search.js.
        Format in JS: var r = [["000001","HXCZ","华夏成长","混合型","HUAXIACHENGZHANG"],...];
        """
        # Check cache (1 day validity)
        cache_key = 'fund_list_latest'
        cache_file = self._get_cache_path(cache_key)
        if cache_file.exists():
            if time.time() - cache_file.stat().st_mtime < 86400:
                print("Loading fund list from cache...")
                return self._load_cache(cache_key)

        print("Fetching fund list from source...")
        try:
            response = requests.get(URL_FUND_LIST, headers=HEADERS_COMMON)
            response.raise_for_status()
            content = response.text
            
            # Extract array content: var r = [[...]];
            start = content.find('[')
            end = content.rfind(']')
            if start != -1 and end != -1:
                json_str = content[start:end+1]
                # The data is a valid JSON array of arrays
                data = json.loads(json_str)
                
                # Transform to list of dicts for easier usage
                # ["000001","HXCZ","华夏成长","混合型","HUAXIACHENGZHANG"]
                fund_list = []
                for item in data:
                    if len(item) >= 5:
                        fund_list.append({
                            'code': item[0],
                            'abbr': item[1],
                            'name': item[2],
                            'type': item[3],
                            'pinyin': item[4]
                        })
                
                self._save_cache(cache_key, fund_list)
                return fund_list
            else:
                print("Could not parse fund list structure.")
                return []
        except Exception as e:
            print(f"Error fetching fund list: {e}")
            return []

    def fetch_fund_detail(self, fund_code):
        """
        Fetches detailed info for a fund from pingzhongdata.
        Returns a dict with holding stocks and basic info.
        """
        cache_key = f'fund_detail_{fund_code}'
        cache_file = self._get_cache_path(cache_key)
        if cache_file.exists():
            if time.time() - cache_file.stat().st_mtime < 86400:
                return self._load_cache(cache_key)

        url = URL_FUND_DETAIL_BASE.format(fund_code)
        # print(f"Fetching details for {fund_code}...")
        try:
            response = requests.get(url, headers=HEADERS_COMMON)
            response.raise_for_status()
            content = response.text
            
            data = {}
            
            # Extract stock codes: var stockCodes=["000001",...];
            stock_match = re.search(r'var stockCodes=\[([^\]]+)\];', content)
            if stock_match:
                stock_list = [x.strip().strip('"').strip("'") for x in stock_match.group(1).split(',')]
                data['stock_codes'] = stock_list
            else:
                data['stock_codes'] = []

            # Extract basic info
            name_match = re.search(r'var fS_name = "([^"]+)";', content)
            if name_match:
                data['name'] = name_match.group(1)
            
            # Extract holders structure (optional, holding distribution)
            # var Data_holderStructure ={"categories":["..."],"series":[...]};
            # We can extract if needed, but let's stick to core requirements first.
            
            # Extract Fund Manager basic info just in case
            # var Data_currentFundManager =[...]
            mgr_match = re.search(r'var Data_currentFundManager =(\[.*?\]);', content, re.DOTALL)
            if mgr_match:
                try:
                    # Clean up JSON string if needed (comments etc)
                    mgr_json = mgr_match.group(1)
                    # Simple cleanup
                    mgr_json = re.sub(r'/\*.*?\*/', '', mgr_json)
                    mgr_data = json.loads(mgr_json)
                    data['managers'] = mgr_data
                except:
                    pass

            self._save_cache(cache_key, data)
            return data

        except Exception as e:
            print(f"Error fetching fund detail for {fund_code}: {e}")
            return None

if __name__ == '__main__':
    fetcher = FundFetcher()
    print("Fetching list...")
    funds = fetcher.fetch_fund_list()
    print(f"Found {len(funds)} funds.")
    if funds:
        sample = funds[0]
        print(f"Sample: {sample}")
        print(f"Fetching detail for {sample['code']}...")
        detail = fetcher.fetch_fund_detail(sample['code'])
        print(f"Detail keys: {detail.keys()}")
        if 'stock_codes' in detail:
            print(f"Stocks: {detail['stock_codes']}")
