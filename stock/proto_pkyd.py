import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import os

cookies = {
    'qgqp_b_id': '125fef21bf721e77a102bb668642803e',
    'st_si': '53976007936223',
    'fullscreengg': '1',
    'fullscreengg2': '1',
    'st_nvi': 'whttZFKXNnA_km71gtVGJfd20',
    'nid': '007529139545699f3d5bcde2db867b0f',
    'nid_create_time': '1754089134200',
    'gvi': 'ipOZoFN7KPqbDqt6RfknYcbcb',
    'gvi_create_time': '1754089134200',
    'rskey': 'TCgQ4ZTBQTUltcnNWTEUyU1FQbFR6S29PQT09PTnz9',
    'st_asi': 'delete',
    'st_pvi': '59192766921846',
    'st_sp': '2025-07-13%2011%3A14%3A04',
    'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
    'st_sn': '132',
    'st_psi': '20250802234635508-113200301831-9379920167',
}

headers = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
    'Connection': 'keep-alive',
    'Referer': 'https://quote.eastmoney.com/sz000050.html',
    'Sec-Fetch-Dest': 'script',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    # 'Cookie': 'qgqp_b_id=125fef21bf721e77a102bb668642803e; st_si=53976007936223; fullscreengg=1; fullscreengg2=1; st_nvi=whttZFKXNnA_km71gtVGJfd20; nid=007529139545699f3d5bcde2db867b0f; nid_create_time=1754089134200; gvi=ipOZoFN7KPqbDqt6RfknYcbcb; gvi_create_time=1754089134200; rskey=TCgQ4ZTBQTUltcnNWTEUyU1FQbFR6S29PQT09PTnz9; st_asi=delete; st_pvi=59192766921846; st_sp=2025-07-13%2011%3A14%3A04; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=132; st_psi=20250802234635508-113200301831-9379920167',
}

# 异动类型映射（对照 index.js 中的 pkyd_types）
PKYD_TYPE_MAPPING = {
    '1': '有大买盘',
    '101': '有大卖盘',
    '2': '大笔买入',
    '102': '大笔卖出',
    '201': '封涨停板',
    '301': '封跌停板',
    '202': '打开涨停',
    '302': '打开跌停',
    '203': '高开5日线',
    '303': '低开5日线',
    '204': '60日新高',
    '304': '60日新低',
    '401': '向上缺口',
    '501': '向下缺口',
    '402': '火箭发射',
    '502': '高台跳水',
    '403': '快速反弹',
    '503': '快速下跌',
    '404': '竞价上涨',
    '504': '竞价下跌',
    '405': '60日大幅上涨',
    '505': '60日大幅下跌'
}

