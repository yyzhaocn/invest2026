#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金分析Web应用
提供Web界面输入基金代码并生成HTML报告
"""

from flask import Flask, request, render_template, jsonify, redirect, url_for
import os
import sys
from datetime import datetime

# 导入fund模块
from fund_analyzer import FundAnalyzer

app = Flask(__name__, template_folder='../templates')

# 配置
app.config['SECRET_KEY'] = 'fund-analyzer-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_fund():
    """分析基金并生成报告"""
    try:
        fund_code = request.form.get('fund_code', '').strip()
        
        if not fund_code:
            return jsonify({
                'success': False,
                'error': '请输入基金代码'
            }), 400
        
        # 验证基金代码格式（基本验证）
        if not fund_code.isdigit() or len(fund_code) != 6:
            return jsonify({
                'success': False,
                'error': '基金代码应为6位数字'
            }), 400
        
        # 创建分析器实例
        analyzer = FundAnalyzer()
        
        # 生成报告
        output_file = analyzer.analyze_fund(fund_code, use_simple_report=True)
        
        if output_file and os.path.exists(output_file):
            # 读取生成的HTML内容
            with open(output_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 生成报告ID（基于时间戳）
            report_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            return jsonify({
                'success': True,
                'report_id': report_id,
                'fund_code': fund_code,
                'html_content': html_content,
                'message': f'基金 {fund_code} 分析报告生成成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '生成报告失败，请检查基金代码是否正确'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'分析过程中出现错误: {str(e)}'
        }), 500

@app.route('/report/<fund_code>')
def show_report(fund_code):
    """显示基金报告页面"""
    try:
        # 验证基金代码
        if not fund_code.isdigit() or len(fund_code) != 6:
            return "无效的基金代码", 400
        
        # 创建分析器实例并生成报告
        analyzer = FundAnalyzer()
        output_file = analyzer.analyze_fund(fund_code, use_simple_report=True)
        
        if output_file and os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            return html_content
        else:
            return f"无法生成基金 {fund_code} 的报告", 404
            
    except Exception as e:
        return f"生成报告时出错: {str(e)}", 500

@app.route('/api/analyze/<fund_code>')
def api_analyze_fund(fund_code):
    """API接口：分析基金"""
    try:
        # 验证基金代码
        if not fund_code.isdigit() or len(fund_code) != 6:
            return jsonify({
                'success': False,
                'error': '无效的基金代码格式'
            }), 400
        
        # 创建分析器实例
        analyzer = FundAnalyzer()
        
        # 生成报告
        output_file = analyzer.analyze_fund(fund_code, use_simple_report=True)
        
        if output_file and os.path.exists(output_file):
            return jsonify({
                'success': True,
                'fund_code': fund_code,
                'report_url': url_for('show_report', fund_code=fund_code, _external=True),
                'message': f'基金 {fund_code} 分析完成'
            })
        else:
            return jsonify({
                'success': False,
                'error': '生成报告失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return render_template('error.html', 
                         error_code=404, 
                         error_message="页面未找到"), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return render_template('error.html', 
                         error_code=500, 
                         error_message="服务器内部错误"), 500

if __name__ == '__main__':
    # 确保templates目录存在
    templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    print("🚀 启动基金分析Web应用...")
    print("📊 访问地址: http://localhost:5001")
    print("📈 API文档:")
    print("  - 主页: GET /")
    print("  - 分析基金: POST /analyze")
    print("  - 查看报告: GET /report/<fund_code>")
    print("  - API接口: GET /api/analyze/<fund_code>")
    print("\n按 Ctrl+C 停止服务器")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
