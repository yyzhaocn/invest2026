#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buysell Submodule for Stock Analysis Web Application
Presents links to all buysell_ files and displays buying stocks by sections
"""

import os
import sys
import configparser
import glob
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from flask import Blueprint, render_template, request, jsonify, send_from_directory

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import quote function for current stock data
try:
    from stock.utils_reem import get_quote
    QUOTE_AVAILABLE = True
except ImportError:
    get_quote = None
    QUOTE_AVAILABLE = False

# Create blueprint for buysell module
buysell_bp = Blueprint('buysell', __name__, url_prefix='/buysell')

class BuysellAnalyzer:
    """Analyzer for buysell_*.ini files"""
    
    def __init__(self, data_dir: str = None):
        """
        Initialize BuysellAnalyzer
        
        Args:
            data_dir: Data directory path, defaults to generated/em
        """
        if data_dir is None:
            # Default to generated/em directory
            self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'generated', 'em')
        else:
            self.data_dir = data_dir
        
        # Strategy display names mapping
        self.strategy_names = {
            '评分': '评分策略',
            '小市值': '小市值策略', 
            '主力净占比': '主力净占比策略',
            '超大单占比': '超大单占比策略',
            '换手率': '换手率策略',
            '手工': '手工策略',
            '盘口异动': '盘口异动策略'
        }
        
        # Chinese holidays (non-trading days)
        self.holidays = {
            # 2025 Chinese National Day holiday: Oct 1-8
            '2025-10-01': '国庆节',
            '2025-10-02': '国庆节',
            '2025-10-03': '国庆节',
            '2025-10-04': '国庆节',
            '2025-10-05': '国庆节',
            '2025-10-06': '国庆节',
            '2025-10-07': '国庆节',
            '2025-10-08': '国庆节',
        }
    
    def is_trading_day(self, date_str: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a given date is a trading day
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            
        Returns:
            Tuple of (is_trading_day, holiday_name)
        """
        try:
            # Parse the date
            check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Check if it's a weekend (Saturday=5, Sunday=6)
            if check_date.weekday() >= 5:
                return False, "周末"
            
            # Check if it's a holiday
            if date_str in self.holidays:
                return False, self.holidays[date_str]
            
            return True, None
            
        except ValueError:
            # Invalid date format
            return False, "无效日期格式"
    
    def get_current_stock_info_with_holiday_check(self, stock_code: str) -> Dict:
        """
        Get current stock information with holiday check
        
        Args:
            stock_code: Stock code to analyze
            
        Returns:
            Dictionary with current stock info and holiday status
        """
        current_info = self.get_current_stock_info(stock_code)
        
        # Add holiday information
        today = date.today().strftime('%Y-%m-%d')
        is_trading, holiday_name = self.is_trading_day(today)
        
        current_info['is_trading_day'] = is_trading
        current_info['holiday_name'] = holiday_name
        current_info['current_date'] = today
        
        # If it's not a trading day, add a note
        if not is_trading:
            current_info['trading_note'] = f"今日为{holiday_name}，非交易日" if holiday_name else "今日非交易日"
        else:
            current_info['trading_note'] = "今日为交易日"
        
        return current_info
    
    def find_buysell_files(self) -> List[Dict]:
        """
        Find all buysell_*.ini files in the data directory
        
        Returns:
            List of file information dictionaries
        """
        files_info = []
        
        # Search in shared directory first
        shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared')
        if os.path.exists(shared_dir):
            pattern = os.path.join(shared_dir, "buysell_*.ini")
            files = glob.glob(pattern)
            for file_path in files:
                files_info.append(self._get_file_info(file_path, 'shared'))
        
        # Search in data directory and subdirectories
        pattern = os.path.join(self.data_dir, "**/buysell_*.ini")
        files = glob.glob(pattern, recursive=True)
        for file_path in files:
            files_info.append(self._get_file_info(file_path, 'generated'))
        
        # Sort by modification time (newest first)
        files_info.sort(key=lambda x: x['modified_time'], reverse=True)
        
        return files_info
    
    def _get_file_info(self, file_path: str, source: str) -> Dict:
        """
        Get file information
        
        Args:
            file_path: Path to the file
            source: Source type ('shared' or 'generated')
            
        Returns:
            File information dictionary
        """
        stat = os.stat(file_path)
        filename = os.path.basename(file_path)
        
        # Extract date from filename (buysell_YYMMDD.ini)
        date_str = filename.replace('buysell_', '').replace('.ini', '')
        
        return {
            'filename': filename,
            'filepath': file_path,
            'relative_path': os.path.relpath(file_path, os.getcwd()),
            'date': date_str,
            'modified_time': stat.st_mtime,
            'modified_datetime': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'size': stat.st_size,
            'source': source
        }
    
    def parse_buysell_file(self, file_path: str) -> Dict:
        """
        Parse a buysell_*.ini file and extract stock data by sections
        
        Args:
            file_path: Path to the buysell file
            
        Returns:
            Dictionary containing parsed data by sections
        """
        config = configparser.ConfigParser()
        config.read(file_path, encoding='utf-8')
        
        result = {
            'file_info': self._get_file_info(file_path, 'unknown'),
            'sections': {},
            'summary': {
                'total_stocks': 0,
                'total_sections': 0,
                'total_quantity': 0,
                'total_value': 0.0
            }
        }
        
        for section_name in config.sections():
            if section_name in self.strategy_names:
                section_data = self._parse_section(config[section_name], section_name)
                result['sections'][section_name] = section_data
                result['summary']['total_stocks'] += len(section_data['stocks'])
                result['summary']['total_quantity'] += section_data['total_quantity']
                result['summary']['total_value'] += section_data['total_value']
        
        result['summary']['total_sections'] = len(result['sections'])
        
        return result
    
    def _parse_section(self, section, section_name: str) -> Dict:
        """
        Parse a section of the buysell file
        
        Args:
            section: ConfigParser section
            section_name: Name of the section
            
        Returns:
            Dictionary containing section data
        """
        stocks = []
        total_quantity = 0
        total_value = 0.0
        
        for key, value in section.items():
            try:
                # Parse stock data: 股票代码_股票名称 = 买入时间,数量,买入价格,备注
                parts = value.split(',')
                if len(parts) >= 3:
                    buy_time = parts[0]
                    quantity = int(parts[1])
                    buy_price = float(parts[2])
                    note = parts[3] if len(parts) > 3 else ''
                    
                    # Extract stock code and name from key
                    if '_' in key:
                        stock_code, stock_name = key.split('_', 1)
                    else:
                        stock_code = key
                        stock_name = ''
                    
                    stock_data = {
                        'code': stock_code,
                        'name': stock_name,
                        'buy_time': buy_time,
                        'quantity': quantity,
                        'buy_price': buy_price,
                        'note': note,
                        'total_value': quantity * buy_price
                    }
                    
                    stocks.append(stock_data)
                    total_quantity += quantity
                    total_value += stock_data['total_value']
                    
            except (ValueError, IndexError) as e:
                print(f"Error parsing stock data {key}={value}: {e}")
                continue
        
        # Sort stocks by total value (descending)
        stocks.sort(key=lambda x: x['total_value'], reverse=True)
        
        return {
            'name': section_name,
            'display_name': self.strategy_names.get(section_name, section_name),
            'stocks': stocks,
            'total_quantity': total_quantity,
            'total_value': total_value,
            'stock_count': len(stocks)
        }
    
    def get_stock_analysis(self, file_path: str) -> Dict:
        """
        Get comprehensive stock analysis for a buysell file
        
        Args:
            file_path: Path to the buysell file
            
        Returns:
            Analysis results
        """
        parsed_data = self.parse_buysell_file(file_path)
        
        # Additional analysis
        analysis = {
            'file_data': parsed_data,
            'top_stocks': self._get_top_stocks(parsed_data),
            'strategy_performance': self._analyze_strategy_performance(parsed_data),
            'stock_distribution': self._analyze_stock_distribution(parsed_data)
        }
        
        return analysis
    
    def _get_top_stocks(self, parsed_data: Dict, limit: int = 10) -> List[Dict]:
        """Get top stocks by total value across all strategies"""
        all_stocks = []
        for section_data in parsed_data['sections'].values():
            all_stocks.extend(section_data['stocks'])
        
        # Sort by total value and return top N
        all_stocks.sort(key=lambda x: x['total_value'], reverse=True)
        return all_stocks[:limit]
    
    def _analyze_strategy_performance(self, parsed_data: Dict) -> Dict:
        """Analyze performance by strategy"""
        strategy_stats = {}
        
        for section_name, section_data in parsed_data['sections'].items():
            strategy_stats[section_name] = {
                'display_name': section_data['display_name'],
                'stock_count': section_data['stock_count'],
                'total_quantity': section_data['total_quantity'],
                'total_value': section_data['total_value'],
                'avg_value_per_stock': section_data['total_value'] / section_data['stock_count'] if section_data['stock_count'] > 0 else 0
            }
        
        return strategy_stats
    
    def _analyze_stock_distribution(self, parsed_data: Dict) -> Dict:
        """Analyze stock distribution patterns"""
        all_stocks = []
        for section_data in parsed_data['sections'].values():
            all_stocks.extend(section_data['stocks'])
        
        # Analyze by stock codes
        code_distribution = {}
        for stock in all_stocks:
            code = stock['code']
            if code not in code_distribution:
                code_distribution[code] = {
                    'name': stock['name'],
                    'total_quantity': 0,
                    'total_value': 0.0,
                    'strategies': set()
                }
            code_distribution[code]['total_quantity'] += stock['quantity']
            code_distribution[code]['total_value'] += stock['total_value']
            # Find which strategy this stock belongs to
            for section_name, section_data in parsed_data['sections'].items():
                if stock in section_data['stocks']:
                    code_distribution[code]['strategies'].add(section_name)
        
        # Convert sets to lists for JSON serialization
        for code_data in code_distribution.values():
            code_data['strategies'] = list(code_data['strategies'])
        
        return {
            'unique_stocks': len(code_distribution),
            'code_distribution': code_distribution
        }
    
    def get_current_stock_info(self, stock_code: str) -> Dict:
        """
        Get current stock information and calculate profit
        
        Args:
            stock_code: Stock code to analyze
            
        Returns:
            Dictionary with current stock info and profit calculations
        """
        current_info = {
            'stock_code': stock_code,
            'current_price': 0.0,
            'stock_name': '',
            'change': 0.0,
            'change_percent': 0.0,
            'market_cap': '',
            'pe_ratio': 0.0,
            'pb_ratio': 0.0,
            'volume': 0,
            'turnover': 0,
            'high': 0.0,
            'low': 0.0,
            'open': 0.0,
            'turnover_rate': 0.0,
            'data_available': False,
            'error': None
        }
        
        if not QUOTE_AVAILABLE or not get_quote:
            current_info['error'] = 'Quote data not available'
            return current_info
        
        try:
            quote_data = get_quote(stock_code)
            
            if quote_data:
                current_info.update({
                    'current_price': float(quote_data.get('当前价格', 0)),
                    'stock_name': quote_data.get('股票名称', f'股票{stock_code}'),
                    'change': float(quote_data.get('涨跌额', 0)),
                    'change_percent': float(quote_data.get('涨跌幅', 0)),
                    'market_cap': f"{quote_data.get('总市值', 0):.2f}亿",
                    'pe_ratio': float(quote_data.get('市盈率(动)', 0)),
                    'pb_ratio': float(quote_data.get('市净率', 0)),
                    'volume': quote_data.get('成交量', 0),
                    'turnover': quote_data.get('成交额', 0),
                    'high': quote_data.get('最高', 0),
                    'low': quote_data.get('最低', 0),
                    'open': quote_data.get('今开', 0),
                    'turnover_rate': quote_data.get('换手率', 0),
                    'data_available': True
                })
            else:
                current_info['error'] = 'No quote data returned'
                
        except Exception as e:
            current_info['error'] = f'Error fetching quote data: {str(e)}'
        
        return current_info
    
    def calculate_profit_analysis(self, stock_analysis: Dict, current_info: Dict) -> Dict:
        """
        Calculate profit analysis based on current stock price
        
        Args:
            stock_analysis: Stock analysis from buysell files
            current_info: Current stock information
            
        Returns:
            Profit analysis dictionary
        """
        if not current_info['data_available'] or current_info['current_price'] <= 0:
            return {
                'total_profit': 0.0,
                'total_profit_percent': 0.0,
                'avg_buy_price': 0.0,
                'profit_available': False,
                'error': 'Current price not available'
            }
        
        current_price = current_info['current_price']
        total_quantity = stock_analysis['total_quantity']
        total_buy_value = stock_analysis['total_value']
        
        # Calculate average buy price
        avg_buy_price = total_buy_value / total_quantity if total_quantity > 0 else 0
        
        # Calculate current total value
        current_total_value = current_price * total_quantity
        
        # Calculate profit
        total_profit = current_total_value - total_buy_value
        total_profit_percent = (total_profit / total_buy_value * 100) if total_buy_value > 0 else 0
        
        return {
            'total_profit': total_profit,
            'total_profit_percent': total_profit_percent,
            'avg_buy_price': avg_buy_price,
            'current_total_value': current_total_value,
            'total_buy_value': total_buy_value,
            'profit_available': True,
            'error': None
        }

