#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时资金流向数据获取和可视化工具
基于东方财富API获取股票实时资金流向数据并绘制图表
"""

import requests
import pandas as pd

pd.set_option('display.unicode.east_asian_width', True)

import matplotlib
# 设置matplotlib后端为非交互式，避免GUI相关问题
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import json
import re
import os
import glob
import stock_dotenv_load  # noqa: F401 — load stock/.env before CACHE_DIR
import time
import numpy as np
import pickle
from matplotlib.patches import Wedge
import matplotlib.patches as mpatches
import configparser

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['figure.autolayout'] = True

# 数据缓存目录：默认在项目下 generated/cache；可用环境变量 STOCK_CACHE_DIR 指向外置盘等路径
_STOCK_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.environ.get(
    'STOCK_CACHE_DIR',
    os.path.join(_STOCK_DIR, 'generated', 'cache'),
)
os.makedirs(CACHE_DIR, exist_ok=True)


def _requests_session_no_proxy() -> requests.Session:
    """Ignore system HTTP proxy (broken local proxies break East Money APIs)."""
    session = requests.Session()
    session.trust_env = False
    return session

def is_trading_time():
    """检查当前是否为交易时间"""
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # 非工作日（周六、周日）
    if weekday >= 5:
        return False
    
    # 工作日检查时间
    current_time = now.time()
    morning_start = datetime.strptime('09:30', '%H:%M').time()
    morning_end = datetime.strptime('11:30', '%H:%M').time()
    afternoon_start = datetime.strptime('13:00', '%H:%M').time()
    afternoon_end = datetime.strptime('15:00', '%H:%M').time()
    
    return (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end)

def get_cache_expiry_seconds(cache_type='realtime'):
    """根据缓存类型和当前时间获取合适的过期时间（秒）"""
    is_trading = is_trading_time()
    
    if cache_type == 'realtime':
        # 实时数据：交易时间5分钟，非交易时间2小时
        return 300 if is_trading else 7200
    elif cache_type in ['hist', 'price']:
        # 历史和价格数据：交易时段 5 分钟，非连续竞价时段/非交易日 24 小时
        return 300 if is_trading else 86400
    else:
        # 默认1小时
        return 3600

def log_cache_usage(cache_type, stock_code, action='hit'):
    """记录缓存使用情况"""
    if not _cache_logging_enabled:
        return
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    trading_status = "交易时间" if is_trading_time() else "非交易时间"
    print(f"📊 缓存{action.upper()}: {cache_type}_{stock_code} ({trading_status}) - {timestamp}")

def enable_cache_logging():
    """启用缓存日志记录"""
    global _cache_logging_enabled
    _cache_logging_enabled = True
    print("✅ 缓存日志记录已启用")

def disable_cache_logging():
    """禁用缓存日志记录"""
    global _cache_logging_enabled
    _cache_logging_enabled = False
    print("❌ 缓存日志记录已禁用")

# 全局变量控制缓存日志
_cache_logging_enabled = False

def get_realtime_cache_path(stock_code):
    """获取实时资金流向缓存文件路径"""
    return os.path.join(CACHE_DIR, f'realtime_flow_{stock_code}.csv')

def load_realtime_cached_data(stock_code, allow_stale=False):
    """加载实时资金流向缓存数据"""
    cache_path = get_realtime_cache_path(stock_code)
    meta_path = cache_path.replace('.csv', '_meta.json')
    
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path)
            df['时间'] = pd.to_datetime(df['时间'])
            meta_data = {'timestamp': os.path.getmtime(cache_path)}
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta_data = json.load(f)
            expiry_seconds = get_cache_expiry_seconds('realtime')
            age = time.time() - meta_data['timestamp']
            if age < expiry_seconds:
                log_cache_usage('realtime', stock_code, 'hit')
                return df
            if allow_stale:
                print(f"使用过期实时资金缓存: {cache_path} ({age/3600:.1f}h)")
                return df
        except Exception as e:
            print(f"加载实时缓存数据失败: {e}")
    return None

def save_realtime_cached_data(stock_code, data):
    """保存实时资金流向数据到缓存"""
    cache_path = get_realtime_cache_path(stock_code)
    meta_path = cache_path.replace('.csv', '_meta.json')
    
    try:
        # 保存数据到CSV
        data.to_csv(cache_path, index=False, encoding='utf-8')
        
        # 保存元数据到JSON
        meta_data = {
            'stock_code': stock_code,
            'timestamp': time.time()
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        
        log_cache_usage('realtime', stock_code, 'save')
    except Exception as e:
        print(f"保存实时缓存数据失败: {e}")

# 保留旧的PKL缓存函数以兼容性
def get_cache_path(stock_code):
    """获取缓存文件路径（PKL格式，已废弃）"""
    return os.path.join(CACHE_DIR, f'flow_{stock_code}.pkl')

def load_cached_data(stock_code):
    """加载缓存的数据（PKL格式，已废弃）"""
    cache_path = get_cache_path(stock_code)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                cached_data = pickle.load(f)
            # 检查缓存是否过期（超过5分钟）
            if time.time() - cached_data['timestamp'] < 300:
                return cached_data['data']
        except Exception as e:
            print(f"加载缓存数据失败: {e}")
    return None

def save_cached_data(stock_code, data):
    """保存数据到缓存（PKL格式，已废弃）"""
    cache_path = get_cache_path(stock_code)
    try:
        cached_data = {
            'data': data,
            'timestamp': time.time()
        }
        with open(cache_path, 'wb') as f:
            pickle.dump(cached_data, f)
    except Exception as e:
        print(f"保存缓存数据失败: {e}")

def get_realtime_flow(stock_code, use_cache=True):
    """
    获取股票实时资金流向数据
    
    参数:
    stock_code: 股票代码，如 '002456'
    use_cache: 是否使用缓存数据
    
    返回:
    DataFrame: 包含实时资金流向数据的DataFrame
    """
    
    # 尝试从缓存加载数据
    if use_cache:
        cached_data = load_realtime_cached_data(stock_code)
        if cached_data is not None:
            return cached_data
    
    # 确定市场代码
    if stock_code.startswith('0') or stock_code.startswith('3'):
        market = 0  # 深圳
        secid = f"0.{stock_code}"
    elif stock_code.startswith('6'):
        market = 1  # 上海
        secid = f"1.{stock_code}"
    else:
        raise ValueError(f"不支持的股票代码格式: {stock_code}")
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/zjlx/',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    # 构建请求参数
    timestamp = int(time.time() * 1000)
    callback = f'jQuery{timestamp}_{timestamp + 1}'
    
    params = {
        'cb': callback,
        'lmt': '0',
        'klt': '1',  # 分钟级数据
        'fields1': 'f1,f2,f3,f7',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65',
        'ut': 'b2884a393a59ad64002292a3e90d46a5',
        'secid': secid,
        '_': timestamp + 2,
    }

    try:
        print(f"正在获取实时数据: {stock_code}")
        response = _requests_session_no_proxy().get(
            'https://push2delay.eastmoney.com/api/qt/stock/fflow/kline/get',
            params=params, headers=headers, timeout=15,
        )
        response.raise_for_status()
        
        # 解析JSONP响应
        json_str = re.search(r'jQuery\d+_\d+\((.*)\)', response.text)
        if not json_str:
            raise ValueError("无法解析API响应")
        
        data = json.loads(json_str.group(1))
        
        if data['rc'] != 0:
            raise ValueError(f"API返回错误: {data.get('rt', '未知错误')}")
        
        # 提取K线数据
        klines = data['data']['klines']
        stock_name = data['data']['name']
        
        # 定义列名
        columns = [
            '时间', '主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入'
        ]
        
        # 解析每行数据
        rows = []
        for kline in klines:
            values = kline.split(',')
            
            if len(values) >= 5:
                try:
                    row = {
                        '时间': pd.to_datetime(values[0]),
                        '主力净流入': float(values[1]) / 1E8,  # 转换为亿元
                        '超大单净流入': float(values[5]) / 1E8,
                        '大单净流入': float(values[4]) / 1E8,
                        '中单净流入': float(values[3]) / 1E8,
                        '小单净流入': float(values[2]) / 1E8
                    }
                    rows.append(row)
                except (ValueError, IndexError) as e:
                    print(f"解析数据行时出错: {e}, 数据: {kline}")
                    continue
        
        df = pd.DataFrame(rows)
        df['股票名称'] = stock_name
        
        # 保存到缓存
        save_realtime_cached_data(stock_code, df)
        
        return df
        
    except Exception as e:
        print(f"获取实时资金流向数据失败: {e}")
        return load_realtime_cached_data(stock_code, allow_stale=True)


def _flow_distribution_cache_path(stock_code: str) -> str:
    return os.path.join(CACHE_DIR, f'flow_distribution_{stock_code}.json')


def get_flow_distribution(stock_code, use_cache=True):
    """当日累计成交分布：超大/大/中/小单流入流出（单位：元）。"""
    code = str(stock_code).zfill(6)
    cache_path = _flow_distribution_cache_path(code)

    if use_cache and os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            age = time.time() - cached.get('timestamp', 0)
            if age < get_cache_expiry_seconds('realtime'):
                return cached.get('data')
        except Exception as e:
            print(f"加载成交分布缓存失败: {e}")

    if code.startswith('0') or code.startswith('3'):
        secid = f'0.{code}'
    elif code.startswith('6'):
        secid = f'1.{code}'
    else:
        raise ValueError(f'不支持的股票代码格式: {code}')

    timestamp = int(time.time() * 1000)
    callback = f'jQuery{timestamp}_{timestamp + 1}'
    params = {
        'invt': '2',
        'fltt': '1',
        'cb': callback,
        'fields': 'f138,f139,f141,f142,f144,f145,f147,f148',
        'secid': secid,
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'wbp2u': '|0|0|0|web',
        'dect': '1',
        '_': timestamp + 2,
    }

    try:
        response = _requests_session_no_proxy().get(
            'https://push2.eastmoney.com/api/qt/stock/get',
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        json_str = re.search(r'jQuery\d+_\d+\((.*)\)', response.text)
        if not json_str:
            raise ValueError('无法解析成交分布 API 响应')

        payload = json.loads(json_str.group(1))
        if payload.get('rc') != 0 or not payload.get('data'):
            raise ValueError(payload.get('rt', '成交分布 API 返回错误'))

        raw = payload['data']

        def _val(key):
            return float(raw.get(key) or 0)

        result = {
            'super_in': _val('f138'),
            'super_out': _val('f139'),
            'big_in': _val('f141'),
            'big_out': _val('f142'),
            'mid_in': _val('f144'),
            'mid_out': _val('f145'),
            'small_in': _val('f147'),
            'small_out': _val('f148'),
            'updated_at': datetime.now().strftime('%H:%M'),
        }

        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({'timestamp': time.time(), 'data': result}, f, ensure_ascii=False)
        except Exception as e:
            print(f"保存成交分布缓存失败: {e}")

        return result
    except Exception as e:
        print(f"获取成交分布失败: {e}")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('data')
            except Exception:
                pass
        return None


def plot_realtime_flow(stock_code, save_path=None):
    """
    绘制实时资金流向图
    
    参数:
    stock_code: 股票代码
    save_path: 保存路径，如果为None则不保存
    """
    
    # 获取数据
    df = get_realtime_flow(stock_code)
    if df is None or df.empty:
        print("无法获取数据")
        return None
    
    # 创建图表
    df2 = df.reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(14, 10))
    
    # 设置图表样式
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    
    # 绘制各条线
    colors = {
        '主力净流入': '#FF6B6B',      # 粉红色
        '超大单净流入': '#8B0000',    # 深红色
        '大单净流入': '#DC143C',      # 红色
        '中单净流入': '#FF8C00',      # 橙色
        '小单净流入': '#87CEEB'       # 浅蓝色
    }
    
    line_styles = {
        '主力净流入': '-',
        '超大单净流入': '-',
        '大单净流入': '-',
        '中单净流入': '-',
        '小单净流入': '-'
    }
    
    for col in ['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']:
        linewidth = 3.5 if col == '主力净流入' else 0.9
        ax.plot(df2.index, df2[col], 
               color=colors[col], 
               linewidth=linewidth,
               linestyle=line_styles[col],
               label=col)
    
    # 设置网格
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # 设置坐标轴
    ax.set_xlabel('时间', fontsize=12, fontweight='bold')
    ax.set_ylabel('资金流向 (亿元)', fontsize=12, fontweight='bold')
    
    # 设置标题
    stock_name = df['股票名称'].iloc[0] if '股票名称' in df.columns else stock_code
    current_time = datetime.now().strftime('%H:%M')
    current_date = datetime.now().strftime('%Y-%m-%d')
    ax.set_title(f'{stock_name}({stock_code}) 实时资金流向({current_date}) - 更新时间: {current_time}', 
                fontsize=14, fontweight='bold', pad=20)
    
    # 设置x轴格式 - 使用索引作为x轴标签
    ax.set_xlabel('数据点索引', fontsize=12, fontweight='bold')
    
    # 设置x轴刻度标签格式为 {:03d}
    step = max(1, len(df2) // 10)  # 显示大约10个刻度
    tick_positions = range(0, len(df2), step)
    # 将tick_labels改为df2['时间']对应的hh:mm格式
    tick_labels = []
    for i in tick_positions:
        if i < len(df2):
            t = df2['时间'].iloc[i]
            # 如果是datetime类型，直接格式化，否则尝试解析
            if isinstance(t, (datetime, pd.Timestamp)):
                tick_labels.append(t.strftime('%H:%M'))
            else:
                try:
                    tick_labels.append(pd.to_datetime(t).strftime('%H:%M'))
                except Exception:
                    tick_labels.append(str(t))
        else:
            tick_labels.append(f'{i:03d}')
    # tick_labels = [f'{i:03d}' for i in tick_positions]

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    
    # 旋转x轴标签
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # 设置y轴范围
    y_min = min(df2[['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']].min())
    y_max = max(df2[['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']].max())
    y_range = y_max - y_min
    ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.1)
    
    # 添加零线
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
    
    # 设置图例
    legend = ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    legend.get_frame().set_facecolor('white')
    legend.get_frame().set_edgecolor('gray')
    legend.get_frame().set_alpha(0.9)
    
    # 添加数据统计信息
    latest_data = df2.iloc[-1]
    stats_text = f"""今日累计净流入:
