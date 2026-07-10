import requests
print("Script starting...")
import pandas as pd
import json
import glob
import time
import shutil
import re
import random
from tqdm import tqdm
from utils_reem import get_capreal_ext
from datetime import datetime, timedelta
import os
import argparse

md_dir_home = '/Volumes/ASME/myobs/0syncs/stock/'
md_dir_office = os.path.expanduser('~/Public/myobs/0syncs/stock/')

def get_md_dir():
    """动态获取基础目录路径"""
    return md_dir_home if os.path.exists(md_dir_home) else md_dir_office
    
def parse_response(response_text):
    """解析API响应"""
    try:
        pattern = r'jQuery\d+_\d+\((.*)\)'
        match = re.search(pattern, response_text)
        if not match:
            # Try direct JSON parsing if regex fails
            try:
                return json.loads(response_text)
            except:
                return None
        json_str = match.group(1)
        return json.loads(json_str)
    except Exception as e:
        print(f"解析响应时出错: {e}")
        return None

def get_sector_list(sector_type='industry', page_size=100):
    """
    获取板块列表
    sector_type: 'industry' (行业) or 'concept' (概念)
    """
    cookies = {
        'qgqp_b_id': '125fef21bf721e77a102bb668642803e',
        'st_si': '53976007936223',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_nvi': 'whttZFKXNnA_km71gtVGJfd20',
        'nid': '007529139545699f3d5bcde2db867b0f',
        'nid_create_time': '1754089134200',
        'gvi': 'ipOZoFN7KPqbDqt6RfknYcbcb',
        'gvi_create_time': '1754089134200',
        'rskey': 'TCgQ4ZTBQTUltcnNWTEUyU1FQbFR6S29PQT09PTnz9',
        'st_asi': 'delete',
        'st_pvi': '59192766921846',
        'st_sp': '2025-07-13%2011%3A14%3A04',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '191',
        'st_psi': '20250803162545905-113200301201-0814983901',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://quote.eastmoney.com/center/gridlist.html',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    }

    # Determine fs parameter based on sector type
    if sector_type == 'industry':
        fs = 'm:90+t:2+f:!50'
    else:  # concept
        fs = 'm:90+t:3+f:!50'

    all_data = []
    page = 1
    
    timestamp = int(time.time() * 1000)
    params = {
        'np': '1', 'fltt': '1', 'invt': '2',
        'cb': f'jQuery{timestamp}_{timestamp}',
        'fs': fs,
        'fields': 'f12,f13,f14,f1,f2,f4,f3,f152,f20,f8,f104,f105,f128,f140,f141,f207,f208,f209,f136,f222,f62',
        'fid': 'f3', 'pn': page, 'pz': page_size, 'po': '1', # Sort by change percent desc
        'dect': '1', 'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'wbp2u': '|0|0|0|web', '_': str(timestamp),
    }

    try:
        response = requests.get(
            'https://push2.eastmoney.com/api/qt/clist/get',
            params=params, cookies=cookies, headers=headers, timeout=10
        )
        response.raise_for_status()
        
        data = parse_response(response.text)
        if not data or 'data' not in data:
            print("无法获取板块数据")
            return pd.DataFrame()
        
        total_pages = (data['data']['total'] + page_size - 1) // page_size
        print(f"{sector_type}板块总页数: {total_pages}")
        
        if 'diff' in data['data']:
            all_data.extend(data['data']['diff'])
        
        # Fetch remaining pages
        for page in range(2, total_pages + 1):
            timestamp = int(time.time() * 1000)
            params['pn'] = page
            params['cb'] = f'jQuery{timestamp}_{timestamp}'
            params['_'] = str(timestamp)
            
            try:
                response = requests.get(
                    'https://push2.eastmoney.com/api/qt/clist/get',
                    params=params, cookies=cookies, headers=headers, timeout=10
                )
                data = parse_response(response.text)
                if data and 'data' in data and 'diff' in data['data']:
                    all_data.extend(data['data']['diff'])
                time.sleep(0.1)
            except Exception as e:
                print(f"获取第{page}页时出错: {e}")
                continue
        
        if all_data:
            df = pd.DataFrame(all_data)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        print(f"获取板块列表时出错: {e}")
        return pd.DataFrame()

def is_trading_time():
    """
    Check if current time is within trading hours (Mon-Fri 9:30-11:30, 13:00-15:00)
    """
    now = datetime.now()
    if now.weekday() >= 5: # Saturday, Sunday
        return False
        
    t = now.time()
    # 9:30 - 11:30
    scan_morning_start = datetime.strptime('09:30', '%H:%M').time()
    scan_morning_end = datetime.strptime('11:30', '%H:%M').time()
    
    # 13:00 - 15:00
    scan_afternoon_start = datetime.strptime('13:00', '%H:%M').time()
    scan_afternoon_end = datetime.strptime('15:00', '%H:%M').time()
    
    return (scan_morning_start <= t <= scan_morning_end) or \
           (scan_afternoon_start <= t <= scan_afternoon_end)


def get_cached_sector_list(sector_type='industry', force_refresh=False):
    """
    获取板块列表（带缓存）
    缓存策略:
    - 交易时间: 1小时过期
    - 非交易时间: 只要是今天的缓存就使用（不刷新）
    
    Args:
        sector_type: 'industry' (行业) or 'concept' (概念)
        force_refresh: 强制刷新缓存
    
    Returns:
        DataFrame containing sector list
    """
    cache_dir = '../generated/em'
    cache_file = os.path.join(cache_dir, f'sector_list_{sector_type}.csv')
    
    # Check if cache exists
    if not force_refresh and os.path.exists(cache_file):
        try:
            file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
            file_age_sec = (datetime.now() - file_mtime).total_seconds()
            file_date = file_mtime.strftime('%Y%m%d')
            today_str = datetime.now().strftime('%Y%m%d')
            
            is_fresh = False
            
            if is_trading_time():
                # Trading time: 1 hour expiry
                if file_age_sec < 3600:
                    is_fresh = True
                    print(f"Trading time: Cache is fresh (< 1h old)")
                else:
                    print(f"Trading time: Cache expired (> 1h old)")
            else:
                # Non-trading time: valid if from today
                if file_date == today_str:
                    is_fresh = True
                    print(f"Non-trading time: Cache from today used")
                else:
                    # If fetching allowed, logic falls through to API fetch
                    pass

            if is_fresh:
                print(f"Loading {sector_type} sector list from cache: {cache_file}")
                return pd.read_csv(cache_file, encoding='utf-8-sig')
        except Exception as e:
            print(f"Error loading cache: {e}, fetching from API...")
    
    # Fetch from API
    print(f"Fetching {sector_type} sector list from API...")
    df = get_sector_list(sector_type, page_size=200)
    
    if not df.empty:
        # Apply field mapping and formatting before caching
        # Map fields to Chinese
        mapping = {
            'f12': '股票代码',
            'f13': '市场类型',
            'f14': '股票名称',
            'f1': '状态',
            'f2': '最新价',
            'f3': '涨跌幅',
            'f4': '涨跌额',
            'f8': '换手率',
            'f20': '总市值',
            'f62': '主力净流入', # Will be formatted to 100 million
            'f152': '振幅',
            'f184': '主力净流入占比'
        }
        
        # Rename columns that exist in the mapping
        df = df.rename(columns=mapping)
        
        # Format Capital Inflow (主力净流入) to 1E8 (亿)
        if '主力净流入' in df.columns:
            try:
                df['主力净流入'] = pd.to_numeric(df['主力净流入'], errors='coerce') / 100000000
                df['主力净流入'] = df['主力净流入'].round(2) # Keep 2 decimal places
            except Exception as e:
                print(f"Warning: Error formatting capital inflow: {e}")

        # Save to cache
        try:
            os.makedirs(cache_dir, exist_ok=True)
            df.to_csv(cache_file, index=False, encoding='utf-8-sig')
            print(f"Cached {sector_type} sector list to: {cache_file}")
        except Exception as e:
            print(f"Warning: Could not cache sector list: {e}")
    
    return df

def lookup_sector_code(sector_name, sector_type=None):
    """
    根据板块名称查找板块代码（支持模糊匹配）
    
    Args:
        sector_name: 板块名称（如 '盲盒经济'）
        sector_type: 'industry' or 'concept'，None时搜索两种类型
    
    Returns:
        (sector_code, sector_type) tuple, or (None, None) if not found
    """
    from difflib import get_close_matches
    
    # Try both types if not specified
    types_to_try = [sector_type] if sector_type else ['concept', 'industry']
    
    for stype in types_to_try:
        df = get_cached_sector_list(stype)
        
        if df.empty:
            continue
        
        # Exact match
        exact = df[df['股票名称'] == sector_name]
        if not exact.empty:
            code = exact.iloc[0]['股票代码']
            print(f"Found exact match: {sector_name} ({code}) in {stype}")
            return code, stype
        
        # Fuzzy match
        all_names = df['股票名称'].tolist()
        matches = get_close_matches(sector_name, all_names, n=5, cutoff=0.6)
        
        if matches:
            print(f"\n'{sector_name}' not found in {stype}. Did you mean:")
            for i, match in enumerate(matches, 1):
                code = df[df['股票名称'] == match].iloc[0]['股票代码']
                change = df[df['股票名称'] == match].iloc[0].get('涨跌幅', 0)
                try:
                    change_pct = float(change) / 100
                    print(f"  {i}. {match} ({code}) [{change_pct:+.2f}%]")
                except:
                    print(f"  {i}. {match} ({code})")
            print(f"  0. Cancel")
            
            try:
                choice = input(f"\nSelect option (0-{len(matches)}): ").strip()
                idx = int(choice)
                if idx == 0:
                    print("Cancelled by user")
                    return None, None
                if 1 <= idx <= len(matches):
                    selected_name = matches[idx - 1]
                    selected_code = df[df['股票名称'] == selected_name].iloc[0]['股票代码']
                    print(f"Selected: {selected_name} ({selected_code})")
                    return selected_code, stype
                else:
                    print("Invalid selection")
            except (ValueError, EOFError, KeyboardInterrupt):
                print("\nCancelled")
                return None, None
    
    print(f"Error: Sector '{sector_name}' not found in any sector type")
    return None, None

STOCK_FIELD_MAPPING = {
    # 行业/概念板块下股票列表字段映射
    'f12': '股票代码',
    'f13': '市场类型',
    'f14': '股票名称',
    'f1': '状态',
    'f2': '最新价',
    'f3': '涨跌幅',
    'f4': '涨跌额',
    'f8': '换手率',
    'f20': '总市值',
    'f62': '主力净流入',
    'f152': '振幅',
    'f184': '主力净流入占比',
}

def get_sector_stocks(sector_code, sort_field='f3', top_n=5, return_df=False, mapped_header=False):
    """
    获取指定板块的前N只股票，或所有股票（当top_n=None时）
    sort_field: 排序字段 
        f3: 涨跌幅 (大涨股)
        f8: 换手率 (热点股)
        f62: 主力净流入 (龙头股)
    top_n: 返回前N只股票，如果为None则返回所有股票
    
    字段含义参考 STOCK_FIELD_MAPPING，例如：
    - f12/f14: 股票代码/名称
    - f2/f3/f4: 现价/涨跌幅/涨跌额（f2、f3、f4 需要 ÷100）
    - f8: 换手率（÷100）；f62: 主力净流入；f184: 主力净流入占比
    return_df: 是否返回 DataFrame（默认 False 保持原有列表返回）
    mapped_header: 当 return_df=True 时，是否使用中文表头映射（默认 False）
    """
    cookies = {
        'qgqp_b_id': '125fef21bf721e77a102bb668642803e',
        'st_si': '53976007936223',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_nvi': 'whttZFKXNnA_km71gtVGJfd20',
        'nid': '007529139545699f3d5bcde2db867b0f',
        'nid_create_time': '1754089134200',
        'gvi': 'ipOZoFN7KPqbDqt6RfknYcbcb',
        'gvi_create_time': '1754089134200',
        'rskey': 'TCgQ4ZTBQTUltcnNWTEUyU1FQbFR6S29PQT09PTnz9',
        'st_asi': 'delete',
        'st_pvi': '59192766921846',
        'st_sp': '2025-07-13%2011%3A14%3A04',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '191',
        'st_psi': '20250803162545905-113200301201-0814983901',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': f'https://quote.eastmoney.com/center/gridlist.html',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    }

    # Construct fs parameter for the specific sector
    fs = f'b:{sector_code}+f:!50'
    
    # Ensure we have all necessary fields
    # f3: Change%, f8: Turnover, f62: Net Inflow
    fields = 'f12,f13,f14,f1,f2,f4,f3,f152,f20,f8,f62,f184'
    
    all_stocks = []
    page = 1
    page_size = 100 if top_n is None else top_n
    
    while True:
        timestamp = int(time.time() * 1000)
        params = {
            'np': '1', 'fltt': '1', 'invt': '2',
            'cb': f'jQuery{timestamp}_{timestamp}',
            'fs': fs,
            'fields': fields,
            'fid': sort_field, 
            'pn': str(page),
            'pz': str(page_size), 
            'po': '1', # Descending
            'dect': '1', 'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'wbp2u': '|0|0|0|web', '_': str(timestamp),
        }

        try:
            response = requests.get(
                'https://push2.eastmoney.com/api/qt/clist/get',
                params=params, cookies=cookies, headers=headers, timeout=10
            )
            response.raise_for_status()
            
            data = parse_response(response.text)
            if not data or 'data' not in data:
                break
                
            if 'diff' not in data['data'] or not data['data']['diff']:
                break
                
            all_stocks.extend(data['data']['diff'])
            
            # If we only want top_n, return after first page
            if top_n is not None:
                subset = all_stocks[:top_n]
                if return_df:
                    df = pd.DataFrame(subset)
                    if mapped_header:
                        df = df.rename(columns={k: v for k, v in STOCK_FIELD_MAPPING.items() if k in df.columns})
                    return df
                if mapped_header:
                    return [{STOCK_FIELD_MAPPING.get(k, k): v for k, v in item.items()} for item in subset]
                return subset
            
            # Check if there are more pages
            total = data['data'].get('total', 0)
            if len(all_stocks) >= total:
                break
                
            page += 1
            time.sleep(0.1)  # Rate limiting
            
        except Exception as e:
            print(f"获取板块{sector_code}股票时出错: {e}")
            break
            
    if return_df:
        df = pd.DataFrame(all_stocks)
        if mapped_header:
            df = df.rename(columns={k: v for k, v in STOCK_FIELD_MAPPING.items() if k in df.columns})
        return df
    if mapped_header:
        return [{STOCK_FIELD_MAPPING.get(k, k): v for k, v in item.items()} for item in all_stocks]
    return all_stocks

def _sanitize_filename(name: str) -> str:
    """将名称转换为安全的文件名"""
    return re.sub(r'[\\/*?:"<>|]', '_', str(name)).strip() or "unknown"

def _get_sector_store_dir(sector_type: str) -> str:
    """
    生成板块成分股缓存目录
    目标路径形如: {md_dir}/sector/{sector_type}/
    """
    base_dir = os.path.join(get_md_dir(), 'sector')
    target_dir = os.path.join(base_dir, sector_type)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

def _is_stale(path: str, stale_days: int) -> bool:
    """判断文件是否超过 stale_days 天未更新"""
    if not os.path.exists(path):
        return True
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mtime > timedelta(days=stale_days)

def _load_exclude_list() -> set:
    """加载 bk_exclude.tsv 中的排除列表"""
    exclude_set = set()
    try:
        exclude_path = os.path.join(os.path.dirname(__file__), 'bk_exclude.tsv')
        if os.path.exists(exclude_path):
            exdf = pd.read_csv(exclude_path, sep='\t', comment='#')
            # 标准化列名
            exdf.columns = [c.strip() for c in exdf.columns]
            name_col = '名称' if '名称' in exdf.columns else exdf.columns[0]
            flag_col = '排除显示' if '排除显示' in exdf.columns else exdf.columns[1]
            # 取需要排除的名称集合（排除显示==1）
            to_exclude = exdf[exdf[flag_col].astype(str).str.strip() == '1'][name_col].astype(str).str.strip()
            exclude_set = set(to_exclude)
    except Exception as e:
        print(f"读取排除列表时出错: {e}")
    return exclude_set

def update_sector_list(sector_type='industry', random_missing=False, stale_days=7, max_updates=None):
    """
    根据板块列表维护本地成分股CSV缓存
    - 文件路径: {md_dir}/sector/{sector_type}/{bk_name}_{bk_code}.csv
    - 仅当文件缺失或超过 stale_days 天才更新
    - random_missing=True 时，仅随机更新最多5个缺失文件
    - 遵守 bk_exclude.tsv 排除规则
    """
    print(f"\n开始更新 {sector_type} 板块成分股列表缓存（缓存有效期: {stale_days} 天）...")
    sectors_df = get_sector_list(sector_type, page_size=200)
    if sectors_df.empty:
        print("未获取到板块列表，跳过缓存更新")
        return

    # 加载排除列表
    exclude_set = _load_exclude_list()
    if exclude_set:
        original_count = len(sectors_df)
        sectors_df = sectors_df[~sectors_df['f14'].astype(str).str.strip().isin(exclude_set)]
        excluded_count = original_count - len(sectors_df)
        if excluded_count > 0:
            print(f"已排除 {excluded_count} 个板块（根据 bk_exclude.tsv）")

    store_dir = _get_sector_store_dir(sector_type)
    sector_entries = []
    for _, row in sectors_df.iterrows():
        sector_code = row.get('f12')
        sector_name = row.get('f14')
        safe_name = _sanitize_filename(sector_name)
        filename = f"{safe_name}_{sector_code}.csv"
        path = os.path.join(store_dir, filename)
        sector_entries.append({
            'code': sector_code,
            'name': sector_name,
            'path': path,
            'exists': os.path.exists(path)
        })

    # 确定需要更新的列表
    if random_missing:
        missing = [s for s in sector_entries if not s['exists']]
        random.shuffle(missing)
        targets = missing[:5]
        max_updates = 5  # random_missing 模式固定为5个
    else:
        # 只更新缺失或过期的文件（已存在且在 stale_days 天内不更新）
        targets = [s for s in sector_entries if _is_stale(s['path'], stale_days)]
        # 默认限制为10个，除非明确指定了 max_updates
        if max_updates is None:
            max_updates = 10
        if max_updates > 0:
            targets = targets[:max_updates]

    if not targets:
        print(f"所有文件均在有效期内（{stale_days} 天），无需更新。")
        return

    print(f"预计更新 {len(targets)} 个板块成分股文件（限制最多 {max_updates} 个，缓存有效期 {stale_days} 天），保存目录: {store_dir}")

    for item in targets:
        code = item['code']
        name = item['name']
        try:
            df = get_sector_stocks(code, sort_field='f3', top_n=None, return_df=True, mapped_header=True)
        except Exception as e:
            print(f"获取 {name}({code}) 成分股失败: {e}")
            continue

        if df is None or df.empty:
            print(f"{name}({code}) 未返回数据，跳过")
            continue

        try:
            df.to_csv(item['path'], index=False, encoding='utf-8-sig')
            print(f"✓ 已保存 {name}({code}) -> {item['path']}")
        except Exception as e:
            print(f"保存 {name}({code}) 至 {item['path']} 失败: {e}")
        time.sleep(0.2)  # 轻度限速，避免接口过载

def format_stock_list(stocks, value_key, suffix=''):
    """格式化股票列表输出"""
    result = []
    for s in stocks:
        val = s.get(value_key)
        # Divide by 100 for f3 (change %) and f8 (turnover rate)
        if value_key in ['f3', 'f8'] and val is not None:
            try:
                val = float(val) / 100
            except (ValueError, TypeError):
                pass
        result.append(f"{s.get('f14')}({val}{suffix})")
    return ", ".join(result)

def analyze_all_performers(sector_type='industry', top_sectors_count=10):
    """
    分析所有股票，获取每个板块中每只股票的排名
    Returns: DataFrame containing all stock data
    """
    print(f"正在获取 {sector_type} 板块列表...")
    by_sector_df = get_sector_list(sector_type, page_size=100)
    
    if by_sector_df.empty:
        print(f"未获取到 {sector_type} 板块数据")
        return pd.DataFrame(), None

    # Sort by change percent (f3) descending
    by_sector_df['f3'] = pd.to_numeric(by_sector_df['f3'], errors='coerce').fillna(0)
    
    # If top_sectors_count is 0 or None, select all
    if not top_sectors_count or top_sectors_count <= 0:
        top_sectors = by_sector_df.sort_values('f3', ascending=False)
        count_msg = "所有"
    else:
        top_sectors = by_sector_df.sort_values('f3', ascending=False).head(top_sectors_count)
        count_msg = f"前 {len(top_sectors)}"
    
    print(f"获取到 {len(by_sector_df)} 个 {sector_type} 板块，将分析 {count_msg} 个表现最好的板块")
    
    all_results = []
    
    for _, row in tqdm(top_sectors.iterrows(), total=len(top_sectors), desc="分析板块"):
        sector_code = row['f12']
        sector_name = row['f14']
        sector_change = row['f3']
        
        # Rate limiting inside loop to be safe
        time.sleep(0.5)
        
        # Get all stocks sorted by different criteria
        try:
            all_stocks_by_change = get_sector_stocks(sector_code, sort_field='f3', top_n=None)
            all_stocks_by_turnover = get_sector_stocks(sector_code, sort_field='f8', top_n=None)
            all_stocks_by_inflow = get_sector_stocks(sector_code, sort_field='f62', top_n=None)
        except Exception as e:
            print(f"Error fetching stocks for sector {sector_name}: {e}")
            continue
        
        # Create ranking dictionaries
        rank_by_change = {s['f12']: i+1 for i, s in enumerate(all_stocks_by_change)}
        rank_by_turnover = {s['f12']: i+1 for i, s in enumerate(all_stocks_by_turnover)}
        rank_by_inflow = {s['f12']: i+1 for i, s in enumerate(all_stocks_by_inflow)}
        
        # Combine all unique stocks
        all_stock_codes = set()
        stock_data = {}
        
        for s in all_stocks_by_change:
            code = s['f12']
            all_stock_codes.add(code)
            stock_data[code] = s
        
        # Add any stocks that might be in other lists
        for s in all_stocks_by_turnover + all_stocks_by_inflow:
            code = s['f12']
            if code not in stock_data:
                all_stock_codes.add(code)
                stock_data[code] = s
        
        # Create detailed records for each stock
        for code in all_stock_codes:
            stock = stock_data[code]
            
            # Helper function to safely convert and divide by 100
            def safe_divide_100(val):
                try:
                    return float(val) / 100 if val is not None else None
                except (ValueError, TypeError):
                    return None
            
            record = {
                '板块名称': sector_name,
                '板块代码': sector_code,
                '板块涨跌幅': sector_change / 100,
                '股票名称': stock.get('f14'),
                '股票代码': stock.get('f12'),
                '涨跌幅': safe_divide_100(stock.get('f3')),
                '涨跌幅排名': rank_by_change.get(code, '-'),
                '换手率': safe_divide_100(stock.get('f8')),
                '换手率排名': rank_by_turnover.get(code, '-'),
                '主力净流入': stock.get('f62'),
                '主力净流入排名': rank_by_inflow.get(code, '-'),
                '现价': safe_divide_100(stock.get('f2')),
                '涨跌额': safe_divide_100(stock.get('f4')),
            }
            all_results.append(record)
    
    # Save to CSV
    timestamp = datetime.now().strftime('%H%M')
    df_all = pd.DataFrame(all_results)
    filename = None
    
    if not df_all.empty:
        # Sort by sector change (desc) then by stock change (desc)
        df_all = df_all.sort_values(['板块涨跌幅', '涨跌幅'], ascending=[False, False])
        
        dte_short = datetime.now().strftime('%y%m%d')
        os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
        filename = f'../generated/em/{dte_short}/performers_{sector_type}_{timestamp}.csv'
        df_all.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"\n所有股票详细数据已保存到: {filename}")
        print(f"总共分析了 {len(all_results)} 只股票")
        
        # Print summary
        print("\n" + "=" * 100)
        print("各板块股票数量统计:")
        print("=" * 100)
        sector_counts = df_all.groupby('板块名称').size().sort_values(ascending=False)
        for sector, count in sector_counts.items():
            print(f"{sector}: {count} 只股票")
    else:
        print(f"\n未获取到 {sector_type} 板块的股票数据")

    return df_all, filename

def main(sector_type='industry', sectors_count=10, csv_path=None, top_n=5):
    """
    主函数
    sectors_count: 分析前N个表现最好的板块
    csv_path: 如果提供，则从CSV加载数据
    top_n: 每个分类保留的股票数量
    """
    if csv_path:
        print(f"\n使用CSV文件模式: {csv_path}\n")
        results = load_results_from_csv(csv_path, top_n=top_n)
        current_csv_path = csv_path
    else:
        # Run analysis (equivalent to old 'all' mode)
        print(f"分析板块数: {sectors_count}")
        print(f"每板块股票数: 全部 (带排名 analysis)")
        print(f"输出保留前 {top_n} 只股票")
        
        df_all, generated_csv_path = analyze_all_performers(sector_type=sector_type, top_sectors_count=sectors_count)
        
        if df_all.empty or generated_csv_path is None:
            print("未获取到数据，退出")
            return
        
        current_csv_path = generated_csv_path

        # Convert the dataframe to the structure needed for obsidian notes
        results = process_dataframe_to_results(df_all, top_n=top_n)

    # Generate Obsidian Notes
    generate_obsidian_notes(results, sector_type=sector_type, output_root=get_md_dir(), csv_source=current_csv_path)
    print("\n✓ Obsidian笔记生成完成!")

def load_results_from_csv(csv_path):
    """
    从CSV文件加载数据并转换为generate_obsidian_notes所需的格式
    CSV columns: 板块名称,板块代码,板块涨跌幅,股票名称,股票代码,涨跌幅,涨跌幅排名,换手率,换手率排名,主力净流入,主力净流入排名,现价,涨跌额
    """
    print(f"正在从CSV文件加载数据: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
def process_dataframe_to_results(df, top_n=5):
    """
    将包含板块和股票数据的DataFrame转换为generate_obsidian_notes所需的格式
    top_n: 每个分类（大涨/热点/龙头）保留的股票数量
    """
    # Group by sector
    sectors = []
    
    # Check if necessary columns exist
    required_cols = ['板块名称', '板块代码', '板块涨跌幅', '股票名称', '股票代码', 
                     '涨跌幅', '涨跌幅排名', '换手率', '换手率排名', 
                     '主力净流入', '主力净流入排名', '现价', '涨跌额']
    
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        print(f"Warning: Missing columns in DataFrame: {missing_cols}")
        
    for sector_name in df['板块名称'].unique():
        sector_df = df[df['板块名称'] == sector_name]
        
        # Get sector info from first row
        first_row = sector_df.iloc[0]
        sector_code = first_row['板块代码']
        sector_change = first_row['板块涨跌幅']
        
        # Helper function to convert CSV row to API format
        def row_to_stock_dict(row):
            return {
                'f14': row['股票名称'],
                'f12': row['股票代码'],
                'f3': row['涨跌幅'] * 100 if pd.notna(row['涨跌幅']) else 0,
                'f8': row['换手率'] * 100 if pd.notna(row['换手率']) else 0,
                'f62': row['主力净流入'] if pd.notna(row['主力净流入']) else 0,
                'f2': row['现价'] * 100 if pd.notna(row['现价']) else 0,
                'f4': row['涨跌额'] * 100 if pd.notna(row['涨跌额']) else 0,
                # Add explicit ranking info for valid string types
                'rank_change': int(row['涨跌幅排名']) if pd.notna(row['涨跌幅排名']) and str(row['涨跌幅排名']).isdigit() else 9999,
                'rank_turnover': int(row['换手率排名']) if pd.notna(row['换手率排名']) and str(row['换手率排名']).isdigit() else 9999,
                'rank_inflow': int(row['主力净流入排名']) if pd.notna(row['主力净流入排名']) and str(row['主力净流入排名']).isdigit() else 9999,
            }
        
        # For the single table layout, we primarily want the top N stocks by CHANGE
        # and then we will show their other rankings.
        if '涨跌幅排名' in df.columns:
            # Get top N by change
            gainers_df = sector_df[sector_df['涨跌幅排名'] != '-'].copy()
            gainers_df['涨跌幅排名'] = pd.to_numeric(gainers_df['涨跌幅排名'], errors='coerce')
            gainers_df = gainers_df.sort_values('涨跌幅排名').head(top_n)
            gainers = [row_to_stock_dict(row) for _, row in gainers_df.iterrows()]
        else:
            gainers = []
            
        sector_info = {
            '板块名称': sector_name,
            '板块代码': sector_code,
            '板块涨跌幅': sector_change,
            # For the new layout, 'main_list' serves as the primary data source
            # which we derive from 'gainers' (Top N by Change)
            'main_list': gainers
        }
        sectors.append(sector_info)
    
    return sectors

def load_results_from_csv(csv_path, top_n=5):
    """
    从CSV文件加载数据并转换为generate_obsidian_notes所需的格式
    CSV columns: 板块名称,板块代码,板块涨跌幅,股票名称,股票代码,涨跌幅,涨跌幅排名,换手率,换手率排名,主力净流入,主力净流入排名,现价,涨跌额
    """
    print(f"正在从CSV文件加载数据: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    sectors = process_dataframe_to_results(df, top_n=top_n)
    print(f"成功加载 {len(sectors)} 个板块的数据")
    return sectors

def parse_markdown_table(md_file_path):
    """
    从 markdown 文件中解析表格数据
    返回 DataFrame
    """
    try:
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找表格部分（以 | 开头的行）
        lines = content.split('\n')
        table_lines = []
        in_table = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|') and '---' not in stripped:
                # 跳过分隔行（包含 --- 的行）
                if not re.match(r'^\|[\s\-:]+\|', stripped):
                    table_lines.append(stripped)
                    in_table = True
            elif in_table and not stripped.startswith('|'):
                # 表格结束
                break
        
        if not table_lines:
            print(f"警告: 在 {md_file_path} 中未找到表格数据")
            return pd.DataFrame()
        
        # 解析表格行
        rows = []
        for line in table_lines:
            # 移除首尾的 |，然后分割
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            # 移除 HTML 标签（如 <span style="color:red">...</span>）
            cells = [re.sub(r'<[^>]+>', '', cell) for cell in cells]
            rows.append(cells)
        
        if not rows:
            return pd.DataFrame()
        
        # 第一行是表头
        headers = rows[0]
        data_rows = rows[1:]
        
        # 创建 DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        return df
        
    except Exception as e:
        print(f"解析 markdown 文件 {md_file_path} 时出错: {e}")
        return pd.DataFrame()

def merge_view(industry_view_path, concept_view_path):
    """
    合并 industry_view.md 和 concept_view.md 的内容，保存为 checkboard.csv
    """
    industry_df = pd.DataFrame()
    concept_df = pd.DataFrame()
    
    if industry_view_path:
        print(f"正在读取行业视图: {industry_view_path}")
        industry_df = parse_markdown_table(industry_view_path)
        print(f"  行业视图: 解析到 {len(industry_df)} 行数据")
    else:
        print("警告: 行业视图文件路径为空，跳过")
    
    if concept_view_path:
        print(f"正在读取概念视图: {concept_view_path}")
        concept_df = parse_markdown_table(concept_view_path)
        print(f"  概念视图: 解析到 {len(concept_df)} 行数据")
    else:
        print("警告: 概念视图文件路径为空，跳过")
    
    if industry_df.empty and concept_df.empty:
        print("错误: 两个视图文件都为空")
        return
    
    # 添加类型列
    if not industry_df.empty:
        industry_df.insert(0, '类型', 'industry')
    if not concept_df.empty:
        concept_df.insert(0, '类型', 'concept')
    
    # 合并两个 DataFrame（简单拼接，不去重）
    if industry_df.empty:
        merged_df = concept_df
    elif concept_df.empty:
        merged_df = industry_df
    else:
        # 确保列名一致
        all_columns = set(industry_df.columns) | set(concept_df.columns)
        for col in all_columns:
            if col not in industry_df.columns:
                industry_df[col] = ''
            if col not in concept_df.columns:
                concept_df[col] = ''
        
        # 重新排列列顺序，确保一致
        common_cols = ['类型'] + [col for col in industry_df.columns if col != '类型']
        industry_df = industry_df[common_cols]
        concept_df = concept_df[common_cols]
        
        # 简单拼接，不去重
        merged_df = pd.concat([industry_df, concept_df], ignore_index=True)
        print(f"  合并后: {len(merged_df)} 行 (行业: {len(industry_df)} + 概念: {len(concept_df)})")
    
    # 确定输出目录：CSV 使用 ../generated/em/{dte_short}/，MD 使用 /Volumes/ASME/myobs/0syncs/stock/{dte}/
    dte_short = datetime.now().strftime('%y%m%d')
    dte = datetime.now().strftime('%Y%m%d')
    
    # CSV 输出目录
    csv_output_dir = os.path.join('..', 'generated', 'em', dte_short)
    os.makedirs(csv_output_dir, exist_ok=True)
    output_csv = os.path.join(csv_output_dir, 'checkboard.csv')
    
    # MD 输出目录：使用 get_md_dir()/{dte}/ (4位年份格式，如 20251218)
    md_output_dir = os.path.join(get_md_dir(), dte)
    os.makedirs(md_output_dir, exist_ok=True)
    output_md = os.path.join(md_output_dir, 'checkboard.md')
    
    # 保存为 CSV
    merged_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    
    # 根据颜色模式筛选并写入 checkbord.csv
    def extract_numeric_value(value_str, is_inflow=False):
        """从可能包含HTML标签的字符串中提取数值
        is_inflow: 如果是主力净流入，统一转换为"亿"为单位
        """
        if pd.isna(value_str) or value_str == '':
            return None
        try:
            # 转换为字符串
            value_str = str(value_str).strip()
            if not value_str or value_str == '':
                return None
            
            # 移除HTML标签
            clean_str = re.sub(r'<[^>]+>', '', value_str)
            # 移除空格
            clean_str = clean_str.strip()
            
            # 提取数字部分（包括负号和小数点）
            # 使用更精确的正则表达式，保留负号和小数点
            numeric_match = re.search(r'-?\d+\.?\d*', clean_str)
            if not numeric_match:
                return None
            
            numeric_str = numeric_match.group(0)
            value = float(numeric_str)
            
            # 如果是主力净流入，需要统一单位
            if is_inflow:
                # 如果包含"亿"，已经是亿为单位，直接返回
                if '亿' in clean_str:
                    return value
                # 如果包含"万"，转换为亿
                elif '万' in clean_str:
                    return value / 10000
                # 如果不包含单位，假设是元，转换为亿
                else:
                    return value / 100000000
            
            return value
        except Exception as e:
            # 调试信息：如果解析失败，打印原始值
            # print(f"解析数值失败: {value_str}, 错误: {e}")
            pass
        return None
    
    def get_color_pattern(df):
        """根据涨跌幅、主力净流入、换手率的颜色模式筛选数据"""
        patterns = []
        
        # 确保必要的列存在
        if '涨跌幅' not in df.columns or '主力净流入' not in df.columns or '换手率' not in df.columns:
            print("警告: 缺少必要的列（涨跌幅、主力净流入、换手率），跳过颜色模式筛选")
            print(f"  当前列名: {list(df.columns)}")
            return pd.DataFrame()
        
        print(f"开始颜色模式筛选，数据行数: {len(df)}")
        
        # 创建数据副本用于处理
        work_df = df.copy()
        
        # 提取数值
        work_df['涨跌幅_数值'] = work_df['涨跌幅'].apply(extract_numeric_value)
        work_df['主力净流入_数值'] = work_df['主力净流入'].apply(lambda x: extract_numeric_value(x, is_inflow=True))
        work_df['换手率_数值'] = work_df['换手率'].apply(extract_numeric_value)
        
        # 移除无法解析的行
        before_drop = len(work_df)
        work_df = work_df.dropna(subset=['涨跌幅_数值', '主力净流入_数值', '换手率_数值'])
        after_drop = len(work_df)
        
        if before_drop > after_drop:
            print(f"  移除了 {before_drop - after_drop} 行无法解析的数据")
        
        if work_df.empty:
            print("警告: 没有有效的数据行可用于颜色模式筛选")
            return pd.DataFrame()
        
        print(f"  有效数据行数: {len(work_df)}")
        
        # Pattern 1: 双红（涨跌幅>0，主力净流入>0），主力净流入倒排序前10
        pattern1 = work_df[
            (work_df['涨跌幅_数值'] > 0) & 
            (work_df['主力净流入_数值'] > 0)
        ].copy()
        if not pattern1.empty:
            # 按主力净流入倒排序（降序），取前10
            pattern1 = pattern1.sort_values('主力净流入_数值', ascending=False).head(10)
            pattern1['模式'] = '双红_高换手_主力流入'
            patterns.append(pattern1)
            print(f"  模式1 (双红_高换手_主力流入): 匹配 {len(pattern1)} 行")
        else:
            print(f"  模式1 (双红_高换手_主力流入): 无匹配")
        
        # 按换手率倒排序（降序），用于 Pattern 2 和 Pattern 3
        work_df_sorted_by_tov = work_df.sort_values('换手率_数值', ascending=False)
        top_10_by_tov = work_df_sorted_by_tov.head(10)
        
        # Pattern 2: red_green（涨跌幅>0，主力净流入<0）OR green_red（涨跌幅<0，主力净流入>0），主力净流出倒排序前20
        pattern2 = work_df[
            ((work_df['涨跌幅_数值'] > 0) & (work_df['主力净流入_数值'] < 0)) |  # red_green
            ((work_df['涨跌幅_数值'] < 0) & (work_df['主力净流入_数值'] > 0))   # green_red
        ].copy()
        if not pattern2.empty:
            # 计算主力净流出绝对值（对于red_green是主力净流入的绝对值，对于green_red也是主力净流入的绝对值）
            pattern2['主力净流出_绝对值'] = pattern2['主力净流入_数值'].abs()
            # 按主力净流出倒排序（降序），取前20
            pattern2 = pattern2.sort_values('主力净流出_绝对值', ascending=False).head(20)
            pattern2 = pattern2.drop(columns=['主力净流出_绝对值'])
            pattern2['模式'] = '红涨绿流_高换手_主力流出'
            patterns.append(pattern2)
            print(f"  模式2 (红涨绿流_高换手_主力流出): 匹配 {len(pattern2)} 行")
        else:
            print(f"  模式2 (红涨绿流_高换手_主力流出): 无匹配")
        
        # Pattern 3: 换手率倒排序前10，且双绿（涨跌幅<0，主力净流入<0），主力净流出倒排序
        pattern3 = top_10_by_tov[
            (top_10_by_tov['涨跌幅_数值'] < 0) & 
            (top_10_by_tov['主力净流入_数值'] < 0)
        ].copy()
        if not pattern3.empty:
            # 按主力净流出倒排序（即主力净流入绝对值降序）
            pattern3['主力净流出_绝对值'] = pattern3['主力净流入_数值'].abs()
            pattern3 = pattern3.sort_values('主力净流出_绝对值', ascending=False)
            pattern3 = pattern3.drop(columns=['主力净流出_绝对值'])
            pattern3['模式'] = '双绿_高换手_主力流出'
            patterns.append(pattern3)
            print(f"  模式3 (双绿_高换手_主力流出): 匹配 {len(pattern3)} 行")
        else:
            print(f"  模式3 (双绿_高换手_主力流出): 无匹配")
        
        if patterns:
            result_df = pd.concat(patterns, ignore_index=True)
            # 移除辅助列
            result_df = result_df.drop(columns=['涨跌幅_数值', '主力净流入_数值', '换手率_数值'], errors='ignore')
            return result_df
        else:
            return pd.DataFrame()
    
    # 生成颜色模式筛选结果
    pattern_df = get_color_pattern(merged_df)
    
    # 保存为 Markdown（使用与 save_md_view 相同的规则）
    def save_merged_md_view(df, output_path):
        """保存合并后的Markdown视图文件，使用与 save_md_view 相同的规则"""
        df = df.copy()

        def format_colored_value(value, is_positive=True):
            """
            格式化带颜色的值，兼容 Obsidian（隐藏符号，仅颜色）和 GitHub（显示符号）
            """
            if is_positive:
                return f'<span style="display:none">↑ </span><span style="color:red">{value}</span>'
            return f'<span style="display:none">↓ </span><span style="color:green">{value}</span>'
        
        def format_table_row(row, head, df):
            """格式化表格行"""
            row_vals = []
            
            # 1. 类型（如果有）
            if '类型' in head:
                row_vals.append(str(row.get('类型', '')))
            
            # 2. 名称（附带 eastmoney 链接）
            name = str(row.get('名称', ''))
            bk_code = row.get('板块代码', '')
            if pd.notna(bk_code) and str(bk_code).strip() != '':
                try:
                    bk = str(int(float(bk_code))) if str(bk_code).replace('.', '').isdigit() else str(bk_code).strip()
                    name = f'[{name}](https://data.eastmoney.com/bkzj/{bk}.html)'
                except (ValueError, TypeError):
                    pass
            row_vals.append(name)
            
            # 3. 涨跌幅（直接显示数值，不乘以100，添加颜色标记）
            zdf = row.get('涨跌幅', '')
            if zdf != '' and not pd.isna(zdf):
                try:
                    zdf_clean = re.sub(r'[^\d\.\-]+', '', str(zdf))
                    zdf_val = float(zdf_clean) if zdf_clean else 0.0
                    zdf_str = f"{zdf_val:.2f}"
                    # 添加颜色标记：>0红色，<0绿色（隐藏符号，仅颜色）
                    if zdf_val > 0:
                        zdf_str = format_colored_value(zdf_str, is_positive=True)
                    elif zdf_val < 0:
                        zdf_str = format_colored_value(zdf_str, is_positive=False)
                except Exception:
                    zdf_str = str(zdf)
            else:
                zdf_str = ''
            row_vals.append(zdf_str)
            
            # 4. 主力净流入（亿元，添加颜色标记）
            zjlx = row.get('主力净流入', '')
            if zjlx != '' and not pd.isna(zjlx):
                try:
                    # 清洗字符串，提取数字部分（如 "↓ -2.97亿" -> -2.97）
                    zjlx_clean = re.sub(r'[^\d\.\-]', '', str(zjlx))
                    zjlx_val = float(zjlx_clean) if zjlx_clean else 0.0
                    zjlx_str = f"{zjlx_val:.2f}亿"
                    # 添加颜色标记：>0红色，<0绿色（隐藏符号，仅颜色）
                    if zjlx_val > 0:
                        zjlx_str = format_colored_value(zjlx_str, is_positive=True)
                    elif zjlx_val < 0:
                        zjlx_str = format_colored_value(zjlx_str, is_positive=False)
                except Exception:
                    zjlx_str = str(zjlx) if zjlx else '0.00亿'
            else:
                zjlx_str = '0.00亿'
            row_vals.append(zjlx_str)
            
            # 5. 换手率（直接显示数值，不乘以100）
            hs = row.get('换手率', '')
            if hs != '' and not pd.isna(hs):
                try:
                    hs_val = float(hs)
                    hs_str = f"{hs_val:.2f}"
                except Exception:
                    hs_str = str(hs) if hs else ''
            else:
                hs_str = ''
            row_vals.append(hs_str)
            
            # 6. 上涨家数/下跌家数
            up = ''
            down = ''
            # 检查是否有合并的列名（从 markdown 解析出来的）
            if '上涨家数/下跌家数' in df.columns:
                updown_val = row.get('上涨家数/下跌家数', '')
                if updown_val != '' and not pd.isna(updown_val):
                    # 解析格式 "5/1"
                    parts = str(updown_val).split('/')
                    if len(parts) == 2:
                        up = parts[0].strip()
                        down = parts[1].strip()
            else:
                # 检查分开的列名（原始 DataFrame）
                if '上涨家数' in df.columns:
                    up_val = row.get('上涨家数', '')
                    if up_val != '' and not pd.isna(up_val):
                        try:
                            up = str(int(float(up_val)))
                        except:
                            up = str(up_val)
                if '下跌家数' in df.columns:
                    down_val = row.get('下跌家数', '')
                    if down_val != '' and not pd.isna(down_val):
                        try:
                            down = str(int(float(down_val)))
                        except:
                            down = str(down_val)
            row_vals.append(f"{up}/{down}")
            
            # 7. 领涨股/领跌股（添加链接到个股表现section）
            lz_val = ''
            ld_val = ''
            # 检查是否有合并的列名（从 markdown 解析出来的）
            if '领涨股/领跌股' in df.columns:
                lzld_val = row.get('领涨股/领跌股', '')
                if lzld_val != '' and not pd.isna(lzld_val):
                    # 解析格式 "龙洲股份/双枪科技"
                    parts = str(lzld_val).split('/')
                    if len(parts) == 2:
                        lz_val = parts[0].strip()
                        ld_val = parts[1].strip()
                    elif len(parts) == 1:
                        lz_val = parts[0].strip()
            else:
                # 检查分开的列名（原始 DataFrame）
                if '领涨股名称' in df.columns:
                    lz_val = str(row.get('领涨股名称', '')) if row.get('领涨股名称', '') != '' and not pd.isna(row.get('领涨股名称', '')) else ''
                if '领跌股名称' in df.columns:
                    ld_val = str(row.get('领跌股名称', '')) if row.get('领跌股名称', '') != '' and not pd.isna(row.get('领跌股名称', '')) else ''
            
            # 加载股票名称到代码的映射（用于生成链接）
            from utils_reem import load_stock_name_code_map
            name_code_map = load_stock_name_code_map()
            
            def generate_anchor_id(text):
                """生成标准的 Markdown 锚点ID"""
                anchor = text.lower()
                anchor = re.sub(r'[\s/\\|]+', '-', anchor)
                anchor = re.sub(r'[^a-z0-9\-]', '', anchor)
                anchor = re.sub(r'-+', '-', anchor)
                anchor = anchor.strip('-')
                return anchor
            
            # 为领涨股添加链接
            if lz_val:
                lz_clean = re.sub(r'^\*?ST\s*', '', lz_val.strip())
                if lz_clean in name_code_map:
                    anchor_id = generate_anchor_id(f"个股表现-{lz_clean}")
                    lz_val = f"[{lz_val}](#{anchor_id})"
            
            # 为领跌股添加链接
            if ld_val:
                ld_clean = re.sub(r'^\*?ST\s*', '', ld_val.strip())
                if ld_clean in name_code_map:
                    anchor_id = generate_anchor_id(f"个股表现-{ld_clean}")
                    ld_val = f"[{ld_val}](#{anchor_id})"
            
            if lz_val and ld_val:
                row_vals.append(f"{lz_val}/{ld_val}")
            elif lz_val:
                row_vals.append(lz_val)
            elif ld_val:
                row_vals.append(ld_val)
            else:
                row_vals.append('')
            
            # 8. 板块表现（走势图/K线图）
            if '板块表现' in head:
                bk_code_for_chart = row.get('板块代码', '')
                if pd.notna(bk_code_for_chart) and str(bk_code_for_chart).strip() != '':
                    try:
                        # 格式化板块代码
                        if str(bk_code_for_chart).replace('.', '').isdigit():
                            bk_chart = str(int(float(bk_code_for_chart)))
                        else:
                            bk_chart = str(bk_code_for_chart).strip()
                        
                        # 生成时间戳用于图片URL
                        timestamp_ms = int(datetime.now().timestamp() * 1000)
                        
                        # 生成板块走势图和K线图URL
                        # 板块nid格式: 90.{code}
                        nid = f"90.{bk_chart}"
                        
                        # 走势图URL
                        trend_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms}"
                        
                        # K线图URL
                        kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms}"
                        
                        # 生成Markdown图片链接
                        trend_link = f"[走势图]({trend_url})"
                        kline_link = f"[K线图]({kline_url})"
                        row_vals.append(f"{trend_link} / {kline_link}")
                    except (ValueError, TypeError) as e:
                        row_vals.append('')
                else:
                    row_vals.append('')
            
            return row_vals
        
        # 统一列名（如果有板块名称列，重命名为名称）
        col_map = {}
        if '板块名称' in df.columns:
            col_map['板块名称'] = '名称'
        elif '名称' in df.columns:
            col_map['名称'] = '名称'
        
        if col_map:
            df = df.rename(columns=col_map)
        
        # 构建Markdown
        md_lines = []
        
        # 表头 - 按指定顺序：类型 | 名称 | 涨跌幅 | 主力净流入 | 换手率 | 上涨家数/下跌家数 | 领涨股/领跌股 | 板块表现 | 模式
        head = []
        if '类型' in df.columns:
            head.append('类型')
        head.append('名称')
        if '涨跌幅' in df.columns:
            head.append('涨跌幅')
        # 主力净流入和换手率总是添加（即使列不存在也会显示空值）
        head.append('主力净流入')
        head.append('换手率')
        # 上涨家数/下跌家数和领涨股/领跌股总是添加（即使列不存在也会显示空值）
        head.append('上涨家数/下跌家数')
        head.append('领涨股/领跌股')
        # 添加板块表现列
        head.append('板块表现')
        if '模式' in df.columns:
            head.append('模式')
        
        # 检查是否有模式列，如果有则按模式分组
        if '模式' in df.columns and not df.empty:
            # 按模式分组
            pattern_groups = df.groupby('模式')
            
            # 添加MOC（目录）
            md_lines.append("## 目录\n\n")
            for pattern_name in pattern_groups.groups.keys():
                # 创建安全的锚点链接（移除特殊字符）
                anchor = pattern_name.replace(' ', '-').replace('_', '-')
                md_lines.append(f"- [[#{pattern_name}|{pattern_name}]]\n")
            md_lines.append("\n---\n\n")
            
            # 为每个模式创建section
            for pattern_name, pattern_df in pattern_groups:
                # 限制每个模式最多10项
                pattern_df_limited = pattern_df.head(10)
                
                # 添加模式标题
                md_lines.append(f"## {pattern_name}\n\n")
                
                # 添加表格
                md_lines.append('| ' + ' | '.join(head) + ' |')
                md_lines.append('| ' + ' | '.join(['---'] * len(head)) + ' |')
                
                # 添加数据行
                for _, row in pattern_df_limited.iterrows():
                    row_vals = format_table_row(row, head, df)
                    md_lines.append('| ' + ' | '.join(row_vals) + ' |')
                
                md_lines.append("\n")
        else:
            # 没有模式列，使用原来的逻辑
            md_lines.append('| ' + ' | '.join(head) + ' |')
            md_lines.append('| ' + ' | '.join(['---'] * len(head)) + ' |')
            
            # 排序（按涨跌幅降序）
            out_df = df.copy()
            if '涨跌幅' in out_df.columns:
                out_df = out_df.sort_values('涨跌幅', ascending=False)
            
            # 限制最多显示前N项（如果没有模式分组）
            if len(out_df) > 30:
                out_df = out_df.head(30)
            
            # 每一行 - 按表头顺序填充数据
            for _, row in out_df.iterrows():
                row_vals = format_table_row(row, head, df)
                md_lines.append('| ' + ' | '.join(row_vals) + ' |')
        
        # 收集所有领涨股和领跌股（用于生成个股表现section）
        stock_names = set()
        for _, row in df.iterrows():
            lz_val = ''
            ld_val = ''
            if '领涨股/领跌股' in df.columns:
                lzld_val = row.get('领涨股/领跌股', '')
                if lzld_val != '' and not pd.isna(lzld_val):
                    parts = str(lzld_val).split('/')
                    if len(parts) >= 1:
                        lz_val = parts[0].strip()
                    if len(parts) >= 2:
                        ld_val = parts[1].strip()
            else:
                if '领涨股名称' in df.columns:
                    lz_val = str(row.get('领涨股名称', '')) if row.get('领涨股名称', '') != '' and not pd.isna(row.get('领涨股名称', '')) else ''
                if '领跌股名称' in df.columns:
                    ld_val = str(row.get('领跌股名称', '')) if row.get('领跌股名称', '') != '' and not pd.isna(row.get('领跌股名称', '')) else ''
            if lz_val:
                stock_names.add(lz_val.strip())
            if ld_val:
                stock_names.add(ld_val.strip())
        
        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f_md:
            f_md.write("# 板块数据视图（合并）\n\n")
            f_md.write(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f_md.write('\n'.join(md_lines))
            f_md.write('\n')
            
            # 添加"个股表现"部分
            if stock_names:
                f_md.write("\n## 个股表现\n\n")
                
                # 加载股票名称到代码的映射
                from utils_reem import load_stock_name_code_map
                name_code_map = load_stock_name_code_map()
                
                # 生成时间戳用于图片URL
                timestamp_ms = int(datetime.now().timestamp() * 1000)
                
                # 为每个股票生成走势图和K线图
                for stock_name in sorted(stock_names):
                    stock_clean = re.sub(r'^\*?ST\s*', '', stock_name)
                    if stock_clean in name_code_map:
                        stock_code = name_code_map[stock_clean]
                        # 生成股票nid（根据代码前缀判断市场）
                        if stock_code.startswith(('6', '9')):
                            nid = f"1.{stock_code}"
                        else:
                            nid = f"0.{stock_code}"
                        
                        # 走势图URL
                        trend_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms}"
                        
                        # K线图URL
                        kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms}"
                        
                        # 生成锚点ID
                        def generate_anchor_id(text):
                            anchor = text.lower()
                            anchor = re.sub(r'[\s/\\|]+', '-', anchor)
                            anchor = re.sub(r'[^a-z0-9\-]', '', anchor)
                            anchor = re.sub(r'-+', '-', anchor)
                            anchor = anchor.strip('-')
                            return anchor
                        anchor_id = generate_anchor_id(f"个股表现-{stock_clean}")
                        
                        # 添加个股表现部分
                        f_md.write(f"### {stock_name} ({stock_code})\n\n")
                        f_md.write(f"**走势图**\n\n")
                        f_md.write(f"![{stock_name}走势图]({trend_url})\n\n")
                        f_md.write(f"**K线图**\n\n")
                        f_md.write(f"![{stock_name}K线图]({kline_url})\n\n")
                        f_md.write("---\n\n")
        
        print(f"✓ 合并Markdown视图已保存到: {output_path}")
    
    # 保存 Markdown 视图（使用颜色模式筛选结果）
    if not pattern_df.empty:
        save_merged_md_view(pattern_df, output_md)
        print(f"✓ checkboard.md 已保存（包含颜色模式筛选结果）: {output_md}")
        print(f"  模式1 (双红_高换手_主力流入): {len(pattern_df[pattern_df['模式'] == '双红_高换手_主力流入'])} 行")
        print(f"  模式2 (红涨绿流_高换手_主力流出): {len(pattern_df[pattern_df['模式'] == '红涨绿流_高换手_主力流出'])} 行")
        print(f"  模式3 (双绿_高换手_主力流出): {len(pattern_df[pattern_df['模式'] == '双绿_高换手_主力流出'])} 行")
    else:
        # 如果没有匹配的模式数据，保存空的 markdown
        empty_df = pd.DataFrame(columns=merged_df.columns.tolist() + ['模式'])
        save_merged_md_view(empty_df, output_md)
        print(f"✓ checkboard.md 已创建（无匹配的模式数据）: {output_md}")
    
    print(f"✓ 合并视图已保存到: {output_csv}")
    print(f"  行业板块: {len(industry_df)} 行")
    print(f"  概念板块: {len(concept_df)} 行")
    print(f"  总计: {len(merged_df)} 行")

