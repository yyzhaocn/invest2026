import sys
import os
import argparse
import pandas as pd
import re
from pathlib import Path
from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fund_analyzer import FundAnalyzer
from stock_info_parser import StockInfoParser

def get_display_width(text):
    """
    计算字符串在终端中的显示宽度
    中文字符占2个字符宽度，英文字符占1个字符宽度
    """
    # 确保text是字符串类型
    if text is None:
        text = ''
    text = str(text)
    
    width = 0
    for char in text:
        # 判断是否为中文字符（包括中文标点）
        if ord(char) > 127:
            width += 2
        else:
            width += 1
    return width

def pad_string(text, target_width, align='left'):
    """
    填充字符串到目标显示宽度
    """
    # 确保text是字符串类型
    if text is None:
        text = ''
    text = str(text)
    
    current_width = get_display_width(text)
    if current_width >= target_width:
        return text
    
    padding = target_width - current_width
    if align == 'left':
        return text + ' ' * padding
    elif align == 'right':
        return ' ' * padding + text
    else:  # center
        left_pad = padding // 2
        right_pad = padding - left_pad
        return ' ' * left_pad + text + ' ' * right_pad

def load_from_csv_cache(fundcode, report_date, cache_days=7):
    """
    从CSV缓存文件加载基金持仓数据
    
    Args:
        fundcode: 基金代码（字符串，保持前导0）
        report_date: 报告日期 (YYYY-MM-DD)
        cache_days: 缓存有效期（天数），默认7天
    
    Returns:
        dict: 如果缓存有效，返回与API格式相同的数据结构；否则返回None
    """
    # CSV文件路径
    csv_file = Path("../generated/em/fundHoldings.csv")
    
    if not csv_file.exists():
        return None
    
    try:
        # 读取CSV文件，确保代码列保持为字符串类型（保留前导0）
        df = pd.read_csv(csv_file, dtype={
            'fundcode': str,
            'holder_code': str,
            'stock_code': str
        })
        
        # 确保输入的fundcode也是字符串格式
        fundcode_str = str(fundcode)
        
        # 检查是否有匹配的基金代码和报告日期
        # 将fundcode列转换为字符串进行比较，确保前导0不被丢失
        df['fundcode'] = df['fundcode'].astype(str)
        mask = (df['fundcode'] == fundcode_str) & (df['report_date'] == report_date)
        matched_data = df[mask].copy()  # 使用 copy() 避免 SettingWithCopyWarning
        
        if matched_data.empty:
            return None
        
        # 检查update_time是否在缓存有效期内
        # 获取最新的update_time
        matched_data['update_time'] = pd.to_datetime(matched_data['update_time'])
        latest_update = matched_data['update_time'].max()
        
        # 检查是否在7天内
        days_diff = (datetime.now() - latest_update.to_pydatetime()).days
        if days_diff > cache_days:
            # 不显示过期信息，保持输出简洁
            return None
        
        # 确保所有代码字段都是字符串类型（保留前导0）
        if 'holder_code' in matched_data.columns:
            matched_data['holder_code'] = matched_data['holder_code'].astype(str)
        if 'stock_code' in matched_data.columns:
            matched_data['stock_code'] = matched_data['stock_code'].astype(str)
        
        # 转换DataFrame为字典列表
        stocks = matched_data.to_dict('records')
        
        # 转换为与API返回格式相同的数据结构
        result = {
            'fundcode': fundcode,
            'report_date': report_date,
            'stocks': stocks,
            'total': len(stocks),
            'page_num': 1,
            'page_size': len(stocks)
        }
        
        # 不显示缓存信息，保持输出简洁
        return result
        
    except Exception as e:
        # 静默失败，直接返回None，将从API获取数据
        return None


def fetch_daily_change_pct(stock_codes):
    """
    批量获取股票当日涨跌幅，返回 {stock_code: change_pct}
    """
    if not stock_codes:
        return {}

    parser = StockInfoParser()
    all_quotes = {}
    # 单次查询过多代码可能触发不稳定，分批获取
    batch_size = 80
    unique_codes = list(dict.fromkeys([str(c).zfill(6) for c in stock_codes if c]))

    for i in range(0, len(unique_codes), batch_size):
        batch_codes = unique_codes[i:i + batch_size]
        try:
            raw_data = parser.fetch_stock_data(batch_codes, quiet=True)
            diff = raw_data.get('data', {}).get('diff', []) if isinstance(raw_data, dict) else []
            for item in diff:
                code = str(item.get('f12', '')).zfill(6)
                pct = item.get('f3', 0.0)
                try:
                    pct = float(pct)
                except (TypeError, ValueError):
                    pct = 0.0
                all_quotes[code] = pct
        except Exception:
            # 行情接口失败时保留已有结果，不中断主流程
            continue

    return all_quotes


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    text = str(name or '').strip()
    if not text:
        return "unknown"
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "", text)
    return text[:80]