# Initialize analyzer
analyzer = BuysellAnalyzer()

@buysell_bp.route('/')
def index():
    """Main buysell page - list all buysell files"""
    files_info = analyzer.find_buysell_files()
    
    return render_template('buysell/index.html', 
                         files=files_info,
                         title="Buysell Files Overview")

@buysell_bp.route('/file/<path:filename>')
def view_file(filename):
    """View specific buysell file with detailed analysis"""
    # Find the file
    files_info = analyzer.find_buysell_files()
    file_info = None
    
    for f in files_info:
        if f['filename'] == filename:
            file_info = f
            break
    
    if not file_info:
        return "File not found", 404
    
    # Parse the file
    analysis = analyzer.get_stock_analysis(file_info['filepath'])
    
    return render_template('buysell/file_detail.html',
                         analysis=analysis,
                         title=f"Buysell File: {filename}")

@buysell_bp.route('/api/files')
def api_files():
    """API endpoint to get all buysell files"""
    files_info = analyzer.find_buysell_files()
    return jsonify({
        'success': True,
        'files': files_info,
        'count': len(files_info)
    })

@buysell_bp.route('/api/file/<path:filename>')
def api_file_data(filename):
    """API endpoint to get specific file data"""
    # Find the file
    files_info = analyzer.find_buysell_files()
    file_info = None
    
    for f in files_info:
        if f['filename'] == filename:
            file_info = f
            break
    
    if not file_info:
        return jsonify({
            'success': False,
            'error': 'File not found'
        }), 404
    
    # Parse the file
    analysis = analyzer.get_stock_analysis(file_info['filepath'])
    
    return jsonify({
        'success': True,
        'analysis': analysis
    })

