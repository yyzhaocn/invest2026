#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据股票名称获取股票代码列表
"""

from fund_analyzer import FundAnalyzer

def main():
    # 股票名称列表
    stock_names = [
        "蓝色光标",
        "利欧股份",
        "南兴股份",
        "掌阅科技",
        "德生科技",
        "三变科技"
    ]
    
    print("="*60)
    print("根据股票名称获取股票代码")
    print("="*60)
    
    analyzer = FundAnalyzer()
    
    # 方法1: 从CSV文件查找（更快）
    print("\n方法1: 从最新CSV文件查找...")
    results = analyzer.get_stock_codes_by_names2(stock_names)
    
    # 检查是否所有股票都找到了
    missing = [name for name, (code, _) in results.items() if not code]
    
    # 如果还有未找到的，使用方法2: 通过API搜索
    if missing:
        print(f"\n方法2: 通过API搜索未找到的股票: {missing}...")
        api_results = analyzer.get_stock_codes_by_names(missing)
        
        # 合并结果
        for name in missing:
            if name in api_results and api_results[name][0]:
                results[name] = api_results[name]
    
    # 显示搜索过程
    for stock_name in stock_names:
        code, pinyin = results.get(stock_name, (None, ''))
        if code:
            if pinyin:
                print(f"✅ 找到: {stock_name} ({code}) - 简拼: {pinyin}")
            else:
                print(f"✅ 找到: {stock_name} ({code})")
        else:
            print(f"❌ 未找到: {stock_name}")
    
    print("\n" + "="*60)
    print("股票代码列表:")
    print("="*60)
    
    for stock_name, (code, pinyin) in results.items():
        if code:
            if pinyin:
                print(f"{stock_name}: {code} ({pinyin})")
            else:
                print(f"{stock_name}: {code}")
        else:
            print(f"{stock_name}: 未找到")
    
    # 生成代码列表
    print("\n" + "="*60)
    print("Python 列表格式:")
    print("="*60)
    codes = [code for code, _ in results.values() if code]
    print(f"stock_codes = {codes}")

if __name__ == "__main__":
    main()