def export_holdings_csv(result):
    """
    导出持仓到 fund_{code}_{name}.csv，并在末尾追加预计涨幅行
    """
    stocks = result.get('stocks', [])
    if not stocks:
        return None, 0.0

    fund_code = str(result.get('fundcode', '')).zfill(6)
    fund_name = str(stocks[0].get('holder_name') or f"fund{fund_code}")
    safe_name = sanitize_filename(fund_name)
    output_file = Path(f"fund_{fund_code}_{safe_name}.csv")

    # 转换为DataFrame，补充当日涨跌幅
    df = pd.DataFrame(stocks).copy()
    if 'stock_code' in df.columns:
        df['stock_code'] = df['stock_code'].astype(str).str.zfill(6)
    stock_codes = df.get('stock_code', pd.Series(dtype=str)).tolist()
    change_map = fetch_daily_change_pct(stock_codes)
    df['daily_change_pct'] = df['stock_code'].map(change_map).fillna(0.0)

    # 估算贡献：按净值占比 * 当日涨跌幅
    df['netasset_ratio'] = pd.to_numeric(df.get('netasset_ratio', 0.0), errors='coerce').fillna(0.0)
    df['estimated_contribution_pct'] = df['netasset_ratio'] * df['daily_change_pct'] / 100.0
    estimated_rise_pct = float(df['estimated_contribution_pct'].sum())

    # 常用排序：按持仓市值降序
    if 'hold_value' in df.columns:
        df['hold_value'] = pd.to_numeric(df['hold_value'], errors='coerce').fillna(0.0)
        df = df.sort_values(by='hold_value', ascending=False).reset_index(drop=True)

    # 末尾追加汇总行
    summary = {col: '' for col in df.columns}
    summary['stock_name'] = '预计涨幅(按净值占比估算)'
    summary['daily_change_pct'] = ''
    summary['estimated_contribution_pct'] = round(estimated_rise_pct, 6)
    summary['hold_value'] = ''
    summary['stock_code'] = ''
    summary['netasset_ratio'] = ''
    summary['report_date'] = result.get('report_date', '')
    summary['fundcode'] = fund_code
    summary['holder_name'] = fund_name

    df_export = pd.concat([df, pd.DataFrame([summary])], ignore_index=True)
    df_export.to_csv(output_file, index=False, encoding='utf-8-sig')
    return output_file, estimated_rise_pct

def print_horizontal_bar(stocks, max_width=50, limit=20):
    """
    在终端打印横向条形图
    
    Args:
        stocks: 股票列表，每个股票包含 stock_name, stock_code, hold_amount 等字段
        max_width: 条形图最大宽度（字符数）
        limit: 显示数量限制，-1 表示显示全部，默认20
    """
    if not stocks:
        print("没有股票数据可显示")
        return
    
    # 从第一个股票记录中获取基金信息
    holder_name = str(stocks[0].get('holder_name', '')) if stocks else ''
    holder_code = str(stocks[0].get('holder_code', '')) if stocks else ''
    
    # 如果holder_code为空，尝试使用fundcode
    if not holder_code and stocks and stocks[0].get('fundcode'):
        holder_code = str(stocks[0].get('fundcode', ''))
    
    # 构建标题
    if holder_name and holder_code:
        title = f"{holder_name}({holder_code})"
    elif holder_code:
        title = f"({holder_code})"
    else:
        title = "持仓股票横向条形图（按持仓金额排序）"
    
    # 按持仓金额排序（降序）
    sorted_stocks = sorted(stocks, key=lambda x: x.get('hold_amount', 0), reverse=True)
    
    # 应用数量限制
    total_count = len(sorted_stocks)
    if limit > 0:
        sorted_stocks = sorted_stocks[:limit]
    
    # 找到最大持仓金额，用于计算比例
    max_amount = max(s.get('hold_amount', 0) for s in sorted_stocks) if sorted_stocks else 1
    
    # 定义列宽（显示宽度）
    name_width = 20
    code_width = 10
    amount_width = 15
    ratio_width = 8
    bar_width = max_width
    
    # 计算标题行的宽度
    title_width = name_width + code_width + amount_width + ratio_width + bar_width + 10
    
    print("\n" + "=" * title_width)
    print(title)
    print("=" * title_width)
    
    # 打印表头
    header = pad_string("股票名称", name_width) + " " + \
             pad_string("股票代码", code_width) + " " + \
             pad_string("持仓金额", amount_width, 'right') + " " + \
             pad_string("比例", ratio_width, 'right') + " " + \
             "条形图"
    print(header)
    print("-" * title_width)
    
    for stock in sorted_stocks:
        # 确保所有字段都是正确的类型
        stock_name = str(stock.get('stock_name', 'N/A'))
        # 限制名称长度（按显示宽度）
        if get_display_width(stock_name) > name_width:
            # 截断名称
            truncated = ""
            for char in stock_name:
                if get_display_width(truncated + char) <= name_width - 2:
                    truncated += char
                else:
                    break
            stock_name = truncated + ".."
        
        stock_code = str(stock.get('stock_code', 'N/A'))
        hold_amount = float(stock.get('hold_amount', 0))
        hold_ratio = float(stock.get('hold_ratio', 0))
        
        # 计算条形长度
        if max_amount > 0:
            bar_length = int((hold_amount / max_amount) * max_width)
        else:
            bar_length = 0
        
        # 生成条形图（使用Unicode块字符）
        bar = '█' * bar_length
        
        # 格式化持仓金额（以万为单位显示，如果很大）
        if hold_amount >= 10000:
            amount_str = f"{hold_amount/10000:.2f}万"
        else:
            amount_str = f"{hold_amount:,.0f}"
        
        # 格式化比例
        ratio_str = f"{hold_ratio:.2f}%"
        
        # 使用正确的对齐方式打印
        line = pad_string(stock_name, name_width) + " " + \
               pad_string(stock_code, code_width) + " " + \
               pad_string(amount_str, amount_width, 'right') + " " + \
               pad_string(ratio_str, ratio_width, 'right') + " " + \
               bar
        print(line)
    
    print("=" * title_width)
    if limit > 0 and total_count > limit:
        print(f"显示: {len(sorted_stocks)}/{total_count} 只股票 (使用 --limit -1 显示全部)")
    else:
        print(f"总计: {len(sorted_stocks)} 只股票")
    if max_amount >= 10000:
        print(f"最大持仓金额: {max_amount/10000:.2f}万")
    else:
        print(f"最大持仓金额: {max_amount:,.0f}")