def get_file_count_stats(dte_short):
    """
    统计 ../generated/em/{dte_short} 目录下的文件
    实现逻辑: ls ../generated/em/{dte_short}/* | awk -F'/' '{print $NF}' | awk -F'_' '{print $1}' | sort | uniq -c | sort -nr
    
    Returns:
        list of tuples: [(count, prefix), ...] 按计数降序排列
    """
    raw_dir = os.path.join('..', 'generated', 'em', dte_short)
    
    if not os.path.exists(raw_dir):
        return []
    
    # 统计文件前缀（第一个_之前的部分）
    prefix_count = {}
    
    try:
        for filename in os.listdir(raw_dir):
            filepath = os.path.join(raw_dir, filename)
            if os.path.isfile(filepath):
                # 提取文件名中第一个_之前的部分
                prefix = filename.split('_')[0] if '_' in filename else filename
                prefix_count[prefix] = prefix_count.get(prefix, 0) + 1
    except Exception as e:
        print(f"统计文件时出错: {e}")
        return []
    
    # 按计数降序排序
    sorted_stats = sorted(prefix_count.items(), key=lambda x: x[1], reverse=True)
    return sorted_stats

def generate_obsidian_notes(results, sector_type='industry', output_root=None, csv_source=None):
    """生成Obsidian格式的笔记"""
    # 动态获取输出根目录（如果未提供）
    if output_root is None:
        output_root = get_md_dir()
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    date_yyyymmdd = datetime.now().strftime('%Y%m%d')
    time_str = datetime.now().strftime('%H:%M:%S')
    folder_name = date_yyyymmdd
    base_dir = os.path.join(output_root, folder_name)
    sectors_dir = os.path.join(base_dir, f"{sector_type}")
    
    os.makedirs(sectors_dir, exist_ok=True)
    
    # Create raw directory
    dte_short = datetime.now().strftime('%y%m%d')
    raw_dir = os.path.join('..', 'generated', 'em', dte_short)
    os.makedirs(raw_dir, exist_ok=True)

    # 1. Create Dashboard Note (renamed to README.md)
    dashboard_path = os.path.join(base_dir, "README.md")
    with open(dashboard_path, 'w', encoding='utf-8') as f:
        # 1.1 Insert latest Capital Flow Chart if available
        # Look for capital_flow_merged_*.png in output_root (parent of base_dir)
        # Note: output_root is passed in ('/Users/.../stock')
        f.write(f"# {sector_type} Analysis Dashboard - {date_str}\n\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        
        # 1.2 In-Note MOC (TOC) - Use Obsidian Wiki Links for robust header linking
        f.write("### Table of Contents\n")
        
        header_top_sectors = f"Top {len(results)} Performing {sector_type}s"
        header_sector_charts = f"Sector K-Line Charts (Top {len(results)})"
        header_stock_charts = "Stock K-Line Charts (Top Gainers)"
        header_file_count = "File Count"

        f.write(f"- [[#{header_top_sectors}]]\n")
        f.write(f"- [[#{header_sector_charts}]]\n")
        f.write(f"- [[#{header_stock_charts}]]\n\n")
        f.write(f"- [[#{header_file_count}]]\n\n")

        f.write(f"## Top 15s\n\n")
        # Look for capital_flow_merged_*.png in base_dir/charts/ (stock/{date_long}/charts/)
        charts_dir = os.path.join(base_dir, "charts")
        chart_pattern = os.path.join(charts_dir, "capital_flow_merged_*.png")
        charts = glob.glob(chart_pattern)
        if charts:
            # Sort by modification time (most recent first) or by filename (which includes timestamp)
            # Use modification time for most accurate "latest" detection
            charts.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            latest_chart = charts[0]
            chart_filename = os.path.basename(latest_chart)
            # Relative path from base_dir (stock/YYYYMMDD) to base_dir/charts/chart.png is charts/chart.png
            f.write(f"![Capital Flow](charts/{chart_filename})\n\n")
        
                
        f.write(f"## {header_top_sectors}\n\n")
        f.write("| Rank | Sector | Change | Top Gainer (Change%) | Leader (Inflow) |\n")
        f.write("|---|---|---|---|---|\n")
        
        for i, item in enumerate(results, 1):
            name = item['板块名称']
            change = item['板块涨跌幅'] 
            
            # Using main_list which is sorted by change %
            top_stock = item['main_list'][0] if item['main_list'] else None
            
            top_gainer_name = top_stock['f14'] if top_stock else "N/A"
            top_gainer_change = f"{top_stock['f3']/100:.2f}%" if top_stock else ""
            
            # Find Top Inflow Stock (Leader) from main_list
            leader_stock = None
            if item['main_list']:
                # Sort by f62 (Net Inflow) descending
                def safe_float(val):
                    """安全地将值转换为 float，处理 '-' 等非数字值"""
                    if val is None:
                        return 0.0
                    if val == '-' or val == '':
                        return 0.0
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return 0.0
                
                sorted_by_inflow = sorted(item['main_list'], key=lambda x: safe_float(x.get('f62', 0)), reverse=True)
                leader_stock = sorted_by_inflow[0]
            
            leader_name = leader_stock['f14'] if leader_stock else "N/A"
            # Helper logic for money format just for this short snippet or redefine/import?
            # Creating a tiny local helper for formatting inflow to keep code robust
            def mini_fmt(val):
                try:
                    v = float(val)
                    if abs(v) > 100000000: return f"{v/100000000:.2f}亿"
                    if abs(v) > 10000: return f"{v/10000:.0f}万"
                    return str(val)
                except: return str(val)
                
            leader_inflow = mini_fmt(leader_stock['f62']) if leader_stock else ""
            
            # Using standard markdown link for Sector to avoid pipe '|' conflict in table
            # Append rank to the link destination as file will be named that way
            f.write(f"| {i} | [{name}]({name}) | {change} | [[{top_gainer_name}]] ({top_gainer_change}) | [[{leader_name}]] ({leader_inflow}) |\n")
        
        # Sector Charts Section
        f.write(f"\n## {header_sector_charts}\n\n")
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        
        # Display charts for all results since we are now filtering by --sectors count
        for item in results:
            name = item['板块名称']
            code = item['板块代码']
            # Sector nid is likely 90.code
            nid = f"90.{code}"
            
            f.write(f"### {name}\n")
            # Trend Chart
            f.write(f"![{name}走势图](https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms})\n")
            # K-Line Chart
            f.write(f"![{name}K线图](https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms})\n\n")
            
        # Stock Charts Section
        f.write(f"\n## Stock K-Line Charts (Top Gainers)\n\n")
        for item in results:
            if item['main_list']:
                top_stock = item['main_list'][0]
                stock_name = top_stock['f14']
                stock_code = top_stock['f12']
                
                market_prefix = "1" if str(stock_code).startswith('6') else "0"
                full_code_nid = f"{market_prefix}.{stock_code}"
                
                f.write(f"### {stock_name} ({item['板块名称']})\n")
                # Trend Chart
                f.write(f"![{stock_name}走势图](https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={full_code_nid}&timespan={timestamp_ms})\n")
                # K-Line Chart
                f.write(f"![{stock_name}K线图](https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={full_code_nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms})\n\n")
        
        # File count section
        f.write(f"\n## File count\n\n")
        file_stats = get_file_count_stats(dte_short)
        if file_stats:
            f.write("| Count | Prefix |\n")
            f.write("|:---:|---|\n")
            for count, prefix in file_stats:
                f.write(f"| {count} | {prefix} |\n")
        else:
            f.write(f"No files found in `../generated/em/{dte_short}/`\n")
        f.write("\n")
        
    
    # Move existing files in sectors_dir before creating new ones
    if os.path.exists(sectors_dir):
        existing_files = [f for f in os.listdir(sectors_dir) if os.path.isfile(os.path.join(sectors_dir, f))]
        if existing_files:
            # Find the latest creation time among all files
            latest_ctime = max(os.path.getctime(os.path.join(sectors_dir, f)) for f in existing_files)
            backup_time = datetime.fromtimestamp(latest_ctime).strftime('%H%M')
            backup_dir = os.path.join(sectors_dir, backup_time)
            
            # Create backup directory
            os.makedirs(backup_dir, exist_ok=True)
            print(f"移动现有文件到: {backup_dir}")
            
            # Move all existing files to backup directory
            for filename in existing_files:
                src_path = os.path.join(sectors_dir, filename)
                dst_path = os.path.join(backup_dir, filename)
                try:
                    shutil.move(src_path, dst_path)
                    print(f"  已移动: {filename}")
                except Exception as e:
                    print(f"  移动 {filename} 时出错: {e}")
            
    # 2. Create Individual Sector Notes
    # 
    for i, item in enumerate(results, 1):
        name = item['板块名称']
        code = item['板块代码']
        change = item['板块涨跌幅']
        
        # Append rank to filename: e.g. "SectorName_1.md"
        note_path = os.path.join(sectors_dir, f"{name}_{i}.md")
        # Ensure the directory exists (in case name contains path separators)
        os.makedirs(os.path.dirname(note_path), exist_ok=True)
        with open(note_path, 'w', encoding='utf-8') as f:
            f.write(f"# {name} ({code})\n\n")
            f.write(f"**Change**: {change}\n")
            f.write(f"**Date**: {date_str} {time_str}\n\n")
            
            # MOC for Sector Note - Link to Summary Table header
            f.write("- [[#股票表现汇总]]\n\n")

            # Sector Charts
            timestamp_ms = int(datetime.now().timestamp() * 1000)
            # Find common market type prefix (sh/sz usually not needed for chart API but let's check format)
            # The Eastmoney chart API uses format like 90.BKxxxx for sectors
            # BK code is generally sufficient with 90. prefix for sectors
            
            # K-Line Chart
            f.write(f"![{name}K线图](https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=90.{code}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms})\n\n")
            
            # Intraday Chart
            f.write(f"![{name}分时图](https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid=90.{code}&timespan={timestamp_ms})\n\n")
            
            # Helper function for money formatting
            def fmt_money(val):
                try:
                    v = float(val)
                    if abs(v) > 100000000: return f"{v/100000000:.2f}亿"
                    if abs(v) > 10000: return f"{v/10000:.0f}万"
                    return str(val)
                except: return str(val)
            
            # Summary Table
            f.write("## 股票表现汇总\n\n")
            
            # Header
            f.write("| 序号 | 股票名称 | 涨跌幅 | 主力净流入 | 换手率 | 现价 | 🚀 | 🔥 | 💰 | 当日走势 |\n")
            f.write("|:---:|---|---:|---:|---:|---:|:---:|:---:|:---:|:---:|\n")
            
            for idx, s in enumerate(item['main_list'], 1):
                stock_code = s['f12']
                stock_name = s['f14']
                
                # Determine appropriate market prefix for charts (0. for sz, 1. for sh)
                # Simple heuristic: 60xxxx -> 1.60xxxx, 00xxxx/30xxxx -> 0.xxxxxx
                # However, Eastmoney chart API generally accepts 1. for SH, 0. for SZ
                market_prefix = "1" if str(stock_code).startswith('6') else "0"
                full_code_nid = f"{market_prefix}.{stock_code}"
                
                def safe_float_divide_100(val):
                    """安全地将值转换为 float 并除以 100，处理 '-' 等非数字值"""
                    if val is None or val == '-' or val == '':
                        return 0.0
                    try:
                        return float(val) / 100
                    except (ValueError, TypeError):
                        return 0.0
                
                price = safe_float_divide_100(s.get('f2', 0))
                change_pct_val = safe_float_divide_100(s.get('f3', 0))
                turnover_val = safe_float_divide_100(s.get('f8', 0))
                change_pct = f"{change_pct_val:.2f}%" if change_pct_val != 0 else "-"
                turnover = f"{turnover_val:.2f}%" if turnover_val != 0 else "-"
                inflow = fmt_money(s.get('f62', '-'))
                
                # Ranks
                rank_change = s.get('rank_change', '-') 
                rank_turnover = s.get('rank_turnover', '-')
                rank_inflow = s.get('rank_inflow', '-')
                
                # Intraday Chart Thumbnail
                chart_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?nid={full_code_nid}&imageType=RJY&token=44c9d251add88e27b65ed86506f6e5da&rnd={timestamp_ms}"
                chart_md = f"![{stock_name}]({chart_url})"
                
                f.write(f"| {idx} | [{stock_name}](#{stock_name}) | {change_pct} | {inflow} | {turnover} | {price:.2f} | {rank_change} | {rank_turnover} | {rank_inflow} | {chart_md} |\n")

            f.write("\n## 股票K线图\n\n")
            
            for s in item['main_list']:
                stock_code = s['f12']
                stock_name = s['f14']
                market_prefix = "1" if str(stock_code).startswith('6') else "0"
                full_code_nid = f"{market_prefix}.{stock_code}"
                
                f.write(f"### {stock_name}\n\n")
                f.write(f"![{stock_name}K线图](https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={full_code_nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms})\n\n")

            f.write("---\n")
            f.write(f"[[toc|Back to Dashboard]]\n")

    print(f"\nObsidian笔记已生成: {base_dir}")

def generate_sector_notes(sector_code_or_name, topN=10, sector_type=None, output_root=None):
    """
    Generate markdown view file for a specific sector code or name
    
    Args:
        sector_code_or_name: Sector code (e.g., 'BK0954') or name (e.g., '盲盒经济')
        topN: Number of top stocks to include (default: 10)
        sector_type: 'industry' or 'concept', auto-detected if None
        output_root: Output directory root, uses get_md_dir() if None
    
    Returns:
        Path to generated markdown file
    """
    # Get output root directory
    if output_root is None:
        output_root = get_md_dir()
    
    # Determine if input is a code or name
    sector_code = sector_code_or_name
    
    # If input doesn't start with 'BK', treat as name and lookup code
    if not str(sector_code_or_name).startswith('BK'):
        print(f"Input '{sector_code_or_name}' appears to be a sector name, looking up code...")
        sector_code, detected_type = lookup_sector_code(sector_code_or_name, sector_type)
        
        if sector_code is None:
            print("Sector lookup failed or cancelled")
            return None
        
        # Use detected type if not explicitly provided
        if sector_type is None:
            sector_type = detected_type
    
    # Auto-detect sector type if not provided
    if sector_type is None:
        print(f"Auto-detecting sector type for code: {sector_code}")
        
        # Try industry first (using cached list)
        industry_df = get_cached_sector_list('industry')
        if not industry_df.empty and sector_code in industry_df['股票代码'].values:
            sector_type = 'industry'
            print(f"  Detected as industry sector")
        else:
            # Try concept (using cached list)
            concept_df = get_cached_sector_list('concept')
            if not concept_df.empty and sector_code in concept_df['股票代码'].values:
                sector_type = 'concept'
                print(f"  Detected as concept sector")
            else:
                print(f"Error: Sector code {sector_code} not found in industry or concept lists")
                return None
    
    # Get sector information (using cached list)
    print(f"Fetching sector information for {sector_code}...")
    sector_df = get_cached_sector_list(sector_type)
    
    if sector_df.empty:
        print(f"Error: Could not fetch {sector_type} sector list")
        return None
    
    sector_row = sector_df[sector_df['股票代码'] == sector_code]
    if sector_row.empty:
        print(f"Error: Sector code {sector_code} not found in {sector_type} list")
        return None
    
    sector_name = sector_row.iloc[0]['股票名称']
    sector_change = float(sector_row.iloc[0]['涨跌幅']) / 100  # Convert to percentage
    
    print(f"Sector: {sector_name} ({sector_code}), Change: {sector_change:.2f}%")
    
    # Get stocks with rankings
    print(f"Fetching top {topN} stocks...")
    
    # Get all stocks sorted by different criteria
    all_stocks_by_change = get_sector_stocks(sector_code, sort_field='f3', top_n=None)
    all_stocks_by_turnover = get_sector_stocks(sector_code, sort_field='f8', top_n=None)
    all_stocks_by_inflow = get_sector_stocks(sector_code, sort_field='f62', top_n=None)
    
    if not all_stocks_by_change:
        print(f"Error: No stocks found for sector {sector_code}")
        return None
    
    # Create ranking dictionaries
    rank_by_change = {s['f12']: i+1 for i, s in enumerate(all_stocks_by_change)}
    rank_by_turnover = {s['f12']: i+1 for i, s in enumerate(all_stocks_by_turnover)}
    rank_by_inflow = {s['f12']: i+1 for i, s in enumerate(all_stocks_by_inflow)}
    
    # Get top N stocks by change
    top_stocks = all_stocks_by_change[:topN]
    
    # Add ranking info to each stock
    for stock in top_stocks:
        code = stock['f12']
        stock['rank_change'] = rank_by_change.get(code, '-')
        stock['rank_turnover'] = rank_by_turnover.get(code, '-')
        stock['rank_inflow'] = rank_by_inflow.get(code, '-')
    
    # Create output directory
    date_yyyymmdd = datetime.now().strftime('%Y%m%d')
    date_str = datetime.now().strftime('%Y-%m-%d')
    time_str = datetime.now().strftime('%H:%M:%S')
    
    base_dir = os.path.join(output_root, date_yyyymmdd)
    sectors_dir = os.path.join(base_dir, sector_type)
    os.makedirs(sectors_dir, exist_ok=True)
    
    # Calculate sector ranking based on change percentage
    # Get all sectors sorted by change to determine ranking
    all_sectors_df = sector_df.copy()
    all_sectors_df['f3_numeric'] = pd.to_numeric(all_sectors_df['涨跌幅'], errors='coerce')
    all_sectors_df = all_sectors_df.sort_values('f3_numeric', ascending=False)
    
    # Find ranking (1-indexed)
    sector_ranking = None
    for idx, row in enumerate(all_sectors_df.itertuples(), 1):
        # Access by attribute if mapped, or check logic
        # row._1 is index usually, but itertuples yields namedtuple. 
        # Column names like '股票代码' might be tricky in itertuples if they are Chinese.
        # Safer to use iterrows or access by position if names are problematic
        pass # placeholder loop logic replaced below in cleaner way
    
    sector_ranking = None
    # Reset index to allow finding index by condition easier
    all_sectors_df = all_sectors_df.reset_index(drop=True)
    matches = all_sectors_df.index[all_sectors_df['股票代码'] == sector_code].tolist()
    if matches:
        sector_ranking = matches[0] + 1
    
    # Generate markdown file with new naming convention: {sector_name}_{ranking}.md
    if sector_ranking:
        filename = f"{sector_name}_{sector_ranking}.md"
    else:
        # Fallback if ranking not found
        filename = f"{sector_name}.md"
    
    output_path = os.path.join(sectors_dir, filename)
    
    print(f"Generating markdown file: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"# {sector_name} ({sector_code})\n\n")
        f.write(f"**Change**: {sector_change:.2f}%\n")
        f.write(f"**Date**: {date_str} {time_str}\n\n")
        
        # Sector Charts
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        nid = f"90.{sector_code}"
        
        f.write(f"![{sector_name}走势图](https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms})\n\n")
        
        # Helper function for money formatting
        def fmt_money(val):
            try:
                v = float(val)
                if abs(v) > 100000000: return f"{v/100000000:.2f}亿"
                if abs(v) > 10000: return f"{v/10000:.0f}万"
                return str(val)
            except: return str(val)
        
        # Stock performance table
        f.write("## 股票表现汇总\n\n")
        f.write("| 序号 | 股票名称 | 涨跌幅 | 主力净流入 | 换手率 | 现价 | 🚀 | 🔥 | 💰 | 当日走势 |\n")
        f.write("|:---:|---|---:|---:|---:|---:|:---:|:---:|:---:|:---:|\n")
        
        for idx, s in enumerate(top_stocks, 1):
            stock_code = s['f12']
            stock_name = s['f14']
            
            # Determine market prefix
            market_prefix = "1" if str(stock_code).startswith('6') else "0"
            full_code_nid = f"{market_prefix}.{stock_code}"
            
            def safe_float_divide_100(val):
                if val is None or val == '-' or val == '':
                    return 0.0
                try:
                    return float(val) / 100
                except (ValueError, TypeError):
                    return 0.0
            
            price = safe_float_divide_100(s.get('f2', 0))
            change_pct_val = safe_float_divide_100(s.get('f3', 0))
            turnover_val = safe_float_divide_100(s.get('f8', 0))
            change_pct = f"{change_pct_val:.2f}%" if change_pct_val != 0 else "-"
            turnover = f"{turnover_val:.2f}%" if turnover_val != 0 else "-"
            inflow = fmt_money(s.get('f62', '-'))
            
            # Ranks
            rank_change = s.get('rank_change', '-')
            rank_turnover = s.get('rank_turnover', '-')
            rank_inflow = s.get('rank_inflow', '-')
            
            # Chart thumbnail
            chart_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?nid={full_code_nid}&imageType=RJY&token=44c9d251add88e27b65ed86506f6e5da&rnd={timestamp_ms}"
            chart_md = f"![{stock_name}]({chart_url})"
            
            f.write(f"| {idx} | [{stock_name}](#{stock_name}) | {change_pct} | {inflow} | {turnover} | {price:.2f} | {rank_change} | {rank_turnover} | {rank_inflow} | {chart_md} |\n")
        
        # K-line charts section
        f.write("\n## 股票K线图\n\n")
        
        for s in top_stocks:
            stock_code = s['f12']
            stock_name = s['f14']
            market_prefix = "1" if str(stock_code).startswith('6') else "0"
            full_code_nid = f"{market_prefix}.{stock_code}"
            
            f.write(f"### {stock_name}\n\n")
            f.write(f"![{stock_name}K线图](https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={full_code_nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms})\n\n")
    
    print(f"✓ Markdown file generated: {output_path}")
    return output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='分析行业板块股票表现',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取并保存板块扩展数据 (包含行业和概念)
  python sched_performers.py --ext-info

  # 分析前10个板块的所有股票（结果保留前5名）
  python sched_performers.py
  
  # 分析前20个板块的所有股票，结果保留前10名
  python sched_performers.py --sectors 20 --top 10

  # 分析所有板块 (使用 0)
  python sched_performers.py --sectors 0 --top 5

  # 更新板块成分股缓存 (行业)
  python sched_performers.py --sector-type industry --update-sector-list

  # 更新板块成分股缓存 (概念)
  python sched_performers.py --sector-type concept --update-sector-list

  # 仅更新板块成分股缓存后退出
  python sched_performers.py --sector-type industry --update-sector-list-only

  # 随机补全5个缺失的板块成分股文件
  python sched_performers.py --sector-type concept --update-random-missing --update-sector-list-only

  # 自定义过期天数并限制更新数量
  python sched_performers.py --sector-type industry --update-sector-list --sector-stale-days 10 --update-limit 8

  # 正常分析并顺带刷新缓存
  python sched_performers.py --sector-type industry --update-sector-list --sectors 15 --top 8

  
        """
    )
    
    parser.add_argument(
        '--sectors',
        type=int,
        default=10,
        help='分析前N个表现最好的板块 (0表示所有板块, 默认: 10)'
    )
    parser.add_argument(
        '--sector-type',
        type=str,
        default='industry',
        choices=['industry', 'concept'],
        help='板块类型: industry (行业) or concept (概念), 默认: industry'
    )
    
    parser.add_argument(
        '--top',
        type=int,
        default=5,
        help='每个分类保留前N只股票在结果中 (默认: 5)'
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        help='从CSV文件加载数据并生成Obsidian笔记 (用于测试)'
    )

    parser.add_argument(
        '--ext-info',
        action='store_true',
        help='获取板块数据（扩展版本，包含行业和概念）'
    )

    parser.add_argument(
        '--update-sector-list',
        action='store_true',
        help='更新板块成分股缓存 (md_dir/sector/{sector_type})'
    )

    parser.add_argument(
        '--update-sector-list-only',
        action='store_true',
        help='仅更新板块成分股缓存后退出'
    )

    parser.add_argument(
        '--update-random-missing',
        action='store_true',
        help='随机更新5个缺失的板块成分股文件'
    )

    parser.add_argument(
        '--sector-stale-days',
        type=int,
        default=7,
        help='板块成分股文件超过该天数视为过期 (默认7天)'
    )

    parser.add_argument(
        '--update-limit',
        type=int,
        help='本次最多更新的板块数量 (可选)'
    )

    parser.add_argument(
        '--sector',
        type=str,
        help='生成指定板块的笔记 (可以是板块代码如 BK0954 或板块名称如 盲盒经济)'
    )

    parser.add_argument(
        '--sector-top',
        type=int,
        default=10,
        help='生成单个板块笔记时，包含的股票数量 (默认: 10)'
    )

    
    args = parser.parse_args()

    # 更新板块成分股缓存
    should_update_sector_list = args.update_sector_list or args.update_random_missing or args.update_sector_list_only
    if should_update_sector_list:
        update_sector_list(
            sector_type=args.sector_type,
            random_missing=args.update_random_missing,
            stale_days=args.sector_stale_days,
            max_updates=args.update_limit
        )
        # --update-sector-list 和 --update-sector-list-only 都只更新缓存后退出
        if args.update_sector_list_only or args.update_sector_list:
            exit(0)
    
    # If ext-info is requested, fetch extended sector data and exit
    if args.ext_info:
        # print("\n正在获取行业板块扩展数据...")
        industry_view = get_capreal_ext(sector_type='industry', md_dir=get_md_dir())
        # print("\n正在获取概念板块扩展数据...")
        concept_view = get_capreal_ext(sector_type='concept', md_dir=get_md_dir())
        print("\n✓ 扩展数据获取完成!")
        print("\n✓ Merging view!")
        if industry_view or concept_view:
            merge_view(industry_view, concept_view)
        else:
            print("警告: 无法获取视图文件，跳过合并")
            exit(0)

        # Exit after fetching extended info, as this is a separate mode
        exit(0)

    # If --sector is provided, generate notes for a specific sector
    if args.sector:
        print(f"\n生成单个板块笔记: {args.sector}")
        result = generate_sector_notes(
            args.sector, 
            topN=args.sector_top, 
            sector_type=args.sector_type if args.sector_type != 'industry' else None
        )
        if result:
            print(f"\n✓ 板块笔记已生成: {result}")
        else:
            print("\n✗ 板块笔记生成失败")
        exit(0)

    # If CSV file is provided, load from CSV and generate notes
    if args.csv:
        main(csv_path=args.csv, top_n=args.top)
    else:
        # Normal API-based mode
        print(f"分析板块数: {args.sectors}")
        main(sector_type=args.sector_type, sectors_count=args.sectors, top_n=args.top)

