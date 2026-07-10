#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Concept Fund Analyzer
Identifies funds that invest most in a specific group of concept stocks.
"""

import os
import sys
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fund_analyzer import FundAnalyzer
from anyStock import load_from_csv_cache, save_cache_metadata, pad_string, get_display_width

import re

def extract_stocks_from_md(file_path):
    '''
    从 markdown 文件中提取股票名称
    支持格式: 股票名称: (例如: 利欧股份:)
    '''
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 匹配股票名称格式: 股票名称:
    # 匹配中文字符、英文字母、数字等，后面跟冒号和可能的空白
    pattern = r'^([^\n:]+?):\s*$'
    matches = re.findall(pattern, content, re.MULTILINE)
    
    # 清理提取的股票名称（去除首尾空白）
    stock_names = [match.strip() for match in matches if match.strip()]
    
    # 去重并保持顺序
    seen = set()
    unique_stocks = []
    for name in stock_names:
        if name not in seen:
            seen.add(name)
            unique_stocks.append(name)
    
    return unique_stocks

def main():
    parser = argparse.ArgumentParser(description="Concept Fund Analyzer - Identifies funds that invest most in a specific group of concept stocks")
    parser.add_argument("input_file", help="Input markdown file containing stock names (e.g. itips/字节豆包概念.md)")
    parser.add_argument("--use-codes", action="store_true", help="Show stock codes instead of stock names in the '涉及股票' column (default: show names)")
    args = parser.parse_args()
    
    analyzer = FundAnalyzer()
    
    # 1. 获取股票列表（提取股票代码）
    md_file = args.input_file
    stock_codes = extract_stocks_from_md(md_file)
    print(f"🔍 从 {md_file} 提取到 {len(stock_codes)} 个股票代码: {', '.join(stock_codes)}")
    
    # 从输入文件名提取概念名称（去掉路径和扩展名）
    input_path = Path(md_file)
    concept_name = input_path.stem  # 获取不带扩展名的文件名
    
    # 2. 使用提取的股票代码
    # 如果提取到的是代码（纯数字），直接使用；否则需要进一步处理
    resolved_stocks = {}  # code -> name 映射
    code_to_name = {}  # code -> name 映射，用于后续显示
    for item in stock_codes:
        # 如果是股票代码（纯数字），直接使用
        if item.isdigit() and len(item) >= 4:
            code = item.zfill(6)  # 补齐到6位
            resolved_stocks[code] = code
            code_to_name[code] = code  # 如果没有名称，先使用代码
        else:
            # 如果不是代码，尝试作为名称处理
            name_to_code = analyzer.get_stock_codes_by_names2([item])
            for name, (code, _) in name_to_code.items():
                if code:
                    resolved_stocks[code] = code
                    code_to_name[code] = item  # 保存原始提取的股票名称
    
    # 转换为 code -> code 的映射，后续查询使用代码
    stock_codes_list = list(resolved_stocks.keys())
    print(f"✅ 成功获取 {len(stock_codes_list)} 个股票代码")
    print(stock_codes_list)
    # 3. 查询每个股票的股东并聚合基金
    all_fund_holdings = []
    
    # 使用默认报告日期
    report_date = "2025-09-30"
    
    for code in stock_codes_list:
        print(f"\n📊 正在查询 {code} 的股东信息...")
        # 使用 anyStock.py 的缓存逻辑
        holders_data = load_from_csv_cache(code, report_date, cache_days=7)
        
        # 如果缓存无效或不存在，从API获取数据
        if holders_data is None:
            holders_data = analyzer.stockHolders(code, report_date=report_date, page_num=1, page_size=300)
            
            # 保存查询元数据到缓存（包括空结果）
            if holders_data is not None:
                has_holders = holders_data.get('total', 0) > 0 and len(holders_data.get('holders', [])) > 0
                save_cache_metadata(code, report_date, holders_data.get('total', 0), has_holders)
            else:
                # API返回None，记录为没有股东（防止重复查询）
                save_cache_metadata(code, report_date, 0, False)
        
        if holders_data and holders_data.get('holders'):
            # 获取股票名称（优先使用API返回的名称，否则使用映射中的名称）
            stock_name = code_to_name.get(code, code)
            if holders_data.get('holders') and len(holders_data['holders']) > 0:
                api_stock_name = holders_data['holders'][0].get('stock_name', '')
                if api_stock_name and api_stock_name != code:
                    stock_name = api_stock_name
                    code_to_name[code] = api_stock_name  # 更新映射
            
            for holder in holders_data['holders']:
                # 过滤基金类型 (ORG_TYPE_CODE 通常以 '01' 开头表示公募基金，或者根据实际数据判断)
                # 东方财富 API 中，公募基金的 PARENT_ORG_NAME 通常包含 "基金"
                # 或者 ORG_TYPE 包含 "基金"
                is_fund = False
                holder_name = holder.get('holder_name', '')
                holder_type = holder.get('holder_type_name', '')
                
                if '基金' in holder_name or '基金' in holder_type:
                    is_fund = True
                    
                if is_fund:
                    all_fund_holdings.append({
                        'stock_name': stock_name,
                        'stock_code': code,
                        'fund_name': holder_name,
                        'fund_code': holder.get('holder_code', ''),
                        'hold_value': holder.get('hold_value', 0),
                        'hold_ratio': holder.get('hold_ratio', 0),
                        'parent_org': holder.get('parent_org_name', '')
                    })
    
    if not all_fund_holdings:
        print("❌ 未发现相关基金持仓数据")
        return
    
    # 4. 汇总分析
    df = pd.DataFrame(all_fund_holdings)
    
    # 按基金汇总持仓市值
    if args.use_codes:
        # 如果使用代码，聚合stock_code
        fund_summary = df.groupby(['fund_name', 'fund_code', 'parent_org']).agg({
            'hold_value': 'sum',
            'stock_code': lambda x: ', '.join(sorted(x.unique())),
        }).reset_index()
        # 重命名列
        fund_summary = fund_summary.rename(columns={'stock_code': 'stock_display'})
        # 添加持股数
        hold_counts = df.groupby(['fund_name', 'fund_code', 'parent_org']).size().reset_index(name='hold_count')
        fund_summary = fund_summary.merge(hold_counts, on=['fund_name', 'fund_code', 'parent_org'])
    else:
        # 默认使用名称
        fund_summary = df.groupby(['fund_name', 'fund_code', 'parent_org']).agg({
            'hold_value': 'sum',
            'stock_name': lambda x: ', '.join(sorted(x.unique())),
            'stock_code': 'count'
        }).rename(columns={'stock_code': 'hold_count'}).reset_index()
        # 重命名列以统一处理
        fund_summary = fund_summary.rename(columns={'stock_name': 'stock_display'})
    
    # 按市值排序
    fund_summary = fund_summary.sort_values(by='hold_value', ascending=False)
    
    # 5. 输出结果
    print("\n" + "="*50)
    print(f"🏆 投资【{concept_name}】最多的基金 Top 20")
    print("="*50)
    
    top_funds = fund_summary.head(20)
    
    # 定义列宽（显示宽度）
    name_width = 32
    org_width = 20
    code_width = 12
    value_width = 18
    count_width = 8
    stocks_width = 60  # 增加股票名称列的宽度，以便显示更长的股票名称列表
    
    # 根据选项设置列名
    stock_column_name = "涉及股票(代码)" if args.use_codes else "涉及股票名称"
    
    # 格式化输出表头
    header = pad_string("基金名称", name_width) + " " + \
             pad_string("基金公司", org_width) + " " + \
             pad_string("基金代码", code_width) + " " + \
             pad_string("持仓市值(万)", value_width, 'right') + " " + \
             pad_string("持股数", count_width, 'right') + " " + \
             stock_column_name
    print(header)
    
    # 计算分隔线宽度
    separator_width = name_width + org_width + code_width + value_width + count_width + stocks_width + 5
    print("-" * separator_width)
    
    for _, row in top_funds.iterrows():
        name = str(row['fund_name'])
        # 如果名称过长，截断
        if get_display_width(name) > name_width:
            truncated = ""
            for char in name:
                if get_display_width(truncated + char) <= name_width - 2:
                    truncated += char
                else:
                    break
            name = truncated + ".."
        
        org = str(row['parent_org']) if row['parent_org'] else '-'
        # 如果公司名称过长，截断
        if get_display_width(org) > org_width:
            truncated = ""
            for char in org:
                if get_display_width(truncated + char) <= org_width - 2:
                    truncated += char
                else:
                    break
            org = truncated + ".."
        
        fund_code = str(row['fund_code']) if row['fund_code'] else '-'
        
        val = f"{row['hold_value']:,.2f}"
        count = str(int(row['hold_count']))
        stocks = str(row['stock_display'])
        # 如果股票列表过长，截断
        if get_display_width(stocks) > stocks_width:
            truncated = ""
            for char in stocks:
                if get_display_width(truncated + char) <= stocks_width - 2:
                    truncated += char
                else:
                    break
            stocks = truncated + ".."
        
        line = pad_string(name, name_width) + " " + \
               pad_string(org, org_width) + " " + \
               pad_string(fund_code, code_width) + " " + \
               pad_string(val, value_width, 'right') + " " + \
               pad_string(count, count_width, 'right') + " " + \
               stocks
        print(line)

    # 6. 保存到 Markdown 报告
    output_report = f"../generated/em/{concept_name}_funds.md"
    os.makedirs(os.path.dirname(output_report), exist_ok=True)
    
    with open(output_report, 'w', encoding='utf-8') as f:
        f.write(f"# {concept_name}概念股基金持仓分析报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 1. 概念股列表\n\n")
        f.write("| 股票名称 | 股票代码 |\n")
        f.write("| --- | --- |\n")
        for code in sorted(resolved_stocks.keys()):
            stock_name = code_to_name.get(code, code)
            f.write(f"| {stock_name} | {code} |\n")
            
        f.write("\n## 2. Top 20 持仓基金汇总\n\n")
        stock_column_header = "涉及股票(代码)" if args.use_codes else "涉及股票名称"
        f.write(f"| 基金名称 | 基金代码 | 基金公司 | 总持仓市值(万) | 持股数量 | {stock_column_header} |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for _, row in top_funds.iterrows():
            f.write(f"| {row['fund_name']} | {row['fund_code']} | {row['parent_org']} | {row['hold_value']:,.2f} | {row['hold_count']} | {row['stock_display']} |\n")

    print(f"\n✅ 详细报告已保存至: {output_report}")

if __name__ == "__main__":
    main()
