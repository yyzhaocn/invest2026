#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富股票基本信息解析器
从API获取股票持仓代码的基本信息
"""

import re
import json
import requests
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class StockInfoParser:
    """股票信息解析器"""
    
    def __init__(self):
        self.base_url = "https://push2delay.eastmoney.com/api/qt/ulist.np/get"
        self.search_url = "https://searchapi.eastmoney.com/api/suggest/get"
        self.quote_url = "https://push2.eastmoney.com/api/qt/clist/get"  # 获取详细行情信息
        self.default_params = {
            'fltt': '2',
            'invt': '2', 
            'ut': '267f9ad526dbe6b0262ab19316f5a25b',
            'fields': 'f3,f12,f14,f57'  # f3:涨跌幅, f12:股票代码, f14:股票名称, f57:股票简拼
        }
    
    def fetch_stock_data(self, stock_codes: List[str], quiet: bool = False) -> Dict[str, Any]:
        """获取股票基本信息
        
        Args:
            stock_codes: 股票代码列表
            quiet: 为 True 时不打印调试用的 URL/响应片段（批量行情时建议开启）
        """
        # 将股票代码转换为API需要的格式（添加市场前缀）
        formatted_codes = []
        for code in stock_codes:
            if code.startswith('6'):
                formatted_codes.append(f'1.{code}')  # 上海主板
            elif code.startswith('0') or code.startswith('3'):
                formatted_codes.append(f'0.{code}')  # 深圳主板/创业板
            elif code.startswith('688'):
                formatted_codes.append(f'1.{code}')  # 科创板
            else:
                formatted_codes.append(f'0.{code}')  # 默认深圳
        
        secids = ','.join(formatted_codes)
        
        params = self.default_params.copy()
        params['secids'] = secids
        params['cb'] = f'jQuery{int(datetime.now().timestamp() * 1000)}_{int(datetime.now().timestamp() * 1000)}'
        params['_'] = str(int(datetime.now().timestamp() * 1000))
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            if not quiet:
                print(f"API URL: {response.url}")
                print(f"Response: {response.text[:500]}...")
            return self.parse_response(response.text)
        except requests.RequestException as e:
            raise Exception(f"获取股票数据失败: {e}")
    
    def search_stock_by_name(self, stock_name: str) -> Optional[str]:
        """
        通过股票名称搜索股票代码
        
        Args:
            stock_name: 股票名称，如 "岩山科技"
        
        Returns:
            str: 股票代码，如 "002195"，如果未找到则返回None
        """
        try:
            params = {
                'input': stock_name,
                'type': '14',  # 股票类型
                'token': 'D43BF722C8E33BDC906FB84D85E326E8',
                'markettype': '',
                'mktnum': ''
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://www.eastmoney.com/'
            }
            
            response = requests.get(self.search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析搜索结果
            if data.get('QuotationCodeTable') and data['QuotationCodeTable'].get('Data'):
                for item in data['QuotationCodeTable']['Data']:
                    name = item.get('Name', '')
                    code = item.get('Code', '')
                    if stock_name in name or name in stock_name:
                        return code
            
            return None
            
        except Exception as e:
            print(f"⚠️  搜索股票代码失败: {e}")
            return None
    
    def parse_response(self, response_text: str) -> Dict[str, Any]:
        """解析API响应"""
        # 提取JSONP回调函数中的JSON数据
        pattern = r'jQuery\d+_\d+\((.*)\);'
        match = re.search(pattern, response_text)
        
        if not match:
            raise Exception("无法解析API响应")
        
        try:
            json_data = json.loads(match.group(1))
            return json_data
        except json.JSONDecodeError as e:
            raise Exception(f"JSON解析失败: {e}")
    
    def get_stock_pinyin_abbr(self, stock_name: str) -> str:
        """
        获取股票名称的拼音简拼（首字母缩写）
        
        Args:
            stock_name: 股票名称，如 "平安银行"
        
        Returns:
            str: 拼音简拼，如 "PAYH"
        """
        try:
            from pypinyin import lazy_pinyin, Style
            # 获取拼音首字母并转换为大写
            pinyin_list = lazy_pinyin(stock_name, style=Style.FIRST_LETTER)
            abbreviation = ''.join([letter.upper() for letter in pinyin_list])
            return abbreviation
        except ImportError:
            # 如果未安装 pypinyin，返回空字符串或股票名称
            print("⚠️  未安装 pypinyin 库，无法生成拼音简拼。请运行: pip install pypinyin")
            return ''
        except Exception as e:
            print(f"⚠️  生成拼音简拼失败: {e}")
            return ''
    
    def format_stock_info(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """格式化股票信息"""
        if not data.get('data') or not data['data'].get('diff'):
            return []
        
        stocks = []
        for item in data['data']['diff']:
            stock_name = item.get('f14', '')
            # f57字段不是简拼，使用拼音生成简拼
            pinyin_abbr = ''
            if stock_name:
                pinyin_abbr = self.get_stock_pinyin_abbr(stock_name)
            
            # 安全处理涨跌幅字段（f3），可能是数字或字符串（如 "-" 表示停牌）
            f3_value = item.get('f3', 0)
            change_pct = 0.0
            if isinstance(f3_value, (int, float)):
                change_pct = float(f3_value)
            elif isinstance(f3_value, str):
                # 如果是字符串，尝试转换为数字，如果失败则默认为0（可能是停牌等）
                try:
                    change_pct = float(f3_value)
                except (ValueError, TypeError):
                    change_pct = 0.0  # 停牌或其他特殊情况
            
            stock_info = {
                'code': item.get('f12', ''),
                'name': stock_name,
                'pinyin_abbr': pinyin_abbr,  # 股票简拼
                'change_pct': change_pct,
                'change_status': self.get_change_status(change_pct)
            }
            stocks.append(stock_info)
        
        return stocks
    
    def search_stock_by_pinyin_abbr(self, pinyin_abbr: str) -> Optional[Dict[str, Any]]:
        """
        通过股票简拼（拼音首字母缩写）搜索股票并返回行情信息
        
        Args:
            pinyin_abbr: 股票简拼，如 "YSKJ" (岩山科技)
        
        Returns:
            dict: 股票行情信息字典，包含代码、名称、简拼、涨跌幅等信息，如果未找到则返回None
        """
        try:
            # 首先尝试通过搜索API查找匹配的股票
            # 搜索简拼（大写）
            pinyin_abbr_upper = pinyin_abbr.upper()
            
            # 使用搜索API搜索
            params = {
                'input': pinyin_abbr_upper,
                'type': '14',  # 股票类型
                'token': 'D43BF722C8E33BDC906FB84D85E326E8',
                'markettype': '',
                'mktnum': ''
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Referer': 'https://www.eastmoney.com/'
            }
            
            response = requests.get(self.search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析搜索结果，找到简拼匹配的股票
            if data.get('QuotationCodeTable') and data['QuotationCodeTable'].get('Data'):
                for item in data['QuotationCodeTable']['Data']:
                    stock_code = item.get('Code', '')
                    stock_name = item.get('Name', '')
                    
                    if not stock_code or not stock_name:
                        continue
                    
                    # 生成该股票名称的简拼，看是否匹配
                    stock_abbr = self.get_stock_pinyin_abbr(stock_name)
                    
                    if stock_abbr == pinyin_abbr_upper:
                        # 找到完全匹配的股票，获取行情信息
                        return self.get_stock_quote_by_code(stock_code)
                    elif stock_abbr.startswith(pinyin_abbr_upper) and len(stock_abbr) >= len(pinyin_abbr_upper):
                        # 如果简拼前缀匹配（如 YSKJ 匹配 YSKJX），也返回第一个匹配的
                        return self.get_stock_quote_by_code(stock_code)
            
            # 如果没有找到，返回None
            print(f"⚠️  未找到简拼为 '{pinyin_abbr}' 的股票")
            return None
            
        except Exception as e:
            print(f"⚠️  通过简拼搜索股票失败: {e}")
            return None
    
    def get_stock_quote_by_code(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        通过股票代码获取股票行情信息
        
        Args:
            stock_code: 股票代码，如 "002195"
        
        Returns:
            dict: 股票行情信息字典，包含代码、名称、简拼、涨跌幅等信息
        """
        try:
            raw_data = self.fetch_stock_data([stock_code])
            stocks = self.format_stock_info(raw_data)
            
            if stocks:
                return stocks[0]
            else:
                print(f"⚠️  未找到股票代码 '{stock_code}' 的行情信息")
                return None
                
        except Exception as e:
            print(f"⚠️  获取股票行情失败: {e}")
            return None
    
    def get_change_status(self, change_pct: float) -> str:
        """
        获取涨跌状态
        
        Args:
            change_pct: 涨跌幅（百分比），如果是字符串（如 "-" 表示停牌），需要先转换为float
        
        Returns:
            str: 涨跌状态
        """
        # 确保 change_pct 是数字类型
        try:
            if isinstance(change_pct, str):
                change_pct = float(change_pct) if change_pct != '-' else 0.0
            change_pct = float(change_pct)
        except (ValueError, TypeError):
            return "停牌"  # 无法解析的情况，可能是停牌
        
        if change_pct > 0:
            return "上涨"
        elif change_pct < 0:
            return "下跌"
        else:
            return "平盘"  # 可能是平盘或停牌
    
    def generate_html_report(self, stocks: List[Dict[str, Any]], output_dir: str = "../generated/funds/") -> str:
        """生成HTML报告"""
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票持仓基本信息报告</title>
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
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stock-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .stock-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }}
        .stock-code {{
            font-family: monospace;
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        .stock-name {{
            font-size: 16px;
            color: #666;
            margin-bottom: 15px;
        }}
        .change-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .change-pct {{
            font-size: 20px;
            font-weight: bold;
        }}
        .positive {{
            color: #dc3545;
        }}
        .negative {{
            color: #28a745;
        }}
        .neutral {{
            color: #6c757d;
        }}
        .change-status {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .status-up {{
            background-color: #d4edda;
            color: #155724;
        }}
        .status-down {{
            background-color: #f8d7da;
            color: #721c24;
        }}
        .status-neutral {{
            background-color: #e2e3e5;
            color: #383d41;
        }}
        .summary {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .summary h3 {{
            margin-top: 0;
            color: #333;
        }}
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .stat-item {{
            text-align: center;
            padding: 10px;
            background: white;
            border-radius: 5px;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #007bff;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
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
            <h1>股票持仓基本信息报告</h1>
            <div class="subtitle">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="summary">
            <h3>持仓概览</h3>
            <div class="summary-stats">
                <div class="stat-item">
                    <div class="stat-value">{len(stocks)}</div>
                    <div class="stat-label">持仓股票数量</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{len([s for s in stocks if s['change_pct'] > 0])}</div>
                    <div class="stat-label">上涨股票</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{len([s for s in stocks if s['change_pct'] < 0])}</div>
                    <div class="stat-label">下跌股票</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{len([s for s in stocks if s['change_pct'] == 0])}</div>
                    <div class="stat-label">平盘股票</div>
                </div>
            </div>
        </div>

        <div class="stock-grid">
            {self.generate_stock_cards(stocks)}
        </div>

        <div class="timestamp">
            数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """
        return html_content
    
    def generate_stock_cards(self, stocks: List[Dict[str, Any]]) -> str:
        """生成股票卡片HTML"""
        cards_html = ""
        for stock in stocks:
            change_class = "positive" if stock['change_pct'] > 0 else "negative" if stock['change_pct'] < 0 else "neutral"
            status_class = "status-up" if stock['change_pct'] > 0 else "status-down" if stock['change_pct'] < 0 else "status-neutral"
            
            cards_html += f"""
            <div class="stock-card">
                <div class="stock-code">{stock['code']}</div>
                <div class="stock-name">{stock['name']}</div>
                <div class="change-info">
                    <span class="change-pct {change_class}">{stock['change_pct']:+.2f}%</span>
                    <span class="change-status {status_class}">{stock['change_status']}</span>
                </div>
            </div>
            """
        return cards_html
    
    def save_html_report(self, html_content: str, output_dir: str = "../generated/funds/") -> str:
        """保存HTML报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"stock_holdings_{datetime.now().strftime('%Y%m%d')}.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def parse_and_generate(self, stock_codes: List[str], output_dir: str = "../generated/funds/") -> str:
        """解析股票数据并生成报告"""
        try:
            print(f"正在获取 {len(stock_codes)} 只股票的基本信息...")
            raw_data = self.fetch_stock_data(stock_codes)
            
            print("正在解析股票数据...")
            stocks = self.format_stock_info(raw_data)
            
            if not stocks:
                print("未获取到股票数据")
                return None
            
            print("正在生成HTML报告...")
            html_content = self.generate_html_report(stocks, output_dir)
            
            print("正在保存报告...")
            output_file = self.save_html_report(html_content, output_dir)
            
            print(f"报告已生成: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"处理失败: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='东方财富股票基本信息解析器')
    parser.add_argument('stock_codes', nargs='+', help='股票代码列表，如: 301061 300866 688235')
    parser.add_argument('--output', '-o', default='../generated/funds/', 
                       help='输出目录 (默认: ../generated/funds/)')
    
    args = parser.parse_args()
    
    # 创建解析器实例
    stock_parser = StockInfoParser()
    
    # 解析并生成报告
    output_file = stock_parser.parse_and_generate(args.stock_codes, args.output)
    
    if output_file:
        print(f"\n✅ 成功生成股票报告: {output_file}")
    else:
        print("\n❌ 生成报告失败")


if __name__ == "__main__":
    main()
