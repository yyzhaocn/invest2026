#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金趋势数据分析器
从基金数据中提取趋势信息并生成带图表的HTML报告
"""

import re
import json
import requests
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import base64
import io


class FundTrendsAnalyzer:
    """基金趋势数据分析器"""
    
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
        }
        
        for key, pattern in array_patterns.items():
            match = re.search(pattern, js_content)
            if match:
                array_str = match.group(1)
                if array_str:
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
                    json_str = re.sub(r'/\*.*?\*/', '', json_str)
                    json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                    json_str = json_str.replace('\\u003c', '<').replace('\\u003e', '>')
                    json_str = json_str.replace('\\u003cbr\\u003e', '<br>')
                    data[key] = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"解析{key}失败: {e}")
                    data[key] = None
        
        return data
    
    def format_trends_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化趋势数据"""
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
            'net_worth_trend': data.get('Data_netWorthTrend', []),
            'position_trend': data.get('Data_fundSharesPositions', []),
            'scale_fluctuation': data.get('Data_fluctuationScale', {}),
            'holder_structure': data.get('Data_holderStructure', {}),
            'asset_allocation': data.get('Data_assetAllocation', {}),
            'performance_evaluation': data.get('Data_performanceEvaluation', {}),
            'fund_manager': data.get('Data_currentFundManager', []),
            'buy_redemption': data.get('Data_buySedemption', {}),
            'holdings': {
                'stock_codes': data.get('stockCodes', []),
                'stock_codes_new': data.get('stockCodesNew', []),
            }
        }
        return formatted
    
    def generate_chart_js(self, trends_data: Dict[str, Any]) -> str:
        """生成图表JavaScript代码"""
        net_worth_data = trends_data['net_worth_trend']
        position_data = trends_data['position_trend']
        scale_data = trends_data['scale_fluctuation']
        allocation_data = trends_data['asset_allocation']
        
        # 处理净值走势数据
        net_worth_chart_data = []
        if net_worth_data:
            for item in net_worth_data[-30:]:  # 最近30个数据点
                if isinstance(item, dict) and 'x' in item and 'y' in item:
                    timestamp = item['x']
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    net_worth_chart_data.append({
                        'date': date,
                        'net_worth': item['y'],
                        'return': item.get('equityReturn', 0)
                    })
        
        # 处理仓位数据
        position_chart_data = []
        if position_data:
            for item in position_data[-30:]:  # 最近30个数据点
                if isinstance(item, list) and len(item) >= 2:
                    timestamp = item[0]
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    position_chart_data.append({
                        'date': date,
                        'position': item[1]
                    })
        
        # 处理规模变动数据
        scale_chart_data = []
        if scale_data and scale_data.get('categories') and scale_data.get('series'):
            categories = scale_data['categories']
            series_data = scale_data['series'][0] if scale_data['series'] else {}
            if series_data.get('data'):
                for i, category in enumerate(categories):
                    if i < len(series_data['data']):
                        scale_chart_data.append({
                            'date': category,
                            'scale': series_data['data'][i],
                            'mom': series_data['mom'][i] if i < len(series_data['mom']) else ''
                        })
        
        # 处理资产配置数据
        allocation_chart_data = []
        if allocation_data and allocation_data.get('categories') and allocation_data.get('series'):
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
        
        // 股票仓位图
        const positionCtx = document.getElementById('positionChart').getContext('2d');
        const positionData = {json.dumps(position_chart_data)};
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
        
        // 规模变动图
        const scaleCtx = document.getElementById('scaleChart').getContext('2d');
        const scaleData = {json.dumps(scale_chart_data)};
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
        
        // 资产配置图
        const allocationCtx = document.getElementById('allocationChart').getContext('2d');
        const allocationData = {json.dumps(allocation_chart_data)};
        
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
        </script>
        """
        
        return chart_js
    
    def generate_html_report(self, trends_data: Dict[str, Any]) -> str:
        """生成带图表的HTML报告"""
        basic = trends_data['basic_info']
        performance = trends_data['performance']
        net_worth = trends_data['net_worth_trend']
        position = trends_data['position_trend']
        scale = trends_data['scale_fluctuation']
        allocation = trends_data['asset_allocation']
        evaluation = trends_data['performance_evaluation']
        manager = trends_data['fund_manager']
        
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
        
        # 生成图表JavaScript
        chart_js = self.generate_chart_js(trends_data)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基金趋势分析报告 - {basic['name']} ({basic['code']})</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
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
        .manager-info {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
        }}
        .evaluation {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
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
            <h1>{basic['name']} 趋势分析报告</h1>
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

        {manager_info}

        {evaluation_html}

        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    {chart_js}
</body>
</html>
        """
        return html_content
    
    def save_html_report(self, html_content: str, output_dir: str = "../generated/funds/"):
        """保存HTML报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"fund_trends_{self.fund_code}_{datetime.now().strftime('%Y%m%d')}.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def analyze_and_generate(self, output_dir: str = "../generated/funds/"):
        """分析趋势数据并生成报告"""
        try:
            print(f"正在获取基金 {self.fund_code} 的趋势数据...")
            js_content = self.fetch_fund_data()
            
            print("正在解析趋势数据...")
            raw_data = self.parse_js_variables(js_content)
            
            print("正在格式化数据...")
            trends_data = self.format_trends_data(raw_data)
            
            print("正在生成趋势分析报告...")
            html_content = self.generate_html_report(trends_data)
            
            print("正在保存报告...")
            output_file = self.save_html_report(html_content, output_dir)
            
            print(f"趋势分析报告已生成: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"处理失败: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='基金趋势数据分析器')
    parser.add_argument('fund_code', help='基金代码，如: 006253')
    parser.add_argument('--output', '-o', default='../generated/funds/', 
                       help='输出目录 (默认: ../generated/funds/)')
    
    args = parser.parse_args()
    
    # 创建分析器实例
    trends_analyzer = FundTrendsAnalyzer(args.fund_code)
    
    # 分析并生成报告
    output_file = trends_analyzer.analyze_and_generate(args.output)
    
    if output_file:
        print(f"\n✅ 成功生成趋势分析报告: {output_file}")
    else:
        print("\n❌ 生成报告失败")


if __name__ == "__main__":
    main()
