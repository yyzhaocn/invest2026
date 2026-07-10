#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票投资分析工具
"""

import argparse
from fund_analyzer import FundAnalyzer
from stock_info_parser import StockInfoParser
from anyStock import resolve_stock_code, print_stock_quote, load_from_csv_cache

def analyze_stock(stockcode, report_date=None):
    """
    综合分析股票
    
    Args:
        stockcode: 股票代码或股票名称
        report_date: 报告日期（默认最新季度末）
    """
    print("="*80)
    print("股票投资分析")
    print("="*80)
    
    # 1. 解析股票代码/名称
    parser = StockInfoParser()
    analyzer = FundAnalyzer()
    
    actual_stockcode, quote = resolve_stock_code(stockcode)
    
    if not actual_stockcode:
        print(f"❌ 未找到股票: {stockcode}")
        return
    
    # 2. 显示股票基本信息
    print("\n【一、股票基本信息】")
    print("="*80)
    print_stock_quote(quote)
    
    # 3. 获取股东信息
    print("\n【二、股东持股分析】")
    print("="*80)
    
    # 使用默认报告日期或指定日期
    if report_date is None:
        from datetime import datetime
        today = datetime.now()
        quarter = (today.month - 1) // 3 + 1
        if quarter == 1:
            report_date = f"{today.year}-03-31"
        elif quarter == 2:
            report_date = f"{today.year}-06-30"
        elif quarter == 3:
            report_date = f"{today.year}-09-30"
        else:
            report_date = f"{today.year}-12-31"
    
    print(f"报告日期: {report_date}\n")
    
    # 检查缓存
    result = load_from_csv_cache(actual_stockcode, report_date, cache_days=7)
    
    if result is None:
        print("📡 从API获取股东数据...")
        result = analyzer.stockHolders(actual_stockcode, report_date=report_date, page_num=1, page_size=300)
    
    if result:
        holders = result.get('holders', [])
        total = result.get('total', 0)
        
        if total > 0 and holders:
            # 按持股比例排序
            sorted_holders = sorted(holders, key=lambda x: x.get('hold_ratio', 0), reverse=True)
            
            print(f"总股东数: {total}")
            print(f"\n前10大股东:")
            print("-"*80)
            print(f"{'排名':<6} {'股东名称':<30} {'持股比例':<12} {'持股数量(万股)':<15} {'持股市值(万元)':<15}")
            print("-"*80)
            
            for i, holder in enumerate(sorted_holders[:10], 1):
                name = holder.get('holder_name', 'N/A')
                ratio = holder.get('hold_ratio', 0)
                amount = holder.get('hold_amount', 0) / 10000  # 转换为万股
                value = holder.get('hold_value', 0) / 10000  # 转换为万元
                
                # 截断过长的名称
                if len(name) > 28:
                    name = name[:25] + "..."
                
                print(f"{i:<6} {name:<30} {ratio:>8.2f}% {amount:>12.2f} {value:>12.2f}")
            
            # 统计信息
            total_ratio = sum(h.get('hold_ratio', 0) for h in sorted_holders[:10])
            avg_ratio = total_ratio / min(10, len(sorted_holders))
            
            print("-"*80)
            print(f"前10大股东合计持股比例: {total_ratio:.2f}%")
            print(f"前10大股东平均持股比例: {avg_ratio:.2f}%")
        else:
            print(f"{actual_stockcode} has 0 holders")
    else:
        print(f"❌ 获取股东信息失败")
    
    # 4. 简要总结
    print("\n【三、投资要点总结】")
    print("="*80)
    print(f"股票代码: {quote['code']}")
    print(f"股票名称: {quote['name']}")
    print(f"股票简拼: {quote.get('pinyin_abbr', '')}")
    print(f"当前涨跌幅: {quote['change_pct']:+.2f}%")
    print(f"市场状态: {quote['change_status']}")
    
    if result and result.get('total', 0) > 0:
        print(f"\n股东信息:")
        print(f"  股东总数: {result.get('total', 0)}")
        sorted_holders = sorted(result.get('holders', []), key=lambda x: x.get('hold_ratio', 0), reverse=True)
        if sorted_holders:
            top_holder = sorted_holders[0]
            print(f"  第一大股东: {top_holder.get('holder_name', 'N/A')}")
            print(f"  第一大股东持股比例: {top_holder.get('hold_ratio', 0):.2f}%")
            total_top10 = sum(h.get('hold_ratio', 0) for h in sorted_holders[:10])
            print(f"  前10大股东合计持股: {total_top10:.2f}%")
    else:
        print(f"\n股东信息: 暂无数据（可能为停牌、退市或其他原因）")

def main():
    parser = argparse.ArgumentParser(description="股票投资分析工具")
    parser.add_argument("stockcode", help="股票代码、股票名称或简拼 (e.g. 002983, 芯瑞达, XRD)")
    parser.add_argument("--date", help="报告日期 (YYYY-MM-DD)，默认最新季度末")
    
    args = parser.parse_args()
    
    analyze_stock(args.stockcode, args.date)

if __name__ == "__main__":
    main()
