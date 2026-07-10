#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合基金分析器
整合基金信息、股票持仓、趋势分析的综合分析工具
"""

import argparse
import json
import os
import time
import requests
import pandas as pd
import re
from datetime import datetime, timedelta
from pathlib import Path
from fund_parser import FundDataParser
from stock_info_parser import StockInfoParser
from fund_trends_analyzer import FundTrendsAnalyzer
'''

implement stockHolding(fundcode) such that I can query stocks held by a fund,
'''

class FundAnalyzer:
    """综合基金分析器"""
    
    def __init__(self, cache_dir="../generated/em/cache/"):
        self.fund_parser = None
        self.stock_parser = StockInfoParser()
        self.trends_analyzer = None
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_duration = 3600  # 1小时缓存时间（秒）
    
    def get_stock_codes_by_names(self, stock_names: list) -> dict:
        """
        根据股票名称列表获取股票代码列表
        
        Args:
            stock_names: 股票名称列表，如 ["蓝色光标", "利欧股份", "南兴股份"]
        
        Returns:
            dict: {股票名称: (股票代码, '')}，如果未找到则值为 (None, '')
        """
        results = {}
        
        for stock_name in stock_names:
            try:
                # 首先尝试通过名称搜索股票代码
                stock_code = self.stock_parser.search_stock_by_name(stock_name)
                
                if stock_code:
                    results[stock_name] = (stock_code, '')
                else:
                    # 如果通过名称没找到，尝试通过简拼搜索
                    quote = self.stock_parser.search_stock_by_pinyin_abbr(stock_name.upper())
                    if quote:
                        results[stock_name] = (quote['code'], '')
                    else:
                        results[stock_name] = (None, '')
            except Exception as e:
                results[stock_name] = (None, '')
        
        return results
    
    def get_stock_codes_by_names2(self, stock_names: list) -> dict:
        """
        根据股票名称列表获取股票代码列表（从最新的CSV文件中查找）
        
        Args:
            stock_names: 股票名称列表，如 ["蓝色光标", "利欧股份", "南兴股份"]
        
        Returns:
            dict: {股票名称: (股票代码, '')}，如果未找到则值为 (None, '')
        """
        results = {name: (None, '') for name in stock_names}
        
        try:
            # 获取基础目录路径
            base_dir = Path("../generated/em")
            
            if not base_dir.exists():
                return results
            
            # 找到最新的日期目录（格式如 260109）
            date_dirs = []
            for item in base_dir.iterdir():
                if item.is_dir() and item.name.isdigit() and len(item.name) == 6:
                    date_dirs.append(item)
            
            if not date_dirs:
                return results
            
            # 按目录名（日期）排序，获取最新的
            date_dirs.sort(key=lambda x: x.name, reverse=True)
            
            latest_quote_file = None
            for date_dir in date_dirs:
                # 在该目录中找到所有的 quote_*.csv 文件
                quote_files = list(date_dir.glob("quote_*.csv"))
                if quote_files:
                    # 按文件名排序，获取最新的（文件名包含时间戳）
                    quote_files.sort(key=lambda x: x.name, reverse=True)
                    latest_quote_file = quote_files[0]
                    break
            
            if not latest_quote_file:
                return results
            
            # 读取CSV文件
            try:
                df = pd.read_csv(latest_quote_file, encoding='utf-8-sig')
                
                # 确保股票代码列是字符串类型（保留前导0）
                if '股票代码' in df.columns:
                    df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
                
                # 创建名称到代码的映射（同时支持原始名称和清理后的名称）
                name_to_code = {}
                if '股票名称' in df.columns and '股票代码' in df.columns:
                    for _, row in df.iterrows():
                        name = str(row['股票名称']).strip()
                        # 清理名称：移除所有空格（处理如 "万  科Ａ" 的情况）
                        name_clean = ''.join(name.split())
                        code = str(row['股票代码']).strip().zfill(6)
                        # 同时保存原始名称 and 清理后的名称
                        name_to_code[name] = code
                        if name_clean != name:
                            name_to_code[name_clean] = code
                
                # 匹配股票名称（支持精确匹配和清理后的匹配）
                for stock_name in stock_names:
                    stock_code = None
                    
                    # 1. 精确匹配
                    if stock_name in name_to_code:
                        stock_code = name_to_code[stock_name]
                    else:
                        # 2. 清理后匹配（移除空格）
                        stock_name_clean = ''.join(stock_name.split())
                        if stock_name_clean in name_to_code:
                            stock_code = name_to_code[stock_name_clean]
                        else:
                            # 3. 模糊匹配（包含匹配）
                            for csv_name, csv_code in name_to_code.items():
                                # 如果CSV名称包含输入名称，或者输入名称包含CSV名称
                                if stock_name in csv_name or csv_name in stock_name:
                                    stock_code = csv_code
                                    break
                    
                    if stock_code:
                        # 直接返回股票代码，不需要获取行情信息
                        results[stock_name] = (stock_code, '')
                    
            except Exception as e:
                # CSV读取失败，静默返回
                pass
                
        except Exception as e:
            # 发生错误，静默返回
            pass
        
        return results
    
    def _get_cache_file(self, fund_code: str, data_type: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{fund_code}_{data_type}.json"
    
    def _is_cache_valid(self, cache_file: Path) -> bool:
        """检查缓存是否有效（1小时内）"""
        if not cache_file.exists():
            return False
        
        # 检查文件修改时间
        file_mtime = cache_file.stat().st_mtime
        current_time = time.time()
        
        return (current_time - file_mtime) < self.cache_duration
    
    def _load_from_cache(self, cache_file: Path) -> dict:
        """从缓存加载数据"""
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"📁 从缓存加载数据: {cache_file.name}")
            return data
        except Exception as e:
            print(f"❌ 加载缓存失败: {e}")
            return None
    
    def _save_to_cache(self, data: dict, cache_file: Path) -> bool:
        """保存数据到缓存"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 数据已缓存: {cache_file.name}")
            return True
        except Exception as e:
            print(f"❌ 保存缓存失败: {e}")
            return False
    
    def _load_complete_cache(self, fund_code: str) -> dict:
        """加载完整的缓存数据"""
        cache_file = self._get_cache_file(fund_code, "complete")
        if self._is_cache_valid(cache_file):
            return self._load_from_cache(cache_file)
        return None
    
    def _save_complete_cache(self, fund_code: str, data: dict) -> bool:
        """保存完整的缓存数据"""
        cache_file = self._get_cache_file(fund_code, "complete")
        return self._save_to_cache(data, cache_file)
    
    def _get_fund_data_with_cache(self, fund_code: str) -> dict:
        """获取基金数据（带缓存）"""
        cache_file = self._get_cache_file(fund_code, "fund")
        
        if self._is_cache_valid(cache_file):
            return self._load_from_cache(cache_file)
        
        # 缓存无效或不存在，重新获取数据
        self.fund_parser = FundDataParser(fund_code)
        try:
            fund_js_content = self.fund_parser.fetch_fund_data()
            fund_raw_data = self.fund_parser.parse_js_variables(fund_js_content)
            fund_formatted_data = self.fund_parser.format_fund_info(fund_raw_data)
            
            print("✅ 基金基本信息获取成功")
            self._save_to_cache(fund_formatted_data, cache_file)
            return fund_formatted_data
            
        except Exception as e:
            print(f"❌ 获取基金信息失败: {e}")
            return None
    
    def _get_trends_data_with_cache(self, fund_code: str) -> dict:
        """获取趋势数据（带缓存）"""
        cache_file = self._get_cache_file(fund_code, "trends")
        
        if self._is_cache_valid(cache_file):
            return self._load_from_cache(cache_file)
        
        # 缓存无效或不存在，重新获取数据
        self.trends_analyzer = FundTrendsAnalyzer(fund_code)
        try:
            trends_js_content = self.trends_analyzer.fetch_fund_data()
            trends_raw_data = self.trends_analyzer.parse_js_variables(trends_js_content)
            trends_formatted_data = self.trends_analyzer.format_trends_data(trends_raw_data)
            
            print("✅ 基金趋势数据获取成功")
            self._save_to_cache(trends_formatted_data, cache_file)
            return trends_formatted_data
            
        except Exception as e:
            print(f"❌ 获取趋势数据失败: {e}")
            return None
    
    def _get_stock_data_with_cache(self, fund_code: str, fund_formatted_data: dict) -> list:
        """获取股票数据（带缓存）"""
        cache_file = self._get_cache_file(fund_code, "stocks")
        
        if self._is_cache_valid(cache_file):
            return self._load_from_cache(cache_file)
        
        # 缓存无效或不存在，重新获取数据
        stock_data = None
        if fund_formatted_data['holdings']['stock_codes']:
            try:
                # 清理股票代码
                stock_codes = fund_formatted_data['holdings']['stock_codes']
                cleaned_codes = []
                for code in stock_codes:
                    if code and code.isdigit():
                        # 统一处理：截取前6位数字
                        if len(code) >= 6:
                            cleaned_codes.append(code[:6])
                        else:
                            cleaned_codes.append(code)
                    else:
                        cleaned_codes.append(code)
                
                print(f"原始股票代码: {stock_codes}")
                print(f"清理后股票代码: {cleaned_codes}")
                
                stock_raw_data = self.stock_parser.fetch_stock_data(cleaned_codes)
                stock_data = self.stock_parser.format_stock_info(stock_raw_data)
                
                print(f"✅ 成功获取 {len(stock_data)} 只股票的基本信息")
                self._save_to_cache(stock_data, cache_file)
                
            except Exception as e:
                print(f"❌ 获取股票信息失败: {e}")
        
        return stock_data
    
    def analyze_fund(self, fund_code: str, output_dir: str = "../generated/em/funds/", use_simple_report: bool = False):
        """综合分析基金"""
        print(f"开始综合分析基金 {fund_code}...")
        
        # 检查是否有完整的缓存数据
        cache_data = self._load_complete_cache(fund_code)
        if cache_data:
            print("📁 使用完整缓存数据，跳过数据获取步骤")
            fund_formatted_data = cache_data.get('fund_data')
            trends_formatted_data = cache_data.get('trends_data')
            stock_data = cache_data.get('stock_data')
        else:
            # 1. 获取基金基本信息
            print("\n=== 第一步：获取基金基本信息 ===")
            fund_formatted_data = self._get_fund_data_with_cache(fund_code)
            if not fund_formatted_data:
                return None
            
            # 2. 获取基金趋势数据
            print("\n=== 第二步：获取基金趋势数据 ===")
            trends_formatted_data = self._get_trends_data_with_cache(fund_code)
            
            # 3. 获取股票持仓信息
            print("\n=== 第三步：获取股票持仓信息 ===")
            stock_data = self._get_stock_data_with_cache(fund_code, fund_formatted_data)
            
            # 保存完整数据到缓存
            self._save_complete_cache(fund_code, {
                'fund_data': fund_formatted_data,
                'trends_data': trends_formatted_data,
                'stock_data': stock_data
            })
        
        # 4. 生成综合报告
        print("\n=== 第四步：生成综合报告 ===")
        try:
            if use_simple_report:
                output_file = self.generate_html_report(
                    fund_formatted_data, trends_formatted_data, stock_data, fund_code, output_dir
                )
            else:
                output_file = self.generate_report(
                    fund_formatted_data, trends_formatted_data, stock_data, fund_code, output_dir
                )
            
            if output_file:
                print(f"✅ 综合分析报告已生成: {output_file}")
                return output_file
            else:
                print("❌ 生成综合报告失败")
                return None
                
        except Exception as e:
            print(f"❌ 生成综合报告失败: {e}")
            return None
    
    def stockHolders(self, stockcode: str, report_date: str = None, page_num: int = 1, page_size: int = 30):
        """
        查询股票的股东信息（股东持股明细）
        
        Args:
            stockcode (str): 股票代码，如 '300124', '002460' 等
            report_date (str): 报告日期，格式 'YYYY-MM-DD'，默认为最新季度末
            page_num (int): 页码，默认1
            page_size (int): 每页数量，默认30
        
        Returns:
            dict: 包含股东信息的字典，包括：
                - holders: 股东列表
                - total: 总记录数
                - page_num: 当前页码
                - page_size: 每页数量
        """
        # 如果没有指定报告日期，使用最新季度末
        if report_date is None:
            today = datetime.now()
            # 计算最新季度末日期
            quarter = (today.month - 1) // 3 + 1
            if quarter == 1:
                report_date = f"{today.year}-03-31"
            elif quarter == 2:
                report_date = f"{today.year}-06-30"
            elif quarter == 3:
                report_date = f"{today.year}-09-30"
            else:
                report_date = f"{today.year}-12-31"
        
        # 构建API URL和参数
        api_url = "https://data.eastmoney.com/dataapi/zlsj/detail"
        
        params = {
            'SHType': '1',  # 股东类型，1表示全部
            'SHCode': '',   # 股东代码，空表示全部
            'SCode': stockcode,  # 股票代码
            'ReportDate': report_date,  # 报告日期
            'sortField': 'TOTAL_SHARES',  # 排序字段
            'sortDirec': '1',  # 排序方向，1表示升序
            'pageNum': str(page_num),
            'pageSize': str(page_size)
        }
        
        # 设置请求头
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Referer': f'https://data.eastmoney.com/zlsj/detail/{report_date}-0-{stockcode}.html',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }
        
        # 重试机制
        max_retries = 3
        retry_delay = 2  # 秒
        
        for attempt in range(max_retries):
            try:
                # 增加超时时间到30秒
                timeout = 30
                response = requests.get(api_url, params=params, headers=headers, timeout=timeout)
                response.raise_for_status()
                
                data = response.json()
                break  # 成功获取数据，退出重试循环
                
            except requests.Timeout as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  请求超时，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"❌ 获取股东信息失败: 请求超时（已重试{max_retries}次）")
                    return None
            except requests.RequestException as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  请求失败，{retry_delay}秒后重试 ({attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"❌ 获取股东信息失败: {e}")
                    return None
        
        # 解析返回的数据
        try:
            result = {
                'stockcode': stockcode,
                'report_date': report_date,
                'holders': [],
                'total': 0,
                'page_num': page_num,
                'page_size': page_size
            }
            
            # 尝试不同的数据结构路径
            holder_data = None
            if data.get('result') and data['result'].get('data'):
                holder_data = data['result']['data']
            elif data.get('data'):
                holder_data = data['data']
            elif isinstance(data, dict) and 'list' in data:
                holder_data = data
            
            if holder_data:
                # 提取总记录数
                if isinstance(holder_data, dict):
                    result['total'] = holder_data.get('total', holder_data.get('TOTAL', 0))
                    # 提取股东列表，尝试多个可能的键名
                    holders_list = holder_data.get('list') or holder_data.get('LIST') or \
                                  holder_data.get('data') or holder_data.get('DATA') or []
                    # 确保holders_list是列表类型
                    if not isinstance(holders_list, list):
                        holders_list = []
                elif isinstance(holder_data, list):
                    holders_list = holder_data
                    result['total'] = len(holders_list)
                else:
                    holders_list = []
                
                # 解析股东信息（根据实际API返回的字段名）
                # 提取数值字段，处理None值
                def safe_float(value, default=0.0):
                    """安全转换为float"""
                    if value is None or value == '':
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                
                def safe_get(holder, key, default=''):
                    """安全获取字典值，如果holder不是字典则返回默认值"""
                    if isinstance(holder, dict):
                        return holder.get(key, default)
                    return default
                
                for holder in holders_list:
                    # 如果holder不是字典类型，跳过或尝试转换
                    if not isinstance(holder, dict):
                        # 如果是列表，可能是嵌套结构，尝试取第一个元素
                        if isinstance(holder, list) and len(holder) > 0:
                            holder = holder[0] if isinstance(holder[0], dict) else {}
                        else:
                            # 跳过非字典类型的holder
                            continue
                    
                    # 确保holder是字典类型后再处理
                    if not isinstance(holder, dict):
                        continue
                    
                    holder_info = {
                        'holder_code': safe_get(holder, 'HOLDER_CODE', ''),
                        'holder_name': safe_get(holder, 'HOLDER_NAME', ''),
                        # 持股数量：TOTAL_SHARES
                        'hold_amount': safe_float(safe_get(holder, 'TOTAL_SHARES')),
                        # 持股比例：TOTAL_SHARES_RATIO
                        'hold_ratio': safe_float(safe_get(holder, 'TOTAL_SHARES_RATIO')),
                        # 持股市值：HOLD_MARKET_CAP
                        'hold_value': safe_float(safe_get(holder, 'HOLD_MARKET_CAP')),
                        # 持股变化：CHANGE_AMOUNT (可能不存在)
                        'change_amount': safe_float(safe_get(holder, 'CHANGE_AMOUNT')),
                        # 持股比例变化：CHANGE_RATIO (可能不存在)
                        'change_ratio': safe_float(safe_get(holder, 'CHANGE_RATIO')),
                        # 股东类型代码：ORG_TYPE_CODE
                        'holder_type': safe_get(holder, 'ORG_TYPE_CODE', ''),
                        # 股东类型名称：ORG_TYPE
                        'holder_type_name': safe_get(holder, 'ORG_TYPE', ''),
                        # 父机构代码：PARENT_ORG_CODE
                        'parent_org_code': safe_get(holder, 'PARENT_ORG_CODE', ''),
                        # 父机构名称：PARENT_ORG_NAME
                        'parent_org_name': safe_get(holder, 'PARENT_ORG_NAME', ''),
                        # 机构简称：ORG_NAME_ABBR
                        'org_name_abbr': safe_get(holder, 'ORG_NAME_ABBR', ''),
                        # 自由流通股比例：FREE_SHARES_RATIO
                        'free_shares_ratio': safe_float(safe_get(holder, 'FREE_SHARES_RATIO')),
                        # 净资产比例：NETASSET_RATIO
                        'netasset_ratio': safe_float(safe_get(holder, 'NETASSET_RATIO'))
                    }
                    result['holders'].append(holder_info)
                
                # 如果没有从data中获取total，使用holders列表长度
                if result['total'] == 0 and result['holders']:
                    result['total'] = len(result['holders'])
            
            # 添加更新时间字段
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for holder_info in result['holders']:
                holder_info['stockcode'] = stockcode
                holder_info['report_date'] = report_date
                holder_info['update_time'] = update_time
            
            # 保存到CSV文件
            self._save_holders_to_csv(result['holders'], stockcode, report_date)
            
            # 如果 holders 为空且 total 为 0，显示友好信息
            if result['total'] == 0 and len(result['holders']) == 0:
                print(f"{stockcode} has 0 holders")
            else:
                print(f"✅ 成功获取股票 {stockcode} 的股东信息，共 {result['total']} 条记录")
            return result
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return None
        except Exception as e:
            import traceback
            # 检查 result 是否存在且 holders 为空、total 为 0
            if 'result' in locals() and result.get('total', -1) == 0 and len(result.get('holders', [])) == 0:
                print(f"{stockcode} has 0 holders")
                return result
            else:
                print(f"❌ 处理股东信息失败: {e}")
                print(result if 'result' in locals() else 'Result not initialized')
                # 在调试模式下打印详细信息
                if hasattr(self, 'debug') and self.debug:
                    print(f"详细错误信息:\n{traceback.format_exc()}")
                    # 打印数据结构信息以便调试
                    if 'data' in locals():
                        print(f"API返回数据类型: {type(data)}")
                        if isinstance(data, dict):
                            print(f"API返回数据键: {list(data.keys())[:10]}")
                return None
    
    def stockHolding(self, fundcode: str, report_date: str = None, page_num: int = 1, page_size: int = 50):
        """
        查询指定基金持有的股票信息
        
        Args:
            fundcode (str): 基金代码，如 '562500', '006253' 等
            report_date (str): 报告日期，格式 'YYYY-MM-DD'，默认为最新季度末
            page_num (int): 页码，默认1
            page_size (int): 每页数量，默认50
        
        Returns:
            dict: 包含持仓股票信息的字典，包括：
                - stocks: 股票列表
                - total: 总记录数
                - page_num: 当前页码
                - page_size: 每页数量
        """
        # 如果没有指定报告日期，使用最新季度末
        if report_date is None:
            today = datetime.now()
            # 计算最新季度末日期
            quarter = (today.month - 1) // 3 + 1
            if quarter == 1:
                report_date = f"{today.year}-03-31"
            elif quarter == 2:
                report_date = f"{today.year}-06-30"
            elif quarter == 3:
                report_date = f"{today.year}-09-30"
            else:
                report_date = f"{today.year}-12-31"
        
        # 构建API URL和参数
        api_url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        
        # 生成callback函数名（模拟jQuery回调）
        import random
        callback_id = random.randint(100000000000000000000, 999999999999999999999)
        callback = f"jQuery{callback_id}_{int(datetime.now().timestamp() * 1000)}"
        
        params = {
            'callback': callback,
            'sortColumns': 'SECURITY_CODE',
            'sortTypes': '-1',  # -1表示降序
            'pageSize': str(page_size),
            'pageNumber': str(page_num),
            'reportName': 'RPT_MAINDATA_MAIN_POSITIONDETAILS',
            'columns': 'ALL',
            'quoteColumns': '',
            'filter': f'(HOLDER_CODE="{fundcode}")(REPORT_DATE=\'{report_date}\')',
            'source': 'WEB',
            'client': 'WEB'
        }
        
        # 设置请求头
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Referer': f'https://data.eastmoney.com/zlsj/ccjj/{report_date}-{fundcode}.html',
            'Sec-Fetch-Dest': 'script',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }
        
        try:
            response = requests.get(api_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析JSONP响应
            response_text = response.text
            # 移除callback包装：jQuery...(...)
            pattern = rf'{re.escape(callback)}\((.*)\);?$'
            match = re.search(pattern, response_text, re.DOTALL)
            
            if not match:
                # 尝试其他格式
                pattern = r'jQuery\d+_\d+\((.*)\);?$'
                match = re.search(pattern, response_text, re.DOTALL)
            
            if not match:
                print(f"❌ 无法解析JSONP响应")
                print(f"响应前500字符: {response_text[:500]}")
                return None
            
            json_str = match.group(1)
            data = json.loads(json_str)
            
            # 确保fundcode是字符串格式（保留前导0）
            fundcode_str = str(fundcode)
            
            # 解析返回的数据
            result = {
                'fundcode': fundcode_str,
                'report_date': report_date,
                'stocks': [],
                'total': 0,
                'page_num': page_num,
                'page_size': page_size
            }
            
            # 提取数据
            if data.get('result') and data['result'].get('data'):
                stock_data = data['result']['data']
                
                # 提取总记录数
                if isinstance(stock_data, dict):
                    result['total'] = stock_data.get('total', stock_data.get('TOTAL', 0))
                    # 提取股票列表
                    stocks_list = stock_data.get('list', stock_data.get('LIST', []))
                elif isinstance(stock_data, list):
                    stocks_list = stock_data
                    result['total'] = len(stocks_list)
                else:
                    stocks_list = []
                
                # 解析股票信息（根据实际API返回的字段名）
                for stock in stocks_list:
                    # 安全转换数值
                    def safe_float(value, default=0.0):
                        if value is None or value == '':
                            return default
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            return default
                    
                    stock_info = {
                        # 股票代码（确保是字符串，保留前导0）
                        'stock_code': str(stock.get('SECURITY_CODE', '')),
                        'stock_name': stock.get('SECURITY_NAME_ABBR', ''),
                        # 持股数量：TOTAL_SHARES
                        'hold_amount': safe_float(stock.get('TOTAL_SHARES')),
                        # 持股比例：TOTAL_SHARES_RATIO
                        'hold_ratio': safe_float(stock.get('TOTAL_SHARES_RATIO')),
                        # 持股市值：HOLD_MARKET_CAP
                        'hold_value': safe_float(stock.get('HOLD_MARKET_CAP')),
                        # 持股变化：CHANGE_NUM (可能不存在)
                        'change_amount': safe_float(stock.get('CHANGE_NUM')),
                        # 持股比例变化：CHANGE_RATIO (可能不存在)
                        'change_ratio': safe_float(stock.get('CHANGE_RATIO')),
                        # 市值：MARKET_VALUE (可能不存在)
                        'market_value': safe_float(stock.get('MARKET_VALUE')),
                        # 净资产比例：NETASSET_RATIO
                        'netasset_ratio': safe_float(stock.get('NETASSET_RATIO')),
                        # 自由流通股比例：FREE_SHARES_RATIO
                        'free_shares_ratio': safe_float(stock.get('FREE_SHARES_RATIO')),
                        # 基金代码：HOLDER_CODE（确保是字符串，保留前导0）
                        'holder_code': str(stock.get('HOLDER_CODE', '')),
                        # 基金名称：HOLDER_NAME
                        'holder_name': stock.get('HOLDER_NAME', ''),
                        # 父机构代码：PARENT_ORG_CODE
                        'parent_org_code': stock.get('PARENT_ORG_CODE', ''),
                        # 父机构名称：PARENT_ORG_NAME
                        'parent_org_name': stock.get('PARENT_ORG_NAME', ''),
                        # 机构类型代码：ORG_TYPE_CODE
                        'org_type_code': stock.get('ORG_TYPE_CODE', ''),
                        # 机构类型：ORG_TYPE
                        'org_type': stock.get('ORG_TYPE', ''),
                        # 机构简称：ORG_NAME_ABBR
                        'org_name_abbr': stock.get('ORG_NAME_ABBR', '')
                    }
                    result['stocks'].append(stock_info)
                
                # 如果没有从data中获取total，使用stocks列表长度
                if result['total'] == 0 and result['stocks']:
                    result['total'] = len(result['stocks'])
            
            # 添加更新时间字段
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for stock_info in result['stocks']:
                stock_info['fundcode'] = fundcode_str
                stock_info['report_date'] = report_date
                stock_info['update_time'] = update_time
            
            # 保存到CSV文件
            if result['stocks']:
                self._save_fund_holdings_to_csv(result['stocks'], fundcode_str, report_date)
            
            print(f"✅ 成功获取基金 {fundcode} 的持仓股票信息，共 {result['total']} 条记录")
            return result
            
        except requests.RequestException as e:
            print(f"❌ 获取持仓信息失败: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            print(f"响应文本: {response_text[:500] if 'response_text' in locals() else 'N/A'}")
            return None
        except Exception as e:
            print(f"❌ 处理持仓信息失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_holders_to_csv(self, holders: list, stockcode: str, report_date: str):
        """
        保存股东信息到CSV文件
        保存前会先删除相同股票代码和报告日期的旧缓存数据
        
        Args:
            holders: 股东信息列表
            stockcode: 股票代码
            report_date: 报告日期
        """
        if not holders:
            return
        
        # 确保输出目录存在
        output_dir = Path("../generated/em")
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_file = output_dir / "fundHolders.csv"
        
        try:
            # 确保stockcode是字符串格式（保留前导0）
            stockcode_str = str(stockcode)
            
            # 创建DataFrame
            df_new = pd.DataFrame(holders)
            
            # 确保新数据中的代码列都是字符串类型
            if 'stockcode' in df_new.columns:
                df_new['stockcode'] = df_new['stockcode'].astype(str)
            if 'holder_code' in df_new.columns:
                df_new['holder_code'] = df_new['holder_code'].astype(str)
            
            # 如果CSV文件已存在，先删除旧缓存数据
            if csv_file.exists():
                try:
                    # 读取时确保代码列保持为字符串类型（保留前导0）
                    df_existing = pd.read_csv(csv_file, dtype={
                        'stockcode': str,
                        'holder_code': str
                    })
                    
                    # 确保代码列都是字符串类型
                    df_existing['stockcode'] = df_existing['stockcode'].astype(str)
                    if 'holder_code' in df_existing.columns:
                        df_existing['holder_code'] = df_existing['holder_code'].astype(str)
                    
                    # 先删除相同股票代码和报告日期的旧数据（删除旧缓存）
                    df_existing = df_existing[
                        ~((df_existing['stockcode'] == stockcode_str) & 
                          (df_existing['report_date'] == report_date))
                    ]
                    
                    # 合并新旧数据（旧数据已删除，只保留其他股票的数据和新数据）
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                except Exception as e:
                    print(f"⚠️  读取现有CSV文件失败，将创建新文件: {e}")
                    df_combined = df_new
            else:
                df_combined = df_new
            
            # 按股票代码、报告日期、持股比例排序
            df_combined = df_combined.sort_values(
                by=['stockcode', 'report_date', 'hold_ratio'], 
                ascending=[True, False, False]
            )
            
            # 保存到CSV
            df_combined.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"💾 股东信息已保存到: {csv_file}")
            print(f"   本次新增: {len(df_new)} 条记录")
            print(f"   文件总计: {len(df_combined)} 条记录")
            
        except Exception as e:
            print(f"❌ 保存CSV文件失败: {e}")
    
    def _save_fund_holdings_to_csv(self, stocks: list, fundcode: str, report_date: str):
        """
        保存基金持仓股票信息到CSV文件
        保存前会先删除相同基金代码和报告日期的旧缓存数据
        
        Args:
            stocks: 股票信息列表
            fundcode: 基金代码
            report_date: 报告日期
        """
        if not stocks:
            return
        
        # 确保输出目录存在
        output_dir = Path("../generated/em")
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_file = output_dir / "fundHoldings.csv"
        
        try:
            # 确保fundcode是字符串格式（保留前导0）
            fundcode_str = str(fundcode)
            
            # 创建DataFrame
            df_new = pd.DataFrame(stocks)
            
            # 确保新数据中的代码列都是字符串类型（保留前导0）
            if 'fundcode' in df_new.columns:
                df_new['fundcode'] = df_new['fundcode'].astype(str)
            if 'holder_code' in df_new.columns:
                df_new['holder_code'] = df_new['holder_code'].astype(str)
            if 'stock_code' in df_new.columns:
                df_new['stock_code'] = df_new['stock_code'].astype(str)
            
            # 如果CSV文件已存在，先删除旧缓存数据
            if csv_file.exists():
                try:
                    # 读取时确保代码列保持为字符串类型（保留前导0）
                    df_existing = pd.read_csv(csv_file, dtype={
                        'fundcode': str,
                        'holder_code': str,
                        'stock_code': str
                    })
                    
                    # 确保代码列都是字符串类型
                    df_existing['fundcode'] = df_existing['fundcode'].astype(str)
                    if 'holder_code' in df_existing.columns:
                        df_existing['holder_code'] = df_existing['holder_code'].astype(str)
                    if 'stock_code' in df_existing.columns:
                        df_existing['stock_code'] = df_existing['stock_code'].astype(str)
                    
                    # 先删除相同基金代码和报告日期的旧数据（删除旧缓存）
                    df_existing = df_existing[
                        ~((df_existing['fundcode'] == fundcode_str) & 
                          (df_existing['report_date'] == report_date))
                    ]
                    
                    # 合并新旧数据（旧数据已删除，只保留其他基金的数据和新数据）
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                except Exception as e:
                    print(f"⚠️  读取现有CSV文件失败，将创建新文件: {e}")
                    df_combined = df_new
            else:
                df_combined = df_new
            
            # 按基金代码、报告日期、持股比例排序
            df_combined = df_combined.sort_values(
                by=['fundcode', 'report_date', 'hold_ratio'], 
                ascending=[True, False, False]
            )
            
            # 保存到CSV
            df_combined.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"💾 基金持仓信息已保存到: {csv_file}")
            print(f"   本次新增: {len(df_new)} 条记录")
            print(f"   文件总计: {len(df_combined)} 条记录")
            
        except Exception as e:
            print(f"❌ 保存CSV文件失败: {e}")
    
    def generate_report(self, fund_data, trends_data, stock_data, fund_code, output_dir):
        """生成综合报告"""
        from datetime import datetime
        from pathlib import Path
        
        # 基金基本信息
        basic = fund_data['basic_info']
        performance = fund_data['performance']
        
        # 趋势数据
        net_worth_data = trends_data['net_worth_trend'] if trends_data else []
        position_data = trends_data['position_trend'] if trends_data else []
        scale_data = trends_data['scale_fluctuation'] if trends_data else {}
        allocation_data = trends_data['asset_allocation'] if trends_data else {}
        
        # 股票统计
        stock_stats = ""
        if stock_data:
            up_stocks = [s for s in stock_data if s['change_pct'] > 0]
            down_stocks = [s for s in stock_data if s['change_pct'] < 0]
            flat_stocks = [s for s in stock_data if s['change_pct'] == 0]
            avg_change = sum(s['change_pct'] for s in stock_data) / len(stock_data) if stock_data else 0
            
            stock_stats = f"""
            <div class="stock-stats">
                <h3>持仓股票表现概览</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{len(stock_data)}</div>
                        <div class="stat-label">持仓股票总数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(up_stocks)}</div>
                        <div class="stat-label">上涨股票</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(down_stocks)}</div>
                        <div class="stat-label">下跌股票</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{avg_change:+.2f}%</div>
                        <div class="stat-label">平均涨跌幅</div>
                    </div>
                </div>
            </div>
            """
        
        # 生成图表JavaScript
        chart_js = self.generate_charts(trends_data, stock_data)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>综合基金分析报告 - {basic['name']} ({basic['code']})</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #007bff;
            margin: 0;
            font-size: 32px;
        }}
        .header .subtitle {{
            color: #666;
            margin-top: 10px;
            font-size: 18px;
        }}
        .section {{
            margin-bottom: 30px;
            padding: 25px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #fafafa;
        }}
        .section h2 {{
            color: #333;
            margin-top: 0;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
            font-size: 22px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .info-item {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }}
        .performance-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .performance-item {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .performance-item h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
        }}
        .performance-item .value {{
            font-size: 24px;
            font-weight: bold;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stock-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 80px;
        }}
        .stock-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }}
        .stock-link {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
            text-decoration: none;
            color: inherit;
            transition: all 0.2s ease;
        }}
        .stock-link:hover {{
            text-decoration: none;
            color: inherit;
        }}
        .stock-link:hover .stock-code {{
            color: #007bff;
        }}
        .stock-link:hover .stock-name {{
            color: #007bff;
        }}
        .stock-info {{
            flex: 1;
            margin-right: 15px;
        }}
        .stock-code {{
            font-family: monospace;
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        .stock-name {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        .change-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .change-pct {{
            font-size: 18px;
            font-weight: bold;
        }}
        .positive {{ color: #dc3545; }}
        .negative {{ color: #28a745; }}
        .neutral {{ color: #6c757d; }}
        .stock-chart {{
            width: 120px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            overflow: hidden;
        }}
        .stock-chart img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 4px;
        }}
        .chart-fallback {{
            font-size: 12px;
            color: #6c757d;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-item {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
        }}
        .timestamp {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{basic['name']} 综合分析报告</h1>
            <div class="subtitle">基金代码: {basic['code']} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="section">
            <h2>基金基本信息</h2>
            <div class="info-grid">
                <div class="info-item">
                    <strong>基金名称:</strong> {basic['name']}
                </div>
                <div class="info-item">
                    <strong>基金代码:</strong> {basic['code']}
                </div>
                <div class="info-item">
                    <strong>原费率:</strong> {basic['source_rate']}%
                </div>
                <div class="info-item">
                    <strong>现费率:</strong> {basic['current_rate']}%
                </div>
                <div class="info-item">
                    <strong>最小申购金额:</strong> {basic['min_purchase']}元
                </div>
            </div>
        </div>

        <div class="section">
            <h2>业绩表现</h2>
            <div class="performance-grid">
                <div class="performance-item">
                    <h3>近一年收益率</h3>
                    <div class="value">{performance['y1_return']}%</div>
                </div>
                <div class="performance-item">
                    <h3>近6月收益率</h3>
                    <div class="value">{performance['y6_return']}%</div>
                </div>
                <div class="performance-item">
                    <h3>近三月收益率</h3>
                    <div class="value">{performance['y3_return']}%</div>
                </div>
                <div class="performance-item">
                    <h3>近一月收益率</h3>
                    <div class="value">{performance['y1m_return']}%</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>趋势图表分析</h2>
            <div class="chart-grid">
                <div class="chart-container">
                    <canvas id="netWorthChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="positionChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="scaleChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="allocationChart"></canvas>
                </div>
            </div>
        </div>

        {stock_stats}

        <div class="section">
            <h2>持仓股票详细信息</h2>
            <div class="stock-grid">
                {self.generate_stock_cards_html(stock_data) if stock_data else '<p>暂无股票数据</p>'}
            </div>
        </div>

        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    {chart_js}
</body>
</html>
        """
        
        # 保存文件
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 每天每个基金只生成一个报告
        filename = f"{fund_code}_details.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def generate_charts(self, trends_data, stock_data):
        """生成综合图表JavaScript"""
        import json
        
        # 处理净值走势数据
        net_worth_chart_data = []
        if trends_data and trends_data.get('net_worth_trend'):
            for item in trends_data['net_worth_trend'][-30:]:
                if isinstance(item, dict) and 'x' in item and 'y' in item:
                    from datetime import datetime
                    timestamp = item['x']
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    net_worth_chart_data.append({
                        'date': date,
                        'net_worth': item['y'],
                        'return': item.get('equityReturn', 0)
                    })
        
        # 处理仓位数据
        position_chart_data = []
        if trends_data and trends_data.get('position_trend'):
            for item in trends_data['position_trend'][-30:]:
                if isinstance(item, list) and len(item) >= 2:
                    from datetime import datetime
                    timestamp = item[0]
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    position_chart_data.append({
                        'date': date,
                        'position': item[1]
                    })
        
        # 处理规模变动数据
        scale_chart_data = []
        if trends_data and trends_data.get('scale_fluctuation'):
            scale_data = trends_data['scale_fluctuation']
            
            if scale_data.get('categories') and scale_data.get('series'):
                categories = scale_data['categories']
                series_data = scale_data['series']
                
                # 处理不同的数据结构
                if len(series_data) > 0:
                    # 检查是否是直接的数值数组格式
                    if isinstance(series_data[0], dict) and 'y' in series_data[0]:
                        # 新格式：每个元素包含y和mom字段
                        for i, category in enumerate(categories):
                            if i < len(series_data):
                                scale_chart_data.append({
                                    'date': category,
                                    'scale': series_data[i]['y'],
                                    'mom': series_data[i].get('mom', '')
                                })
                    elif isinstance(series_data[0], dict) and 'data' in series_data[0]:
                        # 旧格式：第一个元素包含data数组
                        series_item = series_data[0]
                        if series_item.get('data'):
                            for i, category in enumerate(categories):
                                if i < len(series_item['data']):
                                    scale_chart_data.append({
                                        'date': category,
                                        'scale': series_item['data'][i],
                                        'mom': series_item['mom'][i] if i < len(series_item['mom']) else ''
                                    })
        
        # 处理资产配置数据
        allocation_chart_data = []
        if trends_data and trends_data.get('asset_allocation'):
            allocation_data = trends_data['asset_allocation']
            if allocation_data.get('categories') and allocation_data.get('series'):
                categories = allocation_data['categories']
                for series in allocation_data['series']:
                    if series.get('name') and series.get('data'):
                        for i, category in enumerate(categories):
                            if i < len(series['data']):
                                allocation_chart_data.append({
                                    'date': category,
                                    'type': series['name'],
                                    'value': series['data'][i]
                                })
        
        # 生成Chart.js代码
        chart_js = f"""
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        // 净值走势图
        const netWorthCtx = document.getElementById('netWorthChart').getContext('2d');
        const netWorthData = {json.dumps(net_worth_chart_data)};
        
        if (netWorthData.length === 0) {{
            // 显示无数据提示
            netWorthCtx.font = '16px Arial';
            netWorthCtx.fillStyle = '#666';
            netWorthCtx.textAlign = 'center';
            netWorthCtx.fillText('暂无净值走势数据', netWorthCtx.canvas.width / 2, netWorthCtx.canvas.height / 2);
        }} else {{
            new Chart(netWorthCtx, {{
                type: 'line',
                data: {{
                    labels: netWorthData.map(item => item.date),
                    datasets: [{{
                        label: '单位净值',
                        data: netWorthData.map(item => item.net_worth),
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        tension: 0.4,
                        yAxisID: 'y'
                    }}, {{
                        label: '收益率(%)',
                        data: netWorthData.map(item => item.return),
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        tension: 0.4,
                        yAxisID: 'y1'
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: '基金净值走势图'
                        }}
                    }},
                    scales: {{
                        y: {{
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {{
                                display: true,
                                text: '单位净值'
                            }}
                        }},
                        y1: {{
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {{
                                display: true,
                                text: '收益率(%)'
                            }},
                            grid: {{
                                drawOnChartArea: false,
                            }},
                        }}
                    }}
                }}
            }});
        }}
        
        // 股票仓位图
        const positionCtx = document.getElementById('positionChart').getContext('2d');
        const positionData = {json.dumps(position_chart_data)};
        
        if (positionData.length === 0) {{
            // 显示无数据提示
            positionCtx.font = '16px Arial';
            positionCtx.fillStyle = '#666';
            positionCtx.textAlign = 'center';
            positionCtx.fillText('暂无仓位变化数据', positionCtx.canvas.width / 2, positionCtx.canvas.height / 2);
        }} else {{
            new Chart(positionCtx, {{
                type: 'line',
                data: {{
                    labels: positionData.map(item => item.date),
                    datasets: [{{
                        label: '股票仓位(%)',
                        data: positionData.map(item => item.position),
                        borderColor: '#dc3545',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        tension: 0.4,
                        fill: true
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: '股票仓位变化图'
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            title: {{
                                display: true,
                                text: '仓位比例(%)'
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        // 规模变动图
        const scaleCtx = document.getElementById('scaleChart').getContext('2d');
        const scaleData = {json.dumps(scale_chart_data)};
        
        // 检查数据是否为空
        if (scaleData.length === 0) {{
            // 显示无数据提示
            scaleCtx.font = '16px Arial';
            scaleCtx.fillStyle = '#666';
            scaleCtx.textAlign = 'center';
            scaleCtx.fillText('暂无规模变动数据', scaleCtx.canvas.width / 2, scaleCtx.canvas.height / 2);
        }} else {{
            new Chart(scaleCtx, {{
                type: 'bar',
                data: {{
                    labels: scaleData.map(item => item.date),
                    datasets: [{{
                        label: '基金规模(亿元)',
                        data: scaleData.map(item => item.scale),
                        backgroundColor: 'rgba(255, 193, 7, 0.8)',
                        borderColor: '#ffc107',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: '基金规模变动图'
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: '规模(亿元)'
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        // 资产配置图
        const allocationCtx = document.getElementById('allocationChart').getContext('2d');
        const allocationData = {json.dumps(allocation_chart_data)};
        
        if (allocationData.length === 0) {{
            // 显示无数据提示
            allocationCtx.font = '16px Arial';
            allocationCtx.fillStyle = '#666';
            allocationCtx.textAlign = 'center';
            allocationCtx.fillText('暂无资产配置数据', allocationCtx.canvas.width / 2, allocationCtx.canvas.height / 2);
        }} else {{
            // 按日期分组数据
            const groupedData = {{}};
            allocationData.forEach(item => {{
                if (!groupedData[item.date]) {{
                    groupedData[item.date] = {{}};
                }}
                groupedData[item.date][item.type] = item.value;
            }});
            
            const dates = Object.keys(groupedData);
            const stockData = dates.map(date => groupedData[date]['股票占净比'] || 0);
            const bondData = dates.map(date => groupedData[date]['债券占净比'] || 0);
            const cashData = dates.map(date => groupedData[date]['现金占净比'] || 0);
            
            new Chart(allocationCtx, {{
                type: 'bar',
                data: {{
                    labels: dates,
                    datasets: [{{
                        label: '股票占净比(%)',
                        data: stockData,
                        backgroundColor: 'rgba(0, 123, 255, 0.8)'
                    }}, {{
                        label: '债券占净比(%)',
                        data: bondData,
                        backgroundColor: 'rgba(40, 167, 69, 0.8)'
                    }}, {{
                        label: '现金占净比(%)',
                        data: cashData,
                        backgroundColor: 'rgba(255, 193, 7, 0.8)'
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        title: {{
                            display: true,
                            text: '资产配置变化图'
                        }}
                    }},
                    scales: {{
                        x: {{
                            stacked: true
                        }},
                        y: {{
                            stacked: true,
                            beginAtZero: true,
                            max: 100,
                            title: {{
                                display: true,
                                text: '占比(%)'
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        // 股票图表图片加载优化
        document.addEventListener('DOMContentLoaded', function() {{
            // 预加载股票图表图片
            const chartImages = document.querySelectorAll('.stock-chart img');
            chartImages.forEach(img => {{
                img.addEventListener('load', function() {{
                    this.style.opacity = '1';
                }});
                img.addEventListener('error', function() {{
                    this.style.display = 'none';
                    const fallback = this.nextElementSibling;
                    if (fallback) {{
                        fallback.style.display = 'flex';
                        fallback.textContent = '图表暂不可用';
                    }}
                }});
                // 设置初始透明度，加载完成后显示
                img.style.opacity = '0';
                img.style.transition = 'opacity 0.3s ease';
            }});
        }});
        </script>
        """
        
        return chart_js
    
    def generate_stock_cards_html(self, stock_data):
        """生成股票卡片HTML"""
        if not stock_data:
            return ""
        
        cards_html = ""
        for i, stock in enumerate(stock_data):
            change_class = "positive" if stock['change_pct'] > 0 else "negative" if stock['change_pct'] < 0 else "neutral"
            
            # 生成东方财富网股票链接和图表链接
            stock_url = self.generate_stock_url(stock['code'])
            chart_url = self.generate_stock_chart_url(stock['code'])
            
            cards_html += f"""
            <div class="stock-card">
                <a href="{stock_url}" target="_blank" class="stock-link">
                    <div class="stock-info">
                        <div class="stock-code">{stock['code']}</div>
                        <div class="stock-name">{stock['name']}</div>
                        <div class="change-info">
                            <span class="change-pct {change_class}">{stock['change_pct']:+.2f}%</span>
                            <span class="change-status">{stock['change_status']}</span>
                        </div>
                    </div>
                    <div class="stock-chart">
                        <img src="{chart_url}" 
                             alt="{stock['name']} 走势图" 
                             width="120" 
                             height="60"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <div class="chart-fallback" style="display:none; align-items:center; justify-content:center; width:120px; height:60px; background:#f8f9fa; border:1px solid #e9ecef; border-radius:4px; color:#6c757d; font-size:12px;">
                            图表加载中...
                        </div>
                    </div>
                </a>
            </div>
            """
        return cards_html
    
    def generate_stock_url(self, stock_code):
        """生成东方财富网股票链接"""
        # 根据股票代码判断市场
        if stock_code.startswith('0') or stock_code.startswith('3'):
            # 深市股票
            return f"https://quote.eastmoney.com/sz{stock_code}.html"
        elif stock_code.startswith('6'):
            # 沪市股票
            return f"https://quote.eastmoney.com/sh{stock_code}.html"
        elif stock_code.startswith('688') or stock_code.startswith('689'):
            # 科创板
            return f"https://quote.eastmoney.com/sh{stock_code}.html"
        elif stock_code.startswith('8') or stock_code.startswith('4'):
            # 北交所
            return f"https://quote.eastmoney.com/bj{stock_code}.html"
        else:
            # 默认深市
            return f"https://quote.eastmoney.com/sz{stock_code}.html"
    
    def generate_stock_chart_url(self, stock_code):
        """生成东方财富网股票图表图片链接"""
        import time
        import random
        
        # 根据股票代码判断市场前缀
        if stock_code.startswith('0') or stock_code.startswith('3'):
            # 深市股票
            nid = f"0.{stock_code}"
        elif stock_code.startswith('6'):
            # 沪市股票
            nid = f"1.{stock_code}"
        elif stock_code.startswith('688') or stock_code.startswith('689'):
            # 科创板
            nid = f"1.{stock_code}"
        elif stock_code.startswith('8') or stock_code.startswith('4'):
            # 北交所
            nid = f"0.{stock_code}"
        else:
            # 默认深市
            nid = f"0.{stock_code}"
        
        # 生成随机token和rnd参数
        token = ''.join(random.choices('0123456789abcdef', k=32))
        rnd = str(int(time.time()))
        
        return f"https://webquotepic.eastmoney.com/GetPic.aspx?nid={nid}&imageType=RJY&token={token}&rnd={rnd}"
    
    def generate_html_report(self, fund_data, trends_data, stock_data, fund_code, output_dir="../generated/em/funds/"):
        """生成HTML报告（简化版本）"""
        from datetime import datetime
        from pathlib import Path
        
        # 基金基本信息
        basic = fund_data['basic_info']
        performance = fund_data['performance']
        
        # 趋势数据
        net_worth_data = trends_data['net_worth_trend'] if trends_data else []
        position_data = trends_data['position_trend'] if trends_data else []
        scale_data = trends_data['scale_fluctuation'] if trends_data else {}
        allocation_data = trends_data['asset_allocation'] if trends_data else {}
        
        # 股票统计
        stock_stats = ""
        if stock_data:
            up_stocks = [s for s in stock_data if s['change_pct'] > 0]
            down_stocks = [s for s in stock_data if s['change_pct'] < 0]
            flat_stocks = [s for s in stock_data if s['change_pct'] == 0]
            avg_change = sum(s['change_pct'] for s in stock_data) / len(stock_data) if stock_data else 0
            
            stock_stats = f"""
            <div class="stock-stats">
                <h3>持仓股票表现概览</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{len(stock_data)}</div>
                        <div class="stat-label">持仓股票总数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(up_stocks)}</div>
                        <div class="stat-label">上涨股票</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{len(down_stocks)}</div>
                        <div class="stat-label">下跌股票</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{avg_change:+.2f}%</div>
                        <div class="stat-label">平均涨跌幅</div>
                    </div>
                </div>
            </div>
            """
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基金分析报告 - {basic['name']} ({basic['code']})</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #007bff;
            margin: 0;
            font-size: 28px;
        }}
        .header .subtitle {{
            color: #666;
            margin-top: 10px;
            font-size: 16px;
        }}
        .section {{
            margin-bottom: 25px;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #fafafa;
        }}
        .section h2 {{
            color: #333;
            margin-top: 0;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
            font-size: 20px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .info-item {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }}
        .performance-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .performance-item {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .performance-item h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
        }}
        .performance-item .value {{
            font-size: 22px;
            font-weight: bold;
        }}
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stock-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .stock-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }}
        .stock-code {{
            font-family: monospace;
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        .stock-name {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        .change-pct {{
            font-size: 18px;
            font-weight: bold;
        }}
        .positive {{ color: #dc3545; }}
        .negative {{ color: #28a745; }}
        .neutral {{ color: #6c757d; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-item {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
        }}
        .timestamp {{
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{basic['name']} 分析报告</h1>
            <div class="subtitle">基金代码: {basic['code']} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="section">
            <h2>基金基本信息</h2>
            <div class="info-grid">
                <div class="info-item">
                    <strong>基金名称:</strong> {basic['name']}
                </div>
                <div class="info-item">
                    <strong>基金代码:</strong> {basic['code']}
                </div>
                <div class="info-item">
                    <strong>原费率:</strong> {basic['source_rate']}%
                </div>
                <div class="info-item">
                    <strong>现费率:</strong> {basic['current_rate']}%
                </div>
                <div class="info-item">
                    <strong>最小申购金额:</strong> {basic['min_purchase']}元
                </div>
            </div>
        </div>

        <div class="section">
            <h2>业绩表现</h2>
            <div class="performance-grid">
                <div class="performance-item">
                    <h3>近一年收益率</h3>
                    <div class="value">{performance['y1_return']}%</div>
                </div>
                <div class="performance-item">
                    <h3>近6月收益率</h3>
                    <div class="value">{performance['y6_return']}%</div>
                </div>
                <div class="performance-item">
                    <h3>近三月收益率</h3>
                    <div class="value">{performance['y3_return']}%</div>
                </div>
                <div class="performance-item">
                    <h3>近一月收益率</h3>
                    <div class="value">{performance['y1m_return']}%</div>
                </div>
            </div>
        </div>

        {stock_stats}

        <div class="section">
            <h2>持仓股票详细信息</h2>
            <div class="stock-grid">
                {self.generate_stock_cards_html(stock_data) if stock_data else '<p>暂无股票数据</p>'}
            </div>
        </div>

        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """
        
        # 保存文件
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        filename = f"{fund_code}_simple_report.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='综合基金分析器')
    parser.add_argument('fund_code', help='基金代码，如: 006253')
    parser.add_argument('--output', '-o', default='../generated/em/funds/', 
                       help='输出目录 (默认: ../generated/em/funds/)')
    
    args = parser.parse_args()
    
    # 创建分析器实例
    analyzer = FundAnalyzer()
    
    # 综合分析基金
    output_file = analyzer.analyze_fund(args.fund_code, args.output)
    
    if output_file:
        print(f"\n🎉 综合分析完成！报告已保存至: {output_file}")
    else:
        print("\n❌ 分析失败")


if __name__ == "__main__":
    main()
