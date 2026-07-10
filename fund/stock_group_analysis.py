#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票组盈利分析工具
"""

import argparse
from fund_analyzer import FundAnalyzer
from stock_info_parser import StockInfoParser
from anyStock import resolve_stock_code
from datetime import datetime

def display_width(text):
    """
    计算字符串的实际显示宽度
    中文字符按2个字符宽度计算，英文字符按1个字符宽度计算
    """
    width = 0
    for char in text:
        # 判断是否为中文字符（包括中文标点）
        if ord(char) >= 0x4E00 and ord(char) <= 0x9FFF:
            width += 2
        elif ord(char) >= 0x3000 and ord(char) <= 0x303F:  # 中文标点
            width += 2
        elif ord(char) >= 0xFF00 and ord(char) <= 0xFFEF:  # 全角字符
            width += 2
        else:
            width += 1
    return width

def pad_string(text, width, align='<'):
    """
    根据实际显示宽度填充字符串
    """
    actual_width = display_width(text)
    if actual_width >= width:
        return text
    
    padding = width - actual_width
    if align == '<':
        return text + ' ' * padding
    elif align == '>':
        return ' ' * padding + text
    else:  # center
        left_pad = padding // 2
        right_pad = padding - left_pad
        return ' ' * left_pad + text + ' ' * right_pad

def truncate_string(text, max_width):
    """
    根据实际显示宽度截断字符串
    """
    if display_width(text) <= max_width:
        return text
    
    result = ''
    current_width = 0
    for char in text:
        char_width = 2 if (ord(char) >= 0x4E00 and ord(char) <= 0x9FFF) or \
                         (ord(char) >= 0x3000 and ord(char) <= 0x303F) or \
                         (ord(char) >= 0xFF00 and ord(char) <= 0xFFEF) else 1
        
        if current_width + char_width > max_width - 3:  # 留出 "..." 的空间
            result += '...'
            break
        result += char
        current_width += char_width
    
    return result

def analyze_stock_group(stock_inputs):
    """
    分析股票组的盈利情况
    
    Args:
        stock_inputs: 股票代码或名称列表（混合支持）
    """
    print("="*80)
    print("股票组盈利分析")
    print("="*80)
    
    parser = StockInfoParser()
    analyzer = FundAnalyzer()
    
    print(f"\n输入数量: {len(stock_inputs)}")
    print(f"输入内容: {', '.join(stock_inputs[:10])}{'...' if len(stock_inputs) > 10 else ''}\n")
    
    # 解析输入（可能是股票代码、名称或简拼）
    print("【正在解析股票代码/名称...】")
    stock_info_map = {}  # {输入值: (股票代码, 股票名称)}
    code_to_input = {}  # {股票代码: 第一个匹配的输入值}
    cleaned_codes_set = set()  # 用于去重
    cleaned_codes = []
    
    for input_value in stock_inputs:
        input_value = input_value.strip()
        if not input_value:
            continue
            
        try:
            actual_code, quote = resolve_stock_code(input_value)
            
            if actual_code:
                # 去重：如果股票代码已存在，跳过
                if actual_code not in cleaned_codes_set:
                    cleaned_codes_set.add(actual_code)
                    cleaned_codes.append(actual_code)
                    code_to_input[actual_code] = input_value
                
                stock_info_map[input_value] = (actual_code, quote['name'])
                print(f"  ✓ {input_value} → {actual_code} ({quote['name']})")
            else:
                print(f"  ✗ 未找到: {input_value}")
        except Exception as e:
            print(f"  ✗ 解析失败: {input_value} - {e}")
    
    if not cleaned_codes:
        print("\n❌ 未找到任何有效的股票代码")
        return
    
    print(f"\n成功解析: {len(cleaned_codes)}/{len(stock_inputs)} 只股票（已去重）")
    print(f"股票代码: {', '.join(cleaned_codes[:10])}{'...' if len(cleaned_codes) > 10 else ''}\n")
    
    # 批量获取股票信息
    print("【正在获取股票行情数据...】")
    try:
        raw_data = parser.fetch_stock_data(cleaned_codes)
        stocks = parser.format_stock_info(raw_data)
    except Exception as e:
        print(f"❌ 获取股票数据失败: {e}")
        return
    
    if not stocks:
        print("❌ 未获取到股票数据")
        return
    
    # 分析盈利情况
    print("\n【一、股票组整体表现】")
    print("="*80)
    
    # 统计信息
    total_stocks = len(stocks)
    up_stocks = [s for s in stocks if s['change_pct'] > 0]
    down_stocks = [s for s in stocks if s['change_pct'] < 0]
    flat_stocks = [s for s in stocks if s['change_pct'] == 0]
    
    avg_change = sum(s['change_pct'] for s in stocks) / total_stocks if total_stocks > 0 else 0
    max_change = max((s['change_pct'] for s in stocks), default=0)
    min_change = min((s['change_pct'] for s in stocks), default=0)
    
    print(f"股票总数: {total_stocks}")
    print(f"上涨股票: {len(up_stocks)} ({len(up_stocks)/total_stocks*100:.1f}%)" if total_stocks > 0 else "上涨股票: 0")
    print(f"下跌股票: {len(down_stocks)} ({len(down_stocks)/total_stocks*100:.1f}%)" if total_stocks > 0 else "下跌股票: 0")
    print(f"平盘股票: {len(flat_stocks)} ({len(flat_stocks)/total_stocks*100:.1f}%)" if total_stocks > 0 else "平盘股票: 0")
    print(f"\n平均涨跌幅: {avg_change:+.2f}%")
    print(f"最大涨幅: {max_change:+.2f}%")
    print(f"最大跌幅: {min_change:+.2f}%")
    
    # 按涨跌幅排序
    print("\n【二、股票涨跌幅排名】")
    print("="*80)
    sorted_stocks = sorted(stocks, key=lambda x: x['change_pct'], reverse=True)
    
    # 表头：使用实际显示宽度对齐
    header_rank = pad_string('排名', 6)
    header_code = pad_string('股票代码', 10)
    header_name = pad_string('股票名称', 20)
    header_change = pad_string('涨跌幅', 12)
    header_status = pad_string('状态', 8)
    header_input = pad_string('原始输入', 15)
    print(f"{header_rank} {header_code} {header_name} {header_change} {header_status} {header_input}")
    print("-"*100)
    
    for i, stock in enumerate(sorted_stocks, 1):
        code = stock['code']
        name = stock['name']
        change_pct = stock['change_pct']
        status = stock['change_status']
        original_input = code_to_input.get(code, code)
        
        # 根据实际显示宽度截断过长的名称
        name = truncate_string(name, 18)
        original_input = truncate_string(original_input, 13)
        
        # 使用实际显示宽度对齐
        rank_str = pad_string(str(i), 6)
        code_str = pad_string(code, 10)
        name_str = pad_string(name, 20)
        change_str = pad_string(f"{change_pct:+.2f}%", 12, '>')
        status_str = pad_string(status, 8)
        input_str = pad_string(original_input, 15)
        
        print(f"{rank_str} {code_str} {name_str} {change_str} {status_str} {input_str}")
    
    # 盈利分析
    print("\n【三、盈利分析】")
    print("="*80)
    
    # 盈利股票（涨幅>0）
    profitable_stocks = [s for s in stocks if s['change_pct'] > 0]
    if profitable_stocks:
        profitable_avg = sum(s['change_pct'] for s in profitable_stocks) / len(profitable_stocks)
        print(f"盈利股票数量: {len(profitable_stocks)}")
        print(f"盈利股票平均涨幅: {profitable_avg:+.2f}%")
    
    # 亏损股票（涨幅<0）
    loss_stocks = [s for s in stocks if s['change_pct'] < 0]
    if loss_stocks:
        loss_avg = sum(s['change_pct'] for s in loss_stocks) / len(loss_stocks)
        print(f"亏损股票数量: {len(loss_stocks)}")
        print(f"亏损股票平均跌幅: {loss_avg:+.2f}%")
    
    # 涨跌幅分布
    print("\n涨跌幅分布:")
    high_gain = len([s for s in stocks if s['change_pct'] >= 3])
    medium_gain = len([s for s in stocks if 1 <= s['change_pct'] < 3])
    low_gain = len([s for s in stocks if 0 < s['change_pct'] < 1])
    low_loss = len([s for s in stocks if -1 < s['change_pct'] < 0])
    medium_loss = len([s for s in stocks if -3 <= s['change_pct'] < -1])
    high_loss = len([s for s in stocks if s['change_pct'] < -3])
    
    print(f"  大涨(≥3%): {high_gain}只")
    print(f"  中涨(1-3%): {medium_gain}只")
    print(f"  小涨(0-1%): {low_gain}只")
    print(f"  小跌(-1-0%): {low_loss}只")
    print(f"  中跌(-3--1%): {medium_loss}只")
    print(f"  大跌(<-3%): {high_loss}只")
    
    # 最佳/最差表现
    print("\n【四、最佳/最差表现股票】")
    print("="*80)
    
    if sorted_stocks:
        best = sorted_stocks[0]
        worst = sorted_stocks[-1]
        
        print(f"最佳表现:")
        print(f"  {best['code']} {best['name']}: {best['change_pct']:+.2f}%")
        print(f"\n最差表现:")
        print(f"  {worst['code']} {worst['name']}: {worst['change_pct']:+.2f}%")
    
    # 投资建议摘要
    print("\n【五、投资建议摘要】")
    print("="*80)
    
    if avg_change > 0:
        if avg_change >= 2:
            print("✓ 股票组整体表现优秀，平均涨幅较高")
        elif avg_change >= 1:
            print("✓ 股票组整体表现良好，平均涨幅适中")
        else:
            print("○ 股票组整体表现一般，平均涨幅较小")
    else:
        if avg_change <= -2:
            print("✗ 股票组整体表现较差，平均跌幅较大")
        elif avg_change <= -1:
            print("✗ 股票组整体表现不佳，平均跌幅适中")
        else:
            print("○ 股票组整体表现偏弱，平均跌幅较小")
    
    profitable_ratio = len(profitable_stocks) / total_stocks * 100 if total_stocks > 0 else 0
    if profitable_ratio >= 70:
        print(f"✓ 盈利股票占比高 ({profitable_ratio:.1f}%)")
    elif profitable_ratio >= 50:
        print(f"○ 盈利股票占比中等 ({profitable_ratio:.1f}%)")
    else:
        print(f"✗ 盈利股票占比较低 ({profitable_ratio:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description="股票组盈利分析工具")
    parser.add_argument("stockcodes", nargs='+', 
                       help="股票代码、股票名称或简拼列表（混合支持） (e.g. 002414 600482 中国动力 臻镭科技 XRD)")
    
    args = parser.parse_args()
    
    analyze_stock_group(args.stockcodes)

if __name__ == "__main__":
    main()