主力: {latest_data['主力净流入']:.2f}亿
超大单: {latest_data['超大单净流入']:.2f}亿
大单: {latest_data['大单净流入']:.2f}亿
中单: {latest_data['中单净流入']:.2f}亿
小单: {latest_data['小单净流入']:.2f}亿"""
    
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
           fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # 添加东方财富水印
    ax.text(0.5, 0.5, '东方财富', transform=ax.transAxes, 
           fontsize=60, alpha=0.1, ha='center', va='center',
           color='gray', rotation=30)
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f"图表已保存到: {save_path}")
    
    return fig, ax

def plot_flowx(stock_code, save_path=None):
    """
    python stock/utils_cap.py --comprehensive --stock-code 002916  
    绘制综合资金流向图表（包含文本信息和饼图）
    
    参数:
    stock_code: 股票代码
    save_path: 保存路径，如果为None则不保存
    """
    
    # 获取数据
    df = get_realtime_flow(stock_code)
    if df is None or df.empty:
        print("无法获取数据")
        return None
    
    # 创建df2用于绘图
    df2 = df.reset_index(drop=True)
    
    # 创建子图布局
    fig = plt.figure(figsize=(20, 12))
    
    # 左侧：实时资金流向图
    ax1 = plt.subplot(2, 2, (1, 3))
    
    # 右侧：成交分布饼图
    ax2 = plt.subplot(2, 2, 2)
    
    # 右下：数据汇总表
    ax3 = plt.subplot(2, 2, 4)
    ax3.axis('off')
    
    # 设置整体样式
    fig.patch.set_facecolor('white')
    ax1.set_facecolor('white')
    ax2.set_facecolor('white')
    
    # 绘制资金流向线图
    colors = {
        '主力净流入': '#FF6B6B',      # 粉红色
        '超大单净流入': '#8B0000',    # 深红色
        '大单净流入': '#DC143C',      # 红色
        '中单净流入': '#FF8C00',      # 橙色
        '小单净流入': '#87CEEB'       # 浅蓝色
    }
    
    for col in ['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']:
        linewidth = 3.5 if col == '主力净流入' else 0.9
        ax1.plot(df2.index, df2[col], 
                color=colors[col], 
                linewidth=linewidth,
                label=col)
    
    # 设置线图样式
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.set_axisbelow(True)
    ax1.set_xlabel('数据点索引', fontsize=12, fontweight='bold')
    ax1.set_ylabel('资金流向 (亿元)', fontsize=12, fontweight='bold')
    
    # 设置标题
    stock_name = df['股票名称'].iloc[0] if '股票名称' in df.columns else stock_code
    current_time = datetime.now().strftime('%H:%M')
    current_date = datetime.now().strftime('%Y-%m-%d')
    ax1.set_title(f'{stock_name}({stock_code}) 实时资金流向({current_date}) - 更新时间: {current_time}', 
                 fontsize=14, fontweight='bold', pad=20)
    
    # 设置x轴格式 - 使用索引作为x轴标签
    step = max(1, len(df2) // 10)  # 显示大约10个刻度
    tick_positions = range(0, len(df2), step)
    # 将tick_labels改为df2['时间']对应的hh:mm格式
    tick_labels = []
    for i in tick_positions:
        if i < len(df2):
            t = df2['时间'].iloc[i]
            # 如果是datetime类型，直接格式化，否则尝试解析
            if isinstance(t, (datetime, pd.Timestamp)):
                tick_labels.append(t.strftime('%H:%M'))
            else:
                try:
                    tick_labels.append(pd.to_datetime(t).strftime('%H:%M'))
                except Exception:
                    tick_labels.append(str(t))
        else:
            tick_labels.append(f'{i:03d}')
    ax1.set_xticks(tick_positions)
    ax1.set_xticklabels(tick_labels)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # 添加零线
    ax1.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
    
    # 设置图例
    legend1 = ax1.legend(loc='upper left', fontsize=10, framealpha=0.9)
    legend1.get_frame().set_facecolor('white')
    legend1.get_frame().set_edgecolor('gray')
    
    # 计算成交分布数据（模拟数据，实际应该从API获取）
    latest_data = df2.iloc[-1]
    
    # 计算流入流出数据（基于净流入数据估算）
    inflow_data = {
        '超大单流入': max(0, latest_data['超大单净流入']) + 20,  # 假设总流入
        '大单流入': max(0, latest_data['大单净流入']) + 15,
        '中单流入': max(0, latest_data['中单净流入']) + 25,
        '小单流入': max(0, latest_data['小单净流入']) + 20
    }
    
    outflow_data = {
        '超大单流出': max(0, -latest_data['超大单净流入']) + 15,
        '大单流出': max(0, -latest_data['大单净流入']) + 20,
        '中单流出': max(0, -latest_data['中单净流入']) + 30,
        '小单流出': max(0, -latest_data['小单净流入']) + 25
    }
    
    # 创建对应的键值映射
    key_mapping = {
        '超大单流入': '超大单流出',
        '大单流入': '大单流出',
        '中单流入': '中单流出',
        '小单流入': '小单流出'
    }
    
    # 绘制饼图
    pie_colors = ['#8B0000', '#DC143C', '#FF8C00', '#87CEEB',  # 流入颜色
                  '#006400', '#32CD32', '#90EE90', '#98FB98']  # 流出颜色
    
    pie_labels = list(inflow_data.keys()) + list(outflow_data.keys())
    pie_sizes = list(inflow_data.values()) + list(outflow_data.values())
    
    wedges, texts, autotexts = ax2.pie(pie_sizes, labels=pie_labels, colors=pie_colors,
                                      autopct='%1.1f%%', startangle=90)
    
    ax2.set_title('实时成交分布图', fontsize=14, fontweight='bold', pad=20)
    
    # 创建数据汇总表
    table_data = []
    table_data.append(['类型', '流入(亿元)', '流出(亿元)', '净流入(亿元)', '净占比(%)'])
    
    # 计算净占比（假设总成交额为100亿）
    total_volume = 100
    
    for key in inflow_data.keys():
        inflow = inflow_data[key]
        outflow_key = key_mapping[key]
        outflow = outflow_data[outflow_key]
        net_inflow = inflow - outflow
        net_ratio = (net_inflow / total_volume) * 100
        
        table_data.append([
            key.replace('流入', ''),
            f'{inflow:.2f}',
            f'{outflow:.2f}',
            f'{net_inflow:.2f}',
            f'{net_ratio:.2f}%'
        ])
    
    # 添加净流入汇总
    total_net_inflow = latest_data['主力净流入']
    total_net_ratio = (total_net_inflow / total_volume) * 100
    
    table_data.append([
        '主力',
        f'{latest_data["主力净流入"]:.2f}',
        '0.00',
        f'{latest_data["主力净流入"]:.2f}',
        f'{total_net_ratio:.2f}%'
    ])
    
    # 绘制表格
    table = ax3.table(cellText=table_data[1:], colLabels=table_data[0],
                     cellLoc='center', loc='center',
                     colWidths=[0.2, 0.2, 0.2, 0.2, 0.2])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # 设置表格样式
    for i in range(len(table_data)):
        for j in range(len(table_data[0])):
            cell = table[(i, j)]
            if i == 0:  # 标题行
                cell.set_facecolor('#4CAF50')
                cell.set_text_props(weight='bold', color='white')
            else:
                cell.set_facecolor('#F5F5F5' if i % 2 == 0 else 'white')
    
    ax3.set_title('资金流向汇总表', fontsize=14, fontweight='bold', pad=20)
    
    # 添加东方财富水印
    ax1.text(0.5, 0.5, '东方财富', transform=ax1.transAxes, 
            fontsize=60, alpha=0.1, ha='center', va='center',
            color='gray', rotation=30)
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        print(f"综合图表已保存到: {save_path}")
    
    return fig, (ax1, ax2, ax3)

def get_flow_summary(stock_code):
    """
    获取资金流向汇总信息
    
    参数:
    stock_code: 股票代码
    
    返回:
    dict: 包含汇总信息的字典
    """
    df = get_realtime_flow(stock_code)
    if df is None or df.empty:
        return None
    
    latest = df.iloc[-1]
    stock_name = df['股票_name'].iloc[0] if '股票_name' in df.columns else stock_code
    
    # 计算净占比（假设总成交额为100亿，实际应该从API获取）
    total_volume = 100  # 这里应该从实际数据计算
    
    summary = {
        '股票代码': stock_code,
        '股票名称': stock_name,
        '更新时间': latest['时间'].strftime('%Y-%m-%d %H:%M:%S'),
        '主力净流入': latest['主力净流入'],
        '主力净占比': (latest['主力净流入'] / total_volume) * 100,
        '超大单净流入': latest['超大单净流入'],
        '超大单净占比': (latest['超大单净流入'] / total_volume) * 100,
        '大单净流入': latest['大单净流入'],
        '大单净占比': (latest['大单净流入'] / total_volume) * 100,
        '中单净流入': latest['中单净流入'],
        '中单净占比': (latest['中单净流入'] / total_volume) * 100,
        '小单净流入': latest['小单净流入'],
        '小单净占比': (latest['小单净流入'] / total_volume) * 100,
    }
    
    return summary

def demo_realtime_flow():
    """演示实时资金流向功能"""
    print("=" * 60)
    print("实时资金流向数据获取和可视化演示")
    print("=" * 60)
    
    # 测试股票代码
    test_stocks = ['002456', '000001', '600000']
    
    for stock_code in test_stocks:
        print(f"\n正在获取股票 {stock_code} 的实时资金流向数据...")
        
        try:
            # 获取数据
            df = get_realtime_flow(stock_code)
            if df is not None and not df.empty:
                print(f"✅ 成功获取 {len(df)} 条数据")
                
                # 显示最新数据
                latest = df.iloc[-1]
                print(f"📊 最新数据 ({latest['时间'].strftime('%H:%M')}):")
                print(f"   主力净流入: {latest['主力净流入']:.2f} 亿元")
                print(f"   超大单净流入: {latest['超大单净流入']:.2f} 亿元")
                print(f"   大单净流入: {latest['大单净流入']:.2f} 亿元")
                print(f"   中单净流入: {latest['中单净流入']:.2f} 亿元")
                print(f"   小单净流入: {latest['小单净流入']:.2f} 亿元")
                
                # 绘制基础图表
                save_path = f'/Volumes/ASME/stock/em/backtest/stockd/charts/realtime_flow_{stock_code}_{datetime.now().strftime("%y%m%d")}.png'
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                fig, ax = plot_realtime_flow(stock_code, save_path)
                if fig:
                    plt.close(fig)  # 关闭图表以释放内存
                    print(f"📈 基础图表已保存到: {save_path}")
                
                # 绘制综合图表
                flowx_path = f'/Volumes/ASME/stock/em/backtest/stockd/charts//flowx_{stock_code}_{datetime.now().strftime("%y%m%d")}.png'
                fig2, axes = plot_flowx(stock_code, flowx_path)
                if fig2:
                    plt.close(fig2)  # 关闭图表以释放内存
                    print(f"📊 综合图表已保存到: {flowx_path}")
                
            else:
                print(f"❌ 获取数据失败")
                
        except Exception as e:
            print(f"❌ 处理股票 {stock_code} 时出错: {e}")
            continue

def get_hist_cache_path(stock_code):
    """获取历史资金流向缓存文件路径（有效交易日）。"""
    from quote_cache import effective_quote_date_short
    dte = effective_quote_date_short()
    return os.path.join(CACHE_DIR, f'hist_flow_{stock_code}_{dte}.csv')


def find_latest_hist_cache_path(stock_code):
    """查找该股票有效交易日的历史资金流向缓存文件。"""
    from quote_cache import effective_quote_date_short
    eff = effective_quote_date_short()
    exact = os.path.join(CACHE_DIR, f'hist_flow_{stock_code}_{eff}.csv')
    if os.path.isfile(exact):
        return exact
    pattern = os.path.join(CACHE_DIR, f'hist_flow_{stock_code}_*.csv')
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_hist_cached_data(stock_code, allow_stale=False):
    """加载历史资金流向缓存数据"""
    cache_path = find_latest_hist_cache_path(stock_code)
    if not cache_path:
        return None
    try:
        df = pd.read_csv(cache_path)
        meta_path = cache_path.replace('.csv', '_meta.json')
        meta_data = {'timestamp': os.path.getmtime(cache_path), 'stock_code': stock_code}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_data = json.load(f)
        expiry_seconds = get_cache_expiry_seconds('hist')
        age = time.time() - meta_data['timestamp']
        if age < expiry_seconds:
            log_cache_usage('hist', meta_data.get('stock_code', stock_code), 'hit')
        elif allow_stale:
            print(f"使用过期历史资金缓存: {cache_path} ({age/3600:.1f}h)")
        else:
            print(f"历史资金缓存已过期: {cache_path}")
            return None
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except Exception as e:
        print(f"加载缓存数据失败: {e}")
    return None

def save_hist_cached_data(stock_code, data, stock_name):
    """保存历史资金流向数据到缓存"""
    cache_path = get_hist_cache_path(stock_code)
    meta_path = cache_path.replace('.csv', '_meta.json')
    
    try:
        # 保存数据到CSV
        data.to_csv(cache_path, index=False, encoding='utf-8')
        
        # 保存元数据到JSON
        meta_data = {
            'stock_name': stock_name,
            'stock_code': stock_code,
            'timestamp': time.time()
        }
        with open(meta_path, 'w', encoding='utf-8') as f:
            import json
            json.dump(meta_data, f, ensure_ascii=False, indent=2)
        
        log_cache_usage('hist', stock_code, 'save')
    except Exception as e:
        print(f"保存缓存数据失败: {e}")

def get_stock_price_data(stock_code, start_date, end_date, use_cache=True):
    """
    获取股票价格数据（基于 get_kline，仅保留交易日；与资金流向等按日期 merge 时使用）。
    日涨幅来自 K 线 API 的涨跌幅，累积涨幅在本地计算。

    参数:
    stock_code: 股票代码
    start_date: 开始日期
    end_date: 结束日期
    use_cache: 保留兼容，实际缓存由 get_kline 控制

    返回:
    DataFrame: 含 日期、开盘价、收盘价、最高价、最低价、成交量、成交额、振幅、日涨幅、累积涨幅
    """
    try:
        from utils_reem import get_kline
        kline_df = get_kline(stock_code)
        if kline_df is None or kline_df.empty:
            return None
        # 按日期范围过滤
        kline_df = kline_df[(kline_df['日期'].dt.date >= start_date.date()) & (kline_df['日期'].dt.date <= end_date.date())]
        if kline_df.empty:
            return None
        # 日涨幅：get_kline 返回列为「涨跌幅」
        if '涨跌幅' in kline_df.columns:
            price_df = kline_df.rename(columns={'涨跌幅': '日涨幅'}).copy()
        else:
            price_df = kline_df.copy()
            price_df['日涨幅'] = price_df['收盘价'].pct_change() * 100
        price_df['累积涨幅'] = price_df['日涨幅'].fillna(0).cumsum()
        price_df['日涨幅'] = price_df['日涨幅'].round(2)
        price_df['累积涨幅'] = price_df['累积涨幅'].round(2)
        # 返回与原先一致的列（不含涨跌额、换手率）
        out_cols = ['日期', '开盘价', '收盘价', '最高价', '最低价', '成交量', '成交额', '振幅', '日涨幅', '累积涨幅']
        return price_df[[c for c in out_cols if c in price_df.columns]]
    except Exception as e:
        print(f"获取价格数据失败: {e}")
        return None

def get_hist_flow(stock_code, use_cache=True):
    """

    python stock/utils_cap.py --hist 002916 
    
    获取股票历史资金流向数据
    
    参数:
    stock_code: 股票代码，如 '002456'
    use_cache: 是否使用缓存数据
    
    返回:
    DataFrame: 包含历史资金流向数据的DataFrame
    """
    
    # 尝试从缓存加载数据
    if use_cache:
        from hist_chart_cache import is_hist_data_stale_ok
        allow_stale = is_hist_data_stale_ok()
        cached_data = load_hist_cached_data(stock_code, allow_stale=allow_stale)
        if cached_data is not None:
            return cached_data
    
    # 确定市场代码
    if stock_code.startswith('0') or stock_code.startswith('3'):
        market = 0  # 深圳
        secid = f"0.{stock_code}"
    elif stock_code.startswith('6'):
        market = 1  # 上海
        secid = f"1.{stock_code}"
    else:
        raise ValueError(f"不支持的股票代码格式: {stock_code}")
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/zjlx/',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    # 构建请求参数
    timestamp = int(time.time() * 1000)
    callback = f'jQuery{timestamp}_{timestamp + 1}'
    
    params = {
        'cb': callback,
        'lmt': '0',
        'klt': '101',  # 日K线数据
        'fields1': 'f1,f2,f3,f7',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65',
        'ut': 'b2884a393a59ad64002292a3e90d46a5',
        'secid': secid,
        '_': timestamp + 2,
    }

    try:
        print(f"正在获取盘后资金流向数据: {stock_code}")
        response = _requests_session_no_proxy().get(
            'https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get',
            params=params, headers=headers, timeout=15,
        )
        response.raise_for_status()
        
        # 解析JSONP响应
        json_str = re.search(r'jQuery\d+_\d+\((.*)\)', response.text)
        if not json_str:
            raise ValueError("无法解析API响应")
        
        data = json.loads(json_str.group(1))
        
        if data['rc'] != 0:
            raise ValueError(f"API返回错误: {data.get('rt', '未知错误')}")
        
        # 提取K线数据
        klines = data['data']['klines']
        stock_name = data['data']['name']
        
        # 解析每行数据
        rows = []
        for kline in klines:
            values = kline.split(',')
            
            if len(values) >= 15:
                try:
                    row = {
                        '日期': pd.to_datetime(values[0]),
                        '主力净流入': float(values[1]) / 1E8,  # 转换为亿元
                        '超大单净流入': float(values[2]) / 1E8,
                        '大单净流入': float(values[3]) / 1E8,
                        '中单净流入': float(values[4]) / 1E8,
                        '小单净流入': float(values[5]) / 1E8,
                        '主力净占比': float(values[6]),
                        '超大单净占比': float(values[7]),
                        '大单净占比': float(values[8]),
                        '中单净占比': float(values[9]),
                        '小单净占比': float(values[10]),
                        '主力净额': float(values[11]) / 1E8,
                        '超大单净额': float(values[12]) / 1E8,
                        '大单净额': float(values[13]) / 1E8,
                        '中单净额': float(values[14]) / 1E8,
                        '小单净额': float(values[15]) / 1E8 if len(values) > 15 else 0
                    }
                    rows.append(row)
                except (ValueError, IndexError) as e:
                    print(f"解析数据行时出错: {e}, 数据: {kline}")
                    continue
        
        df = pd.DataFrame(rows)
        df['股票名称'] = stock_name
        df['股票代码'] = stock_code
        
        # 保存到缓存
        save_hist_cached_data(stock_code, df, stock_name)
        
        return df
        
    except Exception as e:
        print(f"获取历史资金流向数据失败: {e}")
        fallback = _fetch_hist_flow_from_datacenter(stock_code)
        if fallback is not None:
            return fallback
        return load_hist_cached_data(stock_code, allow_stale=True)


def _fetch_hist_flow_from_datacenter(stock_code):
    """Fallback: daily main-force flow via datacenter-web when push2his is unavailable."""
    try:
        from utils_cmts import EastMoneyAPI
        api = EastMoneyAPI()
        secu_code = api.get_secu_code(stock_code)
        timestamp = int(time.time() * 1000)
        cb_name = f"jQuery{timestamp}_{timestamp + 1}"
        params = {
            'callback': cb_name,
            'reportName': 'PRT_STOCK_CAPITALFLOWS',
            'filter': f'(SECUCODE="{secu_code}")',
            'sortColumns': 'TRADE_DATE',
            'sortTypes': -1,
            'pageSize': 120,
            'columns': 'SECUCODE,TRADE_DATE,CAPITAL_FLOWS,CAPITAL_FLOWS_RATIO',
            'source': 'WEB',
            'client': 'WEB',
            '_': timestamp,
        }
        response = api.session.get(
            'https://datacenter-web.eastmoney.com/api/data/v1/get',
            params=params, timeout=15,
        )
        data = api._clean_jsonp_response(response.text)
        rows = (data.get('result') or {}).get('data') or []
        if not rows:
            return None

        parsed = []
        for row in rows:
            parsed.append({
                '日期': pd.to_datetime(row['TRADE_DATE']),
                '主力净流入': float(row['CAPITAL_FLOWS']) / 1E8,
                '超大单净流入': 0.0,
                '大单净流入': 0.0,
                '中单净流入': 0.0,
                '小单净流入': 0.0,
                '主力净占比': float(row.get('CAPITAL_FLOWS_RATIO', 0)),
                '超大单净占比': 0.0,
                '大单净占比': 0.0,
                '中单净占比': 0.0,
                '小单净占比': 0.0,
                '主力净额': float(row['CAPITAL_FLOWS']) / 1E8,
                '超大单净额': 0.0,
                '大单净额': 0.0,
                '中单净额': 0.0,
                '小单净额': 0.0,
            })
        df = pd.DataFrame(parsed).sort_values('日期').reset_index(drop=True)
        df['股票代码'] = stock_code
        df['股票名称'] = stock_code
        save_hist_cached_data(stock_code, df, stock_code)
        print(f"✅ 使用 datacenter 备用接口获取历史资金: {stock_code} ({len(df)} 条)")
        return df
    except Exception as e:
        print(f"datacenter 历史资金备用接口失败: {e}")
        return None

def calculate_technical_indicators(df):
    """计算技术指标"""
    if df is None or df.empty or '收盘价' not in df.columns:
        return df
    
    # 计算移动平均线
    df['MA5'] = df['收盘价'].rolling(window=5).mean()
    df['MA10'] = df['收盘价'].rolling(window=10).mean()
    df['MA20'] = df['收盘价'].rolling(window=20).mean()
    df['MA30'] = df['收盘价'].rolling(window=30).mean()
    
    # 计算RSI
    df['RSI'] = calculate_rsi(df['收盘价'])
    
    # 计算MACD
    macd_data = calculate_macd(df['收盘价'])
    df['MACD'] = macd_data['MACD']
    df['MACD_Signal'] = macd_data['Signal']
    df['MACD_Histogram'] = macd_data['Histogram']
    
    return df

def calculate_rsi(prices, period=6):
    """计算RSI指标"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD指标"""
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    
    return {
        'MACD': macd,
        'Signal': signal_line,
        'Histogram': histogram
    }