def fetch_pkyd(timefrom=None, timeto=None, limit=2000):
    """
    获取盘口异动数据（原始 API 调用）
    
    Args:
        timefrom: 开始时间，格式为 'YYYY-MM-DD HH:MM:SS' 或 datetime 对象
                 如果为None，默认为当天开始时间
        timeto: 结束时间，格式为 'YYYY-MM-DD HH:MM:SS' 或 datetime 对象
               如果为None，默认为当前时间
        limit: 返回数据的最大条数，默认2000条
    
    Returns:
        dict: 包含盘口异动数据的字典，键为列名，值为数据列表
              列名包括：时间、股票代码、股票名称、异动类型、异动描述、价格、涨跌幅
    """
    # 处理时间参数
    if timefrom is None:
        timefrom = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif isinstance(timefrom, str):
        timefrom = datetime.strptime(timefrom, '%Y-%m-%d %H:%M:%S')
    
    if timeto is None:
        timeto = datetime.now()
    elif isinstance(timeto, str):
        timeto = datetime.strptime(timeto, '%Y-%m-%d %H:%M:%S')
    
    # 转换为时间戳（毫秒）
    timefrom_ts = int(timefrom.timestamp() * 1000)
    timeto_ts = int(timeto.timestamp() * 1000)
    
    # print(timefrom)
    # print(timeto)
    # print(timefrom_ts)
    # print(timeto_ts)
    # input('?')
    # 构建请求参数
    params = {
        'cb': f'jQuery{int(datetime.now().timestamp() * 1000)}_{int(datetime.now().timestamp() * 1000)}',
        'fields': 'f1,f2,f3,f4,f5,f6,f7',
        'lmt': str(limit),  # 动态设置返回数量
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'wbp2u': '|0|0|0|web',
        'timefrom': str(timefrom_ts),
        'timeto': str(timeto_ts),
        '_': str(int(datetime.now().timestamp() * 1000)),
    }
    # input(params)


    try:
        response = requests.get('https://push2.eastmoney.com/api/qt/pkyd/get', 
                              params=params, cookies=cookies, headers=headers)
        response.raise_for_status()
        
        # 解析JSONP响应
        text = response.text
        
        # 移除JSONP包装
        json_str = text[text.find('(') + 1:text.rfind(')')]
        data = json.loads(json_str)
        
        if 'data' not in data or 'pkyd' not in data['data']:
            return {'error': '数据格式错误'}
        
        # 处理数据
        pkyd_data = data['data']['pkyd']
        result = {
            '时间': [],
            '股票代码': [],
            '股票名称': [],
            '异动类型': [],
            '异动描述': [],
            '价格': [],
            '涨跌幅': []
        }
        
        for item in pkyd_data:
            # 解析逗号分隔的字符串
            # 格式: "时间,股票代码,市场类型,股票名称,异动类型,异动描述,涨跌方向"
            fields = item.split(',')
            if len(fields) >= 7:
                time_str = fields[0]  # 时间格式: HH:MM:SS
                stock_code = fields[1]  # 股票代码
                market_type = fields[2]  # 市场类型 (0=深市, 1=沪市)
                stock_name = fields[3]  # 股票名称
                pkyd_type = fields[4]  # 异动类型
                pkyd_desc = fields[5]  # 异动描述
                direction = fields[6]  # 涨跌方向 (1=上涨, 2=下跌)
                
                # 添加市场标识
                market_suffix = 'SZ' if market_type == '0' else 'SH'
                full_stock_code = f"{stock_code}.{market_suffix}"
                
                # 映射异动类型为可读描述
                pkyd_type_desc = PKYD_TYPE_MAPPING.get(pkyd_type, pkyd_type)
                
                result['时间'].append(time_str)
                result['股票代码'].append(full_stock_code)
                result['股票名称'].append(stock_name)
                result['异动类型'].append(pkyd_type_desc)
                result['异动描述'].append(pkyd_desc)
                result['价格'].append("—")  # 价格信息在异动描述中
                result['涨跌幅'].append("上涨" if direction == '1' else "下跌" if direction == '2' else "—")
            else:
                # 如果字段不足，跳过这条记录
                continue
        
        return result
        
    except requests.RequestException as e:
        return {'error': f'网络请求错误: {str(e)}'}
    except json.JSONDecodeError as e:
        return {'error': f'JSON解析错误: {str(e)}'}
    except Exception as e:
        return {'error': f'未知错误: {str(e)}'}

# 测试代码
if __name__ == "__main__":
    # 获取今天的盘口异动数据
    result = fetch_pkyd()
    print("获取的盘口异动数据:")
    for key, values in result.items():
        print(f"{key}: {values}")
    
    # 获取指定时间范围的盘口异动数据
    timefrom = '2025-08-04 09:30:00'
    timeto = '2025-08-04 15:00:00'
    custom_result = fetch_pkyd(timefrom, timeto, limit=200)
    print(f"\n获取的指定时间范围({timefrom} 到 {timeto})的盘口异动数据:")
    print(f"数据条数: {len(custom_result['时间']) if '时间' in custom_result else 0}")
    for key, values in custom_result.items():
        print(f"{key}: {values[:5]}...")  # 只显示前5条
    
    # 创建表格格式输出
    print("\n表格格式输出:")
    if 'error' not in custom_result:
        df = pd.DataFrame(custom_result)
        print(df.to_string(index=False))
    
    input()
    # 使用示例
    print("\n使用示例:")
    print("# 获取今天的盘口异动数据")
    print("result = get_pkyd()")
    print()
    print("# 获取指定时间范围的盘口异动数据")
    print("result = get_pkyd('2025-01-01 09:30:00', '2025-01-01 15:00:00', limit=500)")
    print()
    print("# 获取更多数据")
    print("result = get_pkyd('2025-08-01 09:30:00', '2025-08-01 15:00:00', limit=2000)")
    print()
    print("# 转换为DataFrame")
    print("df = pd.DataFrame(result)")
    print("print(df)")


