#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票股东查询工具
支持缓存机制和横向条形图显示
"""

import sys
import os
import argparse
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fund_analyzer import FundAnalyzer
from stock_info_parser import StockInfoParser

def get_display_width(text):
    """
    计算字符串在终端中的显示宽度
    中文字符占2个字符宽度，英文字符占1个字符宽度
    """
    # 确保text是字符串类型
    if text is None:
        text = ''
    text = str(text)
    
    width = 0
    for char in text:
        # 判断是否为中文字符（包括中文标点）
        if ord(char) > 127:
            width += 2
        else:
            width += 1
    return width

def pad_string(text, target_width, align='left'):
    """
    填充字符串到目标显示宽度
    """
    # 确保text是字符串类型
    if text is None:
        text = ''
    text = str(text)
    
    current_width = get_display_width(text)
    if current_width >= target_width:
        return text
    
    padding = target_width - current_width
    if align == 'left':
        return text + ' ' * padding
    elif align == 'right':
        return ' ' * padding + text
    else:  # center
        left_pad = padding // 2
        right_pad = padding - left_pad
        return ' ' * left_pad + text + ' ' * right_pad

def get_cache_metadata_file():
    """获取缓存元数据文件路径"""
    cache_dir = Path("../generated/em")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "stockHolders_metadata.json"

def save_cache_metadata(stockcode, report_date, total, has_holders):
    """
    保存查询元数据到缓存文件（包括空结果）
    
    Args:
        stockcode: 股票代码
        report_date: 报告日期
        total: 总记录数（0表示没有股东）
        has_holders: 是否有股东数据（True/False）
    """
    metadata_file = get_cache_metadata_file()
    cache_key = f"{stockcode}_{report_date}"
    
    try:
        # 读取现有的元数据
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        # 更新元数据
        metadata[cache_key] = {
            'stockcode': str(stockcode),
            'report_date': report_date,
            'total': total,
            'has_holders': has_holders,
            'query_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 保存元数据
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        # 静默失败，不影响主流程
        pass

def load_cache_metadata(stockcode, report_date, cache_days=7):
    """
    加载查询元数据（包括空结果）
    
    Args:
        stockcode: 股票代码
        report_date: 报告日期
        cache_days: 缓存有效期（天数）
    
    Returns:
        dict: 如果缓存有效，返回元数据；否则返回None
    """
    metadata_file = get_cache_metadata_file()
    
    if not metadata_file.exists():
        return None
    
    try:
        # 确保stockcode是字符串格式，保持一致
        cache_key = f"{str(stockcode)}_{report_date}"
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 检查精确匹配
        if cache_key not in metadata:
            # 尝试所有键，看是否有匹配的（处理可能的格式不一致）
            for key, value in metadata.items():
                if str(stockcode) == str(value.get('stockcode', '')) and report_date == value.get('report_date', ''):
                    cache_info = value
                    break
            else:
                return None
        else:
            cache_info = metadata[cache_key]
        
        query_time_str = cache_info.get('query_time', '')
        
        if not query_time_str:
            return None
        
        # 检查是否在缓存有效期内
        query_time = datetime.strptime(query_time_str, '%Y-%m-%d %H:%M:%S')
        days_diff = (datetime.now() - query_time).days
        
        if days_diff > cache_days:
            return None
        
        return cache_info
        
    except Exception as e:
        # 静默失败
        return None

def load_from_csv_cache(stockcode, report_date, cache_days=7):
    """
    从CSV缓存文件加载股票股东数据
    
    Args:
        stockcode: 股票代码（字符串，保持前导0）
        report_date: 报告日期 (YYYY-MM-DD)
        cache_days: 缓存有效期（天数），默认7天
    
    Returns:
        dict: 如果缓存有效，返回与API格式相同的数据结构；否则返回None
    """
    # 首先检查元数据缓存（包括空结果）
    # 确保stockcode格式一致
    stockcode_str = str(stockcode)
    metadata = load_cache_metadata(stockcode_str, report_date, cache_days)
    
    if metadata:
        # 如果没有股东数据（total=0），直接返回空结果，不需要查询CSV
        if not metadata.get('has_holders', False) or metadata.get('total', 0) == 0:
            # 从缓存返回空结果，避免重复查询API
            return {
                'stockcode': stockcode_str,
                'report_date': report_date,
                'holders': [],
                'total': 0,
                'page_num': 1,
                'page_size': 0
            }
    
    # CSV文件路径
    csv_file = Path("../generated/em/fundHolders.csv")
    
    if not csv_file.exists():
        return None
    
    try:
        # 读取CSV文件，确保代码列保持为字符串类型（保留前导0）
        df = pd.read_csv(csv_file, dtype={
            'stockcode': str,
            'holder_code': str
        })
        
        # 确保输入的stockcode也是字符串格式
        stockcode_str = str(stockcode)
        
        # 检查是否有匹配的股票代码和报告日期
        df['stockcode'] = df['stockcode'].astype(str)
        mask = (df['stockcode'] == stockcode_str) & (df['report_date'] == report_date)
        matched_data = df[mask].copy()  # 使用 copy() 避免 SettingWithCopyWarning
        
        if matched_data.empty:
            return None
        
        # 检查update_time是否在缓存有效期内
        matched_data['update_time'] = pd.to_datetime(matched_data['update_time'])
        latest_update = matched_data['update_time'].max()
        
        # 检查是否在7天内
        days_diff = (datetime.now() - latest_update.to_pydatetime()).days
        if days_diff > cache_days:
            return None
        
        # 确保所有代码字段都是字符串类型（保留前导0）
        if 'holder_code' in matched_data.columns:
            matched_data['holder_code'] = matched_data['holder_code'].astype(str)
        
        # 转换DataFrame为字典列表
        holders = matched_data.to_dict('records')
        
        # 转换为与API返回格式相同的数据结构
        result = {
            'stockcode': stockcode,
            'report_date': report_date,
            'holders': holders,
            'total': len(holders),
            'page_num': 1,
            'page_size': len(holders)
        }
        
        return result
        
    except Exception as e:
        # 静默失败，直接返回None，将从API获取数据
        return None

def resolve_stock_code(input_value):
    """
    解析股票输入（可能是股票代码或股票名称），返回股票代码和行情信息
    
    Args:
        input_value: 股票代码或股票名称，如 "002195" 或 "岩山科技" 或 "YSKJ"
    
    Returns:
        tuple: (stock_code, quote_info) 股票代码和行情信息字典，如果未找到则返回 (None, None)
    """
    stock_parser = StockInfoParser()
    
    # 首先检查是否是纯数字（可能是股票代码）
    if input_value.isdigit() and len(input_value) >= 4:
        # 尝试直接作为股票代码获取行情
        # try:
        #     quote = stock_parser.get_stock_quote_by_code(input_value)
        #     if quote:
        #         return quote['code'], quote
        # except Exception as e:
        #     # 如果获取失败，继续尝试其他方法
        #     pass
        # 直接返回股票代码，不获取行情信息
        return input_value, None
    
    # 如果不是纯数字，尝试作为股票名称或简拼搜索
    # 1. 先尝试通过名称搜索（精确匹配或包含匹配）
    try:
        stock_code = stock_parser.search_stock_by_name(input_value)
        if stock_code:
            # quote = stock_parser.get_stock_quote_by_code(stock_code)
            # if quote:
            #     return quote['code'], quote
            # 直接返回股票代码，不获取行情信息
            return stock_code, None
    except Exception:
        pass
    
    # 2. 再尝试通过简拼搜索
    # try:
    #     quote = stock_parser.search_stock_by_pinyin_abbr(input_value.upper())
    #     if quote:
    #         return quote['code'], quote
    # except Exception:
    #     pass
    
    # 如果都找不到，返回None
    return None, None

def print_stock_quote(quote):
    """
    打印股票行情信息
    
    Args:
        quote: 股票行情信息字典
    """
    if not quote:
        return
    
    print("\n" + "="*60)
    print("股票行情信息")
    print("="*60)
    print(f"股票代码: {quote['code']}")
    print(f"股票名称: {quote['name']}")
    if quote.get('pinyin_abbr'):
        print(f"股票简拼: {quote['pinyin_abbr']}")
    print(f"涨跌幅: {quote['change_pct']:+.2f}%")
    print(f"状态: {quote['change_status']}")
    print("="*60)

def print_horizontal_bar(holders, stockcode, max_width=50, limit=20):
    """
    在终端打印横向条形图
    
    Args:
        holders: 股东列表，每个股东包含 holder_name, holder_code, hold_amount 等字段
        stockcode: 股票代码
        max_width: 条形图最大宽度（字符数）
    """
    if not holders:
        print("没有股东数据可显示")
        return
    
    # 从第一个股东记录中获取股票信息
    stock_name = str(holders[0].get('stock_name', '')) if holders else ''
    stockcode_str = str(stockcode)
    
    # 构建标题
    if stock_name:
        title = f"{stock_name}({stockcode_str})"
    else:
        title = f"({stockcode_str})"
    
    # 按持股金额排序（降序）
    sorted_holders = sorted(holders, key=lambda x: x.get('hold_amount', 0), reverse=True)
    
    # 只显示前 limit 条记录
    sorted_holders = sorted_holders[:limit]
    
    # 找到最大持股金额，用于计算比例
    max_amount = max(h.get('hold_amount', 0) for h in sorted_holders) if sorted_holders else 1
    
    # 定义列宽（显示宽度）
    name_width = 25
    code_width = 15
    amount_width = 15
    ratio_width = 8
    bar_width = max_width
    
    # 计算标题行的宽度
    title_width = name_width + code_width + amount_width + ratio_width + bar_width + 10
    
    print("\n" + "=" * title_width)
    print(title)
    print("=" * title_width)
    
    # 打印表头
    header = pad_string("股东名称", name_width) + " " + \
             pad_string("股东代码", code_width) + " " + \
             pad_string("持股数量", amount_width, 'right') + " " + \
             pad_string("比例", ratio_width, 'right') + " " + \
             "条形图"
    print(header)
    print("-" * title_width)
    
    for holder in sorted_holders:
        # 确保所有字段都是正确的类型
        holder_name = str(holder.get('holder_name', 'N/A'))
        # 限制名称长度（按显示宽度）
        if get_display_width(holder_name) > name_width:
            # 截断名称
            truncated = ""
            for char in holder_name:
                if get_display_width(truncated + char) <= name_width - 2:
                    truncated += char
                else:
                    break
            holder_name = truncated + ".."
        
        holder_code = str(holder.get('holder_code', 'N/A'))
        hold_amount = float(holder.get('hold_amount', 0))
        hold_ratio = float(holder.get('hold_ratio', 0))
        
        # 计算条形长度
        if max_amount > 0:
            bar_length = int((hold_amount / max_amount) * max_width)
        else:
            bar_length = 0
        
        # 生成条形图（使用Unicode块字符）
        bar = '█' * bar_length
        
        # 格式化持股数量（以万为单位显示，如果很大）
        if hold_amount >= 10000:
            amount_str = f"{hold_amount/10000:.2f}万"
        else:
            amount_str = f"{hold_amount:,.0f}"
        
        # 格式化比例
        ratio_str = f"{hold_ratio:.2f}%"
        
        # 使用正确的对齐方式打印
        line = pad_string(holder_name, name_width) + " " + \
               pad_string(holder_code, code_width) + " " + \
               pad_string(amount_str, amount_width, 'right') + " " + \
               pad_string(ratio_str, ratio_width, 'right') + " " + \
               bar
        print(line)
    
    print("=" * title_width)
    print(f"总计: {len(sorted_holders)} 个股东")
    if max_amount >= 10000:
        print(f"最大持股数量: {max_amount/10000:.2f}万")
    else:
        print(f"最大持股数量: {max_amount:,.0f}")

def main():
    """Query stock holders via command line arguments"""
    parser = argparse.ArgumentParser(description="Query stock holders")
    parser.add_argument("stockcode", help="Stock Code, Stock Name, or Pinyin Abbreviation (e.g. 002230, 岩山科技, YSKJ)")
    parser.add_argument("--date", default="2025-09-30", help="Report Date (YYYY-MM-DD), default: 2025-09-30")
    parser.add_argument("--limit", type=int, default=10, help="Number of holders to show in list mode, default: 10")
    parser.add_argument("--list", action="store_true", help="Display detailed list instead of bar chart (default: bar chart)")
    
    args = parser.parse_args()
    
    # 默认使用条形图，除非指定 --list
    use_bar = not args.list
    
    # 1. 首先解析输入，获取股票代码和行情信息
    actual_stockcode, quote = resolve_stock_code(args.stockcode)
    
    if not actual_stockcode:
        print(f"❌ 未找到股票: {args.stockcode}")
        print("   请检查输入的股票代码、股票名称或简拼是否正确")
        return
    
    # 2. 显示股票行情信息（只在条形图模式下显示，列表模式下会显示详细信息）
    # if use_bar:
    #     print_stock_quote(quote)
    if not use_bar:
        # print(f"Querying stock {args.stockcode} ({actual_stockcode} {quote['name']}) holders for date {args.date}...")
        print(f"Querying stock {args.stockcode} ({actual_stockcode}) holders for date {args.date}...")
        print("=" * 60)
    
    analyzer = FundAnalyzer()
    
    # 3. 检查CSV缓存（使用实际的股票代码）
    # 如果缓存有效，直接使用缓存数据，不调用API
    result = load_from_csv_cache(actual_stockcode, args.date, cache_days=7)
    
    # 4. 如果缓存无效或不存在，从API获取数据
    # API获取后会自动保存到CSV（保存前会先删除旧缓存）
    if result is None:
        if not use_bar:
            print("📡 从API获取数据...")
        # 条形图模式获取更多数据
        page_size = 300 if use_bar else 50
        result = analyzer.stockHolders(actual_stockcode, report_date=args.date, page_num=1, page_size=page_size)
        
        # 保存查询元数据到缓存（包括空结果）
        # 即使result是空结果（total=0），也要保存元数据
        if result is not None:
            has_holders = result.get('total', 0) > 0 and len(result.get('holders', [])) > 0
            save_cache_metadata(actual_stockcode, args.date, result.get('total', 0), has_holders)
        else:
            # API返回None，可能是错误，但也记录为没有股东（防止重复查询）
            save_cache_metadata(actual_stockcode, args.date, 0, False)
    
    if result:
        # 如果使用条形图，只显示条形图
        if use_bar:
            print_horizontal_bar(result['holders'], actual_stockcode)
        else:
            # 列表模式显示详细信息
            # 先显示股票行情
            # print_stock_quote(quote)
            print(f"\n股票代码: {result['stockcode']}")
            print(f"报告日期: {result['report_date']}")
            print(f"总记录数: {result['total']}")
            
            # Calculate max pages for display info
            page_size = result.get('page_size', 50)
            total = result.get('total', 0)
            total_pages = (total // page_size + 1) if page_size > 0 else 1
            print(f"当前页: {result['page_num']}/{total_pages}")
            
            print("\n股东列表:")
            print("-" * 60)
            
            holders_to_show = result['holders'][:args.limit]
            
            for i, holder in enumerate(holders_to_show, 1):
                print(f"\n{i}. {holder['holder_name']}")
                print(f"   股东代码: {holder['holder_code']}")
                print(f"   持股数量: {holder['hold_amount']:,.0f}")
                print(f"   持股比例: {holder['hold_ratio']:.2f}%")
                print(f"   持股市值: {holder['hold_value']:,.0f}")
                print(f"   持股变化: {holder['change_amount']:,.0f}")
                print(f"   比例变化: {holder['change_ratio']:.2f}%")
                print(f"   股东类型: {holder['holder_type_name']}")
            
            remaining = len(result['holders']) - args.limit
            if remaining > 0:
                print(f"\n... 还有 {remaining} 个股东 (use --limit to see more)")
    else:
        print("❌ Query Failed")

if __name__ == "__main__":
    main()