def _load_kline_for_hist(stock_code, ndays, price_df=None):
    """Load K-line data for hist chart; fall back to merged price_df when API/cache fails."""
    kline_df = None
    try:
        from utils_reem import get_kline
        kline_df = get_kline(stock_code)
        if kline_df is not None and not kline_df.empty:
            kline_df = kline_df.tail(ndays).reset_index(drop=True)
            print(f"使用get_kline数据源，限制K线图显示最近 {ndays} 天数据")
    except Exception as exc:
        print(f"get_kline失败，尝试使用价格缓存: {exc}")

    if (kline_df is None or kline_df.empty) and price_df is not None and not price_df.empty:
        kline_df = price_df.tail(ndays).reset_index(drop=True).copy()
        print(f"使用价格缓存绘制K线，共 {len(kline_df)} 条记录")

    return kline_df


def _draw_hist_kline_panel(stock_code, df, kline_df, axes, ndays):
    """Draw right-side K-line / volume / RSI / MACD panel."""
    ax2, ax2_volume, ax2_rsi, ax2_macd = axes
    stock_name = df['股票名称'].iloc[0] if '股票名称' in df.columns else stock_code

    if kline_df is None or kline_df.empty:
        for ax in axes:
            ax.text(0.5, 0.5, '无K线数据', transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='gray')
            ax.set_title('股票K线图' if ax is ax2 else '', fontsize=14, fontweight='bold', pad=8)
        return

    kline_df = calculate_technical_indicators(kline_df)
    dates = kline_df['日期']
    opens = kline_df['开盘价']
    highs = kline_df['最高价']
    lows = kline_df['最低价']
    closes = kline_df['收盘价']
    volumes = kline_df['成交量']

    if 'MA5' in kline_df.columns:
        ax2.plot(range(len(dates)), kline_df['MA5'], label='MA5', color='blue', linewidth=2, alpha=0.8, zorder=1)
    if 'MA10' in kline_df.columns:
        ax2.plot(range(len(dates)), kline_df['MA10'], label='MA10', color='purple', linewidth=2, alpha=0.8, zorder=1)
    if 'MA20' in kline_df.columns:
        ax2.plot(range(len(dates)), kline_df['MA20'], label='MA20', color='orange', linewidth=2, alpha=0.8, zorder=1)
    if 'MA30' in kline_df.columns:
        ax2.plot(range(len(dates)), kline_df['MA30'], label='MA30', color='brown', linewidth=2, alpha=0.8, zorder=1)

    for i in range(len(dates)):
        color = 'red' if closes.iloc[i] >= opens.iloc[i] else 'green'
        ax2.plot([i, i], [lows.iloc[i], highs.iloc[i]], color='black', linewidth=1, zorder=3)
        body_height = abs(closes.iloc[i] - opens.iloc[i])
        body_bottom = min(opens.iloc[i], closes.iloc[i])
        if body_height > 0:
            rect = plt.Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                                 facecolor=color, alpha=0.8, zorder=2)
            ax2.add_patch(rect)
        else:
            ax2.plot([i - 0.3, i + 0.3], [opens.iloc[i], opens.iloc[i]],
                     color='black', linewidth=2, zorder=3)

    ax2.set_title(f'{stock_name}({stock_code}) 技术分析图表', fontsize=14, fontweight='bold', pad=8)
    ax2.set_ylabel('价格', fontsize=12)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    ax2_volume.bar(range(len(dates)), volumes,
                   color=['red' if c >= o else 'green' for c, o in zip(closes, opens)],
                   alpha=0.7)
    ax2_volume.set_ylabel('成交量', fontsize=12)
    ax2_volume.grid(True, alpha=0.3)

    if 'RSI' in kline_df.columns:
        ax2_rsi.plot(range(len(dates)), kline_df['RSI'], label='RSI', color='purple')
        ax2_rsi.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='超买线')
        ax2_rsi.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='超卖线')
        ax2_rsi.set_ylabel('RSI', fontsize=12)
        ax2_rsi.legend(loc='upper left', fontsize=8)
        ax2_rsi.grid(True, alpha=0.3)

    if 'MACD' in kline_df.columns and 'MACD_Signal' in kline_df.columns:
        ax2_macd.plot(range(len(dates)), kline_df['MACD'], label='MACD', color='blue', linewidth=1.5)
        ax2_macd.plot(range(len(dates)), kline_df['MACD_Signal'], label='Signal', color='red', linewidth=1.5)
        histogram = kline_df['MACD_Histogram']
        colors = ['red' if x >= 0 else 'green' for x in histogram]
        ax2_macd.bar(range(len(dates)), histogram, color=colors, alpha=0.6, width=0.8)
        ax2_macd.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        ax2_macd.set_ylabel('MACD', fontsize=12)
        ax2_macd.set_xlabel('日期', fontsize=12)
        ax2_macd.legend(loc='upper left', fontsize=8)
        ax2_macd.grid(True, alpha=0.3)

    step = max(1, len(dates) // 8)
    ax2.set_xticks([])
    ax2_volume.set_xticks([])
    ax2_rsi.set_xticks([])
    ax2_macd.set_xticks(range(0, len(dates), step))
    ax2_macd.set_xticklabels([dates.iloc[i].strftime('%m-%d') for i in range(0, len(dates), step)],
                             rotation=45, fontsize=9)


def plot_professional_chart(stock_code, save_path=None, use_cache=True):
    """
    绘制专业的技术分析图表（类似candlestick_pattern_detector.py）
    
    参数:
    stock_code: 股票代码
    save_path: 保存路径，如果为None则不保存
    use_cache: 是否使用缓存数据
    """
    print(f"正在获取股票数据: {stock_code}")
    
    # 获取历史资金流向数据
    df = get_hist_flow(stock_code, use_cache=use_cache)
    if df is None or df.empty:
        print("无法获取资金流向数据")
        return None
    
    # 获取股票价格数据
    price_df = get_stock_price_data(stock_code, df['日期'].min(), df['日期'].max(), use_cache=use_cache)
    if price_df is None or price_df.empty:
        print("无法获取价格数据")
        return None
    
    # 计算技术指标
    price_df = calculate_technical_indicators(price_df)
    
    # 限制显示最近100天的数据
    if len(price_df) > 100:
        price_df = price_df.tail(100).reset_index(drop=True)
    
    # 准备数据
    dates = price_df['日期']
    opens = price_df['开盘价']
    highs = price_df['最高价']
    lows = price_df['最低价']
    closes = price_df['收盘价']
    volumes = price_df['成交量']
    
    # 创建4个子图
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 10), 
                                             gridspec_kw={'height_ratios': [3, 1, 1, 1]})
    
    # 第一个子图：K线图和移动平均线
    # 先绘制移动平均线（在K线柱下方）
    if 'MA5' in price_df.columns:
        ax1.plot(range(len(dates)), price_df['MA5'], 
                label='MA5', color='blue', linewidth=2, alpha=0.8, zorder=1)
    if 'MA10' in price_df.columns:
        ax1.plot(range(len(dates)), price_df['MA10'], 
                label='MA10', color='purple', linewidth=2, alpha=0.8, zorder=1)
    if 'MA20' in price_df.columns:
        ax1.plot(range(len(dates)), price_df['MA20'], 
                label='MA20', color='orange', linewidth=2, alpha=0.8, zorder=1)
    if 'MA30' in price_df.columns:
        ax1.plot(range(len(dates)), price_df['MA30'], 
                label='MA30', color='brown', linewidth=2, alpha=0.8, zorder=1)
    
    # 绘制K线图（在移动平均线上方）
    for i in range(len(dates)):
        color = 'red' if closes.iloc[i] >= opens.iloc[i] else 'green'
        
        # 绘制影线
        ax1.plot([i, i], [lows.iloc[i], highs.iloc[i]], color='black', linewidth=1, zorder=3)
        
        # 绘制实体
        body_height = abs(closes.iloc[i] - opens.iloc[i])
        body_bottom = min(opens.iloc[i], closes.iloc[i])
        
        if body_height > 0:
            rect = plt.Rectangle((i-0.3, body_bottom), 0.6, body_height, 
                               facecolor=color, alpha=0.8, zorder=2)
            ax1.add_patch(rect)
        else:
            # 十字星
            ax1.plot([i-0.3, i+0.3], [opens.iloc[i], opens.iloc[i]], 
                    color='black', linewidth=2, zorder=3)
    
    # 设置第一个子图
    stock_name = df['股票名称'].iloc[0] if '股票名称' in df.columns else stock_code
    # ax1.set_title(f'{stock_name}({stock_code}) 技术分析图表', fontsize=16, fontweight='bold')
    
    ax1.set_ylabel('价格', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 第二个子图：成交量
    ax2.bar(range(len(dates)), volumes, 
           color=['red' if c >= o else 'green' for c, o in zip(closes, opens)],
           alpha=0.7)
    ax2.set_ylabel('成交量', fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    # 第三个子图：RSI
    if 'RSI' in price_df.columns:
        ax3.plot(range(len(dates)), price_df['RSI'], 
                label='RSI', color='purple')
        ax3.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='超买线')
        ax3.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='超卖线')
        ax3.set_ylabel('RSI', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
    
    # 第四个子图：MACD
    if 'MACD' in price_df.columns and 'MACD_Signal' in price_df.columns:
        # 绘制MACD线和信号线
        ax4.plot(range(len(dates)), price_df['MACD'], 
                label='MACD', color='blue', linewidth=1.5)
        ax4.plot(range(len(dates)), price_df['MACD_Signal'], 
                label='Signal', color='red', linewidth=1.5)
        
        # 绘制MACD柱状图
        histogram = price_df['MACD_Histogram']
        colors = ['red' if x >= 0 else 'green' for x in histogram]
        ax4.bar(range(len(dates)), histogram, color=colors, alpha=0.6, width=0.8)
        
        # 添加零线
        ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        
        ax4.set_ylabel('MACD', fontsize=12)
        ax4.set_xlabel('日期', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
    
    # 设置x轴标签
    step = max(1, len(dates) // 10)
    ax1.set_xticks(range(0, len(dates), step))
    ax1.set_xticklabels([dates.iloc[i].strftime('%m-%d') for i in range(0, len(dates), step)], 
                       rotation=45)
    
    ax2.set_xticks(range(0, len(dates), step))
    ax2.set_xticklabels([dates.iloc[i].strftime('%m-%d') for i in range(0, len(dates), step)], 
                       rotation=45)
    
    ax3.set_xticks(range(0, len(dates), step))
    ax3.set_xticklabels([dates.iloc[i].strftime('%m-%d') for i in range(0, len(dates), step)], 
                       rotation=45)
    
    ax4.set_xticks(range(0, len(dates), step))
    ax4.set_xticklabels([dates.iloc[i].strftime('%m-%d') for i in range(0, len(dates), step)], 
                       rotation=45)
    
    plt.tight_layout()
    
    # 保存图片
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"专业图表已保存到: {save_path}")
    
    return fig

def plot_hist_flow(stock_code, save_path=None, use_cache=True, ndays=80):
    """
    绘制历史资金流向图表（类似东方财富的样式）
    
    参数:
    stock_code: 股票代码，如 '002456'
    save_path: 保存路径，如果为None则不保存
    use_cache: 是否使用缓存数据
    ndays: K线图显示最近多少天的数据，默认50天
    """
    
    try:
        # 获取历史资金流向数据
        df = get_hist_flow(stock_code, use_cache=use_cache)
        if df is None or df.empty:
            print("无法获取数据")
            return None
    except Exception as e:
        print(f"获取历史资金流向数据时出错: {e}")
        return None
    
    # 限制历史资金流向数据为最近ndays天
    if len(df) > ndays:
        df = df.tail(ndays).reset_index(drop=True)
        print(f"限制历史资金流向数据为最近 {ndays} 天")
    
    # 获取股票价格数据（用于计算日涨幅）
    price_df = get_stock_price_data(stock_code, df['日期'].min(), df['日期'].max())
    if price_df is not None and not price_df.empty:
        # 合并数据（价格数据已经包含了日涨幅和累积涨幅的计算）
        df = df.merge(price_df[['日期', '日涨幅', '累积涨幅']], on='日期', how='left')
        print(f"✅ 成功获取价格数据: {len(price_df)} 条记录（包含非交易日填充）")
    else:
        print("警告: 无法获取价格数据，将跳过日涨幅图表")
        df['日涨幅'] = 0
        df['累积涨幅'] = 0
    
    # 创建图表 - 左侧4行，右侧4行K线图
    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(4, 2, height_ratios=[1, 1, 1, 1], width_ratios=[1, 1])
    
    # 左侧：4行均匀分布
    ax0 = fig.add_subplot(gs[0, 0])  # 最上左：实时资金流向
    ax1 = fig.add_subplot(gs[1, 0])  # 上左：历史资金流向趋势
    ax1_price = fig.add_subplot(gs[2, 0])  # 中左：日涨幅累积趋势
    ax1_cumsum = fig.add_subplot(gs[3, 0])  # 下左：历史资金流向累积趋势
    
    # 右侧：股票K线图占据整个列（4个子图，高度比例3:1:1:1）
    gs_right = gs[:, 1].subgridspec(4, 1, height_ratios=[3, 1, 1, 1])
    ax2 = fig.add_subplot(gs_right[0])  # K线图（占3/6高度）
    ax2_volume = fig.add_subplot(gs_right[1])  # 成交量（占1/6高度）
    ax2_rsi = fig.add_subplot(gs_right[2])  # RSI（占1/6高度）
    ax2_macd = fig.add_subplot(gs_right[3])  # MACD（占1/6高度）
    
    # 设置整体样式
    fig.patch.set_facecolor('white')
    ax0.set_facecolor('white')
    ax1.set_facecolor('white')
    ax1_price.set_facecolor('white')
    ax1_cumsum.set_facecolor('white')
    ax2.set_facecolor('white')
    ax2_volume.set_facecolor('white')
    ax2_rsi.set_facecolor('white')
    ax2_macd.set_facecolor('white')
    
    # 定义颜色（与图片中的颜色匹配）
    colors = {
        '主力净流入': '#FF1493',      # 深粉红色
        '超大单净流入': '#8B0000',    # 深红色
        '大单净流入': '#DC143C',      # 红色
        '中单净流入': '#FF8C00',      # 橙色
        '小单净流入': '#87CEEB'       # 浅蓝色
    }
    
    # 最上左：实时资金流向图（使用plot_realtime_flow的绘制逻辑）
    try:
        # 获取实时资金流向数据
        realtime_df = get_realtime_flow(stock_code, use_cache=use_cache)
        if realtime_df is not None and not realtime_df.empty:
            # 创建df2用于绘图
            realtime_df2 = realtime_df.reset_index(drop=True)
            
            # 绘制各条线（使用plot_realtime_flow的绘制逻辑）
            realtime_colors = {
                '主力净流入': '#FF6B6B',      # 粉红色
                '超大单净流入': '#8B0000',    # 深红色
                '大单净流入': '#DC143C',      # 红色
                '中单净流入': '#FF8C00',      # 橙色
                '小单净流入': '#87CEEB'       # 浅蓝色
            }
            
            for col in ['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']:
                if col in realtime_df2.columns:
                    if col == '主力净流入':
                        linewidth = 3.5
                    elif col == '超大单净流入':
                        linewidth = 1.5
                    else:
                        linewidth = 0.9
                    ax0.plot(realtime_df2.index, realtime_df2[col], 
                           color=realtime_colors[col], 
                           linewidth=linewidth,
                           label=col)
            
            # 设置图表样式
            ax0.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
            ax0.set_axisbelow(True)
            ax0.set_xlabel('数据点索引', fontsize=12, fontweight='bold')
            ax0.set_ylabel('资金流向 (亿元)', fontsize=12, fontweight='bold')
            ax0.set_title('实时资金流向', fontsize=14, fontweight='bold', pad=8)
            
            # 设置x轴格式 - 使用索引作为x轴标签
            step = max(1, len(realtime_df2) // 10)  # 显示大约10个刻度
            tick_positions = range(0, len(realtime_df2), step)
            # 将tick_labels改为realtime_df2['时间']对应的hh:mm格式
            tick_labels = []
            for i in tick_positions:
                if i < len(realtime_df2):
                    t = realtime_df2['时间'].iloc[i]
                    # 如果是datetime类型，直接格式化，否则尝试解析
                    if isinstance(t, (datetime, pd.Timestamp)):
                        tick_labels.append(t.strftime('%H:%M'))
                    else:
                        try:
                            tick_labels.append(pd.to_datetime(t).strftime('%H:%M'))
                        except Exception:
                            tick_labels.append(str(t))
                else:
                    tick_labels.append(f'{i:03d}')
            ax0.set_xticks(tick_positions)
            ax0.set_xticklabels(tick_labels)
            plt.setp(ax0.xaxis.get_majorticklabels(), rotation=45)
            
            # 添加零线
            ax0.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
            
            # 设置图例
            legend0 = ax0.legend(loc='upper left', fontsize=10, framealpha=0.9)
            legend0.get_frame().set_facecolor('white')
            legend0.get_frame().set_edgecolor('gray')
        else:
            ax0.text(0.5, 0.5, '无实时数据', transform=ax0.transAxes, 
                    ha='center', va='center', fontsize=14, color='gray')
            ax0.set_title('实时资金流向', fontsize=14, fontweight='bold', pad=8)
    except Exception as e:
        print(f"获取实时资金流向数据失败: {e}")
        ax0.text(0.5, 0.5, '获取实时数据失败', transform=ax0.transAxes, 
                ha='center', va='center', fontsize=14, color='gray')
        ax0.set_title('实时资金流向', fontsize=14, fontweight='bold', pad=8)
    
    # 上左：盘后资金流向趋势图（原始数据）
    for col in ['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']:
        if col == '主力净流入':
            linewidth = 3.5
        elif col == '超大单净流入':
            linewidth = 1.5
        else:
            linewidth = 0.9
        ax1.plot(df['日期'], df[col], 
                color=colors[col], 
                linewidth=linewidth,
                label=col)
    
    # 设置上左图表样式
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.set_axisbelow(True)
    # ax1.set_xlabel('日期', fontsize=12, fontweight='bold')  # 隐藏x轴标签
    ax1.set_ylabel('资金流向 (亿元)', fontsize=12, fontweight='bold')
    ax1.set_title('历史资金流向趋势', fontsize=14, fontweight='bold', pad=8)
    
    # 设置x轴格式 - 隐藏刻度标签
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=7))
    ax1.set_xticklabels([])  # 隐藏x轴刻度标签
    
    # 添加零线
    ax1.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
    
    # 设置图例 - 隐藏历史资金流向趋势的图例
    # legend1 = ax1.legend(loc='upper left', fontsize=10, framealpha=0.9)
    # legend1.get_frame().set_facecolor('white')
    # legend1.get_frame().set_edgecolor('gray')
    
    # 中左：日涨幅累积趋势图
    if '累积涨幅' in df.columns and not df['累积涨幅'].isna().all():
        # 绘制累积涨幅线 - 根据正负值改变颜色
        color = 'green' if df['累积涨幅'].iloc[-1] <= 0 else 'red'
        ax1_price.plot(df['日期'], df['累积涨幅'], 
                      color=color, 
                      linewidth=1.5,
                      label='累积涨幅')
        
        # 设置中左图表样式
        ax1_price.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax1_price.set_axisbelow(True)
        ax1_price.set_xlabel('日期', fontsize=12, fontweight='bold')  # 显示x轴标签
        ax1_price.set_ylabel('累积涨幅 (%)', fontsize=12, fontweight='bold')
        ax1_price.set_title('股票日涨幅累积趋势', fontsize=14, fontweight='bold', pad=8)
        
        # 设置x轴格式 - 显示刻度标签
        ax1_price.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        ax1_price.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        plt.setp(ax1_price.xaxis.get_majorticklabels(), rotation=45)
        
        # 添加零线
        ax1_price.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
        
        # 设置图例 - 隐藏股票日涨幅累积趋势的图例
        # legend1_price = ax1_price.legend(loc='upper left', fontsize=10, framealpha=0.9)
        # legend1_price.get_frame().set_facecolor('white')
        # legend1_price.get_frame().set_edgecolor('gray')
    else:
        ax1_price.text(0.5, 0.5, '无价格数据', transform=ax1_price.transAxes, 
                      ha='center', va='center', fontsize=14, color='gray')
        ax1_price.set_title('股票日涨幅累积趋势', fontsize=14, fontweight='bold', pad=8)
    
    # 下左：盘后资金流向累积和趋势图（最近10日）
    n_days = 10
    df_recent = df.tail(n_days) if len(df) > n_days else df
    
    for col in ['主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入']:
        if col == '主力净流入':
            linewidth = 3.5
        elif col == '超大单净流入':
            linewidth = 1.5
        else:
            linewidth = 0.9
        cumsum_data = df_recent[col].cumsum()
        ax1_cumsum.plot(df_recent['日期'], cumsum_data, 
                       color=colors[col], 
                       linewidth=linewidth,
                       label=f'{col}(累积)')
    
    # 设置下左图表样式
    ax1_cumsum.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1_cumsum.set_axisbelow(True)
    ax1_cumsum.set_xlabel('日期', fontsize=12, fontweight='bold')
    ax1_cumsum.set_ylabel('累积资金流向 (亿元)', fontsize=12, fontweight='bold')
    ax1_cumsum.set_title(f'历史资金流向累积趋势(最近{n_days}日)', fontsize=14, fontweight='bold', pad=8)
    
    # 设置x轴格式
    ax1_cumsum.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax1_cumsum.xaxis.set_major_locator(mdates.DayLocator(interval=7))
    plt.setp(ax1_cumsum.xaxis.get_majorticklabels(), rotation=45)
    
    # 添加零线
    ax1_cumsum.axhline(y=0, color='black', linestyle='-', alpha=0.3, linewidth=1)
    
    # 设置图例 - 隐藏历史资金流向累积趋势的图例
    # legend1_cumsum = ax1_cumsum.legend(loc='upper left', fontsize=10, framealpha=0.9)
    # legend1_cumsum.get_frame().set_facecolor('white')
    # legend1_cumsum.get_frame().set_edgecolor('gray')
    
    # 右侧：K线 / 成交量 / RSI / MACD
    kline_df = _load_kline_for_hist(stock_code, ndays, price_df)
    try:
        _draw_hist_kline_panel(
            stock_code, df, kline_df,
            (ax2, ax2_volume, ax2_rsi, ax2_macd),
            ndays,
        )
    except Exception as e:
        print(f"绘制K线面板失败: {e}")
        _draw_hist_kline_panel(stock_code, df, None, (ax2, ax2_volume, ax2_rsi, ax2_macd), ndays)

    # 添加更新时间
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    stock_name = df['股票名称'].iloc[0] if '股票名称' in df.columns else stock_code
    fig.suptitle(f'{stock_name}({stock_code})历史资金流向 - 更新时间: {current_time}', fontsize=16, fontweight='bold', y=0.98)
    
    try:
        fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.08, hspace=0.52, wspace=0.22)
        
        # 保存图片
        if save_path:
            plt.savefig(save_path, dpi=180, bbox_inches='tight',
                       facecolor='white', edgecolor='none', pad_inches=0.35)
            print(f"历史资金流向图表已保存到: {save_path}")
        
        return fig, (ax0, ax1, ax1_price, ax1_cumsum, ax2, ax2_volume, ax2_rsi, ax2_macd)
    except Exception as e:
        print(f"保存图表时出错: {e}")
        if save_path:
            print(f"尝试保存到备用路径...")
            try:
                backup_path = save_path.replace('.png', '_backup.png')
                plt.savefig(backup_path, dpi=150, bbox_inches='tight', pad_inches=0.35)
                print(f"图表已保存到备用路径: {backup_path}")
            except Exception as backup_e:
                print(f"备用保存也失败: {backup_e}")
        return fig, (ax0, ax1, ax1_price, ax1_cumsum, ax2, ax2_volume, ax2_rsi, ax2_macd)