def main():
    """Query fund holdings via command line arguments"""
    parser = argparse.ArgumentParser(description="Query fund stock holdings")
    parser.add_argument("fundcode", help="Fund Code (e.g. 013942)")
    parser.add_argument("--date", default="2025-09-30", help="Report Date (YYYY-MM-DD), default: 2025-09-30")
    parser.add_argument("--limit", type=int, default=20, help="Number of stocks to show (bar chart default: 20, list mode default: 20). Use -1 to show all")
    parser.add_argument("--list", action="store_true", help="Display detailed list instead of bar chart (default: bar chart)")
    
    args = parser.parse_args()
    
    # 默认使用条形图，除非指定 --list
    use_bar = not args.list
    
    analyzer = FundAnalyzer()
    
    # 只在列表模式下显示查询信息
    if not use_bar:
        print(f"Querying fund {args.fundcode} holdings for date {args.date}...")
        print("=" * 60)
    
    # 首先检查CSV缓存（7天内有效）
    # 如果缓存有效，直接使用缓存数据，不调用API
    result = load_from_csv_cache(args.fundcode, args.date, cache_days=7)
    
    # 如果缓存无效或不存在，从API获取数据
    # API获取后会自动保存到CSV（保存前会先删除旧缓存）
    if result is None:
        if not use_bar:
            print("📡 从API获取数据...")
        # 条形图模式获取更多数据
        page_size = 200 if use_bar else 50
        result = analyzer.stockHolding(args.fundcode, report_date=args.date, page_num=1, page_size=page_size)
    
    if result:
        output_file, estimated_rise = export_holdings_csv(result)
        if output_file:
            print(f"📄 已导出: {output_file}")
            print(f"📈 估算预计涨幅: {estimated_rise:.4f}%")

        # 如果使用条形图，只显示条形图
        if use_bar:
            # 处理 limit 参数：-1 表示显示全部，否则使用指定值或默认20
            limit = args.limit if args.limit > 0 else -1
            print_horizontal_bar(result['stocks'], limit=limit)
        else:
            # 列表模式显示详细信息
            print(f"\nFund Code: {result['fundcode']}")
            print(f"Report Date: {result['report_date']}")
            print(f"Total Records: {result['total']}")
            
            # Calculate max pages for display info
            page_size = result.get('page_size', 50)
            total = result.get('total', 0)
            total_pages = (total // page_size + 1) if page_size > 0 else 1
            print(f"Page: {result['page_num']}/{total_pages}")
            
            print("\nHoldings List:")
            print("-" * 60)
            
            # 处理 limit 参数：-1 表示显示全部
            if args.limit == -1:
                stocks_to_show = result['stocks']
            else:
                stocks_to_show = result['stocks'][:args.limit]
            
            for i, stock in enumerate(stocks_to_show, 1):
                print(f"\n{i}. {stock['stock_name']} ({stock['stock_code']})")
                print(f"   Hold Amount: {stock['hold_amount']:,.0f}")
                print(f"   Hold Ratio:  {stock['hold_ratio']:.2f}%")
                print(f"   Hold Value:  {stock['hold_value']:,.0f}")
                print(f"   Change Amt:  {stock['change_amount']:,.0f}")
                print(f"   Change Ratio:{stock['change_ratio']:.2f}%")
                print(f"   NetAsset Rat:{stock['netasset_ratio']:.2f}%")
            
            if args.limit != -1:
                remaining = len(result['stocks']) - len(stocks_to_show)
                if remaining > 0:
                    print(f"\n... and {remaining} more stocks (use --limit -1 to see all)")
    else:
        print("❌ Query Failed")

if __name__ == "__main__":
    main()