@buysell_bp.route('/api/section/<path:filename>/<section_name>')
def api_section_data(filename, section_name):
    """API endpoint to get specific section data"""
    # Find the file
    files_info = analyzer.find_buysell_files()
    file_info = None
    
    for f in files_info:
        if f['filename'] == filename:
            file_info = f
            break
    
    if not file_info:
        return jsonify({
            'success': False,
            'error': 'File not found'
        }), 404
    
    # Parse the file
    parsed_data = analyzer.parse_buysell_file(file_info['filepath'])
    
    if section_name not in parsed_data['sections']:
        return jsonify({
            'success': False,
            'error': 'Section not found'
        }), 404
    
    return jsonify({
        'success': True,
        'section': parsed_data['sections'][section_name],
        'file_info': parsed_data['file_info']
    })

@buysell_bp.route('/api/stock/<stock_code>')
def api_stock_analysis(stock_code):
    """API endpoint to analyze a specific stock across all files"""
    files_info = analyzer.find_buysell_files()
    stock_analysis = {
        'stock_code': stock_code,
        'appearances': [],
        'total_quantity': 0,
        'total_value': 0.0,
        'strategies': set()
    }
    
    for file_info in files_info:
        try:
            parsed_data = analyzer.parse_buysell_file(file_info['filepath'])
            
            for section_name, section_data in parsed_data['sections'].items():
                for stock in section_data['stocks']:
                    if stock['code'] == stock_code:
                        appearance = {
                            'file': file_info['filename'],
                            'file_date': file_info['date'],
                            'section': section_name,
                            'section_display': section_data['display_name'],
                            'quantity': stock['quantity'],
                            'buy_price': stock['buy_price'],
                            'total_value': stock['total_value'],
                            'buy_time': stock['buy_time'],
                            'note': stock['note']
                        }
                        stock_analysis['appearances'].append(appearance)
                        stock_analysis['total_quantity'] += stock['quantity']
                        stock_analysis['total_value'] += stock['total_value']
                        stock_analysis['strategies'].add(section_name)
        except Exception as e:
            print(f"Error analyzing file {file_info['filename']}: {e}")
            continue
    
    # Convert set to list for JSON serialization
    stock_analysis['strategies'] = list(stock_analysis['strategies'])
    
    # Sort appearances by file date (newest first)
    stock_analysis['appearances'].sort(key=lambda x: x['file_date'], reverse=True)
    
    # Get current stock information with holiday check
    current_info = analyzer.get_current_stock_info_with_holiday_check(stock_code)
    
    # Calculate profit analysis
    profit_analysis = analyzer.calculate_profit_analysis(stock_analysis, current_info)
    
    return jsonify({
        'success': True,
        'analysis': stock_analysis,
        'current_info': current_info,
        'profit_analysis': profit_analysis
    })