def manage_cache(action='list'):
    """
    管理缓存文件
    
    参数:
    action: 操作类型 ('list', 'clear', 'info')
    """
    if action == 'list':
        print("=" * 60)
        print("缓存文件列表")
        print("=" * 60)
        
        if not os.path.exists(CACHE_DIR):
            print("缓存目录不存在")
            return
        
        # 获取所有缓存文件（包括pkl和csv）
        pkl_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.pkl')]
        csv_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.csv') and ('hist_flow' in f or 'price_data' in f or 'realtime_flow' in f)]
        
        if not pkl_files and not csv_files:
            print("没有找到缓存文件")
            return
        
        # 处理pkl文件（旧格式）
        for cache_file in sorted(pkl_files):
            cache_path = os.path.join(CACHE_DIR, cache_file)
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                
                file_size = os.path.getsize(cache_path)
                cache_time = datetime.fromtimestamp(cached_data['timestamp'])
                age_hours = (time.time() - cached_data['timestamp']) / 3600
                
                if 'stock_name' in cached_data:
                    print(f"📊 {cached_data['stock_name']} ({cached_data['stock_code']}) [PKL]")
                else:
                    print(f"📊 {cache_file} [PKL]")
                
                print(f"   创建时间: {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   文件大小: {file_size / 1024:.1f} KB")
                print(f"   缓存时长: {age_hours:.1f} 小时")
                print(f"   文件路径: {cache_path}")
                print()
                
            except Exception as e:
                print(f"❌ 读取缓存文件失败: {cache_file} - {e}")
        
        # 处理csv文件（新格式）
        for cache_file in sorted(csv_files):
            cache_path = os.path.join(CACHE_DIR, cache_file)
            meta_path = cache_path.replace('.csv', '_meta.json')
            
            try:
                file_size = os.path.getsize(cache_path)
                
                if os.path.exists(meta_path):
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        import json
                        meta_data = json.load(f)
                    
                    cache_time = datetime.fromtimestamp(meta_data['timestamp'])
                    age_hours = (time.time() - meta_data['timestamp']) / 3600
                    
                    if 'hist_flow' in cache_file:
                        print(f"📊 {meta_data['stock_name']} ({meta_data['stock_code']}) [历史资金流向CSV]")
                    elif 'price_data' in cache_file:
                        print(f"📊 {meta_data['stock_code']} ({meta_data['start_date']} 到 {meta_data['end_date']}) [价格数据CSV]")
                    elif 'realtime_flow' in cache_file:
                        print(f"📊 {meta_data['stock_code']} [实时资金流向CSV]")
                    else:
                        print(f"📊 {cache_file} [CSV]")
                    
                    print(f"   创建时间: {cache_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   文件大小: {file_size / 1024:.1f} KB")
                    print(f"   缓存时长: {age_hours:.1f} 小时")
                    print(f"   文件路径: {cache_path}")
                    print()
                else:
                    print(f"📊 {cache_file} [CSV] (无元数据)")
                    print(f"   文件大小: {file_size / 1024:.1f} KB")
                    print(f"   文件路径: {cache_path}")
                    print()
                
            except Exception as e:
                print(f"❌ 读取缓存文件失败: {cache_file} - {e}")
    
    elif action == 'clear':
        print("=" * 60)
        print("清理缓存文件")
        print("=" * 60)
        
        if not os.path.exists(CACHE_DIR):
            print("缓存目录不存在")
            return
        
        # 获取所有缓存文件
        pkl_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.pkl')]
        csv_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.csv') and ('hist_flow' in f or 'price_data' in f or 'realtime_flow' in f)]
        json_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('_meta.json')]
        
        all_files = pkl_files + csv_files + json_files
        
        if not all_files:
            print("没有找到缓存文件")
            return
        
        cleared_count = 0
        for cache_file in all_files:
            cache_path = os.path.join(CACHE_DIR, cache_file)
            try:
                os.remove(cache_path)
                cleared_count += 1
                print(f"✅ 已删除: {cache_file}")
            except Exception as e:
                print(f"❌ 删除失败: {cache_file} - {e}")
        
        print(f"\n🎉 清理完成，共删除 {cleared_count} 个缓存文件")
    
    elif action == 'info':
        print("=" * 60)
        print("缓存信息")
        print("=" * 60)
        
        if not os.path.exists(CACHE_DIR):
            print("缓存目录不存在")
            return
        
        # 统计所有缓存文件
        pkl_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.pkl')]
        csv_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.csv') and ('hist_flow' in f or 'price_data' in f or 'realtime_flow' in f)]
        json_files = [f for f in os.listdir(CACHE_DIR) if f.endswith('_meta.json')]
        
        all_files = pkl_files + csv_files + json_files
        total_size = 0
        
        for cache_file in all_files:
            cache_path = os.path.join(CACHE_DIR, cache_file)
            total_size += os.path.getsize(cache_path)
        
        print(f"缓存目录: {CACHE_DIR}")
        print(f"PKL文件数量: {len(pkl_files)}")
        print(f"CSV文件数量: {len(csv_files)}")
        print(f"JSON元数据文件数量: {len(json_files)}")
        print(f"总文件数量: {len(all_files)}")
        print(f"总大小: {total_size / 1024:.1f} KB")
        # 显示智能缓存过期时间
        realtime_expiry = get_cache_expiry_seconds('realtime')
        hist_expiry = get_cache_expiry_seconds('hist')
        price_expiry = get_cache_expiry_seconds('price')
        
        trading_status = "交易时间" if is_trading_time() else "非交易时间"
        print(f"当前状态: {trading_status}")
        print(f"实时数据缓存过期时间: {realtime_expiry//60}分钟")
        print(f"历史数据缓存过期时间: {hist_expiry//3600}小时")
        print(f"价格数据缓存过期时间: {price_expiry//3600}小时")
        print()
        print("💡 智能缓存策略:")
        print("   - 交易时间: 实时数据5分钟，历史/价格数据1小时")
        print("   - 非交易时间: 实时数据2小时，历史/价格数据24小时")
        print("   - 周末和节假日: 所有数据缓存24小时")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='实时资金流向数据获取和可视化工具')
    parser.add_argument('--stock-code', type=str, help='股票代码')
    parser.add_argument('--plot', action='store_true', help='生成基础图表')
    parser.add_argument('--ext', action='store_true', help='生成综合图表（包含文本和饼图）')
    parser.add_argument('--demo', action='store_true', help='运行演示')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存数据')
    parser.add_argument('--hist', type=str, help='股票代码，生成历史资金流向图表')
    parser.add_argument('--no-cache-hist', action='store_true', help='不使用历史资金流向缓存数据')
    parser.add_argument('--ndays', type=int, default=80, help='K线图显示最近多少天的数据，默认80天')
    parser.add_argument('--professional', type=str, help='股票代码，生成专业技术分析图表')
    parser.add_argument('--no-cache-professional', action='store_true', help='不使用专业图表缓存数据')
    parser.add_argument('--section', type=str, help='.ini文件路径，批量生成历史资金流向图表')
    parser.add_argument('--section-name', type=str, help='指定section名称，与--section一起使用')
    parser.add_argument('--cache-list', action='store_true', help='列出所有缓存文件')
    parser.add_argument('--cache-clear', action='store_true', help='清理所有缓存文件')
    parser.add_argument('--cache-info', action='store_true', help='显示缓存信息')
    parser.add_argument('--cache-log', action='store_true', help='启用缓存日志记录')
    
    args = parser.parse_args()
    
    # 如果启用了缓存日志，先启用它
    if args.cache_log:
        enable_cache_logging()
    
    if args.cache_list:
        manage_cache('list')
    elif args.cache_clear:
        manage_cache('clear')
    elif args.cache_info:
        manage_cache('info')
    elif args.cache_log and not any([args.hist, args.professional, args.section, args.stock_code, args.demo]):
        # 如果只有 --cache-log 参数，显示提示信息
        print("💡 提示: 现在运行其他命令将显示缓存使用日志")
        print("   例如: python stock/utils_cap.py --cache-log --stock-code 002456")
        print("   或者: python stock/utils_cap.py --cache-log --hist 002456")
    elif args.hist:
        # 使用股票代码绘制历史资金流向图表
        save_path = f'/Volumes/ASME/stock/em/backtest/stockd/charts/hist_flow_{args.hist}_{datetime.now().strftime("%y%m%d")}.png'
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plot_hist_flow(args.hist, save_path, use_cache=not args.no_cache_hist, ndays=args.ndays)
    elif args.professional:
        # 使用股票代码绘制专业技术分析图表
        save_path = f'/Volumes/ASME/stock/em/backtest/stockd/charts//professional_{args.professional}_{datetime.now().strftime("%y%m%d")}.png'
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plot_professional_chart(args.professional, save_path, use_cache=not args.no_cache_professional)
    elif args.section:
        # 批量生成历史资金流向图表
        plot_section(args.section, args.section_name)
    elif args.demo:
        demo_realtime_flow()
    elif args.stock_code:
        if args.plot:
            save_path = f'/Volumes/ASME/stock/em/backtest/stockd/charts//flow_{args.stock_code}_{datetime.now().strftime("%y%m%d")}.png'
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plot_realtime_flow(args.stock_code, save_path)
        elif args.ext:
            save_path = f'/Volumes/ASME/stock/em/backtest/stockd/charts//flowx_{args.stock_code}_{datetime.now().strftime("%y%m%d")}.png'
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plot_flowx(args.stock_code, save_path)
        else:
            summary = get_flow_summary(args.stock_code)
            if summary:
                print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        parser.print_help()