def get_pkyd_by_day(date_str=None, limit=15000, save_dir='.'):
    """
    获取指定日期的盘口异动数据并保存为CSV文件
    
    Args:
        date_str: 日期字符串，格式为 'YYYY-MM-DD'，如果为None则使用今天
        limit: 返回数据的最大条数，默认5000条
        save_dir: 保存目录，默认为当前目录
    
    Returns:
        str: 保存的文件路径，如果失败则返回None
    """
    # 处理日期参数
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    # 解析日期
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"错误: 日期格式不正确，应为 'YYYY-MM-DD'，例如 '2025-08-02'")
        return None
    
    # 设置时间范围（交易时间）
    timefrom = target_date.replace(hour=9, minute=30, second=0, microsecond=0)
    timeto = target_date.replace(hour=15, minute=0, second=0, microsecond=0)
    
    print(f"获取 {date_str} 的盘口异动数据...")
    print(f"时间范围: {timefrom.strftime('%Y-%m-%d %H:%M:%S')} 到 {timeto.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取数据
    result = fetch_pkyd(timefrom, timeto, limit)
    
    if 'error' in result:
        print(f"获取数据失败: {result['error']}")
        return None
    
    if not result['时间']:
        print(f"未找到 {date_str} 的盘口异动数据")
        return None
    
    # 创建DataFrame
    df = pd.DataFrame(result)
    
    # 生成文件名：pkyd_YYMMDDHHMM.csv
    timestamp = datetime.now().strftime('%y%m%d')
    filename = f"pkyd_{timestamp}.csv"
    
    # 确保保存目录存在
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # 构建完整文件路径
    filepath = os.path.join(save_dir, filename)
    
    # 保存为CSV文件
    try:
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"成功保存 {len(df)} 条数据到: {filepath}")
        
        # 显示数据统计
        print(f"\n数据统计:")
        print(f"总条数: {len(df)}")
        print(f"时间范围: {df['时间'].min()} 到 {df['时间'].max()}")
        
        # 按异动类型统计
        print(f"\n异动类型统计:")
        type_counts = df['异动类型'].value_counts()
        print(type_counts.head(10))  # 显示前10个类型
        
        # 按涨跌幅统计
        print(f"\n涨跌幅统计:")
        direction_counts = df['涨跌幅'].value_counts()
        print(direction_counts)
        
        return filepath
        
    except Exception as e:
        print(f"保存文件失败: {str(e)}")
        return None


def _pkyd_em_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'generated', 'em'))


def pkyd_save_dir(date_str: str = None) -> str:
    """generated/em/{yymmdd}/ for pkyd CSV output."""
    if date_str:
        target = datetime.strptime(date_str, '%Y-%m-%d')
        dte_short = target.strftime('%y%m%d')
    else:
        dte_short = datetime.now().strftime('%y%m%d')
    path = os.path.join(_pkyd_em_root(), dte_short)
    os.makedirs(path, exist_ok=True)
    return path


def find_latest_pkyd_file():
    """查找最新的 pkyd_*.csv 文件。"""
    import glob

    files = glob.glob(os.path.join(_pkyd_em_root(), '*/pkyd_*.csv'))
    files.extend(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pkyd_*.csv')))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def get_pkyd(force_refetch: bool = False, date_str: str = None, limit: int = 25000):
    """
    获取盘口异动数据（缓存策略同 get_stockcomment）。

    - 东财异动数据每日约 17:00 更新一批
    - 本地文件不早于「当前应持有的最新 17:00 批次」则复用
    - 非交易日不主动拉取，复用最近批次
    - force_refetch=True 时强制重新获取
    """
    if not force_refetch:
        latest = find_latest_pkyd_file()
        if latest:
            try:
                from stock.module_cache_policy import (
                    is_pkyd_cache_fresh,
                    is_trading_calendar_day,
                    pkyd_cache_policy_summary,
                )
            except ImportError:
                from module_cache_policy import (
                    is_pkyd_cache_fresh,
                    is_trading_calendar_day,
                    pkyd_cache_policy_summary,
                )

            file_mtime = datetime.fromtimestamp(os.path.getmtime(latest))
            now = datetime.now()
            if is_pkyd_cache_fresh(file_mtime, now):
                print(f"📋 pkyd 缓存有效 ({pkyd_cache_policy_summary()}):")
                print(f"  📊 pkyd: {latest}")
                return {
                    'pkyd_file': latest,
                    'cached': True,
                    'reason': f'缓存有效 · {pkyd_cache_policy_summary()}',
                }
            if not is_trading_calendar_day(now):
                print("⏰ 非交易日，复用最近 pkyd 批次:")
                print(f"  📊 pkyd: {latest}")
                return {
                    'pkyd_file': latest,
                    'cached': True,
                    'stale': True,
                    'reason': '非交易日复用最近批次',
                }
            print("🔄 pkyd 缓存已过期（已过当日 17:00 批次），重新获取…")
        else:
            print("⚠️  未找到 pkyd 缓存文件，将获取新数据")

    today_str = date_str or datetime.now().strftime('%Y-%m-%d')
    save_dir = pkyd_save_dir(today_str)
    filepath = get_pkyd_by_day(date_str=today_str, limit=limit, save_dir=save_dir)
    if not filepath:
        latest = find_latest_pkyd_file()
        if latest:
            return {
                'pkyd_file': latest,
                'cached': True,
                'stale': True,
                'reason': '拉取失败，回退最近缓存',
            }
        return {
            'pkyd_file': None,
            'cached': False,
            'reason': '拉取失败且无缓存',
        }
    return {
        'pkyd_file': filepath,
        'cached': False,
        'reason': '已重新拉取',
    }


if __name__ == "__main__":
    get_pkyd_by_day(save_dir='../generated/em/')