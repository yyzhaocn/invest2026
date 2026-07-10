#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富基金数据解析器
从JavaScript文件中提取基金信息并生成HTML报告
"""

import re
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class FundDataParser:
    """基金数据解析器"""
    
    def __init__(self, fund_code: str):
        self.fund_code = fund_code
        self.base_url = "https://fund.eastmoney.com/pingzhongdata/{}.js"
        self.data = {}
        
    def fetch_fund_data(self) -> str:
        """获取基金数据JavaScript文件"""
        url = self.base_url.format(self.fund_code)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise Exception(f"获取基金数据失败: {e}")
    
    def parse_js_variables(self, js_content: str) -> Dict[str, Any]:
        """解析JavaScript变量"""
        data = {}
        
        # 提取基本信息
        patterns = {
            'fS_name': r'var fS_name = "([^"]+)";',
            'fS_code': r'var fS_code = "([^"]+)";',
            'fund_sourceRate': r'var fund_sourceRate="([^"]+)";',
            'fund_Rate': r'var fund_Rate="([^"]+)";',
            'fund_minsg': r'var fund_minsg="([^"]+)";',
            'syl_1n': r'var syl_1n="([^"]+)";',
            'syl_6y': r'var syl_6y="([^"]+)";',
            'syl_3y': r'var syl_3y="([^"]+)";',
            'syl_1y': r'var syl_1y="([^"]+)";',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, js_content)
            if match:
                data[key] = match.group(1)
        
        # 提取数组数据
        array_patterns = {
            'stockCodes': r'var stockCodes=\[([^\]]+)\];',
            'stockCodesNew': r'var stockCodesNew =\[([^\]]+)\];',
            'zqCodes': r'var zqCodes = "([^"]+)";',
            'zqCodesNew': r'var zqCodesNew = "([^"]+)";',
        }
        
        for key, pattern in array_patterns.items():
            match = re.search(pattern, js_content)
            if match:
                if key in ['zqCodes', 'zqCodesNew']:
                    data[key] = match.group(1) if match.group(1) else ""
                else:
                    # 解析数组
                    array_str = match.group(1)
                    if array_str:
                        # 移除引号并分割
                        items = [item.strip().strip('"') for item in array_str.split(',')]
                        data[key] = items
                    else:
                        data[key] = []
        
        # 提取复杂JSON数据
        json_patterns = {
            'Data_netWorthTrend': r'var Data_netWorthTrend = (\[.*?\]);',
            'Data_fundSharesPositions': r'var Data_fundSharesPositions = (\[.*?\]);',
            'Data_fluctuationScale': r'var Data_fluctuationScale = (\{.*?\});',
            'Data_holderStructure': r'var Data_holderStructure =(\{.*?\});',
            'Data_assetAllocation': r'var Data_assetAllocation = (\{.*?\});',
            'Data_performanceEvaluation': r'var Data_performanceEvaluation = (\{.*?\});',
            'Data_currentFundManager': r'var Data_currentFundManager =(\[.*?\]);',
            'Data_buySedemption': r'var Data_buySedemption =(\{.*?\});',
        }
        
        for key, pattern in json_patterns.items():
            match = re.search(pattern, js_content, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    # 清理JSON字符串
                    json_str = re.sub(r'/\*.*?\*/', '', json_str)  # 移除注释
                    json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)  # 移除行注释
                    # 处理JavaScript中的特殊字符
                    json_str = json_str.replace('\\u003c', '<').replace('\\u003e', '>')
                    json_str = json_str.replace('\\u003cbr\\u003e', '<br>')
                    
                    # 特殊处理基金经理数据
                    if key == 'Data_currentFundManager':
                        data[key] = self.parse_fund_manager_data(json_str)
                    else:
                        data[key] = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"解析{key}失败: {e}")
                    # 如果解析失败，尝试提取基本字符串信息
                    if key == 'Data_currentFundManager':
                        data[key] = self.extract_manager_basic_info(json_str)
                    else:
                        data[key] = None
        
        return data
    
    def parse_fund_manager_data(self, json_str: str) -> List[Dict[str, Any]]:
        """解析基金经理数据"""
        try:
            # 尝试直接解析
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 如果失败，尝试修复常见的JSON问题
            try:
                # 修复未转义的引号
                fixed_json = json_str.replace('"', '"').replace('"', '"')
                # 修复换行符
                fixed_json = fixed_json.replace('\n', ' ').replace('\r', ' ')
                # 修复多余的空格
                fixed_json = re.sub(r'\s+', ' ', fixed_json)
                return json.loads(fixed_json)
            except json.JSONDecodeError:
                return self.extract_manager_basic_info(json_str)
    
    def extract_manager_basic_info(self, json_str: str) -> List[Dict[str, Any]]:
        """从失败的JSON中提取基金经理基本信息"""
        managers = []
        
        # 提取基金经理姓名
        name_match = re.search(r'"name":"([^"]+)"', json_str)
        if name_match:
            manager_name = name_match.group(1)
            
            # 提取其他基本信息
            work_time_match = re.search(r'"workTime":"([^"]+)"', json_str)
            fund_size_match = re.search(r'"fundSize":"([^"]+)"', json_str)
            star_match = re.search(r'"star":(\d+)', json_str)
            
            manager_info = {
                'name': manager_name,
                'workTime': work_time_match.group(1) if work_time_match else 'N/A',
                'fundSize': fund_size_match.group(1) if fund_size_match else 'N/A',
                'star': int(star_match.group(1)) if star_match else 0,
                'power': {'avr': 'N/A'},
                'profit': {'categories': [], 'series': []}
            }
            
            # 尝试提取评分信息
            avr_match = re.search(r'"avr":"([^"]+)"', json_str)
            if avr_match:
                manager_info['power'] = {'avr': avr_match.group(1)}
            
            managers.append(manager_info)
        
        return managers
    
    def format_fund_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化基金信息"""
        formatted = {
            'basic_info': {
                'name': data.get('fS_name', ''),
                'code': data.get('fS_code', ''),
                'source_rate': data.get('fund_sourceRate', ''),
                'current_rate': data.get('fund_Rate', ''),
                'min_purchase': data.get('fund_minsg', ''),
            },
            'performance': {
                'y1_return': data.get('syl_1n', ''),
                'y6_return': data.get('syl_6y', ''),
                'y3_return': data.get('syl_3y', ''),
                'y1m_return': data.get('syl_1y', ''),
            },
            'holdings': {
                'stock_codes': data.get('stockCodes', []),
                'stock_codes_new': data.get('stockCodesNew', []),
                'bond_codes': data.get('zqCodes', ''),
                'bond_codes_new': data.get('zqCodesNew', ''),
            },
            'net_worth_trend': data.get('Data_netWorthTrend', []),
            'position_data': data.get('Data_fundSharesPositions', []),
            'scale_fluctuation': data.get('Data_fluctuationScale', {}),
            'holder_structure': data.get('Data_holderStructure', {}),
            'asset_allocation': data.get('Data_assetAllocation', {}),
            'performance_evaluation': data.get('Data_performanceEvaluation', {}),
            'fund_manager': data.get('Data_currentFundManager', []),
            'buy_redemption': data.get('Data_buySedemption', {}),
        }
        return formatted
    
    def generate_html_report(self, fund_data: Dict[str, Any]) -> str:
        """生成HTML报告"""
        basic = fund_data['basic_info']
        performance = fund_data['performance']
        holdings = fund_data['holdings']
        manager = fund_data['fund_manager']
        evaluation = fund_data['performance_evaluation']
        allocation = fund_data['asset_allocation']
        scale = fund_data['scale_fluctuation']
        holders = fund_data['holder_structure']
        
        # 获取基金经理信息
        manager_info = ""
        if manager and len(manager) > 0 and isinstance(manager, list):
            mgr = manager[0]
            if isinstance(mgr, dict):
                manager_info = f"""
                <div class="manager-info">
                    <h3>基金经理信息</h3>
                    <p><strong>姓名:</strong> {mgr.get('name', 'N/A')}</p>
                    <p><strong>从业时间:</strong> {mgr.get('workTime', 'N/A')}</p>
                    <p><strong>管理规模:</strong> {mgr.get('fundSize', 'N/A')}</p>
                    <p><strong>综合评分:</strong> {mgr.get('power', {}).get('avr', 'N/A')}分</p>
                </div>
                """
        
        # 获取业绩评价
        evaluation_html = ""
        if evaluation and isinstance(evaluation, dict):
            eval_data = evaluation.get('data', [])
            eval_categories = evaluation.get('categories', [])
            if eval_data and eval_categories:
                evaluation_html = "<div class='evaluation'><h3>业绩评价</h3><ul>"
                for i, category in enumerate(eval_categories):
                    if i < len(eval_data):
                        evaluation_html += f"<li><strong>{category}:</strong> {eval_data[i]}分</li>"
                evaluation_html += f"<li><strong>综合评分:</strong> {evaluation.get('avr', 'N/A')}分</li></ul></div>"
        
        # 获取资产配置
        allocation_html = ""
        if allocation and isinstance(allocation, dict) and allocation.get('series'):
            allocation_html = "<div class='allocation'><h3>资产配置</h3><ul>"
            for series in allocation['series']:
                if series.get('name') and series.get('data'):
                    latest_value = series['data'][-1] if series['data'] else 0
                    allocation_html += f"<li><strong>{series['name']}:</strong> {latest_value}%</li>"
            allocation_html += "</ul></div>"
        
        # 获取规模变动
        scale_html = ""
        if scale and isinstance(scale, dict) and scale.get('categories') and scale.get('series'):
            scale_html = "<div class='scale'><h3>规模变动</h3><ul>"
            categories = scale['categories']
            series_data = scale['series']
            if series_data and len(series_data) > 0 and series_data[0].get('data'):
                for i, category in enumerate(categories):
                    if i < len(series_data[0]['data']):
                        value = series_data[0]['data'][i]
                        mom = series_data[0]['mom'][i] if i < len(series_data[0]['mom']) else ""
                        scale_html += f"<li><strong>{category}:</strong> {value}亿元 {mom}</li>"
            scale_html += "</ul></div>"
        
        # 获取持有人结构
        holders_html = ""
        if holders and isinstance(holders, dict) and holders.get('series') and holders.get('categories'):
            holders_html = "<div class='holders'><h3>持有人结构</h3><ul>"
            for series in holders['series']:
                if series.get('name') and series.get('data'):
                    latest_value = series['data'][-1] if series['data'] else 0
                    holders_html += f"<li><strong>{series['name']}:</strong> {latest_value}%</li>"
            holders_html += "</ul></div>"
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基金信息报告 - {basic['name']} ({basic['code']})</title>
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
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #007bff;
            margin: 0;
        }}
        .header .subtitle {{
            color: #666;
            margin-top: 10px;
        }}
        .section {{
            margin-bottom: 30px;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
            background-color: #fafafa;
        }}
        .section h2 {{
            color: #333;
            margin-top: 0;
            border-bottom: 1px solid #ccc;
            padding-bottom: 10px;
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
        .info-item strong {{
            color: #333;
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
        .holdings {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .holdings h3 {{
            margin-top: 0;
            color: #333;
        }}
        .stock-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 10px 0;
        }}
        .stock-code {{
            background: #e3f2fd;
            padding: 5px 10px;
            border-radius: 15px;
            font-family: monospace;
            font-size: 12px;
        }}
        ul {{
            list-style-type: none;
            padding: 0;
        }}
        li {{
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        li:last-child {{
            border-bottom: none;
        }}
        .positive {{
            color: #28a745;
        }}
        .negative {{
            color: #dc3545;
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
            <h1>{basic['name']}</h1>
            <div class="subtitle">基金代码: {basic['code']} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="section">
            <h2>基本信息</h2>
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
            <h2>基金持仓</h2>
            <div class="holdings">
                <h3>股票持仓代码</h3>
                <div class="stock-list">
                    {''.join([f'<span class="stock-code">{code}</span>' for code in holdings['stock_codes'][:10]])}
                </div>
                {f'<p><em>显示前10只股票，共{len(holdings["stock_codes"])}只</em></p>' if len(holdings['stock_codes']) > 10 else ''}
            </div>
        </div>

        {manager_info}

        {evaluation_html}

        {allocation_html}

        {scale_html}

        {holders_html}

        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """
        return html_content
    
    def save_html_report(self, html_content: str, output_dir: str = "../generated/funds/"):
        """保存HTML报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"fund_{self.fund_code}_{datetime.now().strftime('%Y%m%d')}.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def parse_and_generate(self, output_dir: str = "../generated/funds/"):
        """解析数据并生成报告"""
        try:
            print(f"正在获取基金 {self.fund_code} 的数据...")
            js_content = self.fetch_fund_data()
            
            print("正在解析数据...")
            raw_data = self.parse_js_variables(js_content)
            
            print("正在格式化数据...")
            formatted_data = self.format_fund_info(raw_data)
            
            print("正在生成HTML报告...")
            html_content = self.generate_html_report(formatted_data)
            
            print("正在保存报告...")
            output_file = self.save_html_report(html_content, output_dir)
            
            print(f"报告已生成: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"处理失败: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='东方财富基金数据解析器')
    parser.add_argument('fund_code', help='基金代码，如: 006253')
    parser.add_argument('--output', '-o', default='../generated/funds/', 
                       help='输出目录 (默认: ../generated/funds/)')
    
    args = parser.parse_args()
    
    # 创建解析器实例
    fund_parser = FundDataParser(args.fund_code)
    
    # 解析并生成报告
    output_file = fund_parser.parse_and_generate(args.output)
    
    if output_file:
        print(f"\n✅ 成功生成基金报告: {output_file}")
    else:
        print("\n❌ 生成报告失败")


if __name__ == "__main__":
    main()
