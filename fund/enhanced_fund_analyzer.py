#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版基金分析器
充分利用从基金数据链接中提取的所有数据
"""

import re
import json
import requests
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


class EnhancedFundAnalyzer:
    """增强版基金分析器"""
    
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
            'swithSameType': r'var swithSameType = (\[.*?\]);',
        }
        
        for key, pattern in json_patterns.items():
            match = re.search(pattern, js_content, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    json_str = re.sub(r'/\*.*?\*/', '', json_str)
                    json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                    json_str = json_str.replace('\\u003c', '<').replace('\\u003e', '>')
                    json_str = json_str.replace('\\u003cbr\\u003e', '<br>')
                    
                    # 特殊处理基金经理数据
                    if key == 'Data_currentFundManager':
                        data[key] = self.parse_fund_manager_data(json_str)
                    else:
                        data[key] = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"解析{key}失败: {e}")
                    # 特殊处理不同类型的数据
                    if key == 'Data_currentFundManager':
                        data[key] = self.extract_manager_basic_info(json_str)
                    elif key == 'swithSameType':
                        data[key] = self.parse_swithSameType(json_str)
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
    
    def parse_swithSameType(self, json_str: str) -> List[List[str]]:
        """解析同类型基金数据"""
        try:
            # 这是一个包含字符串数组的数组，需要特殊处理
            # 格式: [['基金代码_基金名称_涨幅'], ...]
            result = []
            # 移除方括号
            content = json_str.strip('[]')
            # 按行分割
            lines = content.split('],[')
            for line in lines:
                # 清理每行
                line = line.strip("'\"[]")
                # 按逗号分割
                items = [item.strip("'\"") for item in line.split(',')]
                result.append(items)
            return result
        except Exception as e:
            print(f"解析swithSameType失败: {e}")
            return []
    
    def parse_ranking_trend(self, net_worth_data: List[Dict]) -> List[Dict]:
        """解析排名走势数据"""
        ranking_data = []
        
        for item in net_worth_data:
            if isinstance(item, dict) and 'x' in item and 'y' in item and 'sc' in item:
                timestamp = item['x']
                date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                # 检查y值是否看起来像排名（通常排名是整数且较大）
                y_value = item['y']
                sc_value = item['sc']
                
                # 如果y值大于100且sc值也大于100，很可能是排名数据
                if isinstance(y_value, (int, float)) and isinstance(sc_value, (int, float)) and y_value > 100 and sc_value > 100:
                    ranking_data.append({
                        'date': date,
                        'ranking': int(y_value),  # 排名
                        'total_funds': int(sc_value),  # 同类基金总数
                        'ranking_percentage': round((y_value / sc_value) * 100, 2) if sc_value > 0 else 0
                    })
        
        return ranking_data
    
    def format_comprehensive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化综合数据"""
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
            'trends': {
                'net_worth_trend': data.get('Data_netWorthTrend', []),
                'position_trend': data.get('Data_fundSharesPositions', []),
                'ranking_trend': self.parse_ranking_trend(data.get('Data_netWorthTrend', [])),
            },
            'scale_fluctuation': data.get('Data_fluctuationScale', {}),
            'holder_structure': data.get('Data_holderStructure', {}),
            'asset_allocation': data.get('Data_assetAllocation', {}),
            'performance_evaluation': data.get('Data_performanceEvaluation', {}),
            'fund_manager': data.get('Data_currentFundManager', []),
            'buy_redemption': data.get('Data_buySedemption', {}),
            'same_type_funds': data.get('swithSameType', []),
        }
        return formatted
    
    def generate_comprehensive_charts(self, data: Dict[str, Any]) -> str:
        """生成综合图表JavaScript"""
        import json
        
        # 净值走势数据
        net_worth_data = []
        if data['trends']['net_worth_trend']:
            for item in data['trends']['net_worth_trend'][-60:]:  # 最近60个数据点
                if isinstance(item, dict) and 'x' in item and 'y' in item:
                    timestamp = item['x']
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    net_worth_data.append({
                        'date': date,
                        'net_worth': item['y'],
                        'return': item.get('equityReturn', 0)
                    })
        
        # 仓位数据
        position_data = []
        if data['trends']['position_trend']:
            for item in data['trends']['position_trend'][-60:]:
                if isinstance(item, list) and len(item) >= 2:
                    timestamp = item[0]
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    position_data.append({
                        'date': date,
                        'position': item[1]
                    })
        
        # 排名走势数据
        ranking_data = []
        if data['trends']['ranking_trend']:
            for item in data['trends']['ranking_trend'][-60:]:  # 最近60个数据点
                ranking_data.append({
                    'date': item['date'],
                    'ranking': item['ranking'],
                    'total_funds': item['total_funds'],
                    'ranking_percentage': item['ranking_percentage']
                })
        
        # 规模变动数据
        scale_data = []
        if data['scale_fluctuation'] and data['scale_fluctuation'].get('categories'):
            scale_info = data['scale_fluctuation']
            categories = scale_info['categories']
            series_data = scale_info['series'][0] if scale_info['series'] else {}
            if series_data.get('data'):
                for i, category in enumerate(categories):
                    if i < len(series_data['data']):
                        scale_data.append({
                            'date': category,
                            'scale': series_data['data'][i],
                            'mom': series_data['mom'][i] if i < len(series_data['mom']) else ''
                        })
        
        # 资产配置数据
        allocation_data = []
        if data['asset_allocation'] and data['asset_allocation'].get('categories'):
            allocation_info = data['asset_allocation']
            categories = allocation_info['categories']
            for series in allocation_info['series']:
                if series.get('name') and series.get('data'):
                    for i, category in enumerate(categories):
                        if i < len(series['data']):
                            allocation_data.append({
                                'date': category,
                                'type': series['name'],
                                'value': series['data'][i]
                            })
        
        # 申购赎回数据
        redemption_data = []
        if data['buy_redemption'] and data['buy_redemption'].get('categories'):
            redemption_info = data['buy_redemption']
            categories = redemption_info['categories']
            for series in redemption_info['series']:
                if series.get('name') and series.get('data'):
                    for i, category in enumerate(categories):
                        if i < len(series['data']):
                            redemption_data.append({
                                'date': category,
                                'type': series['name'],
                                'value': series['data'][i]
                            })
        
        # 持有人结构数据
        holder_data = []
        if data['holder_structure'] and data['holder_structure'].get('categories'):
            holder_info = data['holder_structure']
            categories = holder_info['categories']
            for series in holder_info['series']:
                if series.get('name') and series.get('data'):
                    for i, category in enumerate(categories):
                        if i < len(series['data']):
                            holder_data.append({
                                'date': category,
                                'type': series['name'],
                                'value': series['data'][i]
                            })
        
        chart_js = f"""
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        // 净值走势图
        const netWorthCtx = document.getElementById('netWorthChart').getContext('2d');
        const netWorthData = {json.dumps(net_worth_data)};
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
        const positionData = {json.dumps(position_data)};
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
        
        // 排名走势图
        const rankingCtx = document.getElementById('rankingChart').getContext('2d');
        const rankingData = {json.dumps(ranking_data)};
        new Chart(rankingCtx, {{
            type: 'line',
            data: {{
                labels: rankingData.map(item => item.date),
                datasets: [{{
                    label: '同类排名',
                    data: rankingData.map(item => item.ranking),
                    borderColor: '#ffc107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y'
                }}, {{
                    label: '排名百分比(%)',
                    data: rankingData.map(item => item.ranking_percentage),
                    borderColor: '#6f42c1',
                    backgroundColor: 'rgba(111, 66, 193, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y1'
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '基金排名走势图'
                    }},
                    tooltip: {{
                        callbacks: {{
                            afterLabel: function(context) {{
                                const dataIndex = context.dataIndex;
                                const item = rankingData[dataIndex];
                                return [
                                    `同类基金总数: ${{item.total_funds}}`,
                                    `排名百分比: ${{item.ranking_percentage}}%`
                                ];
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        reverse: true,
                        title: {{
                            display: true,
                            text: '排名 (数值越小越好)'
                        }}
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        min: 0,
                        max: 100,
                        title: {{
                            display: true,
                            text: '排名百分比(%)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: '日期'
                        }}
                    }}
                }}
            }}
        }});
        
        // 规模变动图
        const scaleCtx = document.getElementById('scaleChart').getContext('2d');
        const scaleData = {json.dumps(scale_data)};
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
        const allocationData = {json.dumps(allocation_data)};
        
        const groupedAllocationData = {{}};
        allocationData.forEach(item => {{
            if (!groupedAllocationData[item.date]) {{
                groupedAllocationData[item.date] = {{}};
            }}
            groupedAllocationData[item.date][item.type] = item.value;
        }});
        
        const allocationDates = Object.keys(groupedAllocationData);
        const stockAllocationData = allocationDates.map(date => groupedAllocationData[date]['股票占净比'] || 0);
        const bondAllocationData = allocationDates.map(date => groupedAllocationData[date]['债券占净比'] || 0);
        const cashAllocationData = allocationDates.map(date => groupedAllocationData[date]['现金占净比'] || 0);
        
        new Chart(allocationCtx, {{
            type: 'bar',
            data: {{
                labels: allocationDates,
                datasets: [{{
                    label: '股票占净比(%)',
                    data: stockAllocationData,
                    backgroundColor: 'rgba(0, 123, 255, 0.8)'
                }}, {{
                    label: '债券占净比(%)',
                    data: bondAllocationData,
                    backgroundColor: 'rgba(40, 167, 69, 0.8)'
                }}, {{
                    label: '现金占净比(%)',
                    data: cashAllocationData,
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
        
        // 申购赎回图
        const redemptionCtx = document.getElementById('redemptionChart').getContext('2d');
        const redemptionData = {json.dumps(redemption_data)};
        
        const groupedRedemptionData = {{}};
        redemptionData.forEach(item => {{
            if (!groupedRedemptionData[item.date]) {{
                groupedRedemptionData[item.date] = {{}};
            }}
            groupedRedemptionData[item.date][item.type] = item.value;
        }});
        
        const redemptionDates = Object.keys(groupedRedemptionData);
        const purchaseData = redemptionDates.map(date => groupedRedemptionData[date]['期间申购'] || 0);
        const redemptionDataValues = redemptionDates.map(date => groupedRedemptionData[date]['期间赎回'] || 0);
        const totalSharesData = redemptionDates.map(date => groupedRedemptionData[date]['总份额'] || 0);
        
        new Chart(redemptionCtx, {{
            type: 'line',
            data: {{
                labels: redemptionDates,
                datasets: [{{
                    label: '期间申购(亿份)',
                    data: purchaseData,
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    tension: 0.4
                }}, {{
                    label: '期间赎回(亿份)',
                    data: redemptionDataValues,
                    borderColor: '#dc3545',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    tension: 0.4
                }}, {{
                    label: '总份额(亿份)',
                    data: totalSharesData,
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '申购赎回情况图'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: '份额(亿份)'
                        }}
                    }}
                }}
            }}
        }});
        
        // 持有人结构图
        const holderCtx = document.getElementById('holderChart').getContext('2d');
        const holderData = {json.dumps(holder_data)};
        
        const groupedHolderData = {{}};
        holderData.forEach(item => {{
            if (!groupedHolderData[item.date]) {{
                groupedHolderData[item.date] = {{}};
            }}
            groupedHolderData[item.date][item.type] = item.value;
        }});
        
        const holderDates = Object.keys(groupedHolderData);
        const institutionalData = holderDates.map(date => groupedHolderData[date]['机构持有比例'] || 0);
        const individualData = holderDates.map(date => groupedHolderData[date]['个人持有比例'] || 0);
        const internalData = holderDates.map(date => groupedHolderData[date]['内部持有比例'] || 0);
        
        new Chart(holderCtx, {{
            type: 'bar',
            data: {{
                labels: holderDates,
                datasets: [{{
                    label: '机构持有比例(%)',
                    data: institutionalData,
                    backgroundColor: 'rgba(0, 123, 255, 0.8)'
                }}, {{
                    label: '个人持有比例(%)',
                    data: individualData,
                    backgroundColor: 'rgba(40, 167, 69, 0.8)'
                }}, {{
                    label: '内部持有比例(%)',
                    data: internalData,
                    backgroundColor: 'rgba(255, 193, 7, 0.8)'
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: '持有人结构变化图'
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
    
    def generate_enhanced_html_report(self, data: Dict[str, Any]) -> str:
        """生成增强版HTML报告"""
        basic = data['basic_info']
        performance = data['performance']
        holdings = data['holdings']
        trends = data['trends']
        scale = data['scale_fluctuation']
        allocation = data['asset_allocation']
        evaluation = data['performance_evaluation']
        manager = data['fund_manager']
        redemption = data['buy_redemption']
        holder_structure = data['holder_structure']
        same_type_funds = data['same_type_funds']
        
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
        
        # 同类型基金信息
        same_type_html = ""
        if same_type_funds and isinstance(same_type_funds, list):
            same_type_html = "<div class='same-type-funds'><h3>同类型基金表现</h3><ul>"
            for period_funds in same_type_funds[:3]:  # 显示前3个时期
                if isinstance(period_funds, list):
                    same_type_html += "<li><strong>时期:</strong> "
                    for fund in period_funds[:3]:  # 每个时期显示前3只基金
                        same_type_html += f"{fund} | "
                    same_type_html += "</li>"
            same_type_html += "</ul></div>"
        
        # 生成图表JavaScript
        chart_js = self.generate_comprehensive_charts(data)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>增强版基金分析报告 - {basic['name']} ({basic['code']})</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1800px;
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
            font-size: 32px;
        }}
        .header .subtitle {{
            color: #666;
            margin-top: 10px;
            font-size: 18px;
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
            font-size: 22px;
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
        .manager-info, .evaluation, .same-type-funds {{
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
            <h1>{basic['name']} 增强版分析报告</h1>
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
                    <canvas id="rankingChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="scaleChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="allocationChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="redemptionChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="holderChart"></canvas>
                </div>
            </div>
        </div>

        {manager_info}

        {evaluation_html}

        {same_type_html}

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
        
        # 每天每个基金只生成一个报告
        filename = f"enhanced_fund_analysis_{self.fund_code}_{datetime.now().strftime('%Y%m%d')}.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def analyze_and_generate(self, output_dir: str = "../generated/funds/"):
        """分析并生成增强版报告"""
        try:
            print(f"正在获取基金 {self.fund_code} 的完整数据...")
            js_content = self.fetch_fund_data()
            
            print("正在解析所有数据...")
            raw_data = self.parse_js_variables(js_content)
            
            print("正在格式化数据...")
            formatted_data = self.format_comprehensive_data(raw_data)
            
            print("正在生成增强版分析报告...")
            html_content = self.generate_enhanced_html_report(formatted_data)
            
            print("正在保存报告...")
            output_file = self.save_html_report(html_content, output_dir)
            
            print(f"增强版分析报告已生成: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"处理失败: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='增强版基金分析器')
    parser.add_argument('fund_code', help='基金代码，如: 006253')
    parser.add_argument('--output', '-o', default='../generated/funds/', 
                       help='输出目录 (默认: ../generated/funds/)')
    
    args = parser.parse_args()
    
    # 创建分析器实例
    analyzer = EnhancedFundAnalyzer(args.fund_code)
    
    # 分析并生成报告
    output_file = analyzer.analyze_and_generate(args.output)
    
    if output_file:
        print(f"\n✅ 成功生成增强版分析报告: {output_file}")
    else:
        print("\n❌ 生成报告失败")


if __name__ == "__main__":
    main()
