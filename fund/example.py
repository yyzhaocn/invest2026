#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金数据解析器使用示例
"""

from fund_parser import FundDataParser

def main():
    """示例：解析多个基金并生成报告"""
    
    # 要解析的基金代码列表
    fund_codes = [
        "006253",  # 永赢消费主题C
        "000001",  # 华夏成长混合
        "110022",  # 易方达消费行业股票
    ]
    
    print("开始批量解析基金数据...")
    
    for fund_code in fund_codes:
        print(f"\n正在处理基金 {fund_code}...")
        
        try:
            # 创建解析器实例
            parser = FundDataParser(fund_code)
            
            # 解析并生成报告
            output_file = parser.parse_and_generate()
            
            if output_file:
                print(f"✅ 成功生成报告: {output_file}")
            else:
                print(f"❌ 生成报告失败")
                
        except Exception as e:
            print(f"❌ 处理基金 {fund_code} 时出错: {e}")
    
    print("\n批量处理完成！")

if __name__ == "__main__":
    main()