def plot_section(ini_file, section_name=None):
    """

    python stock/utils_cap.py --section shared/buysell_250917.ini
    
    从.ini文件读取股票列表，让用户选择section，为每个股票绘制历史资金流向图表
    
    参数:
    ini_file: .ini文件路径，如 'shared/buysell_250917.ini'
    section_name: 指定section名称，如果为None则让用户选择
    """
    # 从文件名提取日期
    dte = os.path.splitext(os.path.basename(ini_file))[0]
    
    # 创建输出目录
    output_dir = f'/Volumes/ASME/stock/em/backtest/stockd/charts/{dte}'
    os.makedirs(output_dir, exist_ok=True)
    
    # 读取.ini文件
    config = configparser.ConfigParser()
    config.read(ini_file, encoding='utf-8')
    
    # 显示所有sections
    sections = list(config.sections())
    if not sections:
        print("❌ 没有找到任何sections")
        return
    
    print("📊 可用的sections:")
    for i, section in enumerate(sections, 1):
        print(f"  {i}. {section}")
    
    # 选择section
    if section_name:
        if section_name in sections:
            selected_section = section_name
            print(f"✅ 使用指定的section: {selected_section}")
        else:
            print(f"❌ 指定的section '{section_name}' 不存在")
            print(f"可用的sections: {', '.join(sections)}")
            return
    else:
        # 让用户选择section
        try:
            while True:
                choice = input(f"\n请选择section (1-{len(sections)}): ").strip()
                if not choice:
                    print("❌ 请输入选择")
                    continue
                    
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(sections):
                    selected_section = sections[choice_idx]
                    break
                else:
                    print(f"❌ 请输入1到{len(sections)}之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")
            return
        except KeyboardInterrupt:
            print("\n❌ 用户取消操作")
            return
        except EOFError:
            print("❌ 无法读取用户输入，请指定section名称")
            return
    
    print(f"\n✅ 已选择section: {selected_section}")
    
    # 获取该section下的所有股票
    stocks = []
    for key, value in config[selected_section].items():
        # 解析格式: 股票代码_股票名称 = 时间,数量,价格,名称
        parts = value.split(',')
        if len(parts) >= 4:
            stock_code = key.split('_')[0]  # 提取股票代码
            stock_name = parts[3]  # 提取股票名称
            stocks.append((stock_code, stock_name))
    
    if not stocks:
        print("❌ 该section下没有找到股票")
        return
    
    print(f"📈 找到 {len(stocks)} 只股票，开始生成图表...")
    
    # 为每个股票生成图表
    success_count = 0
    for i, (stock_code, stock_name) in enumerate(stocks, 1):
        try:
            print(f"  [{i}/{len(stocks)}] 正在处理 {stock_name}({stock_code})...")
            
            # 生成图表
            save_path = os.path.join(output_dir, f'hist_flow_{stock_code}_{stock_name}.png')
            fig = plot_hist_flow(stock_code, save_path=save_path, use_cache=True)
            
            if fig is not None:
                success_count += 1
                print(f"    ✅ 成功保存: {save_path}")
            else:
                print(f"    ❌ 生成失败: {stock_code}")
                
        except Exception as e:
            print(f"    ❌ 处理 {stock_code} 时出错: {e}")
            continue
    
    print(f"\n🎉 完成! 成功生成 {success_count}/{len(stocks)} 个图表")
    print(f"📁 图表保存在: {output_dir}")

if __name__ == "__main__":
    main()
