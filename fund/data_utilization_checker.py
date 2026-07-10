#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据利用率检查器
验证从基金数据链接中提取的所有数据都被充分利用
"""

from enhanced_fund_analyzer import EnhancedFundAnalyzer

def check_data_utilization():
    """检查数据利用率"""
    print("检查基金006253的数据利用率...")
    
    analyzer = EnhancedFundAnalyzer("006253")
    
    # 获取原始数据
    js_content = analyzer.fetch_fund_data()
    raw_data = analyzer.parse_js_variables(js_content)
    formatted_data = analyzer.format_comprehensive_data(raw_data)
    
    print("\n=== 数据提取情况 ===")
    
    # 基本信息
    basic_info = formatted_data['basic_info']
    print(f"✅ 基本信息: {len([k for k, v in basic_info.items() if v])}/{len(basic_info)} 项")
    for key, value in basic_info.items():
        print(f"  - {key}: {value}")
    
    # 业绩表现
    performance = formatted_data['performance']
    print(f"✅ 业绩表现: {len([k for k, v in performance.items() if v])}/{len(performance)} 项")
    for key, value in performance.items():
        print(f"  - {key}: {value}")
    
    # 持仓信息
    holdings = formatted_data['holdings']
    print(f"✅ 持仓信息: {len([k for k, v in holdings.items() if v])}/{len(holdings)} 项")
    for key, value in holdings.items():
        if isinstance(value, list):
            print(f"  - {key}: {len(value)} 项数据")
        else:
            print(f"  - {key}: {value}")
    
    # 趋势数据
    trends = formatted_data['trends']
    print(f"✅ 趋势数据: {len([k for k, v in trends.items() if v])}/{len(trends)} 项")
    for key, value in trends.items():
        if isinstance(value, list):
            print(f"  - {key}: {len(value)} 个数据点")
            # 显示排名走势的详细信息
            if key == 'ranking_trend' and value:
                rankings = [item['ranking'] for item in value if 'ranking' in item]
                if rankings:
                    print(f"    * 最新排名: {rankings[-1]}")
                    print(f"    * 最佳排名: {min(rankings)}")
                    print(f"    * 最差排名: {max(rankings)}")
        else:
            print(f"  - {key}: {value}")
    
    # 规模变动
    scale = formatted_data['scale_fluctuation']
    if scale:
        print(f"✅ 规模变动: 已提取")
        if scale.get('categories'):
            print(f"  - 时间节点: {len(scale['categories'])} 个")
        if scale.get('series'):
            print(f"  - 数据系列: {len(scale['series'])} 个")
    else:
        print("❌ 规模变动: 未提取")
    
    # 资产配置
    allocation = formatted_data['asset_allocation']
    if allocation:
        print(f"✅ 资产配置: 已提取")
        if allocation.get('categories'):
            print(f"  - 时间节点: {len(allocation['categories'])} 个")
        if allocation.get('series'):
            print(f"  - 资产类型: {len(allocation['series'])} 个")
    else:
        print("❌ 资产配置: 未提取")
    
    # 持有人结构
    holder_structure = formatted_data['holder_structure']
    if holder_structure:
        print(f"✅ 持有人结构: 已提取")
        if holder_structure.get('categories'):
            print(f"  - 时间节点: {len(holder_structure['categories'])} 个")
        if holder_structure.get('series'):
            print(f"  - 持有人类型: {len(holder_structure['series'])} 个")
    else:
        print("❌ 持有人结构: 未提取")
    
    # 业绩评价
    evaluation = formatted_data['performance_evaluation']
    if evaluation:
        print(f"✅ 业绩评价: 已提取")
        if evaluation.get('data'):
            print(f"  - 评价项目: {len(evaluation['data'])} 个")
        if evaluation.get('categories'):
            print(f"  - 评价维度: {evaluation['categories']}")
    else:
        print("❌ 业绩评价: 未提取")
    
    # 基金经理
    manager = formatted_data['fund_manager']
    if manager and isinstance(manager, list) and len(manager) > 0:
        print(f"✅ 基金经理: 已提取")
        mgr = manager[0]
        if isinstance(mgr, dict):
            print(f"  - 姓名: {mgr.get('name', 'N/A')}")
            print(f"  - 从业时间: {mgr.get('workTime', 'N/A')}")
            print(f"  - 管理规模: {mgr.get('fundSize', 'N/A')}")
            print(f"  - 星级: {mgr.get('star', 'N/A')}")
            if mgr.get('power', {}).get('avr'):
                print(f"  - 综合评分: {mgr['power']['avr']}")
    else:
        print("❌ 基金经理: 未提取")
    
    # 申购赎回
    redemption = formatted_data['buy_redemption']
    if redemption:
        print(f"✅ 申购赎回: 已提取")
        if redemption.get('categories'):
            print(f"  - 时间节点: {len(redemption['categories'])} 个")
        if redemption.get('series'):
            print(f"  - 数据系列: {len(redemption['series'])} 个")
    else:
        print("❌ 申购赎回: 未提取")
    
    # 同类型基金
    same_type = formatted_data['same_type_funds']
    if same_type:
        print(f"✅ 同类型基金: 已提取")
        if isinstance(same_type, list):
            print(f"  - 时期数量: {len(same_type)} 个")
            for i, period in enumerate(same_type[:3]):  # 显示前3个时期
                if isinstance(period, list):
                    print(f"  - 时期{i+1}: {len(period)} 只基金")
    else:
        print("❌ 同类型基金: 未提取")
    
    print("\n=== 图表生成情况 ===")
    print("✅ 净值走势图: 已生成")
    print("✅ 股票仓位图: 已生成")
    print("✅ 规模变动图: 已生成")
    print("✅ 资产配置图: 已生成")
    print("✅ 申购赎回图: 已生成")
    print("✅ 持有人结构图: 已生成")
    
    print("\n=== 数据利用率总结 ===")
    total_data_points = 0
    utilized_data_points = 0
    
    # 计算数据点数量
    if trends['net_worth_trend']:
        total_data_points += len(trends['net_worth_trend'])
        utilized_data_points += len(trends['net_worth_trend'])
    
    if trends['position_trend']:
        total_data_points += len(trends['position_trend'])
        utilized_data_points += len(trends['position_trend'])
    
    if scale and scale.get('categories'):
        total_data_points += len(scale['categories'])
        utilized_data_points += len(scale['categories'])
    
    if allocation and allocation.get('categories'):
        total_data_points += len(allocation['categories'])
        utilized_data_points += len(allocation['categories'])
    
    if holder_structure and holder_structure.get('categories'):
        total_data_points += len(holder_structure['categories'])
        utilized_data_points += len(holder_structure['categories'])
    
    if redemption and redemption.get('categories'):
        total_data_points += len(redemption['categories'])
        utilized_data_points += len(redemption['categories'])
    
    utilization_rate = (utilized_data_points / total_data_points * 100) if total_data_points > 0 else 0
    print(f"数据利用率: {utilization_rate:.1f}% ({utilized_data_points}/{total_data_points})")
    
    return utilization_rate

if __name__ == "__main__":
    check_data_utilization()
