#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票评论数据缓存工具
提供便捷的接口来获取和使用缓存的股票评论数据
"""

import os
import pandas as pd
from typing import Dict, Optional, Tuple
from datetime import datetime

def get_cached_stockcomment_data(force_refetch: bool = False) -> Dict:
    """
    获取股票评论数据（带缓存策略）
    
    Args:
        force_refetch: 是否强制重新获取数据
    
    Returns:
        Dict containing:
        - stockcomment_file: 原始数据文件路径
        - stockcommentC_file: 紧凑格式文件路径
        - cached: 是否使用了缓存
        - reason: 缓存原因
        - df: DataFrame对象（如果成功读取）
    """
    try:
        from utils_reem import get_stockcomment
        
        result = get_stockcomment(force_refetch=force_refetch)
        
        # 尝试读取DataFrame
        try:
            df = pd.read_csv(result['stockcommentC_file'], encoding='utf-8')
            result['df'] = df
            result['record_count'] = len(df)
            result['columns'] = list(df.columns)
        except Exception as e:
            result['df'] = None
            result['error'] = str(e)
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'cached': False,
            'reason': '获取失败'
        }

def get_top_stocks_by_score(n: int = 10, score_column: str = '综合得分') -> Optional[pd.DataFrame]:
    """
    获取按评分排序的前N只股票
    
    Args:
        n: 返回的股票数量
        score_column: 评分列名
    
    Returns:
        DataFrame with top N stocks
    """
    result = get_cached_stockcomment_data()
    
    if 'df' in result and result['df'] is not None:
        df = result['df']
        if score_column in df.columns:
            return df.nlargest(n, score_column)
        else:
            print(f"警告: 未找到评分列 '{score_column}'")
            print(f"可用列: {list(df.columns)}")
            return None
    else:
        print(f"无法获取数据: {result.get('error', '未知错误')}")
        return None

def get_small_cap_stocks(market_cap_level: int = 1, n: int = 10) -> Optional[pd.DataFrame]:
    """
    获取小市值股票（市值分位为1的股票）
    
    Args:
        market_cap_level: 市值分位 (1=小市值, 2=中小市值, 3=中市值, 4=大市值)
        n: 返回的股票数量
    
    Returns:
        DataFrame with small cap stocks
    """
    result = get_cached_stockcomment_data()
    
    if 'df' in result and result['df'] is not None:
        df = result['df']
        if '市值分位' in df.columns:
            small_cap_df = df[df['市值分位'] == market_cap_level]
            return small_cap_df.head(n)
        else:
            print("警告: 未找到市值分位列")
            return None
    else:
        print(f"无法获取数据: {result.get('error', '未知错误')}")
        return None

def get_stocks_by_ranking_improvement(n: int = 10) -> Optional[pd.DataFrame]:
    """
    获取排名上升的股票
    
    Args:
        n: 返回的股票数量
    
    Returns:
        DataFrame with stocks showing ranking improvement
    """
    result = get_cached_stockcomment_data()
    
    if 'df' in result and result['df'] is not None:
        df = result['df']
        if '上升/目前排名' in df.columns:
            # 解析排名变化，提取上升数量
            def extract_ranking_rise(ranking_str):
                try:
                    if isinstance(ranking_str, str) and '/' in ranking_str:
                        rise, current = ranking_str.split('/')
                        return int(rise) if rise.isdigit() else 0
                    return 0
                except:
                    return 0
            
            df['排名上升数'] = df['上升/目前排名'].apply(extract_ranking_rise)
            # 按排名上升数排序
            return df.nlargest(n, '排名上升数')
        else:
            print("警告: 未找到排名列")
            return None
    else:
        print(f"无法获取数据: {result.get('error', '未知错误')}")
        return None

def get_cache_status() -> Dict:
    """
    获取缓存状态信息
    
    Returns:
        Dict with cache status information
    """
    try:
        from utils_reem import is_trading_time, find_latest_stockcomment_files
        
        now = datetime.now()
        trading_time = is_trading_time()
        latest_stockcomment, latest_stockcommentC = find_latest_stockcomment_files()
        
        status = {
            'current_time': now.strftime('%Y-%m-%d %H:%M:%S %A'),
            'is_trading_time': trading_time,
            'latest_stockcomment': latest_stockcomment,
            'latest_stockcommentC': latest_stockcommentC,
            'cache_available': latest_stockcomment is not None and latest_stockcommentC is not None
        }
        
        # 获取文件大小和修改时间
        if latest_stockcomment and os.path.exists(latest_stockcomment):
            stat = os.stat(latest_stockcomment)
            status['file_size_mb'] = round(stat.st_size / (1024*1024), 2)
            status['file_modified'] = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        return status
        
    except Exception as e:
        return {'error': str(e)}

def print_cache_status():
    """打印缓存状态"""
    status = get_cache_status()
    
    print("="*60)
    print("股票评论数据缓存状态")
    print("="*60)
    
    if 'error' in status:
        print(f"❌ 错误: {status['error']}")
        return
    
    print(f"🕐 当前时间: {status['current_time']}")
    print(f"📈 交易状态: {'交易时间' if status['is_trading_time'] else '非交易时间'}")
    print(f"📊 缓存可用: {'是' if status['cache_available'] else '否'}")
    
    if status['latest_stockcomment']:
        print(f"📁 原始文件: {status['latest_stockcomment']}")
    
    if status['latest_stockcommentC']:
        print(f"📋 紧凑文件: {status['latest_stockcommentC']}")
    
    if 'file_size_mb' in status:
        print(f"📏 文件大小: {status['file_size_mb']} MB")
    
    if 'file_modified' in status:
        print(f"🕒 修改时间: {status['file_modified']}")

if __name__ == "__main__":
    # 测试函数
    print_cache_status()
    
    print("\n" + "="*60)
    print("测试获取前10只高评分股票")
    print("="*60)
    
    top_stocks = get_top_stocks_by_score(10)
    if top_stocks is not None:
        print(top_stocks[['名称', '最新价', '综合得分', '主力占比']].head())
    
    print("\n" + "="*60)
    print("测试获取小市值股票")
    print("="*60)
    
    small_cap = get_small_cap_stocks(market_cap_level=1, n=5)
    if small_cap is not None:
        print(small_cap[['名称', '最新价', '市值分位', '综合得分']].head())