@buysell_bp.route('/api/summary')
def api_summary():
    """API endpoint to get summary statistics across all files"""
    files_info = analyzer.find_buysell_files()
    
    summary = {
        'total_files': len(files_info),
        'total_stocks': 0,
        'total_sections': 0,
        'strategy_counts': {},
        'date_range': {
            'earliest': None,
            'latest': None
        },
        'file_sources': {
            'shared': 0,
            'generated': 0
        }
    }
    
    for file_info in files_info:
        try:
            parsed_data = analyzer.parse_buysell_file(file_info['filepath'])
            
            summary['total_stocks'] += parsed_data['summary']['total_stocks']
            summary['total_sections'] += parsed_data['summary']['total_sections']
            
            # Count strategies
            for section_name in parsed_data['sections'].keys():
                if section_name not in summary['strategy_counts']:
                    summary['strategy_counts'][section_name] = 0
                summary['strategy_counts'][section_name] += 1
            
            # Track date range
            file_date = file_info['date']
            if summary['date_range']['earliest'] is None or file_date < summary['date_range']['earliest']:
                summary['date_range']['earliest'] = file_date
            if summary['date_range']['latest'] is None or file_date > summary['date_range']['latest']:
                summary['date_range']['latest'] = file_date
            
            # Count file sources
            summary['file_sources'][file_info['source']] += 1
            
        except Exception as e:
            print(f"Error processing file {file_info['filename']}: {e}")
            continue
    
    return jsonify({
        'success': True,
        'summary': summary
    })


# Export the blueprint for use in main app
__all__ = ['buysell_bp', 'BuysellAnalyzer']
