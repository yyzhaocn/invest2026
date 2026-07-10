#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查基金业绩表现
"""

import sys
from pathlib import Path

# 添加当前目录到路径，以便导入同目录下的模块
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from enhanced_fund_analyzer import EnhancedFundAnalyzer

def check_fund_performance(fund_code: str):
    """检查指定基金的业绩表现"""
    print(f"正在查询基金 {fund_code} 的业绩表现...")
    print("=" * 60)
    
    try:
        analyzer = EnhancedFundAnalyzer(fund_code)
        js_content = analyzer.fetch_fund_data()
        data = analyzer.parse_js_variables(js_content)
        formatted_data = analyzer.format_comprehensive_data(data)
        
        # 显示基本信息
        basic_info = formatted_data['basic_info']
        print(f"\n【基本信息】")
        print(f"基金名称: {basic_info.get('name', 'N/A')}")
        print(f"基金代码: {basic_info.get('code', 'N/A')}")
        print(f"申购费率: {basic_info.get('source_rate', 'N/A')}")
        print(f"赎回费率: {basic_info.get('current_rate', 'N/A')}")
        print(f"最小申购金额: {basic_info.get('min_purchase', 'N/A')}")
        
        # 显示业绩表现
        performance = formatted_data['performance']
        print(f"\n【业绩表现】")
        print(f"近一年收益率: {performance.get('y1_return', 'N/A')}%")
        print(f"近6月收益率: {performance.get('y6_return', 'N/A')}%")
        print(f"近三月收益率: {performance.get('y3_return', 'N/A')}%")
        print(f"近一月收益率: {performance.get('y1m_return', 'N/A')}%")
        
        # 显示业绩评价
        evaluation = formatted_data.get('performance_evaluation', {})
        if evaluation:
            print(f"\n【业绩评价】")
            eval_data = evaluation.get('data', [])
            eval_categories = evaluation.get('categories', [])
            if eval_data and eval_categories:
                for i, category in enumerate(eval_categories):
                    if i < len(eval_data):
                        print(f"{category}: {eval_data[i]}")
        
        # 显示持仓信息
        holdings = formatted_data['holdings']
        if holdings.get('stock_codes') or holdings.get('stock_codes_new'):
            print(f"\n【持仓信息】")
            stock_codes = holdings.get('stock_codes_new') or holdings.get('stock_codes', [])
            if stock_codes:
                print(f"股票持仓数量: {len(stock_codes)}")
                print(f"前5只股票代码: {', '.join(stock_codes[:5])}")
        
        # 显示规模变动
        scale_fluctuation = formatted_data.get('scale_fluctuation', {})
        if scale_fluctuation:
            print(f"\n【规模变动】")
            categories = scale_fluctuation.get('categories', [])
            series = scale_fluctuation.get('series', [])
            if categories and series:
                print(f"时间节点: {len(categories)} 个")
                if len(series) > 0 and len(series[0].get('data', [])) > 0:
                    latest_scale = series[0]['data'][-1]
                    print(f"最新规模: {latest_scale} 亿元")
        
        print("\n" + "=" * 60)
        print("查询完成！")
        
        return formatted_data
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import sys
    
    # 默认查询基金 006253，也可以通过命令行参数指定
    fund_code = sys.argv[1] if len(sys.argv) > 1 else "006253"
    
    check_fund_performance(fund_code)

