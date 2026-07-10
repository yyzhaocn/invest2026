#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金和股票持仓综合分析器
结合基金信息和股票持仓基本信息生成综合报告
"""

import argparse
from fund_parser import FundDataParser
from stock_info_parser import StockInfoParser


class FundStockAnalyzer:
    """基金和股票持仓综合分析器"""
    
    def __init__(self):
        self.fund_parser = None
        self.stock_parser = StockInfoParser()
    
    def analyze_fund_and_stocks(self, fund_code: str, output_dir: str = "../generated/funds/"):
        """分析基金和其持仓股票"""
        print(f"开始分析基金 {fund_code} 及其持仓股票...")
        
        # 1. 获取基金信息
        print("\n=== 第一步：获取基金信息 ===")
        self.fund_parser = FundDataParser(fund_code)
        
        try:
            fund_js_content = self.fund_parser.fetch_fund_data()
            fund_raw_data = self.fund_parser.parse_js_variables(fund_js_content)
            fund_formatted_data = self.fund_parser.format_fund_info(fund_raw_data)
            
            # 提取股票代码
            stock_codes = fund_formatted_data['holdings']['stock_codes']
            if not stock_codes:
                print("未找到基金持仓股票代码")
                return None
            
            # 清理股票代码，移除末尾的数字
            cleaned_codes = []
            for code in stock_codes:
                # 移除末尾的数字（如3010610 -> 301061）
                if code and code.isdigit():
                    # 找到第一个非零数字的位置
                    clean_code = code.rstrip('0')
                    if clean_code:
                        cleaned_codes.append(clean_code)
                    else:
                        cleaned_codes.append(code)
                else:
                    cleaned_codes.append(code)
            
            stock_codes = cleaned_codes
            print(f"发现 {len(stock_codes)} 只持仓股票: {stock_codes}")
            
        except Exception as e:
            print(f"获取基金信息失败: {e}")
            return None
        
        # 2. 获取股票基本信息
        print("\n=== 第二步：获取股票基本信息 ===")
        try:
            stock_raw_data = self.stock_parser.fetch_stock_data(stock_codes)
            stocks = self.stock_parser.format_stock_info(stock_raw_data)
            
            if not stocks:
                print("未获取到股票数据")
                return None
            
            print(f"成功获取 {len(stocks)} 只股票的基本信息")
            
        except Exception as e:
            print(f"获取股票信息失败: {e}")
            return None
        
        # 3. 生成综合报告
        print("\n=== 第三步：生成综合报告 ===")
        try:
            output_file = self.generate_comprehensive_report(
                fund_formatted_data, stocks, fund_code, output_dir
            )
            
            if output_file:
                print(f"✅ 综合报告已生成: {output_file}")
                return output_file
            else:
                print("❌ 生成综合报告失败")
                return None
                
        except Exception as e:
            print(f"生成综合报告失败: {e}")
            return None
    
    def generate_comprehensive_report(self, fund_data, stocks, fund_code, output_dir):
        """生成综合报告"""
        from datetime import datetime
        from pathlib import Path
        
        # 基金基本信息
        basic = fund_data['basic_info']
        performance = fund_data['performance']
        
        # 股票统计
        up_stocks = [s for s in stocks if s['change_pct'] > 0]
        down_stocks = [s for s in stocks if s['change_pct'] < 0]
        flat_stocks = [s for s in stocks if s['change_pct'] == 0]
        
        # 计算平均涨跌幅
        avg_change = sum(s['change_pct'] for s in stocks) / len(stocks) if stocks else 0
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基金持仓综合分析报告 - {basic['name']} ({basic['code']})</title>
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
        .fund-info {{
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
        .stock-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stock-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .stock-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }}
        .stock-code {{
            font-family: monospace;
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        .stock-name {{
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }}
        .change-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .change-pct {{
            font-size: 18px;
            font-weight: bold;
        }}
        .positive {{ color: #dc3545; }}
        .negative {{ color: #28a745; }}
        .neutral {{ color: #6c757d; }}
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
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
            <h1>{basic['name']} 持仓综合分析报告</h1>
            <div class="subtitle">基金代码: {basic['code']} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        </div>

        <div class="section">
            <h2>基金基本信息</h2>
            <div class="fund-info">
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
            <h2>基金业绩表现</h2>
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
            <h2>持仓股票表现概览</h2>
            <div class="summary-stats">
                <div class="stat-card">
                    <div class="stat-value">{len(stocks)}</div>
                    <div class="stat-label">持仓股票总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(up_stocks)}</div>
                    <div class="stat-label">上涨股票</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(down_stocks)}</div>
                    <div class="stat-label">下跌股票</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(flat_stocks)}</div>
                    <div class="stat-label">平盘股票</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{avg_change:+.2f}%</div>
                    <div class="stat-label">平均涨跌幅</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>持仓股票详细信息</h2>
            <div class="stock-grid">
                {self.generate_stock_cards_html(stocks)}
            </div>
        </div>

        <div class="timestamp">
            报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
        """
        
        # 保存文件
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"fund_stock_analysis_{fund_code}_{datetime.now().strftime('%Y%m%d')}.html"
        file_path = output_path / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def generate_stock_cards_html(self, stocks):
        """生成股票卡片HTML"""
        cards_html = ""
        for stock in stocks:
            change_class = "positive" if stock['change_pct'] > 0 else "negative" if stock['change_pct'] < 0 else "neutral"
            
            cards_html += f"""
            <div class="stock-card">
                <div class="stock-code">{stock['code']}</div>
                <div class="stock-name">{stock['name']}</div>
                <div class="change-info">
                    <span class="change-pct {change_class}">{stock['change_pct']:+.2f}%</span>
                    <span class="change-status">{stock['change_status']}</span>
                </div>
            </div>
            """
        return cards_html


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='基金和股票持仓综合分析器')
    parser.add_argument('fund_code', help='基金代码，如: 006253')
    parser.add_argument('--output', '-o', default='../generated/funds/', 
                       help='输出目录 (默认: ../generated/funds/)')
    
    args = parser.parse_args()
    
    # 创建分析器实例
    analyzer = FundStockAnalyzer()
    
    # 分析基金和股票
    output_file = analyzer.analyze_fund_and_stocks(args.fund_code, args.output)
    
    if output_file:
        print(f"\n🎉 综合分析完成！报告已保存至: {output_file}")
    else:
        print("\n❌ 分析失败")


if __name__ == "__main__":
    main()
