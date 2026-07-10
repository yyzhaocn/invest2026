#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 myfunds.ini 读取基金配置，生成 Markdown 表格比较基金业绩
"""

import sys
import configparser
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# 添加当前目录到路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from enhanced_fund_analyzer import EnhancedFundAnalyzer

def read_fund_config(date: str = None) -> Dict[str, float]:
    """
    从 myfunds.ini 读取指定日期的基金配置
    
    Args:
        date: 日期字符串，格式 YYYYMMDD，如果为 None 则使用今天的日期
    
    Returns:
        基金代码到金额的字典
    """
    config_path = current_dir / 'myfunds.ini'
    
    if not config_path.exists():
        print(f"配置文件不存在: {config_path}")
        return {}
    
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    
    # 如果没有指定日期，使用今天的日期
    if date is None:
        date = datetime.now().strftime('%Y%m%d')
    
    # 检查是否有该日期的 section
    if not config.has_section(date):
        print(f"配置文件中没有日期 {date} 的配置")
        return {}
    
    funds = {}
    for fund_code, amount_str in config.items(date):
        try:
            funds[fund_code] = float(amount_str)
        except ValueError:
            print(f"警告: 基金 {fund_code} 的金额格式错误: {amount_str}")
    
    return funds

def get_fund_performance(fund_code: str) -> Dict:
    """
    获取单个基金的业绩数据
    
    Returns:
        包含基金信息的字典，如果失败返回 None
    """
    try:
        analyzer = EnhancedFundAnalyzer(fund_code)
        js_content = analyzer.fetch_fund_data()
        data = analyzer.parse_js_variables(js_content)
        formatted_data = analyzer.format_comprehensive_data(data)
        
        return formatted_data
    except Exception as e:
        print(f"❌ 获取基金 {fund_code} 数据失败: {e}")
        return None

def calculate_current_value(initial_amount: float, performance: Dict) -> Tuple[float, float]:
    """
    计算当前市值和收益
    
    Args:
        initial_amount: 初始投资金额
        performance: 基金业绩数据
    
    Returns:
        (当前市值, 收益金额)
    """
    # 使用近一年收益率计算
    y1_return_str = performance.get('performance', {}).get('y1_return', '0')
    try:
        y1_return = float(y1_return_str.replace('%', ''))
        current_value = initial_amount * (1 + y1_return / 100)
        profit = current_value - initial_amount
        return current_value, profit
    except (ValueError, AttributeError):
        return initial_amount, 0.0

def generate_markdown_table(funds_config: Dict[str, float], date: str) -> str:
    """
    生成基金比较的 Markdown 表格
    
    Args:
        funds_config: 基金代码到金额的字典
        date: 日期字符串
    
    Returns:
        Markdown 格式的表格字符串
    """
    print(f"\n正在查询 {len(funds_config)} 只基金的业绩数据...")
    
    fund_data_list = []
    
    for fund_code, initial_amount in funds_config.items():
        print(f"  查询基金 {fund_code}...")
        fund_info = get_fund_performance(fund_code)
        
        if fund_info is None:
            continue
        
        basic_info = fund_info.get('basic_info', {})
        performance = fund_info.get('performance', {})
        evaluation = fund_info.get('performance_evaluation', {})
        
        fund_name = basic_info.get('name', 'N/A')
        
        # 获取收益率
        y1_return = performance.get('y1_return', 'N/A')
        y6_return = performance.get('y6_return', 'N/A')
        y3_return = performance.get('y3_return', 'N/A')
        y1m_return = performance.get('y1m_return', 'N/A')
        
        # 处理空字符串或无效值
        if y1_return == '' or y1_return == 'N/A':
            y1_return = '0'
        if y6_return == '' or y6_return == 'N/A':
            y6_return = '0'
        if y3_return == '' or y3_return == 'N/A':
            y3_return = '0'
        if y1m_return == '' or y1m_return == 'N/A':
            y1m_return = '0'
        
        # 计算当前市值和收益（使用近一年收益率）
        current_value, profit = calculate_current_value(initial_amount, fund_info)
        
        # 获取业绩评价
        eval_data = evaluation.get('data', [])
        eval_categories = evaluation.get('categories', [])
        eval_dict = {}
        if eval_data and eval_categories:
            for i, category in enumerate(eval_categories):
                if i < len(eval_data):
                    eval_dict[category] = eval_data[i]
        
        fund_data = {
            'code': fund_code,
            'name': fund_name,
            'initial_amount': initial_amount,
            'current_value': current_value,
            'profit': profit,
            'profit_pct': (profit / initial_amount * 100) if initial_amount > 0 else 0,
            'y1_return': y1_return,
            'y6_return': y6_return,
            'y3_return': y3_return,
            'y1m_return': y1m_return,
            'evaluation': eval_dict
        }
        
        fund_data_list.append(fund_data)
    
    # 生成 Markdown 表格
    md_lines = []
    md_lines.append(f"# 基金业绩比较 - {date}\n")
    md_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 汇总信息
    total_initial = sum(f['initial_amount'] for f in fund_data_list)
    total_current = sum(f['current_value'] for f in fund_data_list)
    total_profit = total_current - total_initial
    total_profit_pct = (total_profit / total_initial * 100) if total_initial > 0 else 0
    
    md_lines.append("## 汇总信息\n")
    md_lines.append(f"- **总投入**: ¥{total_initial:,.2f}")
    md_lines.append(f"- **当前市值**: ¥{total_current:,.2f}")
    md_lines.append(f"- **总收益**: ¥{total_profit:,.2f} ({total_profit_pct:+.2f}%)\n")
    
    # 业绩比较表格
    md_lines.append("## 业绩比较\n")
    md_lines.append("| 基金代码 | 基金名称 | 投入金额 | 当前市值 | 收益金额 | 收益率 | 近一年 | 近6月 | 近3月 | 近1月 |")
    md_lines.append("|---------|---------|---------|---------|---------|--------|--------|-------|-------|-------|")
    
    # 按收益率排序
    fund_data_list_sorted = sorted(fund_data_list, key=lambda x: x['profit_pct'], reverse=True)
    
    for fund in fund_data_list_sorted:
        profit_pct_str = f"{fund['profit_pct']:+.2f}%"
        y1_str = f"{fund['y1_return']}%" if isinstance(fund['y1_return'], str) else f"{fund['y1_return']:.2f}%"
        y6_str = f"{fund['y6_return']}%" if isinstance(fund['y6_return'], str) else f"{fund['y6_return']:.2f}%"
        y3_str = f"{fund['y3_return']}%" if isinstance(fund['y3_return'], str) else f"{fund['y3_return']:.2f}%"
        y1m_str = f"{fund['y1m_return']}%" if isinstance(fund['y1m_return'], str) else f"{fund['y1m_return']:.2f}%"
        
        md_lines.append(
            f"| {fund['code']} | {fund['name']} | "
            f"¥{fund['initial_amount']:,.2f} | ¥{fund['current_value']:,.2f} | "
            f"¥{fund['profit']:,.2f} | {profit_pct_str} | "
            f"{y1_str} | {y6_str} | {y3_str} | {y1m_str} |"
        )
    
    # 业绩评价表格
    if any(f['evaluation'] for f in fund_data_list):
        md_lines.append("\n## 业绩评价\n")
        md_lines.append("| 基金代码 | 基金名称 | 选证能力 | 收益率 | 抗风险 | 稳定性 | 择时能力 |")
        md_lines.append("|---------|---------|---------|--------|--------|--------|---------|")
        
        for fund in fund_data_list_sorted:
            eval_dict = fund['evaluation']
            # 格式化评价数据，None 显示为 N/A
            def format_eval(value):
                if value is None:
                    return 'N/A'
                return str(value)
            
            md_lines.append(
                f"| {fund['code']} | {fund['name']} | "
                f"{format_eval(eval_dict.get('选证能力'))} | "
                f"{format_eval(eval_dict.get('收益率'))} | "
                f"{format_eval(eval_dict.get('抗风险'))} | "
                f"{format_eval(eval_dict.get('稳定性'))} | "
                f"{format_eval(eval_dict.get('择时能力'))} |"
            )
    
    return "\n".join(md_lines)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='生成基金业绩比较 Markdown 表格')
    parser.add_argument('--date', type=str, help='日期 (YYYYMMDD)，默认为今天')
    parser.add_argument('--output', type=str, help='输出文件路径，默认为控制台输出')
    
    args = parser.parse_args()
    
    date = args.date or datetime.now().strftime('%Y%m%d')
    
    # 读取配置
    funds_config = read_fund_config(date)
    
    if not funds_config:
        print(f"没有找到日期 {date} 的基金配置")
        return
    
    print(f"找到 {len(funds_config)} 只基金配置:")
    for code, amount in funds_config.items():
        print(f"  {code}: ¥{amount:,.2f}")
    
    # 生成 Markdown 表格
    markdown_table = generate_markdown_table(funds_config, date)
    
    # 输出结果
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_table)
        print(f"\n✅ Markdown 表格已保存到: {output_path}")
    else:
        print("\n" + "=" * 80)
        print(markdown_table)
        print("=" * 80)

if __name__ == "__main__":
    main()

