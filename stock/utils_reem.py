import requests,re,json
from datetime import datetime
from bs4 import BeautifulSoup
import pandas as pd
from typing import Dict, List, Any, Optional
import os
import stock_dotenv_load  # noqa: F401 — load stock/.env before KLINE_CACHE_ROOT
from tqdm import tqdm
from tqdm import trange
import time
import sys
# def getticks():
import json
import urllib.request
from http.client import IncompleteRead
import pandas as pd
import glob
from datetime import datetime
import argparse
pd.set_option('display.unicode.east_asian_width', True)

# ============================================================================
# 平台检测和路径处理
# ============================================================================
def get_temp_dir():
    """根据操作系统返回临时目录路径"""
    if sys.platform.startswith('win'):
        return r'd:\temp'
    else:
        return '/tmp'

# 确保临时目录存在
temp_dir = get_temp_dir()
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir, exist_ok=True)


def _requests_session_no_proxy() -> requests.Session:
    """Requests session that ignores system HTTP proxy (avoids broken local proxies)."""
    session = requests.Session()
    session.trust_env = False
    return session


# ============================================================================
# 字段映射更新说明
# ============================================================================
# 
# 本文件中的 get_zjlx_complete 函数已基于 em_zjlx_stock.js 
# 重新映射了字段名称，主要更新包括：
# 
# 1. 基础字段映射 (base_f_col_map):
#    - 基于em_zjlx_stock.js重新定义了字段含义
#    - 修正了资金流向字段的准确描述
#    - 添加了板块涨跌名称和代码字段
#    - 统一了字段命名规范
# 
# 2. 扩展字段映射 (extensive_f_col_map):
#    - 基于em_zjlx_stock.js重新定义了字段含义
#    - 添加了时间序列资金流向字段（1日、3日、5日、10日）
#    - 完善了板块信息相关字段
#    - 添加了排名相关字段
# 
# 3. 字段分类优化:
#    - 基础信息: 代码、名称、市场等
#    - 价格数据: 最新价、涨跌幅、涨跌额、详情接口字段等
#    - 成交量: 成交量、成交额、换手率、详情接口字段等
#    - 资金流向: 主力、超大单、大单、中单、小单的净流入和净占比
#    - 时间序列: 1日、3日、5日、10日资金流向数据（em_zjlx_stock.js独有）
#    - 板块信息: 所属行业、概念、地域、板块、指数、板块涨跌名称和代码等
#    - 技术指标: 委比、委差、内盘、外盘、RSI、量比等
#    - 排名信息: 1日、5日、10日主力排名等
# 
# 4. em_zjlx_stock.js特有功能:
#    - 时间序列资金流向分析
#    - 板块涨跌信息
#    - 主力资金排名
#    - 英文字段映射（zlje, zljzb, cddje, cddjzb等）
# 
# 更新日期: 2025-01-28
# 参考文档: stock/em_zjlx_stock_fields_documentation.md
# ============================================================================

def fetch_eastmoney_sections(url: str) -> Dict[str, List[Any]]:
    """
    Fetches the page at the given URL and extracts all important info under each heading.
    Returns a dictionary mapping heading text to a list of content (tables as DataFrames, lists, or text blocks).
    """
    response = requests.get(url)
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, 'lxml')

    sections = {}
    # Find all headings (h1, h2, h3, h4, h5, h6)
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        title = heading.get_text(strip=True)
        content = []
        # Look for the next siblings until the next heading of same or higher level
        for sib in heading.find_next_siblings():
            if sib.name and sib.name.startswith('h') and int(sib.name[1]) <= int(heading.name[1]):
                break
            # Extract tables
            if sib.name == 'table':
                df = pd.read_html(str(sib))[0]
                content.append(df)
            # Extract lists
            elif sib.name in ['ul', 'ol']:
                items = [li.get_text(strip=True) for li in sib.find_all('li')]
                content.append(items)
            # Extract paragraphs or divs with text
            elif sib.name in ['p', 'div']:
                text = sib.get_text(strip=True)
                if text:
                    content.append(text)
        if content:
            sections[title] = content
    return sections

def print_and_append_markdown(sections: Dict[str, List[Any]], md_path: str, url: str):
    """
    Print the extracted sections and append them to a markdown file.
    """
    with open(md_path, 'a', encoding='utf-8') as f:
        f.write(f'\n# Extracted from {url}\n')
        print(f'\n# Extracted from {url}')
        for heading, contents in sections.items():
            f.write(f'\n## {heading}\n')
            print(f"\n=== {heading} ===")
            for c in contents:
                if isinstance(c, pd.DataFrame):
                    md_table = c.to_markdown(index=False)
                    f.write(f'\n{md_table}\n')
                    print(c.head())
                elif isinstance(c, list):
                    for item in c:
                        f.write(f'- {item}\n')
                        print(f'- {item}')
                else:
                    f.write(f'{c}\n')
                    print(c)

def get_zjlx(max_pages=5, sort_by_zlp=True, get_all=False, start_page=1, progress_file=None, initial_total_fetched=0):
    """

    https://data.eastmoney.com/zjlx/detail.html

    获取主力资金流向数据（增强版，包含换手率、板块、概念等字段）
    
    参数:
    max_pages: 最大下载页数，默认5页
    sort_by_zlp: 是否按主力净占比倒序排序，默认True
    get_all: 是否获取所有数据，默认False。如果True，忽略max_pages限制
    
    返回: 包含主力资金流向、换手率、板块、概念等完整数据的DataFrame
    
    数据字段包括:
    - 基本信息: 代码、名称、最新价、涨跌幅
    - 资金流向: 主力/超大单/大单/中单/小单净流入及占比
    - 交易指标: 换手率、市盈率、市净率、振幅
    - 价格信息: 最高价、最低价、开盘价、昨收价
    - 市值信息: 总市值、流通市值
    - 分类信息: 所属行业、概念、地域、板块、指数
    """
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '61',
        'st_psi': '20250725224944108-113300300975-3122995398',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/zjlx/detail.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'qgqp_b_id=625b35069288e7d72e8e0178a24c21da; st_si=45698176550929; fullscreengg=1; fullscreengg2=1; p_origin=https%3A%2F%2Fai.eastmoney.com; mtp=1; ct=ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4; ut=FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U; pi=7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D; uidal=7160094286471412Redtea; sid=125088262; vtpst=|; st_asi=delete; st_pvi=18468462604372; st_sp=2025-07-09%2022%3A43%3A28; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=61; st_psi=20250725224944108-113300300975-3122995398',
    }
    
    # 基础字段映射（标准模式）
    base_f_col_map = {
        "f1": "序号",
        "f12": "代码",
        "f14": "名称",
        "f124": "相关",
        "f2": "最新价",
        "f3": "今日涨跌幅",
        "f5": "成交量",
        "f8": "换手率",        # 换手率
        "f9": "市盈率",        # 市盈率
        "f10": "市净率",       # 市净率
        "f15": "最高价",       # 最高价
        "f16": "最低价",       # 最低价
        "f17": "开盘价",       # 开盘价
        "f18": "昨收价",       # 昨收价
        "f20": "总市值",       # 总市值
        "f21": "流通市值",     # 流通市值
        "f23": "振幅",         # 振幅
        "f62": "主力净流入",   # 主力净流入-净额
        "f184": "主力净占比",  # 主力净流入-净占比
        "f66": "超大单净流入", # 超大单净流入-净额
        "f69": "超大单净占比", # 超大单净流入-净占比
        "f72": "大单净流入",   # 大单净流入-净额
        "f75": "大单净占比",   # 大单净流入-净占比
        "f78": "中单净流入",   # 中单净流入-净额
        "f81": "中单净占比",   # 中单净流入-净占比
        "f84": "小单净流入",   # 小单净流入-净额
        "f87": "小单净占比",   # 小单净流入-净占比
        "f100": "所属行业",    # 所属行业
        "f101": "所属概念",    # 所属概念
        "f102": "所属地域",    # 所属地域
        "f103": "所属板块",    # 所属板块
        "f104": "所属指数",    # 所属指数
        # 新增价格相关字段 - 根据em_server.py中的fieldnames映射
        "f4": "pl3",           # 3日涨跌幅 (pl3)
        "f5": "pl5",           # 5日涨跌幅 (pl5)
        "f6": "pl10",          # 10日涨跌幅 (pl10)
        "f7": "pl20",          # 20日涨跌幅 (pl20)
        "f11": "pl60",         # 60日涨跌幅 (pl60)
        "f19": "pl_year_start", # 年初至今涨跌幅 (pl_year_start)
        "f13": "-",            # 标志位
        "f204": "-",           # 无数据
        "f205": "-",           # 无数据
        "f206": "-",           # 无数据
    }

    # 优化：使用更大的页面大小以减少请求次数
    page_sizes = [200, 100]
    optimal_page_size = 100  # 默认值
    
    # 测试第一个请求，确定最优页面大小
    # print("正在测试最优页面大小...")
    # test_url = f'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery1123009417707123185337_1753454455066&fid=f62&po=1&pz=1000&pn=1&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A13%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A7%2Bf%3A!2%2Cm%3A1%2Bt%3A3%2Bf%3A!2&fields=f12%2Cf14%2Cf2%2Cf3%2Cf8%2Cf9%2Cf10%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf100%2Cf101%2Cf102%2Cf103%2Cf104%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13'
    
    # try:
    #     test_response = requests.get(test_url, cookies=cookies, headers=headers, timeout=30)
    #     test_data = json.loads(test_response.text.strip('jQuery1123009417707123185337_1753454455066(').strip(');'))
        
    #     if 'data' in test_data and 'diff' in test_data['data']:
    #         # 测试成功，尝试更大的页面大小
    #         for page_size in page_sizes:
    #             test_url = f'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery1123009417707123185337_1753454455066&fid=f62&po=1&pz={page_size}&pn=1&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A13%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A7%2Bf%3A!2%2Cm%3A1%2Bt%3A3%2Bf%3A!2&fields=f12%2Cf14%2Cf2%2Cf3%2Cf8%2Cf9%2Cf10%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf100%2Cf101%2Cf102%2Cf103%2Cf104%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13'
                
    #             try:
    #                 test_response = requests.get(test_url, cookies=cookies, headers=headers, timeout=30)
    #                 test_data = json.loads(test_response.text.strip('jQuery1123009417707123185337_1753454455066(').strip(');'))
                    
    #                 if 'data' in test_data and 'diff' in test_data['data'] and len(test_data['data']['diff']) == page_size:
    #                     optimal_page_size = page_size
    #                     print(f"✓ 测试成功：页面大小 {page_size} 可用")
    #                     break
    #                 else:
    #                     print(f"✗ 页面大小 {page_size} 不可用或数据不完整")
    #             except Exception as e:
    #                 print(f"✗ 页面大小 {page_size} 测试失败: {e}")
    #                 continue
    #     else:
    #         print("⚠️  API测试失败，使用默认页面大小100")
            
    # except Exception as e:
    #     print(f"⚠️  页面大小测试失败，使用默认页面大小100: {e}")
    
    # print(f"最终使用页面大小: {optimal_page_size}")
    
    # 根据排序需求调整API参数
    if sort_by_zlp:
        # 按主力净占比倒序排序：fid=f184 (主力净占比字段)
        sort_field = "f184"
        sort_order = "1"  # 1=降序
        print("✓ 按主力净占比倒序排序下载")
    else:
        # 按主力净流入倒序排序：fid=f62 (主力净流入字段)
        sort_field = "f62"
        sort_order = "1"  # 1=降序
        print("✓ 按主力净流入倒序排序下载")
    
    pn=1

    all_data = []
    total_fetched = 0
    first = True
    ttl = None
    pbar = None
    session = requests.Session()
    session.trust_env = False
    page_retries = 3
    while True:
        url0 = f'https://push2delay.eastmoney.com/api/qt/clist/get?cb=jQuery1123009417707123185337_1753454455066&fid={sort_field}&po={sort_order}&pz={optimal_page_size}&pn={pn}&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A13%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A7%2Bf%3A!2%2Cm%3A1%2Bt%3A3%2Bf%3A!2&fields=f12%2Cf14%2Cf2%2Cf3%2Cf8%2Cf9%2Cf10%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf100%2Cf101%2Cf102%2Cf103%2Cf104%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13'
        
        page_ok = False
        last_error = None
        for attempt in range(page_retries):
            try:
                response = session.get(url0, cookies=cookies, headers=headers, timeout=30)
                
                # 保存原始响应用于调试
                if pn == 1 and attempt == 0:  # 只保存第一页的响应用于调试
                    open(os.path.join(temp_dir, 'zjlx.txt'), 'w', encoding='utf8').write(response.text)
                
                data = json.loads(response.text.strip('jQuery1123009417707123185337_1753454455066(').strip(');'))
                
                if first:
                    ttl = data['data']['total']
                    # 根据get_all参数决定是否限制下载数量
                    if get_all:
                        max_items = ttl  # 获取所有数据
                        print(f"✓ 将获取所有 {ttl} 条数据")
                    else:
                        max_items = min(ttl, max_pages * optimal_page_size)  # 限制页数
                        print(f"✓ 限制下载前 {max_pages} 页，约 {max_items} 条数据")
                    
                    pbar = tqdm(total=max_items, desc=f'抓取主力资金流向数据 (页面大小: {optimal_page_size}, 目标: {max_items}条)')
                    first = False
                    
                df = pd.DataFrame(data['data']['diff'])
                all_data.append(df)
                total_fetched += df.shape[0]
                pbar.update(df.shape[0])
                
                # 动态调整延迟时间：页面越大，延迟越短
                delay_time = max(1, 5 - (optimal_page_size // 200))
                time.sleep(delay_time)
                
                # 检查是否达到限制
                if get_all:
                    # 获取所有数据：检查是否已获取完所有数据
                    if total_fetched >= max_items:
                        print(f"\n✓ 已获取所有数据：{total_fetched} 条")
                        page_ok = True
                        break
                else:
                    # 限制页数：检查是否达到最大页数或数据量限制
                    if pn >= max_pages or total_fetched >= max_items:
                        print(f"\n✓ 已达到限制：页数 {pn}/{max_pages}，数据量 {total_fetched}/{max_items}")
                        page_ok = True
                        break
                pn += 1
                page_ok = True
                break
            except Exception as e:
                last_error = e
                if attempt < page_retries - 1:
                    wait = 2 * (attempt + 1)
                    print(f"第{pn}页请求失败({attempt + 1}/{page_retries}): {e}，{wait}s 后重试...")
                    time.sleep(wait)
                else:
                    print(f"第{pn}页请求失败: {e}")
        
        if page_ok and (
            (get_all and total_fetched >= max_items)
            or (not get_all and (pn > max_pages or total_fetched >= max_items))
        ):
            break
        if not page_ok:
            # 如果当前页面大小失败，尝试减小页面大小
            if optimal_page_size > 100:
                optimal_page_size = max(100, optimal_page_size // 2)
                print(f"自动调整页面大小为: {optimal_page_size}")
                continue
            print("页面大小已降至最小值100，无法继续")
            break
    
    # 关闭进度条
    if pbar is not None:
        pbar.close()
    
    if not all_data:
        raise RuntimeError('未能获取任何主力资金流向数据')

    df2=pd.concat(all_data, ignore_index=True)
    if ttl and len(df2) < ttl * 0.95:
        print(f"⚠ 数据不完整: 仅获取 {len(df2)}/{ttl} 条，请稍后重试")
    
    # 应用字段映射，自动处理未知字段
    mapped_columns = []
    unknown_fields = []
    
    for c in df2.columns:
        if c in base_f_col_map:
            mapped_columns.append(base_f_col_map[c])
        else:
            # 对于未知字段，自动生成名称
            mapped_columns.append(f"未知字段_{c}")
            unknown_fields.append(c)
    
    # 显示发现的未知字段
    if unknown_fields:
        print(f"\n⚠️  发现 {len(unknown_fields)} 个未知字段:")
        for field in unknown_fields:
            print(f"  {field} -> 未知字段_{field}")
        print("建议将这些字段添加到字段映射中以提高数据可读性")
    
    df2.columns = mapped_columns
    
    # 数据清洗和格式化，与get_zjlx_complete保持一致
    # 处理换手率字段，确保数值类型
    if '换手率' in df2.columns:
        df2['换手率'] = pd.to_numeric(df2['换手率'], errors='coerce')
        df2['换手率'] = df2['换手率'].fillna(0)
    
    # 处理市盈率字段
    if '市盈率' in df2.columns:
        df2['市盈率'] = pd.to_numeric(df2['市盈率'], errors='coerce')
        df2['市盈率'] = df2['市盈率'].fillna(0)
    
    # 处理市净率字段
    if '市净率' in df2.columns:
        df2['市净率'] = pd.to_numeric(df2['市净率'], errors='coerce')
        df2['市净率'] = df2['市净率'].fillna(0)
    
    # 处理板块和概念字段，清理和格式化
    if '所属行业' in df2.columns:
        df2['所属行业'] = df2['所属行业'].fillna('未知').astype(str)
        # 清理行业名称，去除多余字符
        df2['所属行业'] = df2['所属行业'].str.replace('None', '未知').str.strip()
    
    if '所属概念' in df2.columns:
        df2['所属概念'] = df2['所属概念'].fillna('无').astype(str)
        # 清理概念名称，去除多余字符
        df2['所属概念'] = df2['所属概念'].str.replace('None', '无').str.strip()
    
    if '所属地域' in df2.columns:
        df2['所属地域'] = df2['所属地域'].fillna('未知').astype(str)
        df2['所属地域'] = df2['所属地域'].str.replace('None', '未知').str.strip()
    
    if '所属板块' in df2.columns:
        df2['所属板块'] = df2['所属板块'].fillna('无').astype(str)
        df2['所属板块'] = df2['所属板块'].str.replace('None', '无').str.strip()
    
    if '所属指数' in df2.columns:
        df2['所属指数'] = df2['所属指数'].fillna('无').astype(str)
        df2['所属指数'] = df2['所属指数'].str.replace('None', '无').str.strip()
    
    tstr = datetime.now().strftime('%y%m%d%H%M')
    # 生成文件名，包含排序信息
    sort_suffix = "zlp" if sort_by_zlp else "zlb"
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    filename = f'../generated/em/{dte_short}/zjlx_{sort_suffix}_{tstr}.csv'
    df2.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"主力资金流向数据已保存到: {filename}")
    print(f"数据总量: {len(df2)} 条")
    print(f"排序方式: {'主力净占比倒序' if sort_by_zlp else '主力净流入倒序'}")
    print(f"下载页数: {pn} 页")
    if get_all:
        print(f"✓ 已获取所有可用数据")
    else:
        print(f"✓ 限制下载前 {max_pages} 页数据")
    print(f"包含字段: {list(df2.columns)}")
    
    # # 显示排序字段的统计信息
    # if sort_by_zlp and '主力净占比' in df2.columns:
    #     print(f"\n主力净占比统计:")
    #     print(f"最高净占比: {df2['主力净占比'].max():.2f}%")
    #     print(f"最低净占比: {df2['主力净占比'].min():.2f}%")
    #     print(f"平均净占比: {df2['主力净占比'].mean():.2f}%")
    # elif not sort_by_zlp and '主力净流入' in df2.columns:
    #     print(f"\n主力净流入统计:")
    #     print(f"最高净流入: {df2['主力净流入'].max():,.0f} 元")
    #     print(f"最低净流入: {df2['主力净流入'].min():,.0f} 元")
    #     print(f"平均净流入: {df2['主力净流入'].mean():,.0f} 元")
    
    # # 显示板块和概念统计信息
    # if '所属行业' in df2.columns:
    #     industry_counts = df2['所属行业'].value_counts().head(10)
    #     print(f"\n行业分布 (前10):")
    #     for industry, count in industry_counts.items():
    #         print(f"  {industry}: {count} 只")
    
    # if '所属概念' in df2.columns:
    #     concept_counts = df2['所属概念'].value_counts().head(10)
    #     print(f"\n概念分布 (前10):")
    #     for concept, count in concept_counts.items():
    #         print(f"  {concept}: {count} 只")
    
    # if '所属地域' in df2.columns:
    #     region_counts = df2['所属地域'].value_counts().head(10)
    #     print(f"\n地域分布 (前10):")
    #     for region, count in region_counts.items():
    #         print(f"  {region}: {count} 只")
    
    # # 显示数据预览
    # print("\n数据预览（前5条）:")
    # print(df2.head().to_string())
    
    # 生成资金流向报告
    tstr = datetime.now().strftime('%y%m%d%H%M')
    sort_suffix = "zlp" if sort_by_zlp else "zlb"
    dte_short = datetime.now().strftime('%y%m%d')
    input_filename = f'../generated/em/{dte_short}/zjlx_{sort_suffix}_{tstr}.csv'
    report_filename = f'../generated/em/{dte_short}/flow_{tstr}.csv'
    
    try:
        gen_z_report(input_filename, report_filename)
    except Exception as e:
        print(f"⚠️ 生成资金流向报告时出错: {e}")
    
    # 调用 queryFlow 分析资金流向数据（无论 gen_z_report 是否成功）
    try:
        print(f"\n开始分析资金流向数据...")
        queryFlow(input_filename)
    except Exception as e:
        print(f"⚠️ 分析资金流向数据时出错: {e}")
    
    return df2

def print_sector_statistics(top_sectors):
    """打印板块统计信息"""
    print(f"\n板块主力净占比统计 (前{len(top_sectors)}名):")
    print("=" * 100)
    print(f"{'排名':<4} {'板块名称':<20} {'平均净占比':<12} {'股票数量':<10} {'平均换手率':<12} {'标准差':<10}")
    print("=" * 100)
    
    for i, (sector, row) in enumerate(top_sectors.iterrows(), 1):
        zlp = row['平均主力净占比']
        count = row['股票数量']
        tov = row['平均换手率']
        std = row['主力净占比标准差']
        
        # 根据净占比添加颜色标识
        if zlp > 0:
            color_indicator = "🔴"  # 红色表示正流入
        elif zlp < 0:
            color_indicator = "🟢"  # 绿色表示负流入
        else:
            color_indicator = "⚪"  # 白色表示中性
        
        print(f"{i:<4} {sector:<20} {zlp:>8.2f}% {count:>8} {tov:>10.2f}% {std:>8.2f} {color_indicator}")
    
    print("=" * 100)
    print(f"🔴 红色: 主力净流入 (正占比)")
    print(f"🔴 绿色: 主力净流出 (负占比)")
    print(f"⚪ 白色: 中性 (零占比)")

def get_zjlx_all(sort_by_zlp=True):
    """
    获取所有主力资金流向数据（完整版）
    
    参数:
    sort_by_zlp: 是否按主力净占比倒序排序，默认True
    
    返回: 包含所有主力资金流向数据的DataFrame
    """
    print("🚀 开始获取所有主力资金流向数据...")
    return get_zjlx(max_pages=999, sort_by_zlp=sort_by_zlp, get_all=False)


def get_zjlx_zlb_all():
    """
    获取全市场主力资金流向（按主力净流入排序，zjlx_zlb 文件）。
    含所属行业/概念等字段，供板块分组等场景使用。
    """
    print("🚀 开始获取全市场 zjlx_zlb 数据（按主力净流入排序）...")
    return get_zjlx(max_pages=999, sort_by_zlp=False, get_all=False)


def find_latest_zjlx_zlb_file(prefer_today: bool = True) -> Optional[str]:
    """Return path to the newest zjlx_zlb CSV, preferring today's trading folder."""
    import glob

    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pattern = os.path.join(parent_dir, 'generated/em/*/zjlx_zlb_*.csv')
    files = glob.glob(pattern)
    if not files:
        return None

    if prefer_today:
        today = datetime.now().strftime('%y%m%d')
        today_files = [p for p in files if f'/em/{today}/' in p.replace('\\', '/')]
        if today_files:
            return max(today_files, key=os.path.getmtime)

    return max(files, key=os.path.getmtime)

def get_zjlx_complete(max_pages=10, sort_by_tov=True, extensive=False):
    """
    获取主力资金流向数据（包含换手率、板块、概念等完整信息）
    增强版：在原有主力资金流向数据基础上，增加换手率、板块、概念、地域等完整指标
    
    注意：字段映射已基于 em_zjlx_stock.js 重新优化，提供更准确的字段名称和描述
    
    参数:
    max_pages: 最大下载页数，默认10页
    sort_by_tov: 是否按换手率倒序排序，默认True
    extensive: 是否获取所有可能的字段，默认False。如果True，将包含更多技术指标、财务指标等字段
    
    返回: 包含主力资金流向、交易活跃度、板块概念等完整数据的DataFrame
    
    主要字段分类（基于em_zjlx_stock.js）:
    - 基础信息: 代码、名称、市场等
    - 价格数据: 最新价、涨跌幅、涨跌额、最新价详情、涨跌额详情、涨跌幅详情等
    - 成交量: 成交量、成交额、换手率、成交额详情、换手率详情等
    - 资金流向: 主力、超大单、大单、中单、小单的净流入和净占比
    - 时间序列: 1日、3日、5日、10日资金流向数据（em_zjlx_stock.js独有）
    - 板块信息: 所属行业、概念、地域、板块、指数、板块涨跌名称和代码等
    - 技术指标: 委比、委差、内盘、外盘、RSI、量比等
    - 排名信息: 1日、5日、10日主力排名等
    """
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '61',
        'st_psi': '20250725224944108-113300300975-3122995398',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/zjlx/detail.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    
    # 基础字段映射（标准模式）- 基于em_zjlx_stock.js重新映射
    base_f_col_map = {
        # 基础信息字段
        "f1": "价格精度",           # 价格小数位数
        "f12": "代码",              # 股票代码
        "f13": "市场",              # 交易市场代码
        "f14": "名称",              # 股票名称
        "f124": "相关",             # 相关标识
        
        # 价格相关字段
        "f2": "最新价",             # 当前最新价格
        "f3": "涨跌幅",             # 涨跌百分比
        "f4": "涨跌额",             # 涨跌金额
        "f5": "成交量",
        "f10": "量比",
        "f15": "最高",
        "f16": "最低",
        "f17": "开盘",
        "f18": "昨收",
        "f20": "市值",
        "f21": "流通",
        "f43": "最新价详情",        # 最新价格（详情接口）
        "f169": "涨跌额详情",       # 涨跌金额（详情接口）
        "f170": "涨跌幅详情",       # 涨跌百分比（详情接口）
        "f152": "涨跌精度",         # 涨跌幅小数位数
        
        # 成交量相关字段
        "f6": "成交额",             # 成交金额
        "f8": "换手率",             # 换手率
        "f47": "成交量",            # 成交数量
        "f48": "成交额详情",        # 成交金额（详情接口）
        "f168": "换手率详情",       # 换手率（详情接口）
        
        # 资金流向字段 - 基于em_zjlx_stock.js的准确映射
        "f62": "主力净流入",        # 主力资金净流入 (zlje)
        "f184": "主力净占比",       # 主力净流入占比 (zljzb)
        "f66": "超大单净流入",      # 超大单资金净流入 (cddje)
        "f69": "超大单净占比",      # 超大单净流入占比 (cddjzb)
        "f72": "大单净流入",        # 大单资金净流入 (ddje)
        "f75": "大单净占比",        # 大单净流入占比 (ddjzb)
        "f78": "中单净流入",        # 中单资金净流入 (zdje)
        "f81": "中单净占比",        # 中单净流入占比 (zdjzb)
        "f84": "小单净流入",        # 小单资金净流入 (xdje)
        "f87": "小单净占比",        # 小单净流入占比 (xdjzb)
        
        # 板块信息字段
        "f100": "所属行业",         # 所属行业
        "f101": "所属概念",         # 所属概念
        "f102": "所属地域",         # 所属地域
        "f103": "所属板块",         # 所属板块
        "f104": "所属指数",         # 所属指数
        "f204": "涨跌名称",         # 板块涨跌名称 (zdname)
        "f205": "涨跌代码",         # 板块涨跌代码 (zdcode)
        
        # 市场统计字段
        "f104": "上涨家数",         # 上涨股票数量
        "f105": "下跌家数",         # 下跌股票数量
        "f106": "平盘家数",         # 平盘股票数量
    }
    
    # 扩展字段映射（extensive=True时使用）- 基于em_zjlx_stock.js重新映射
    extensive_f_col_map = {
        # 技术指标字段
        "f22": "市盈率",                    # 市盈率
        "f25": "市净率",                    # 市净率
        "f26": "市销率",                    # 市销率
        "f27": "市现率",                    # 市现率
        "f28": "内盘",                    # 内盘
        "f29": "总手",                    # 总手数
        "f30": "现手",                    # 现手数
        "f31": "每股收益",                # 每股收益
        "f32": "每股净资产",              # 每股净资产
        "f33": "净资产收益率ROE",         # ROE
        "f34": "毛利率",                  # 毛利率
        "f35": "净利率",                  # 净利率
        "f36": "资产负债率",              # 资产负债率
        "f37": "52周最高价",              # 52周最高价
        "f38": "52周最低价",              # 52周最低价
        "f39": "卖出价",                  # 卖一价
        "f40": "年内最低价",              # 年内最低价
        "f41": "上市天数",                # 上市天数
        "f42": "总股本",                  # 总股本
        
        # 资金流向扩展字段 - 基于em_zjlx_stock.js
        "f43": "最新价详情",              # 最新价格（详情接口）
        "f44": "最高价",                  # 当日最高价
        "f45": "最低价",                  # 当日最低价
        "f46": "今开",                    # 今日开盘价
        "f47": "成交量",                  # 成交数量
        "f48": "成交额详情",              # 成交金额（详情接口）
        "f49": "量比",                    # 量比
        
        # 行业对比字段
        "f50": "行业排名",                # 行业排名
        "f51": "涨停价",                  # 涨停价格
        "f52": "跌停价",                  # 跌停价格
        "f53": "概念排名",                # 概念排名
        "f54": "概念涨跌幅",              # 概念涨跌幅
        "f55": "概念换手率",              # 概念换手率
        
        # 更多技术指标
        "f56": "RSI",                     # RSI指标
        "f57": "代码详情",                # 股票代码（详情接口）
        "f58": "名称详情",                # 股票名称（详情接口）
        "f59": "价格精度详情",            # 价格精度
        "f60": "昨收",                    # 昨日收盘价
        
        # 成交量相关
        "f61": "成交量",                  # 成交量
        "f62": "成交额",                  # 成交额
        "f63": "量比",                    # 量比
        "f64": "换手率",                  # 换手率
        
        # 更多财务指标
        "f65": "营收增长率",              # 营收增长率
        "f66": "净利润增长率",            # 净利润增长率
        "f67": "毛利率",                  # 毛利率
        "f68": "净利率",                  # 净利率
        "f69": "超大单净占比",            # 超大单净流入占比
        "f70": "ROA",                     # 总资产收益率
        
        # 市场表现
        "f71": "年内涨幅",                # 年内涨幅
        "f72": "大单净占比",              # 大单净流入占比
        "f73": "年内换手率",              # 年内换手率
        "f74": "年内成交量",              # 年内成交量
        
        # 基于em_zjlx_stock.js的字段映射
        "f75": "大单净占比",              # 大单净流入占比
        "f76": "中单净占比",              # 中单净流入占比
        "f77": "小单净占比",              # 小单净流入占比
        "f78": "中单净流入",              # 中单资金净流入
        "f79": "中单净占比",              # 中单净流入占比
        "f80": "小单净流入",              # 小单资金净流入
        "f81": "中单净占比",              # 中单净流入占比
        "f82": "小单净流入",              # 小单资金净流入
        "f83": "小单净占比",              # 小单净流入占比
        "f84": "小单净流入",              # 小单资金净流入
        "f85": "小单净占比",              # 小单净流入占比
        "f86": "交易时间",                # 最后交易时间
        "f87": "小单净占比",              # 小单净流入占比
        "f88": "小单净流入",              # 小单资金净流入
        "f89": "小单净占比",              # 小单净流入占比
        "f90": "小单净流入",              # 小单资金净流入
        "f91": "小单净占比",              # 小单净流入占比
        "f92": "每股净资产",              # 每股净资产
        "f93": "小单净流入",              # 小单资金净流入
        "f94": "小单净占比",              # 小单净流入占比
        "f95": "小单净流入",              # 小单资金净流入
        "f96": "小单净占比",              # 小单净流入占比
        "f97": "小单净流入",              # 小单资金净流入
        "f98": "小单净占比",              # 小单净流入占比
        "f99": "小单净流入",              # 小单资金净流入
        "f100": "所属行业",               # 所属行业
        "f101": "所属概念",               # 所属概念
        "f102": "所属地域",               # 所属地域
        "f103": "所属板块",               # 所属板块
        "f104": "所属指数",               # 所属指数
        "f105": "主力流出",               # 主力资金流出
        "f106": "主力净流入",             # 主力资金净流入
        "f107": "主力净流入",             # 主力资金净流入
        "f108": "每股收益TTM",            # 每股收益（滚动12个月）
        "f109": "小单净占比",             # 小单净流入占比
        "f110": "小单净流入",             # 小单资金净流入
        "f111": "小单净占比",             # 小单净流入占比
        "f112": "小单净流入",             # 小单资金净流入
        "f113": "小单净占比",             # 小单净流入占比
        "f114": "小单净流入",             # 小单资金净流入
        "f115": "小单净占比",             # 小单净流入占比
        "f116": "总市值",                 # 总市值
        "f117": "流通市值",               # 流通市值
        "f118": "小单净占比",             # 小单净流入占比
        "f119": "小单净流入",             # 小单资金净流入
        "f120": "小单净占比",             # 小单净流入占比
        "f121": "小单净流入",             # 小单资金净流入
        "f122": "小单净占比",             # 小单净流入占比
        "f123": "小单净流入",             # 小单资金净流入
        "f124": "相关",                   # 相关标识
        "f125": "小单净占比",             # 小单净流入占比
        "f126": "小单净流入",             # 小单资金净流入
        "f127": "小单净占比",             # 小单净流入占比
        "f128": "小单净流入",             # 小单资金净流入
        "f129": "小单净占比",             # 小单净流入占比
        "f130": "小单净流入",             # 小单资金净流入
        "f131": "小单净占比",             # 小单净流入占比
        "f132": "小单净流入",             # 小单资金净流入
        "f133": "小单净占比",             # 小单净流入占比
        "f134": "小单净流入",             # 小单资金净流入
        "f135": "主力流入",               # 主力资金流入
        "f136": "主力流出",               # 主力资金流出
        "f137": "主力净流入",             # 主力资金净流入
        "f138": "超大单流入",             # 超大单资金流入
        "f139": "超大单流出",             # 超大单资金流出
        "f140": "超大单净流入",           # 超大单资金净流入
        "f141": "大单流入",               # 大单资金流入
        "f142": "大单流出",               # 大单资金流出
        "f143": "大单净流入",             # 大单资金净流入
        "f144": "中单流入",               # 中单资金流入
        "f145": "中单流出",               # 中单资金流出
        "f146": "中单净流入",             # 中单资金净流入
        "f147": "小单流入",               # 小单资金流入
        "f148": "小单流出",               # 小单资金流出
        "f149": "小单净流入",             # 小单资金净流入
        "f150": "小单净占比",             # 小单净流入占比
        "f151": "小单净流入",             # 小单资金净流入
        "f152": "涨跌精度",               # 涨跌幅小数位数
        "f153": "小单净占比",             # 小单净流入占比
        "f154": "行业代码",               # 所属行业代码
        "f155": "小单净流入",             # 小单资金净流入
        "f156": "小单净占比",             # 小单净流入占比
        "f157": "小单净流入",             # 小单资金净流入
        "f158": "小单净占比",             # 小单净流入占比
        "f159": "小单净流入",             # 小单资金净流入
        "f160": "小单净占比",             # 小单净流入占比
        
        # 基于em_zjlx_stock.js的时间序列字段
        "f109": "涨跌幅_5日",             # 5日涨跌幅
        "f127": "涨跌幅_1日",             # 1日涨跌幅
        "f160": "涨跌幅_10日",            # 10日涨跌幅
        
        # 时间序列资金流向字段 - em_zjlx_stock.js独有
        # 1日资金流向数据
        "f267": "主力净流入_1日",         # 1日主力净流入
        "f268": "主力净占比_1日",         # 1日主力净占比
        "f269": "超大单净流入_1日",       # 1日超大单净流入
        "f270": "超大单净占比_1日",       # 1日超大单净占比
        "f271": "大单净流入_1日",         # 1日大单净流入
        "f272": "大单净占比_1日",         # 1日大单净占比
        "f273": "中单净流入_1日",         # 1日中单净流入
        "f274": "中单净占比_1日",         # 1日中单净占比
        "f275": "小单净流入_1日",         # 1日小单净流入
        "f276": "小单净占比_1日",         # 1日小单净占比
        
        # 3日资金流向数据
        "f164": "主力净流入_3日",         # 3日主力净流入
        "f165": "主力净占比_3日",         # 3日主力净占比
        "f166": "超大单净流入_3日",       # 3日超大单净流入
        "f167": "超大单净占比_3日",       # 3日超大单净占比
        "f168": "大单净流入_3日",         # 3日大单净流入
        "f169": "大单净占比_3日",         # 3日大单净占比
        "f170": "中单净流入_3日",         # 3日中单净流入
        "f171": "中单净占比_3日",         # 3日中单净占比
        "f172": "小单净流入_3日",         # 3日小单净流入
        "f173": "小单净占比_3日",         # 3日小单净占比
        
        # 10日资金流向数据
        "f174": "主力净流入_10日",        # 10日主力净流入
        "f175": "主力净占比_10日",        # 10日主力净占比
        "f176": "超大单净流入_10日",      # 10日超大单净流入
        "f177": "超大单净占比_10日",      # 10日超大单净占比
        "f178": "大单净流入_10日",        # 10日大单净流入
        "f179": "大单净占比_10日",        # 10日大单净占比
        "f180": "中单净流入_10日",        # 10日中单净流入
        "f181": "中单净占比_10日",        # 10日中单净占比
        "f182": "小单净流入_10日",        # 10日小单净流入
        "f183": "小单净占比_10日",        # 10日小单净占比
        
        # 板块信息字段 - em_zjlx_stock.js独有
        "f257": "涨跌名称_1日",           # 1日板块涨跌名称
        "f258": "涨跌代码_1日",           # 1日板块涨跌代码
        "f260": "涨跌名称_10日",          # 10日板块涨跌名称
        "f261": "涨跌代码_10日",          # 10日板块涨跌代码
        
        # 排名相关字段
        "f225": "主力排名_1日",           # 1日主力排名
        "f263": "主力排名_5日",           # 5日主力排名
        "f264": "主力排名_10日",          # 10日主力排名
        
        # 其他未知字段（避免KeyError）
        "f252": "未知字段252",            # 避免KeyError
        "f253": "未知字段253",            # 避免KeyError
        "f254": "未知字段254",            # 避免KeyError
        "f255": "未知字段255",            # 避免KeyError
        "f256": "未知字段256",            # 避免KeyError
        "f278": "未知字段278",            # 避免KeyError
        "f279": "未知字段279",            # 避免KeyError
        "f280": "未知字段280",            # 避免KeyError
        "f281": "未知字段281",            # 避免KeyError
        "f282": "未知字段282",            # 避免KeyError
    }
    
    # 根据extensive参数选择字段映射
    if extensive:
        f_col_map = {**base_f_col_map, **extensive_f_col_map}
        print("✓ 使用扩展模式：包含所有可能的字段")
    else:
        f_col_map = base_f_col_map
        print("✓ 使用标准模式：包含核心字段")

    # 优化：使用更大的页面大小以减少请求次数
    # 测试不同的页面大小，找到最优值
    page_sizes = [200, 100]
    optimal_page_size = 100  # 默认值
    
    try:
        pn = 1
        all_data = []
        total_fetched = 0
        first = True
        ttl = None
        pbar = None
        
        # 根据排序需求调整API参数
        if sort_by_tov:
            # 按换手率倒序排序：fid=f8 (换手率字段)
            sort_field = "f8"
            sort_order = "1"  # 0=降序，1=升序
            print("✓ 按换手率倒序排序下载")
        else:
            # 按主力净流入倒序排序：fid=f62 (主力净流入字段)
            sort_field = "f62"
            sort_order = "1"  # 1=降序
            print("✓ 按主力净流入倒序排序下载")
        
        while True:
            # 根据extensive参数构建不同的fields参数
            if extensive:
                # 扩展模式：包含所有可能的字段
                fields = "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f15,f16,f17,f18,f19,f20,f21,f22,f23,f25,f26,f27,f28,f29,f30,f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f100,f101,f102,f103,f104,f124,f146,f147,f148,f149,f150,f151,f152,f153,f154,f155,f156,f157,f158,f159,f160,f184,f204,f205"
            else:
                # 标准模式：包含核心字段
                fields = "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f15,f16,f17,f18,f19,f20,f21,f23,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f100,f101,f102,f103,f104,f124,f1,f13"
            
            # 使用最优页面大小构建URL，根据排序需求调整fid和po参数，包含板块概念字段和价格相关字段
            url0 = f'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery1123009417707123185337_1753454455066&fid={sort_field}&po={sort_order}&pz={optimal_page_size}&pn={pn}&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A13%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A7%2Bf%3A!2%2Cm%3A1%2Bt%3A3%2Bf%3A!2&fields={fields}'
            
            try:
                response = requests.get(url0, cookies=cookies, headers=headers, timeout=30)
                
                # 检查HTTP状态码
                response.raise_for_status()
                
                # 保存原始响应用于调试
                if pn == 1:  # 只保存第一页的响应用于调试
                    try:
                        with open(os.path.join(temp_dir, 'zjlx_with_tov.txt'), 'w', encoding='utf8') as f:
                            f.write(response.text)
                    except Exception as debug_e:
                        print(f"⚠️ 调试文件保存失败: {debug_e}")
                
                # 检查响应内容是否为空
                if not response.text.strip():
                    raise ValueError("API返回空响应")
                
                # 尝试解析JSON响应
                try:
                    # 处理jQuery回调格式
                    if response.text.startswith('jQuery') and '(' in response.text and ')' in response.text:
                        # 提取JSON部分
                        start_idx = response.text.find('(') + 1
                        end_idx = response.text.rfind(')')
                        json_str = response.text[start_idx:end_idx]
                        data = json.loads(json_str)
                    else:
                        # 直接解析JSON
                        data = json.loads(response.text)
                except json.JSONDecodeError as json_e:
                    print(f"⚠️ JSON解析失败: {json_e}")
                    print(f"响应内容预览: {response.text[:200]}...")
                    raise ValueError(f"API响应格式错误: {json_e}")
                
                # 验证数据结构
                if not isinstance(data, dict):
                    raise ValueError("API响应不是有效的字典格式")
                
                if 'data' not in data:
                    raise ValueError("API响应缺少'data'字段")
                
                if 'diff' not in data['data']:
                    raise ValueError("API响应缺少'diff'字段")
                
                if not isinstance(data['data']['diff'], list):
                    raise ValueError("API响应'diff'字段不是列表格式")
                
                if first:
                    ttl = data['data'].get('total', 0)
                    if ttl == 0:
                        print("⚠️ API返回总数为0，可能没有数据")
                        break
                    
                    # 限制最大下载数量
                    max_items = min(ttl, max_pages * optimal_page_size)
                    pbar = tqdm(total=max_items, desc=f'抓取主力资金流向+换手率数据 (页面大小: {optimal_page_size}, 最大: {max_items}条)')
                    first = False
                    
                # 检查当前页数据是否为空
                if not data['data']['diff']:
                    print(f"⚠️ 第{pn}页数据为空，跳过")
                    pn += 1
                    continue
                    
                df = pd.DataFrame(data['data']['diff'])
                all_data.append(df)
                total_fetched += df.shape[0]
                pbar.update(df.shape[0])
                
                # 动态调整延迟时间：页面越大，延迟越短
                delay_time = max(1, 5 - (optimal_page_size // 200))  # 页面大小越大，延迟越短
                time.sleep(delay_time)
                
                # 检查是否达到最大页数或数据量限制
                if pn >= max_pages or total_fetched >= max_items:
                    print(f"\n✓ 已达到限制：页数 {pn}/{max_pages}，数据量 {total_fetched}/{max_items}")
                    break
                pn += 1
            
            except requests.exceptions.Timeout:
                print(f"⚠️ 第{pn}页请求超时，重试中...")
                time.sleep(5)  # 等待5秒后重试
                continue
                
            except requests.exceptions.ConnectionError as conn_e:
                print(f"⚠️ 第{pn}页连接错误: {conn_e}")
                print("检查网络连接，等待10秒后重试...")
                time.sleep(10)
                continue
                
            except requests.exceptions.HTTPError as http_e:
                print(f"⚠️ 第{pn}页HTTP错误: {http_e}")
                if response.status_code == 429:  # 请求过于频繁
                    print("API请求过于频繁，等待30秒后重试...")
                    time.sleep(30)
                    continue
                elif response.status_code >= 500:  # 服务器错误
                    print("服务器错误，等待15秒后重试...")
                    time.sleep(15)
                    continue
                else:
                    print(f"HTTP错误，跳过第{pn}页")
                    pn += 1
                    continue
                    
            except (ValueError, KeyError) as data_e:
                print(f"⚠️ 第{pn}页数据格式错误: {data_e}")
                print("尝试减小页面大小...")
                if optimal_page_size > 100:
                    optimal_page_size = max(100, optimal_page_size // 2)
                    print(f"自动调整页面大小为: {optimal_page_size}")
                    continue
                else:
                    print("页面大小已降至最小值100，无法继续")
                    break
                    
            except Exception as e:
                print(f"⚠️ 第{pn}页未知错误: {e}")
                print(f"错误类型: {type(e).__name__}")
                
                # 如果当前页面大小失败，尝试减小页面大小
                if optimal_page_size > 100:
                    optimal_page_size = max(100, optimal_page_size // 2)
                    print(f"自动调整页面大小为: {optimal_page_size}")
                    continue
                else:
                    print("页面大小已降至最小值100，无法继续")
                    break
    
    except Exception as main_e:
        print(f"⚠️ 主要执行过程中出现错误: {main_e}")
        print(f"错误类型: {type(main_e).__name__}")
        
        # 如果有进度条，关闭它
        if pbar is not None:
            pbar.close()
        
        # 如果有部分数据，尝试处理
        if all_data:
            print("尝试处理已获取的部分数据...")
        else:
            print("没有获取到任何数据，返回None")
            return None
    
    # 关闭进度条
    if pbar is not None:
        pbar.close()
    
    # 检查是否有数据
    if not all_data:
        print("⚠️ 没有获取到任何数据")
        return None
    
    # 合并所有分页数据
    try:
        df2 = pd.concat(all_data, ignore_index=True)
    except Exception as concat_e:
        print(f"⚠️ 数据合并失败: {concat_e}")
        return None
    
    # 应用字段映射，自动处理未知字段
    mapped_columns = []
    unknown_fields = []
    
    for c in df2.columns:
        if c in f_col_map:
            mapped_columns.append(f_col_map[c])
        else:
            # 对于未知字段，自动生成名称
            mapped_columns.append(f"未知字段_{c}")
            unknown_fields.append(c)
    
    # 显示发现的未知字段
    if unknown_fields:
        print(f"\n⚠️  发现 {len(unknown_fields)} 个未知字段:")
        for field in unknown_fields:
            print(f"  {field} -> 未知字段_{field}")
        print("建议将这些字段添加到字段映射中以提高数据可读性")
    
    df2.columns = mapped_columns
    
    # 数据清洗和格式化
    try:
        # 处理换手率字段，确保数值类型
        if '换手率' in df2.columns:
            df2['换手率'] = pd.to_numeric(df2['换手率'], errors='coerce')
            df2['换手率'] = df2['换手率'].fillna(0)
        
        # 处理市盈率字段
        if '市盈率' in df2.columns:
            df2['市盈率'] = pd.to_numeric(df2['市盈率'], errors='coerce')
            df2['市盈率'] = df2['市盈率'].fillna(0)
        
        # 处理市净率字段
        if '市净率' in df2.columns:
            df2['市净率'] = pd.to_numeric(df2['市净率'], errors='coerce')
            df2['市净率'] = df2['市净率'].fillna(0)
        
        # 处理新增的价格相关字段
        price_fields = ['pl3', 'pl5', 'pl10', 'pl20', 'pl60', 'pl_year_start']
        for field in price_fields:
            if field in df2.columns:
                df2[field] = pd.to_numeric(df2[field], errors='coerce')
                df2[field] = df2[field].fillna(0)
                
                # 根据字段类型进行不同的处理
                if field in ['pl3', 'pl20', 'pl60', 'pl_year_start']:
                    # 这些字段通常是百分比，需要除以100
                    df2[field] = df2[field] / 100
                elif field in ['pl5', 'pl10']:
                    # 这些字段可能是原始数值，不需要额外处理
                    # 或者如果值过大，可能需要除以1000或10000
                    if df2[field].max() > 1000:  # 如果最大值超过1000，说明需要处理
                        df2[field] = df2[field] / 10000  # 尝试除以10000
                    elif df2[field].max() > 100:  # 如果最大值超过100，说明需要处理
                        df2[field] = df2[field] / 1000   # 尝试除以1000
        
        # 处理扩展模式下的技术指标字段
        if extensive:
            # 处理百分比字段（需要除以100）
            percentage_fields = ['量比', '委比', '委差', 'RSI', 'MACD', 'KDJ', '威廉指标', '毛利率', '净利率', 'ROE', 'ROA']
            for field in percentage_fields:
                if field in df2.columns:
                    df2[field] = pd.to_numeric(df2[field], errors='coerce')
                    df2[field] = df2[field].fillna(0)
                    if field in ['量比', '委比', '委差', 'RSI', 'MACD', 'KDJ', '威廉指标']:
                        df2[field] = df2[field] / 100
            
            # 处理价格字段（需要除以1000或10000）
            price_extended_fields = ['52周最高', '52周最低', '年内最高', '年内最低', '每股收益', '每股净资产']
            for field in price_extended_fields:
                if field in df2.columns:
                    df2[field] = pd.to_numeric(df2[field], errors='coerce')
                    df2[field] = df2[field].fillna(0)
                    if field in ['每股收益', '每股净资产']:
                        df2[field] = df2[field] / 10000  # 每股数据通常需要除以10000
                    else:
                        df2[field] = df2[field] / 1000   # 价格数据通常需要除以1000
            
            # 处理整数字段
            integer_fields = ['外盘', '内盘', '总手', '现手', '上市天数', '总股本', '成交量', '成交额']
            for field in integer_fields:
                if field in df2.columns:
                    df2[field] = pd.to_numeric(df2[field], errors='coerce')
                    df2[field] = df2[field].fillna(0)
        
        # 处理板块和概念字段，清理和格式化
        if '所属行业' in df2.columns:
            df2['所属行业'] = df2['所属行业'].fillna('未知').astype(str)
            # 清理行业名称，去除多余字符
            df2['所属行业'] = df2['所属行业'].str.replace('None', '未知').str.strip()
        
        if '所属概念' in df2.columns:
            df2['所属概念'] = df2['所属概念'].fillna('无').astype(str)
            # 清理概念名称，去除多余字符
            df2['所属概念'] = df2['所属概念'].str.replace('None', '无').str.strip()
        
        if '所属地域' in df2.columns:
            df2['所属地域'] = df2['所属地域'].fillna('未知').astype(str)
            df2['所属地域'] = df2['所属地域'].str.replace('None', '未知').str.strip()
        
        if '所属板块' in df2.columns:
            df2['所属板块'] = df2['所属板块'].fillna('无').astype(str)
            df2['所属板块'] = df2['所属板块'].str.replace('None', '无').str.strip()
        
        if '所属指数' in df2.columns:
            df2['所属指数'] = df2['所属指数'].fillna('无').astype(str)
            df2['所属指数'] = df2['所属指数'].str.replace('None', '无').str.strip()
            
    except Exception as data_processing_e:
        print(f"⚠️ 数据处理过程中出现错误: {data_processing_e}")
        print("继续处理，但某些字段可能未正确格式化")
    
    # 生成时间戳文件名并保存数据
    try:
        tstr = datetime.now().strftime('%y%m%d%H%M')
        sort_suffix = "tov" if sort_by_tov else "zlb"
        dte_short = datetime.now().strftime('%y%m%d')
        os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
        filename = f'../generated/em/{dte_short}/zjlx_{sort_suffix}_{tstr}.csv'
        
        # 保存到CSV文件
        df2.to_csv(filename, index=False, encoding='utf-8-sig')
        
        print(f"✓ 主力资金流向+换手率数据已保存到: {filename}")
        print(f"数据总量: {len(df2)} 条")
        print(f"排序方式: {'换手率倒序' if sort_by_tov else '主力净流入倒序'}")
        print(f"下载页数: {pn} 页")
        print(f"包含字段: {list(df2.columns)}")
        print(f"字段总数: {len(df2.columns)} 个")
        
        if extensive:
            print("📊 扩展模式已启用：包含技术指标、财务指标、成交量等完整数据")
        else:
            print("📊 标准模式：包含核心资金流向和基础指标数据")
            
    except Exception as save_e:
        print(f"⚠️ 文件保存失败: {save_e}")
        print("数据仍会返回，但未保存到文件")
    
    # 显示统计信息
    try:
        # 显示排序字段的统计信息
        if sort_by_tov and '换手率' in df2.columns:
            print(f"\n换手率统计:")
            print(f"最高换手率: {df2['换手率'].max():.2f}%")
            print(f"最低换手率: {df2['换手率'].min():.2f}%")
            print(f"平均换手率: {df2['换手率'].mean():.2f}%")
        elif not sort_by_tov and '主力净流入' in df2.columns:
            print(f"\n主力净流入统计:")
            print(f"最高净流入: {df2['主力净流入'].max():,.0f} 元")
            print(f"最低净流入: {df2['主力净流入'].min():,.0f} 元")
            print(f"平均净流入: {df2['主力净流入'].mean():,.0f} 元")
        
        # 显示板块和概念统计信息
        if '所属行业' in df2.columns:
            industry_counts = df2['所属行业'].value_counts().head(10)
            print(f"\n行业分布 (前10):")
            for industry, count in industry_counts.items():
                print(f"  {industry}: {count} 只")
        
        if '所属概念' in df2.columns:
            concept_counts = df2['所属概念'].value_counts().head(10)
            print(f"\n概念分布 (前10):")
            for concept, count in concept_counts.items():
                print(f"  {concept}: {count} 只")
        
        if '所属地域' in df2.columns:
            region_counts = df2['所属地域'].value_counts().head(10)
            print(f"\n地域分布 (前10):")
            for region, count in region_counts.items():
                print(f"  {region}: {count} 只")
        
        # 显示新增价格字段的统计信息
        print("\n价格相关字段统计:")
        price_fields = ['pl3', 'pl5', 'pl10', 'pl20', 'pl60', 'pl_year_start']
        for field in price_fields:
            if field in df2.columns:
                print(f"{field}: 最高 {df2[field].max():.2f}%, 最低 {df2[field].min():.2f}%, 平均 {df2[field].mean():.2f}%")
        
        # 显示扩展模式下的技术指标统计信息
        if extensive:
            print("\n技术指标字段统计:")
            tech_fields = ['量比', '委比', '委差', 'RSI', 'MACD', 'KDJ', '威廉指标']
            for field in tech_fields:
                if field in df2.columns:
                    print(f"{field}: 最高 {df2[field].max():.2f}, 最低 {df2[field].min():.2f}, 平均 {df2[field].mean():.2f}")
            
            print("\n财务指标字段统计:")
            financial_fields = ['每股收益', '每股净资产', 'ROE', 'ROA', '毛利率', '净利率']
            for field in financial_fields:
                if field in df2.columns:
                    if field in ['每股收益', '每股净资产']:
                        print(f"{field}: 最高 {df2[field].max():.4f}, 最低 {df2[field].min():.4f}, 平均 {df2[field].max():.4f}")
                    else:
                        print(f"{field}: 最高 {df2[field].max():.2f}%, 最低 {df2[field].min():.2f}%, 平均 {df2[field].mean():.2f}%")
            
            print("\n成交量相关字段统计:")
            volume_fields = ['外盘', '内盘', '总手', '现手', '成交量', '成交额']
            for field in volume_fields:
                if field in df2.columns:
                    if field == '成交额':
                        print(f"{field}: 最高 {df2[field].max():,.0f}, 最低 {df2[field].min():,.0f}, 平均 {df2[field].mean():,.0f}")
                    else:
                        print(f"{field}: 最高 {df2[field].max():,.0f}, 最低 {df2[field].min():,.0f}, 平均 {df2[field].mean():,.0f}")
        
        # 显示数据预览
        print("\n数据预览（前5条）:")
        print(df2.head().to_string())
        
    except Exception as stats_e:
        print(f"⚠️ 统计信息显示过程中出现错误: {stats_e}")
        print("数据仍会返回，但统计信息可能不完整")
    dte_short = datetime.now().strftime('%y%m%d')
    input_filename = f'../generated/em/{dte_short}/zjlx_tov_{tstr}.csv'
    report_filename = f'../generated/em/{dte_short}/flow_tov_{tstr}.csv'

    try:
        gen_z_report(input_filename, report_filename)
    except Exception as e:
        print(f"⚠️ 生成资金流向报告时出错: {e}")
    
    # 调用 queryFlow 分析资金流向数据（无论 gen_z_report 是否成功）
    try:
        print(f"\n开始分析资金流向数据...")
        queryFlow(input_filename)
    except Exception as e:
        print(f"⚠️ 分析资金流向数据时出错: {e}")
    
    return df2

def get_zjlx_by_tov(min_tov=1.5):
    """
    获取主力资金流向数据，按换手率由大到小排序，默认只获取换手率>1.5%的数据
    
    参数:
    min_tov: 最小换手率阈值，默认1.5%
    
    返回: 按换手率排序的主力资金流向数据DataFrame
    """
    print(f"开始获取换手率>{min_tov}%的主力资金流向数据...")
    
    # 先获取按换手率排序的前N页数据（默认10页）
    print(f"获取换手率前N页数据，每页约{1000}条...")
    df_full = get_zjlx_complete(max_pages=max(5, min_tov//0.5), sort_by_tov=True)
    
    if df_full is None or len(df_full) == 0:
        print("获取数据失败")
        return None
    
    # 确保换手率字段存在且为数值类型
    if '换手率' not in df_full.columns:
        print("数据中未找到换手率字段，请检查API返回数据")
        return df_full
    
    # 过滤换手率大于阈值的数据
    df_filtered = df_full[df_full['换手率'] > min_tov].copy()
    
    if len(df_filtered) == 0:
        print(f"没有找到换手率>{min_tov}%的股票")
        return df_filtered
    
    # 按换手率降序排序
    df_filtered = df_filtered.sort_values('换手率', ascending=False).reset_index(drop=True)
    
    # 重新编号序号
    df_filtered['序号'] = range(1, len(df_filtered) + 1)
    
    # 生成时间戳文件名
    tstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    filename = f'../generated/em/{dte_short}/zjlx_by_tov_{min_tov}_{tstr}.csv'
    
    # 保存到CSV文件
    df_filtered.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"换手率>{min_tov}%的主力资金流向数据已保存到: {filename}")
    print(f"过滤后数据量: {len(df_filtered)} 条 (原始数据: {len(df_full)} 条)")
    
    # 显示换手率统计信息
    print(f"\n换手率统计信息:")
    print(f"最高换手率: {df_filtered['换手率'].max():.2f}%")
    print(f"最低换手率: {df_filtered['换手率'].min():.2f}%")
    print(f"平均换手率: {df_filtered['换手率'].mean():.2f}%")
    
    # 显示前10条数据预览
    print(f"\n换手率前10名股票:")
    preview_cols = ['序号', '代码', '名称', '换手率', '今日涨跌幅', '主力净流入', '主力净占比', '最新价']
    available_cols = [col for col in preview_cols if col in df_filtered.columns]
    print(df_filtered[available_cols].head(10).to_string(index=False))
    
    # 显示资金流向统计
    if '主力净流入' in df_filtered.columns:
        positive_flow = df_filtered[df_filtered['主力净流入'] > 0]
        negative_flow = df_filtered[df_filtered['主力净流入'] < 0]
        print(f"\n资金流向统计:")
        print(f"主力净流入股票数: {len(positive_flow)} 只")
        print(f"主力净流出股票数: {len(negative_flow)} 只")
        print(f"净流入占比: {len(positive_flow)/len(df_filtered)*100:.1f}%")
    
    # 调用 queryFlow 分析资金流向数据
    try:
        print(f"\n开始分析资金流向数据...")
        queryFlow(filename)
    except Exception as e:
        print(f"⚠️ 分析资金流向数据时出错: {e}")
    
    return df_filtered

def get_capreal():

    cookies = {
        'qgqp_b_id': 'e7a1ea46296469d1fa43b9951dcf960c',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_si': '55114734274095',
        'st_asi': 'delete',
        'qRecords': '%5B%7B%22name%22%3A%22%u6D77%u5170%u4FE1%22%2C%22code%22%3A%22SZ300065%22%7D%2C%7B%22name%22%3A%22%u79D1%u601D%u79D1%u6280%22%2C%22code%22%3A%22SH688788%22%7D%5D',
        'st_pvi': '27639117154963',
        'st_sp': '2025-07-08%2008%3A54%3A21',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '35',
        'st_psi': '20250725084325700-113300302045-3146613912',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/zjlx/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'qgqp_b_id=e7a1ea46296469d1fa43b9951dcf960c; fullscreengg=1; fullscreengg2=1; st_si=55114734274095; st_asi=delete; qRecords=%5B%7B%22name%22%3A%22%u6D77%u5170%u4FE1%22%2C%22code%22%3A%22SZ300065%22%7D%2C%7B%22name%22%3A%22%u79D1%u601D%u79D1%u6280%22%2C%22code%22%3A%22SH688788%22%7D%5D; st_pvi=27639117154963; st_sp=2025-07-08%2008%3A54%3A21; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=35; st_psi=20250725084325700-113300302045-3146613912',
    }

    params = {
        'key': 'f62',
        'code': 'm:90+t:2',
    }

    response = requests.get('https://data.eastmoney.com/dataapi/bkzj/getbkzj', params=params, cookies=cookies, headers=headers)
    # open(os.path.join(temp_dir, 'capreal.txt'), 'w', encoding='utf-8').write(response.text)

    df=pd.DataFrame(json.loads(response.text)['data']['diff'])
    print(df)
    return df

def load_stock_name_code_map():
    """
    从最新的quote文件中加载股票名称到代码的映射
    返回: {股票名称: 股票代码}
    """
    from pathlib import Path
    em_root = Path('../generated/em')
    if not em_root.exists():
        return {}
    
    # 选择最新的日期目录
    date_dirs = [p for p in em_root.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 6]
    if not date_dirs:
        return {}
    latest_dir = sorted(date_dirs, key=lambda p: p.name)[-1]
    
    # 选择该目录下最新时间点的 quote_*.csv
    quote_files = sorted(latest_dir.glob('quote_*.csv'))
    if not quote_files:
        return {}
    latest_quote = quote_files[-1]
    
    try:
        df_q = pd.read_csv(latest_quote, encoding='utf-8-sig')
        name_code_map = {}
        
        # 尝试匹配常见字段名
        name_col = None
        code_col = None
        for c in df_q.columns:
            c_str = str(c)
            if '股票名称' in c_str or c_str == '名称':
                name_col = c
            if '股票代码' in c_str or c_str == '代码':
                code_col = c
        
        if name_col and code_col:
            for _, r in df_q[[name_col, code_col]].iterrows():
                name = str(r[name_col]).strip()
                code = str(r[code_col]).strip()
                # 提取6位数字代码
                code_digits = re.sub(r'\D', '', code)
                if len(code_digits) >= 6:
                    code_digits = code_digits[-6:].zfill(6)
                    if name and code_digits:
                        name_code_map[name] = code_digits
        
        return name_code_map
    except Exception as e:
        print(f"[warn] Failed to load stock name-code map: {e}")
        return {}

def get_capreal_ext(sector_type='industry', md_dir=None):
    """
    获取板块数据（扩展版本，使用 save_all_data.py 的 API 和字段映射）
    sector_type: 'industry' (行业) or 'concept' (概念)
    md_dir: Base Markdown output directory
    """
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
        'st_sn': '191',
        'st_psi': '20250803162545905-113200301201-0814983901',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://quote.eastmoney.com/center/gridlist.html',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
    }

    # Field name mapping from Eastmoney API codes to Chinese names
    field_mapping = {
        'f1': '状态',
        'f2': '当前价格',
        'f3': '涨跌幅',
        'f4': '涨跌额',
        'f8': '换手率',
        'f12': '板块代码',
        'f13': '市场类型',
        'f14': '板块名称',
        'f20': '总市值',
        'f62': '主力净流入',
        'f104': '上涨家数',
        'f105': '下跌家数',
        'f128': '领涨股名称',
        'f140': '领涨股代码',
        'f141': '领涨股市场',
        'f136': '领涨股涨跌幅',
        'f152': '状态2',
        'f205': '股票代码',
        'f207': '领跌股名称',
        'f208': '领跌股代码',
        'f209': '领跌股市场',
        'f222': '领跌股涨跌幅',
    }

    def rename_columns(df):
        """Rename dataframe columns from f-codes to Chinese names"""
        rename_dict = {k: v for k, v in field_mapping.items() if k in df.columns}
        return df.rename(columns=rename_dict)

    def transform_data(df):
        """Transform data: divide 涨跌幅, 当前价格, 换手率 by 100, 总市值 by 1E8"""
        df = df.copy()
        # Convert to numeric and divide by 100
        if '涨跌幅' in df.columns:
            df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce') / 100
        if '当前价格' in df.columns:
            df['当前价格'] = pd.to_numeric(df['当前价格'], errors='coerce') / 100
        if '换手率' in df.columns:
            df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce') / 100
        # Convert 总市值 to 亿元 (divide by 1E8)
        if '总市值' in df.columns:
            df['总市值'] = (pd.to_numeric(df['总市值'], errors='coerce') / 1e8).round(2)
        # Convert 主力净流入 to 亿元 (divide by 1E8)
        if '主力净流入' in df.columns:
            df['主力净流入'] = (pd.to_numeric(df['主力净流入'], errors='coerce') / 1e8).round(2)
        if '涨跌额' in df.columns:
            df['涨跌额'] = pd.to_numeric(df['涨跌额'], errors='coerce') / 100
        if '领涨股涨跌幅' in df.columns:
            df['领涨股涨跌幅'] = pd.to_numeric(df['领涨股涨跌幅'], errors='coerce') / 100
        if '领跌股涨跌幅' in df.columns:
            df['领跌股涨跌幅'] = pd.to_numeric(df['领跌股涨跌幅'], errors='coerce') / 100
        # Format 股票代码 as 6-digit number with leading zeros
        if '股票代码' in df.columns:
            df['股票代码'] = df['股票代码'].apply(lambda x: f"{int(x):06d}" if pd.notna(x) and str(x).isdigit() else x)
        return df

    def parse_response(response_text):
        """解析API响应"""
        try:
            pattern = r'jQuery\d+_\d+\((.*)\)'
            match = re.search(pattern, response_text)
            if not match:
                try:
                    return json.loads(response_text)
                except:
                    return None
            json_str = match.group(1)
            return json.loads(json_str)
        except Exception as e:
            print(f"解析响应时出错: {e}")
            return None

    # Determine fs parameter based on sector type
    if sector_type == 'industry':
        fs = 'm:90+t:2+f:!50'
    else:  # concept
        fs = 'm:90+t:3+f:!50'

    all_data = []
    page = 1
    page_size = 100
    
    timestamp = int(time.time() * 1000)
    params = {
        'np': '1', 'fltt': '1', 'invt': '2',
        'cb': f'jQuery{timestamp}_{timestamp}',
        'fs': fs,
        'fields': 'f12,f13,f14,f1,f2,f4,f3,f152,f20,f8,f62,f104,f105,f128,f140,f141,f205,f207,f208,f209,f136,f222',
        'fid': 'f3', 'pn': page, 'pz': page_size, 'po': '1',
        'dect': '1', 'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'wbp2u': '|0|0|0|web', '_': str(timestamp),
    }

    try:
        print(f"正在获取{sector_type}板块数据...")
        response = requests.get(
            'https://push2.eastmoney.com/api/qt/clist/get',
            params=params, cookies=cookies, headers=headers, timeout=30
        )
        response.raise_for_status()
        
        data = parse_response(response.text)
        if not data or 'data' not in data:
            print(f"无法获取{sector_type}板块数据")
            return pd.DataFrame()
        
        total = data['data']['total']
        total_pages = (total + page_size - 1) // page_size
        print(f"{sector_type}板块总数: {total}, 总页数: {total_pages}")
        
        if 'diff' in data['data']:
            all_data.extend(data['data']['diff'])
            print(f"  第1页: 获取 {len(data['data']['diff'])} 条数据")
        
        # Fetch remaining pages
        for page in range(2, total_pages + 1):
            timestamp = int(time.time() * 1000)
            params['pn'] = page
            params['cb'] = f'jQuery{timestamp}_{timestamp}'
            params['_'] = str(timestamp)
            
            try:
                response = requests.get(
                    'https://push2.eastmoney.com/api/qt/clist/get',
                    params=params, cookies=cookies, headers=headers, timeout=30
                )
                data = parse_response(response.text)
                if data and 'data' in data and 'diff' in data['data']:
                    page_data = data['data']['diff']
                    all_data.extend(page_data)
                    print(f"  第{page}页: 获取 {len(page_data)} 条数据")
                time.sleep(0.1)
            except Exception as e:
                print(f"获取第{page}页时出错: {e}")
                continue
        
        print(f"总共获取 {len(all_data)} 条{sector_type}板块数据\n")
        
        if all_data:
            df = pd.DataFrame(all_data)
            # Rename columns to Chinese names
            df = rename_columns(df)
            # Transform data: divide 涨跌幅, 当前价格, 换手率 by 100
            df = transform_data(df)
            
            # Apply exclude list for concept sectors (根据 bk_exclude.tsv)
            if sector_type == 'concept':
                try:
                    exclude_path = os.path.join(os.path.dirname(__file__), 'bk_exclude.tsv')
                    if os.path.exists(exclude_path):
                        exdf = pd.read_csv(exclude_path, sep='\t', comment='#')
                        # 标准化列名
                        exdf.columns = [c.strip() for c in exdf.columns]
                        name_col = '名称' if '名称' in exdf.columns else exdf.columns[0]
                        flag_col = '排除显示' if '排除显示' in exdf.columns else exdf.columns[1]
                        # 取需要排除的名称集合（排除显示==1）
                        to_exclude = exdf[exdf[flag_col].astype(str).str.strip() == '1'][name_col].astype(str).str.strip()
                        exclude_set = set(to_exclude)
                        if exclude_set and '板块名称' in df.columns:
                            original_count = len(df)
                            df = df[~df['板块名称'].astype(str).str.strip().isin(exclude_set)]
                            excluded_count = original_count - len(df)
                            if excluded_count > 0:
                                print(f"已排除 {excluded_count} 个概念板块（根据 bk_exclude.tsv）")
                except Exception as e:
                    print(f"读取排除列表时出错: {e}")
            
            # Save to CSV with timestamp
            timestamp_str = datetime.now().strftime('%y%m%d%H%M')
            dte_short = datetime.now().strftime('%y%m%d')
            os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
            csv_path = f'../generated/em/{dte_short}/{sector_type}_ext_{timestamp_str}.csv'
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')
            print(f"数据已保存到: {csv_path}")
            # Also save raw CSV to md_dir/{dte}/raw/, file name {sector_type}.csv
            # Use dte (4-digit year) for MD output directory, like 20251218
            dte_short = datetime.now().strftime('%y%m%d')
            dte = datetime.now().strftime('%Y%m%d')
            
            # Use passed md_dir or default to hardcoded (safety fallback)
            if not md_dir:
                 md_dir_home = f'/Volumes/ASME/myobs/0syncs/stock/{dte}'
                 md_dir_office = os.path.expanduser(f'~/Public/myobs/0syncs/stock/{dte}')
                 md_dir_base = md_dir_home if os.path.exists(os.path.dirname(md_dir_home)) else md_dir_office
            else:
                 # Append date to the base directory passed from caller
                 md_dir_base = os.path.join(md_dir, dte)

            # raw_csv_dir = os.path.join(md_dir_base, 'raw')
            # raw_csv_dir = f'../generated/em/{dte_short}'
            # os.makedirs(raw_csv_dir, exist_ok=True)
            # raw_csv_path = os.path.join(raw_csv_dir, f'{sector_type}_{timestamp_str}.csv')
            # df.to_csv(raw_csv_path, index=False, encoding='utf-8-sig')
            # Save Markdown view
            def save_md_view(df, output_path, is_industry=True):
                """保存Markdown视图文件，包含主力净流入和股票代码"""
                df = df.copy()
                col_map = {}
                if '板块名称' in df.columns:
                    col_map['板块名称'] = '名称'
                elif '名称' in df.columns:
                    col_map['名称'] = '名称'
                
                # 统一列名
                view_df = df.rename(columns=col_map)
                
                def format_colored_value(value, is_positive=True):
                    """
                    格式化带颜色的值，同时兼容 Obsidian 和 GitHub
                    - Obsidian: 只显示颜色（符号被 CSS 隐藏）
                    - GitHub: 显示符号前缀（↑ 红色，↓ 绿色），因为 GitHub 不支持 display:none
                    """
                    if is_positive:
                        # 正数：红色（涨）
                        # 符号用 display:none 隐藏，Obsidian 会隐藏符号只显示红色值，GitHub 会显示符号
                        return f'<span style="display:none">↑ </span><span style="color:red">{value}</span>'
                    else:
                        # 负数：绿色（跌）
                        # 符号用 display:none 隐藏，Obsidian 会隐藏符号只显示绿色值，GitHub 会显示符号
                        return f'<span style="display:none">↓ </span><span style="color:green">{value}</span>'
                
                def generate_anchor_id(text):
                    """
                    生成标准的 Markdown 锚点ID
                    - 转换为小写
                    - 空格替换为连字符
                    - 移除或替换特殊字符
                    """
                    import re
                    # 转换为小写
                    anchor = text.lower()
                    # 替换空格和常见分隔符为连字符
                    anchor = re.sub(r'[\s/\\|]+', '-', anchor)
                    # 移除其他特殊字符，只保留字母、数字和连字符
                    anchor = re.sub(r'[^a-z0-9\-]', '', anchor)
                    # 移除连续的连字符
                    anchor = re.sub(r'-+', '-', anchor)
                    # 移除开头和结尾的连字符
                    anchor = anchor.strip('-')
                    return anchor
                
                # 构建Markdown
                md_lines = []
                # 表头 - 按指定顺序：名称 | 涨跌幅 | 主力净流入 | 换手率 | 上涨家数/下跌家数 | 领涨股/领跌股
                head = []
                head.append('名称')
                if '涨跌幅' in view_df.columns:
                    head.append('涨跌幅')
                head.append('主力净流入')
                head.append('换手率')
                if '上涨家数' in view_df.columns and '下跌家数' in view_df.columns:
                    head.append('上涨家数/下跌家数')
                if '领涨股名称' in view_df.columns or '领跌股名称' in view_df.columns:
                    lz = view_df['领涨股名称'] if '领涨股名称' in view_df.columns else None
                    ld = view_df['领跌股名称'] if '领跌股名称' in view_df.columns else None
                    if lz is not None and ld is not None:
                        head.append('领涨股/领跌股')
                    elif lz is not None:
                        head.append('领涨股名称')
                    elif ld is not None:
                        head.append('领跌股名称')
                # 添加板块表现列（走势图和K线图链接）
                head.append('板块表现')

                
                md_lines.append('| ' + ' | '.join(head) + ' |')
                md_lines.append('| ' + ' | '.join(['---'] * len(head)) + ' |')
                
                # 排序（按涨跌幅降序）
                out_df = view_df
                if '涨跌幅' in out_df.columns:
                    out_df = out_df.sort_values('涨跌幅', ascending=False)
                
                # 每一行 - 按表头顺序填充数据：名称 | 涨跌幅 | 主力净流入 | 换手率 | 上涨家数/下跌家数 | 领涨股/领跌股 
                # 生成时间戳用于图片URL
                timestamp_ms = int(datetime.now().timestamp() * 1000)
                
                for _, row in out_df.iterrows():
                    row_vals = []
                    
                    # 1. 名称（添加链接指向"板块表现"部分）
                    name = str(row.get('名称', ''))
                    bk_code = row.get('板块代码', '')
                    # 检查板块代码是否存在且有效
                    if pd.notna(bk_code) and str(bk_code).strip() != '':
                        try:
                            # 格式化板块代码（确保是字符串，去除小数点）
                            if str(bk_code).replace('.', '').isdigit():
                                bk = str(int(float(bk_code)))
                            else:
                                bk = str(bk_code).strip()
                            # 生成锚点ID（使用标准格式）
                            anchor_id = generate_anchor_id(name)
                            # 链接指向"板块表现"部分的对应板块
                            name = f'[{name}](#{name})'
                        except (ValueError, TypeError):
                            # 如果转换失败，使用原始名称（不添加链接）
                            pass
                    row_vals.append(name)
                    
                    # 2. 涨跌幅（直接显示数值，不乘以100，添加颜色标记）
                    zdf = row.get('涨跌幅', '')
                    if zdf != '' and zdf == zdf:
                        try:
                            zdf_val = float(zdf)
                            zdf_str = f"{zdf_val:.2f}"
                            # 添加颜色标记：>0红色，<0绿色（兼容 Obsidian 和 GitHub）
                            if zdf_val > 0:
                                zdf_str = format_colored_value(zdf_str, is_positive=True)
                            elif zdf_val < 0:
                                zdf_str = format_colored_value(zdf_str, is_positive=False)
                        except Exception:
                            zdf_str = str(zdf)
                    else:
                        zdf_str = ''
                    row_vals.append(zdf_str)
                    
                    # 3. 主力净流入（亿元，添加颜色标记）
                    if '主力净流入' in head:
                        zjlx = row.get('主力净流入', '')
                        if zjlx != '' and zjlx == zjlx:
                            try:
                                zjlx_val = float(zjlx)
                                zjlx_val_str = f"{zjlx_val:.2f}亿"
                                # 添加颜色标记：>0红色，<0绿色（兼容 Obsidian 和 GitHub）
                                if zjlx_val > 0:
                                    zjlx_str = format_colored_value(zjlx_val_str, is_positive=True)
                                elif zjlx_val < 0:
                                    zjlx_str = format_colored_value(zjlx_val_str, is_positive=False)
                                else:
                                    zjlx_str = zjlx_val_str
                            except Exception:
                                zjlx_str = str(zjlx)
                        else:
                            zjlx_str = '0.00亿'
                        row_vals.append(zjlx_str)
                    
                    # 4. 换手率（直接显示数值，不乘以100）
                    hs = row.get('换手率', '')
                    if hs != '' and hs == hs:
                        try:
                            hs_val = float(hs)
                            hs_str = f"{hs_val:.2f}"
                        except Exception:
                            hs_str = str(hs)
                    else:
                        hs_str = ''
                    row_vals.append(hs_str)
                    
                    # 5. 上涨家数/下跌家数
                    if '上涨家数/下跌家数' in head:
                        up = str(int(row.get('上涨家数', 0))) if row.get('上涨家数', '') != '' else ''
                        down = str(int(row.get('下跌家数', 0))) if row.get('下跌家数', '') != '' else ''
                        row_vals.append(f"{up}/{down}")
                    
                    # 6. 领涨股/领跌股（添加链接到个股表现section）
                    if '领涨股/领跌股' in head or '领涨股名称' in head or '领跌股名称' in head:
                        lz_val = str(row.get('领涨股名称', '')) if '领涨股名称' in view_df.columns else ''
                        ld_val = str(row.get('领跌股名称', '')) if '领跌股名称' in view_df.columns else ''
                        
                        # 加载股票名称到代码的映射
                        name_code_map = load_stock_name_code_map()
                        
                        # 为领涨股添加链接
                        if lz_val:
                            lz_clean = lz_val.strip()
                            # 移除可能的*ST前缀等
                            lz_clean = re.sub(r'^\*?ST\s*', '', lz_clean)
                            if lz_clean in name_code_map:
                                anchor_id = generate_anchor_id(f"个股表现-{lz_clean}")
                                lz_val = f"[{lz_val}](#{anchor_id})"
                        
                        # 为领跌股添加链接
                        if ld_val:
                            ld_clean = ld_val.strip()
                            ld_clean = re.sub(r'^\*?ST\s*', '', ld_clean)
                            if ld_clean in name_code_map:
                                anchor_id = generate_anchor_id(f"个股表现-{ld_clean}")
                                ld_val = f"[{ld_val}](#{anchor_id})"
                        
                        if lz_val and ld_val:
                            row_vals.append(f"{lz_val}/{ld_val}")
                        elif lz_val:
                            row_vals.append(lz_val)
                        elif ld_val:
                            row_vals.append(ld_val)
                    
                    # 7. 板块表现（走势图和K线图链接）
                    if '板块表现' in head:
                        bk_code_for_chart = row.get('板块代码', '')
                        if pd.notna(bk_code_for_chart) and str(bk_code_for_chart).strip() != '':
                            try:
                                # 格式化板块代码
                                if str(bk_code_for_chart).replace('.', '').isdigit():
                                    bk_chart = str(int(float(bk_code_for_chart)))
                                else:
                                    bk_chart = str(bk_code_for_chart).strip()
                                
                                # 生成板块走势图和K线图URL
                                nid = f"90.{bk_chart}"
                                
                                # 走势图URL
                                trend_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms}"
                                
                                # K线图URL
                                kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms}"
                                
                                # 生成Markdown图片链接
                                trend_link = f"[走势图]({trend_url})"
                                kline_link = f"[K线图]({kline_url})"
                                row_vals.append(f"{trend_link} / {kline_link}")
                            except (ValueError, TypeError) as e:
                                row_vals.append('')
                        else:
                            row_vals.append('')
                    
                    md_lines.append('| ' + ' | '.join(row_vals) + ' |')
                
                # 如果是 industry，计算上涨家数/下跌家数总和
                summary_line = ''
                if is_industry and '上涨家数' in view_df.columns and '下跌家数' in view_df.columns:
                    total_up = 0
                    total_down = 0
                    for _, row in view_df.iterrows():
                        up_val = row.get('上涨家数', '')
                        down_val = row.get('下跌家数', '')
                        if up_val != '' and pd.notna(up_val):
                            try:
                                total_up += int(float(up_val))
                            except:
                                pass
                        if down_val != '' and pd.notna(down_val):
                            try:
                                total_down += int(float(down_val))
                            except:
                                pass
                    
                    # 格式化总和，添加颜色标记（兼容 Obsidian 和 GitHub）
                    if total_up > 0:
                        up_str = format_colored_value(str(total_up), is_positive=True)
                    else:
                        up_str = str(total_up)
                    
                    if total_down > 0:
                        down_str = format_colored_value(str(total_down), is_positive=False)
                    else:
                        down_str = str(total_down)
                    
                    summary_line = f"**总计上涨家数/下跌家数:** {up_str}/{down_str}<br/>"
                
                # 保存文件
                with open(output_path, 'w', encoding='utf-8') as f_md:
                    f_md.write(f"# {'板块' if is_industry else '概念'}数据视图\n\n")
                    
                    # 对于 industry_view，将 summary_line 放在顶部右对齐
                    if is_industry and summary_line:
                        # 使用 HTML div 实现右对齐（兼容 Obsidian 和 GitHub）
                        f_md.write(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} <div style=\"text-align: right; display: inline-block; float: right;\">{summary_line}</div>\n\n")
                    else:
                        f_md.write(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    # 添加MOC（目录）
                    f_md.write("## 目录\n\n")
                    f_md.write("- [数据表格](#数据表格)\n")
                    f_md.write("- [板块表现](#板块表现)\n")
                    f_md.write("- [个股表现](#个股表现)\n")
                    f_md.write("\n---\n\n")
                    
                    # 添加数据表格section
                    f_md.write("## 数据表格\n\n")
                    f_md.write('[返回页首](#板块数据视图)\n\n' if is_industry else '[返回页首](#概念数据视图)\n\n')
                    
                    f_md.write('\n'.join(md_lines))
                    f_md.write('\n')
                    
                    # 如果不是 industry_view，在末尾添加 summary_line
                    if not is_industry and summary_line:
                        f_md.write(f"\n{summary_line}\n")
                    
                    # 为每个板块添加"板块表现"部分
                    f_md.write("\n## 板块表现\n\n")
                    f_md.write('[返回页首](#板块数据视图)\n\n' if is_industry else '[返回页首](#概念数据视图)\n\n')
                    
                    for _, row in out_df.iterrows():
                        sector_name = str(row.get('名称', ''))
                        bk_code_for_chart = row.get('板块代码', '')
                        
                        if pd.notna(bk_code_for_chart) and str(bk_code_for_chart).strip() != '':
                            try:
                                # 格式化板块代码
                                if str(bk_code_for_chart).replace('.', '').isdigit():
                                    bk_chart = str(int(float(bk_code_for_chart)))
                                else:
                                    bk_chart = str(bk_code_for_chart).strip()
                                
                                # 生成板块走势图和K线图URL
                                nid = f"90.{bk_chart}"
                                
                                # 走势图URL
                                trend_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms}"
                                
                                # K线图URL
                                kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms}"
                                
                                # 生成锚点ID（使用标准格式，确保与链接中的锚点一致）
                                anchor_id = generate_anchor_id(sector_name)
                                
                                # 添加板块表现部分（使用 HTML 锚点确保链接正确）
                                f_md.write(f"### {sector_name}\n\n")
                                f_md.write(f"**走势图**\n\n")
                                f_md.write(f"![{sector_name}走势图]({trend_url})\n\n")
                                f_md.write(f"**K线图**\n\n")
                                f_md.write(f"![{sector_name}K线图]({kline_url})\n\n")
                                f_md.write("---\n\n")
                                
                            except (ValueError, TypeError) as e:
                                pass
                    
                    # 添加"个股表现"部分
                    f_md.write("\n## 个股表现\n\n")
                    f_md.write('[返回页首](#板块数据视图)\n\n' if is_industry else '[返回页首](#概念数据视图)\n\n')
                    
                    # 收集所有领涨股和领跌股
                    stock_names = set()
                    for _, row in out_df.iterrows():
                        lz_val = str(row.get('领涨股名称', '')) if '领涨股名称' in view_df.columns else ''
                        ld_val = str(row.get('领跌股名称', '')) if '领跌股名称' in view_df.columns else ''
                        if lz_val and lz_val.strip():
                            stock_names.add(lz_val.strip())
                        if ld_val and ld_val.strip():
                            stock_names.add(ld_val.strip())
                    
                    # 加载股票名称到代码的映射
                    name_code_map = load_stock_name_code_map()
                    
                    # 为每个股票生成走势图和K线图
                    for stock_name in sorted(stock_names):
                        stock_clean = re.sub(r'^\*?ST\s*', '', stock_name)
                        if stock_clean in name_code_map:
                            stock_code = name_code_map[stock_clean]
                            # 生成股票nid（根据代码前缀判断市场）
                            # 修复：确保代码是6位数字字符串
                            stock_code_str = str(stock_code).zfill(6)
                            if stock_code_str.startswith(('6', '9')):
                                nid = f"1.{stock_code_str}"
                            else:
                                nid = f"0.{stock_code_str}"
                            
                            # 走势图URL（修复：使用正确的nid格式）
                            trend_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid={nid}&timespan={timestamp_ms}"
                            
                            # K线图URL（修复：使用正确的nid格式）
                            kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={timestamp_ms}"
                            
                            # 生成锚点ID
                            anchor_id = generate_anchor_id(f"个股表现-{stock_clean}")
                            
                            # 添加个股表现部分
                            f_md.write(f"### {stock_name} ({stock_code_str})\n\n")
                            f_md.write(f"**走势图**\n\n")
                            f_md.write(f"![{stock_name}走势图]({trend_url})\n\n")
                            f_md.write(f"**K线图**\n\n")
                            f_md.write(f"![{stock_name}K线图]({kline_url})\n\n")
                            f_md.write("---\n\n")
                    
                print(f"✓ {'板块' if is_industry else '概念'}Markdown视图已保存到: {output_path}")
            
            
            # 保存Markdown视图
            dte_date = datetime.now().strftime('%Y%m%d')

            # Ensure directory exists
            if not os.path.exists(md_dir_base):
                try:
                    os.makedirs(md_dir_base, exist_ok=True)
                except Exception as e:
                    print(f"创建目录失败: {md_dir_base}, 错误: {e}")

            if sector_type == 'industry':
                view_md = os.path.join(md_dir_base, f"industry_view.md")
            else:
                view_md = os.path.join(md_dir_base, f"concept_view.md")
            
            save_md_view(df, view_md, is_industry=(sector_type == 'industry'))
            
            return view_md
        else:
            return None
            
    except Exception as e:
        print(f"获取{sector_type}板块列表时出错: {e}")
        return None

def get_capreal_bk():
    cookies = {
        'qgqp_b_id': 'e7a1ea46296469d1fa43b9951dcf960c',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_si': '55114734274095',
        'st_asi': 'delete',
        'st_pvi': '27639117154963',
        'st_sp': '2025-07-08%2008%3A54%3A21',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '38',
        'st_psi': '20250725090501243-113300300813-1928368570',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/bkzj/gn.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'qgqp_b_id=e7a1ea46296469d1fa43b9951dcf960c; fullscreengg=1; fullscreengg2=1; st_si=55114734274095; st_asi=delete; st_pvi=27639117154963; st_sp=2025-07-08%2008%3A54%3A21; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=38; st_psi=20250725090501243-113300300813-1928368570',
    }

    all_bk_list = []
    page_num = 1
    page_size = 100
    
    while True:
        params = {
            'cb': 'jQuery112309537502465593548_1753405536965',
            'fid': 'f62',
            'po': '1',
            'pz': str(page_size),
            'pn': str(page_num),
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'ut': '8dec03ba335b81bf4ebdf7b29ec27d15',
            'fs': 'm:90 t:3',
            'fields': 'f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13',
        }

        response = requests.get('https://push2delay.eastmoney.com/api/qt/clist/get', params=params, cookies=cookies, headers=headers)
        
        # Save the first page response to file
        if page_num == 1:
            open(os.path.join(temp_dir, 'capreal_bk.txt'), 'w', encoding='utf-8').write(response.text)
        
        json_str = re.search(r'\((\{.*\})\);?$', response.text, re.DOTALL).group(1)
        data = json.loads(json_str)
        
        # Check if there's data in this page
        if not data['data']['diff'] or len(data['data']['diff']) == 0:
            break
            
        # Add data from this page to our collection
        all_bk_list.extend(data['data']['diff'])
        
        print(f"Fetched page {page_num}, got {len(data['data']['diff'])} records")

        # If we got less than the page size, we've reached the end
        if len(data['data']['diff']) < page_size:
            break
            
        page_num += 1
    
    print(f"Total records fetched: {len(all_bk_list)}")
    df = pd.DataFrame(all_bk_list)
    
    
    # Field mapping to Chinese names (based on provided format)
    field_mapping = {
        'f3': '今日涨跌幅',
        'f12': '板块代码', 
        'f13': '市场类型',
        'f14': '板块名称',
        'f62': '主力净流入',
        'f66': '超大单净流入',
        'f69': '超大单净占比',
        'f72': '大单净流入',
        'f75': '大单净占比',
        'f78': '中单净流入',
        'f81': '中单净占比',
        'f84': '小单净流入',
        'f87': '小单净占比',
        'f124': 'Tme',
        'f184': '主力净流入占比',
        'f204': '主力净流入最大股',
        'f205': '股票代码',
        'f206': 'F206'
    }
    
    # Select and rename columns to match the provided format
    available_columns = [col for col in field_mapping.keys() if col in df.columns]
    df = df[available_columns].rename(columns=field_mapping)
    
    # Convert Tme field to readable time format
    if 'Tme' in df.columns:
        df['Tme'] = pd.to_datetime(df['Tme'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Convert all "流入" fields to 亿 units with 2 decimal places
    def format_inflow_to_yi(value):
        """Convert inflow values to 亿 units with 2 decimal places"""
        try:
            # Handle None, empty string, or NaN values
            if value is None or value == '' or (isinstance(value, float) and pd.isna(value)):
                return 0.00
            
            # Convert to float first, then to 亿 units
            num_value = float(value)
            if num_value == 0:
                return 0.00
            return round(num_value / 100000000, 2)
        except (ValueError, TypeError):
            return 0.00
    
    # Apply formatting to all "流入" columns (excluding "最大股" and "占比" columns)
    inflow_columns = [col for col in df.columns if '流入' in col and '最大股' not in col and '占比' not in col]
    for col in inflow_columns:
        df[col] = df[col].apply(format_inflow_to_yi)
    
    # Format 股票代码 as 6-digit number with leading zeros
    if '股票代码' in df.columns:
        df['股票代码'] = df['股票代码'].apply(lambda x: f"{int(x):06d}" if pd.notna(x) and str(x).isdigit() else x)
    
    # Save to CSV with date string
    dtestr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    csv_path = f'../generated/em/{dte_short}/bk_flow_{dtestr}.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8')
    print(f"Data saved to: {csv_path}")
    
    print(df)
    return df

def get_capreal_stock():
    cookies = {
        'qgqp_b_id': 'e7a1ea46296469d1fa43b9951dcf960c',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_si': '55114734274095',
        'st_asi': 'delete',
        'st_pvi': '27639117154963',
        'st_sp': '2025-07-08%2008%3A54%3A21',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '39',
        'st_psi': '20250725090538652-113300300820-8764063101',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/zjlx/detail.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'qgqp_b_id=e7a1ea46296469d1fa43b9951dcf960c; fullscreengg=1; fullscreengg2=1; st_si=55114734274095; st_asi=delete; st_pvi=27639117154963; st_sp=2025-07-08%2008%3A54%3A21; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=39; st_psi=20250725090538652-113300300820-8764063101',
    }

    response = requests.get(
        'https://push2delay.eastmoney.com/api/qt/clist/get?cb=jQuery1123041815310694054264_1753406409971&fid=f3&po=1&pz=50&pn=1&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A13%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A7%2Bf%3A!2%2Cm%3A1%2Bt%3A3%2Bf%3A!2&fields=f12%2Cf14%2Cf2%2Cf3%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13',
        cookies=cookies,
        headers=headers,
    )
    open(os.path.join(temp_dir, 'capreal_stock.txt'), 'w', encoding='utf-8').write(response.text)
    json_str = re.search(r'\((\{.*\})\);?$', response.text, re.DOTALL).group(1)
    data = json.loads(json_str)
    stock_list = data['data']['diff']
    df=pd.DataFrame(stock_list)
    print(df)
    return df   

def is_trading_time():
    """检查当前是否为交易时间"""
    from datetime import datetime
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # 非工作日（周六、周日）
    if weekday >= 5:
        return False
    
    # 检查是否为节假日
    date_str = now.strftime('%Y-%m-%d')
    holidays = {
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
    
    if date_str in holidays:
        return False
    
    # 工作日检查时间
    current_time = now.time()
    morning_start = datetime.strptime('09:30', '%H:%M').time()
    morning_end = datetime.strptime('11:30', '%H:%M').time()
    afternoon_start = datetime.strptime('13:00', '%H:%M').time()
    afternoon_end = datetime.strptime('15:00', '%H:%M').time()
    
    return (morning_start <= current_time <= morning_end) or (afternoon_start <= current_time <= afternoon_end)

def find_latest_stockcomment_files():
    """查找最新的stockcomment_和stockcommentC_文件"""
    import glob
    
    # 查找stockcomment_文件（在所有日期子目录中）
    stockcomment_files = glob.glob('../generated/em/*/stockcomment_*.csv')
    stockcommentC_files = glob.glob('../generated/em/*/stockcommentC_*.csv')
    
    latest_stockcomment = None
    latest_stockcommentC = None
    
    if stockcomment_files:
        # 按文件名中的时间戳排序（最新的在后）
        stockcomment_files.sort(key=lambda x: os.path.basename(x).split('_')[1].split('.')[0])
        latest_stockcomment = stockcomment_files[-1]
    
    if stockcommentC_files:
        # 按文件名中的时间戳排序（最新的在后）
        stockcommentC_files.sort(key=lambda x: os.path.basename(x).split('_')[1].split('.')[0])
        latest_stockcommentC = stockcommentC_files[-1]
    
    return latest_stockcomment, latest_stockcommentC

def get_stockcomment(force_refetch=False):
    '''
    获取股票评论数据（带缓存策略）
    
    缓存策略：
    - 东财综合评价每日约 17:00 更新一次
    - 若本地文件不早于「当前应持有的最新 17:00 批次」，直接复用
    - 非交易日不主动拉取，复用最近批次
    - force_refetch=True 时强制重新获取
    
    URL: https://datacenter-web.eastmoney.com/api/data/v1/get?...
    '''
    
    if not force_refetch:
        latest_stockcomment, latest_stockcommentC = find_latest_stockcomment_files()
        if latest_stockcomment and latest_stockcommentC:
            try:
                from stock.module_cache_policy import (
                    is_stockcomment_cache_fresh,
                    is_trading_calendar_day,
                    stockcomment_cache_policy_summary,
                )
            except ImportError:
                from module_cache_policy import (
                    is_stockcomment_cache_fresh,
                    is_trading_calendar_day,
                    stockcomment_cache_policy_summary,
                )

            file_mtime = datetime.fromtimestamp(os.path.getmtime(latest_stockcomment))
            now = datetime.now()
            if is_stockcomment_cache_fresh(file_mtime, now):
                print(f"📋 stockcomment 缓存有效 ({stockcomment_cache_policy_summary()}):")
                print(f"  📊 stockcomment: {latest_stockcomment}")
                print(f"  📋 stockcommentC: {latest_stockcommentC}")
                return {
                    'stockcomment_file': latest_stockcomment,
                    'stockcommentC_file': latest_stockcommentC,
                    'cached': True,
                    'reason': f'缓存有效 · {stockcomment_cache_policy_summary()}',
                }
            if not is_trading_calendar_day(now):
                print(f"⏰ 非交易日，复用最近 stockcomment 批次:")
                print(f"  📊 stockcomment: {latest_stockcomment}")
                return {
                    'stockcomment_file': latest_stockcomment,
                    'stockcommentC_file': latest_stockcommentC,
                    'cached': True,
                    'stale': True,
                    'reason': '非交易日复用最近批次',
                }
            print("🔄 stockcomment 缓存已过期（已过当日 17:00 批次），重新获取…")
        else:
            print("⚠️  未找到 stockcomment 缓存文件，将获取新数据")
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '61',
        'st_psi': '20250725224944108-113300300975-3122995398',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/stockcomment/',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    # 股票评论数据字段映射
    stockcomment_col_map = {
        "SECURITY_INNER_CODE": "股票内部代码",
        "SECURITY_CODE": "股票代码",
        "SECUCODE": "完整股票代码",
        "TRADE_DATE": "交易日期",
        "SECURITY_NAME_ABBR": "股票简称",
        "SUPERDEAL_INFLOW": "超大单流入",
        "SUPERDEAL_OUTFLOW": "超大单流出",
        "PRIME_INFLOW": "主力流入",
        "CLOSE_PRICE": "收盘价",
        "CHANGE_RATE": "涨跌幅",
        "TRADE_MARKET_CODE": "交易市场代码",
        "TURNOVERRATE": "换手率",
        "PRIME_COST": "主力成本",
        "PE_DYNAMIC": "市盈率",
        "PRIME_COST_20DAYS": "20日主力成本",
        "PRIME_COST_60DAYS": "60日主力成本",
        "ORG_PARTICIPATE": "机构参与度",
        "PARTICIPATE_TYPE": "参与类型",
        "BIGDEAL_INFLOW": "大单流入",
        "BIGDEAL_OUTFLOW": "大单流出",
        "BUY_SUPERDEAL_RATIO": "买入超大单比例",
        "BUY_BIGDEAL_RATIO": "买入大单比例",
        "RATIO": "主力占比",
        "RATIO_3DAYS": "3日主力占比",
        "RATIO_50DAYS": "50日主力占比",
        "TOTALSCORE": "总分",
        "RANK_UP": "排名上升",
        "RANK": "排名",
        "FOCUS": "关注度",
        "SECURITY_TYPE_CODE": "股票类型代码"
    }

    fn=os.path.join(temp_dir, 'stockcomment.txt')
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    fn_csv = f'../generated/em/{dte_short}/stockcomment_{nowstr}.csv'
    
    page_size = 500
    pgn=1

    # 先获取总页数
    params = {
        'callback': 'jQuery1123004618854589773669_1754089132719',
        'sortColumns': 'SECURITY_CODE',
        'sortTypes': '1',
        'pageSize': page_size,
        'pageNumber': pgn,
        'reportName': 'RPT_DMSK_TS_STOCKNEW',
        'quoteColumns': 'f2~01~SECURITY_CODE~CLOSE_PRICE,f8~01~SECURITY_CODE~TURNOVERRATE,f3~01~SECURITY_CODE~CHANGE_RATE,f9~01~SECURITY_CODE~PE_DYNAMIC',
        'quoteType': '0',
        'columns': 'ALL',
        'filter': '',
        'token': '894050c76af8597a853f5b408b759f5d',
    }

    response = requests.get('https://datacenter-web.eastmoney.com/api/data/v1/get', params=params, cookies=cookies, headers=headers)
    # 先保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    data = parse_stockcomment(fn)
    df = pd.concat([pd.Series(t) for t in data['result']['data']], axis=1).T

    pageTotal = data['result']['pages']
    print(f'Page total {pageTotal}')

    for pgn in trange(1, pageTotal + 1, desc='抓取股票评论数据进度'):
        params = {
            'callback': 'jQuery1123004618854589773669_1754089132719',
            'sortColumns': 'SECURITY_CODE',
            'sortTypes': '1',
            'pageSize': page_size,
            'pageNumber': pgn,
            'reportName': 'RPT_DMSK_TS_STOCKNEW',
            'quoteColumns': 'f2~01~SECURITY_CODE~CLOSE_PRICE,f8~01~SECURITY_CODE~TURNOVERRATE,f3~01~SECURITY_CODE~CHANGE_RATE,f9~01~SECURITY_CODE~PE_DYNAMIC',
            'quoteType': '0',
            'columns': 'ALL',
            'filter': '',
            'token': '894050c76af8597a853f5b408b759f5d',
        }

        response = requests.get('https://datacenter-web.eastmoney.com/api/data/v1/get', params=params, cookies=cookies, headers=headers)
        # 每次都保存当前页内容
        open(fn, 'w', encoding='utf8').write(response.text)
        data = parse_stockcomment(fn)
        df = pd.concat([pd.Series(t) for t in data['result']['data']], axis=1).T

        if pgn == 1:
            open(fn_csv, 'w', encoding='utf8').write(df.to_csv(index=False))
        else:
            open(fn_csv, 'a', encoding='utf8').write(df.to_csv(header=False, index=False))
    
    # 生成紧凑格式报告
    fn_csv_compact = f'../generated/em/{dte_short}/stockcommentC_{nowstr}.csv'
    gen_report(fn_csv, fn_csv_compact)
    
    print(f"✅ 股票评论数据获取完成:")
    print(f"  📊 原始文件: {fn_csv}")
    print(f"  📋 紧凑格式: {fn_csv_compact}")
    
    return {
        'stockcomment_file': fn_csv,
        'stockcommentC_file': fn_csv_compact,
        'cached': False,
        'reason': '新获取数据'
    }

def gen_report(input_file, output_file):
    '''
    从stockcomment文件生成紧凑格式报告
    使用中文表头，保持除"相关"以外的所有字段
    从同目录下最近的quote_文件中获取成交额字段
    '''
    fn_market_level = 'shared/market_level.csv'
    
    # Try to find a flow file dynamically instead of hardcoding
    flow_files = glob.glob('../generated/em/*/flow_*.csv')
    fn_flow = None
    if flow_files:
        # Get the most recent flow file
        fn_flow = max(flow_files, key=os.path.getmtime)
        print(f"Using flow file: {fn_flow}")

    if not os.path.exists(fn_market_level) and fn_flow and os.path.exists(fn_flow):
        try:
            df_market_level = pd.read_csv(fn_flow)
            df_market_level[['股票代码','名称','流通市值','市值分位']].to_csv(fn_market_level, index=False)
        except Exception as e:
            print(f"Warning: Could not create market level file: {e}")
    elif not os.path.exists(fn_market_level):
        print("Warning: No flow file found, skipping market level file creation")
    
    try:
        # 读取原始数据
        df = pd.read_csv(input_file, encoding='utf-8')
        
        # 查找同目录下最近的quote_文件
        input_dir = os.path.dirname(input_file)
        quote_files = glob.glob(os.path.join(input_dir, 'q_*.csv'))
        
        if quote_files:
            # 按修改时间排序，获取最新的quote文件
            # 使用安全的排序函数，处理可能的None值
            def safe_getmtime(filepath):
                try:
                    mtime = os.path.getmtime(filepath)
                    return mtime if mtime is not None else 0
                except (OSError, IOError):
                    return 0
            
            quote_files.sort(key=safe_getmtime, reverse=True)
            latest_quote_file = quote_files[0]
            print(f'使用quote文件: {latest_quote_file}')
            
            # 读取quote文件
            df_quote = pd.read_csv(latest_quote_file, encoding='utf-8')
            
            # 如果quote文件有成交额和成交量字段，则合并数据
            quote_columns = []
            if '成交额' in df_quote.columns:
                quote_columns.append('成交额')
            if '成交量' in df_quote.columns:
                quote_columns.append('成交量')
            
            if quote_columns:
                # 检查quote文件中的股票代码字段名
                code_column = None
                if 'SECURITY_CODE' in df_quote.columns:
                    code_column = 'SECURITY_CODE'
                elif '股票代码' in df_quote.columns:
                    code_column = '股票代码'
                
                if code_column:
                    # 通过股票代码合并数据
                    merge_columns = [code_column] + quote_columns
                    df_merged = df.merge(
                        df_quote[merge_columns], 
                        left_on='SECURITY_CODE',
                        right_on=code_column,
                        how='left'
                    )
                    # 删除重复的代码列
                    if code_column != 'SECURITY_CODE':
                        df_merged = df_merged.drop(columns=[code_column])
                    df = df_merged
                    print(f'成功合并数据，包含字段: {", ".join(quote_columns)}，共{len(df)}条记录')
                else:
                    print('警告: quote文件中未找到股票代码字段')
            else:
                print('警告: quote文件中未找到成交额或成交量字段')
        else:
            print('警告: 未找到quote文件')
        
        # 字段映射：原始字段名 -> 中文表头
        column_mapping = {
            'SECURITY_CODE': '股票代码',
            'SECURITY_NAME_ABBR': '名称', 
            'CLOSE_PRICE': '最新价',
            'CHANGE_RATE': '涨跌幅',
            'TURNOVERRATE': '换手率',
            'PE_DYNAMIC': '市盈率',
            'PRIME_COST': '主力成本',
            'PRIME_INFLOW': '主力流入',
            'ORG_PARTICIPATE': '机构参与度',
            'TOTALSCORE': '综合得分',
            'RATIO': '主力占比',
            'RANK_UP': '上升排名',
            'RANK': '目前排名',
            'FOCUS': '关注指数',
            '成交额': '成交额',
            '成交量': '成交量'
        }
        
        # 选择需要的字段（除了"相关"字段）
        key_columns = list(column_mapping.keys())
        available_columns = [col for col in key_columns if col in df.columns]
        df_compact = df[available_columns].copy()
        
        # 数据类型转换
        numeric_columns = ['CLOSE_PRICE', 'CHANGE_RATE', 'TURNOVERRATE', 'PE_DYNAMIC', 
                          'PRIME_COST', 'ORG_PARTICIPATE', 'TOTALSCORE', 'RANK_UP', 
                          'RANK', 'FOCUS', '成交额', '成交量']
        
        for col in numeric_columns:
            if col in df_compact.columns:
                df_compact[col] = pd.to_numeric(df_compact[col], errors='coerce')
        
        # 格式化股票代码为6位数字
        if 'SECURITY_CODE' in df_compact.columns:
            df_compact['SECURITY_CODE'] = df_compact['SECURITY_CODE'].apply(lambda x: f'{int(x):06d}' if pd.notna(x) else x)
            # 确保股票代码列被保存为字符串格式
            df_compact['SECURITY_CODE'] = df_compact['SECURITY_CODE'].astype(str)
        
        # 格式化数值字段，保留2位小数
        decimal_columns = ['CLOSE_PRICE', 'PE_DYNAMIC', 'PRIME_COST', 'TOTALSCORE', 'FOCUS', '成交额', '成交量']
        for col in decimal_columns:
            if col in df_compact.columns:
                df_compact[col] = df_compact[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else x)
        
        # 格式化百分比字段
        if 'CHANGE_RATE' in df_compact.columns:
            df_compact['CHANGE_RATE'] = df_compact['CHANGE_RATE'].apply(lambda x: f'{x:.2f}%' if pd.notna(x) else x)
        if 'TURNOVERRATE' in df_compact.columns:
            df_compact['TURNOVERRATE'] = df_compact['TURNOVERRATE'].apply(lambda x: f'{x:.2f}%' if pd.notna(x) else x)
        if 'ORG_PARTICIPATE' in df_compact.columns:
            df_compact['ORG_PARTICIPATE'] = df_compact['ORG_PARTICIPATE'].apply(lambda x: f'{x:.2f}%' if pd.notna(x) else x)
        
        # 合并上升排名和目前排名为"上升/目前排名"格式
        if 'RANK_UP' in df_compact.columns and 'RANK' in df_compact.columns:
            df_compact['上升/目前排名'] = df_compact.apply(
                lambda row: f"{int(row['RANK_UP'])}/{int(row['RANK'])}" 
                if pd.notna(row['RANK_UP']) and pd.notna(row['RANK']) else '', axis=1
            )
            # 删除单独的排名列
            df_compact = df_compact.drop(['RANK_UP', 'RANK'], axis=1)
        
        # 重命名列为中文
        df_compact = df_compact.rename(columns=column_mapping)
        
        # 按综合得分排序
        if '综合得分' in df_compact.columns:
            df_compact = df_compact.sort_values('综合得分', ascending=False)
        
        # 读取 shared/market_level.csv 并与 df_compact 按股票代码合并，添加“市值分位”列
        try:
            df_market = pd.read_csv('shared/market_level.csv', dtype={'股票代码': str})
            # 兼容不同股票代码字段名
            code_col = None
            for col in ['SECURITY_CODE', '股票代码']:
                if col in df_compact.columns:
                    code_col = col
                    break
            if code_col is not None:
                # 统一股票代码为6位字符串
                df_compact[code_col] = df_compact[code_col].apply(lambda x: f'{int(x):06d}' if pd.notna(x) and str(x).isdigit() else str(x))
                df_market['股票代码'] = df_market['股票代码'].apply(lambda x: f'{int(x):06d}' if pd.notna(x) and str(x).isdigit() else str(x))
                df_compact = df_compact.merge(
                    df_market[['股票代码', '流通市值','市值分位']],
                    left_on=code_col,
                    right_on='股票代码',
                    how='left'
                )
                df_compact = df_compact.drop(columns=['股票代码'])

        except Exception as e:
            print(f"⚠️ 合并市值分位信息时出错: {e}")

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 保存紧凑格式文件
        df_compact.to_csv(output_file, index=False, encoding='utf-8')
        print(f'紧凑格式报告已保存到: {output_file}')
        print(f'报告包含 {len(df_compact)} 条记录，{len(df_compact.columns)} 个字段')
        
        # 显示前10条记录
        print('\n前10条记录预览:')
        print(df_compact.head(10).to_string(index=False))
        
    except Exception as e:
        print(f'生成报告时出错: {e}')
        raise

def parse_stockcomment(fn):
    '''
    解析股票评论数据
    字段映射:
    - SECURITY_INNER_CODE: 股票内部代码
    - SECURITY_CODE: 股票代码
    - SECUCODE: 完整股票代码
    - TRADE_DATE: 交易日期
    - SECURITY_NAME_ABBR: 股票简称
    - SUPERDEAL_INFLOW: 超大单流入
    - SUPERDEAL_OUTFLOW: 超大单流出
    - PRIME_INFLOW: 主力流入
    - CLOSE_PRICE: 收盘价
    - CHANGE_RATE: 涨跌幅
    - TRADE_MARKET_CODE: 交易市场代码
    - TURNOVERRATE: 换手率
    - PRIME_COST: 主力成本
    - PE_DYNAMIC: 市盈率
    - PRIME_COST_20DAYS: 20日主力成本
    - PRIME_COST_60DAYS: 60日主力成本
    - ORG_PARTICIPATE: 机构参与度
    - PARTICIPATE_TYPE: 参与类型
    - BIGDEAL_INFLOW: 大单流入
    - BIGDEAL_OUTFLOW: 大单流出
    - BUY_SUPERDEAL_RATIO: 买入超大单比例
    - BUY_BIGDEAL_RATIO: 买入大单比例
    - RATIO: 主力占比
    - RATIO_3DAYS: 3日主力占比
    - RATIO_50DAYS: 50日主力占比
    - TOTALSCORE: 总分
    - RANK_UP: 排名上升
    - RANK: 排名
    - FOCUS: 关注度
    - SECURITY_TYPE_CODE: 股票类型代码
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    # 用正则提取大括号包裹的 JSON 内容
    match = re.search(r'\((\{.*\})\);?$', content, re.DOTALL)
    if not match:
        raise ValueError("未找到 JSON 数据")
    json_str = match.group(1)
    data = json.loads(json_str)
    return data

def get_fund():
    '''
    获取基金排名数据
    URL: https://fund.eastmoney.com/data/rankhandler.aspx?op=ph&dt=kf&ft=all&rs=&gs=0&sc=1nzf&st=desc&sd=2024-08-02&ed=2025-08-02&qdii=&tabSubtype=,,,,,&pi=2&pn=50&dx=1&v=0.5614412470750552
    '''
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '61',
        'st_psi': '20250725224944108-113300300975-3122995398',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://fund.eastmoney.com/data/fundranking.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    # 基金数据字段映射
    fund_col_map = {
        "FUND_CODE": "基金代码",
        "FUND_NAME": "基金名称",
        "FUND_PINYIN": "基金拼音",
        "NAV_DATE": "净值日期",
        "UNIT_NAV": "单位净值",
        "ACCUM_NAV": "累计净值",
        "DAILY_GROWTH_RATE": "日增长率",
        "WEEKLY_GROWTH_RATE": "近1周",
        "MONTHLY_GROWTH_RATE": "近1月",
        "QUARTERLY_GROWTH_RATE": "近3月",
        "HALF_YEAR_GROWTH_RATE": "近6月",
        "YEARLY_GROWTH_RATE": "近1年",
        "YEAR_TO_DATE_GROWTH_RATE": "今年以来",
        "SINCE_INCEPTION_GROWTH_RATE": "成立以来",
        "ESTABLISH_DATE": "成立日期",
        "FUND_TYPE": "基金类型",
        "FUND_SIZE": "基金规模",
        "MANAGEMENT_FEE": "管理费率",
        "CUSTODIAN_FEE": "托管费率",
        "SUBSCRIPTION_STATUS": "申购状态",
        "SUBSCRIPTION_FEE": "申购费率",
        "REDEMPTION_STATUS": "赎回状态",
        "REDEMPTION_FEE": "赎回费率",
        "MIN_SUBSCRIPTION_AMOUNT": "最小申购金额"
    }

    fn=os.path.join(temp_dir, 'fundrank.txt')
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    fn_csv = f'../generated/em/{dte_short}/fund_{nowstr}.csv'
    page_size = 100
    pgn=1

    # 先获取总页数
    params = {
        'op': 'ph',
        'dt': 'kf',
        'ft': 'all',
        'rs': '',
        'gs': '0',
        'sc': '1nzf',
        'st': 'desc',
        'sd': '2024-08-02',
        'ed': '2025-08-02',
        'qdii': '',
        'tabSubtype': ',,,,,',
        'pi': pgn,
        'pn': page_size,
        'dx': '1',
        'v': '0.5614412470750552',
    }

    response = requests.get('https://fund.eastmoney.com/data/rankhandler.aspx', params=params, cookies=cookies, headers=headers)
    # 先保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    data = parse_fund(fn)
    
    # 解析第一页数据获取总页数
    pageTotal = data['allPages']
    print(f'Page total {pageTotal}')

    all_fund_data = []
    
    for pgn in trange(1, pageTotal + 1, desc='抓取基金排名数据进度'):
        params = {
            'op': 'ph',
            'dt': 'kf',
            'ft': 'all',
            'rs': '',
            'gs': '0',
            'sc': '1nzf',
            'st': 'desc',
            'sd': '2024-08-02',
            'ed': '2025-08-02',
            'qdii': '',
            'tabSubtype': ',,,,,',
            'pi': pgn,
            'pn': page_size,
            'dx': '1',
            'v': '0.5614412470750552',
        }

        response = requests.get('https://fund.eastmoney.com/data/rankhandler.aspx', params=params, cookies=cookies, headers=headers)
        # 每次都保存当前页内容
        open(fn, 'w', encoding='utf8').write(response.text)
        data = parse_fund(fn)
        
        # 解析基金数据
        if 'datas' in data and data['datas']:
            for fund_str in data['datas']:
                fund_data = fund_str.split(',')
                if len(fund_data) >= 24:  # 确保有足够的字段
                    fund_dict = {
                        "FUND_CODE": fund_data[0],
                        "FUND_NAME": fund_data[1],
                        "FUND_PINYIN": fund_data[2],
                        "NAV_DATE": fund_data[3],
                        "UNIT_NAV": fund_data[4],
                        "ACCUM_NAV": fund_data[5],
                        "DAILY_GROWTH_RATE": fund_data[6],
                        "WEEKLY_GROWTH_RATE": fund_data[7],
                        "MONTHLY_GROWTH_RATE": fund_data[8],
                        "QUARTERLY_GROWTH_RATE": fund_data[9],
                        "HALF_YEAR_GROWTH_RATE": fund_data[10],
                        "YEARLY_GROWTH_RATE": fund_data[11],
                        "YEAR_TO_DATE_GROWTH_RATE": fund_data[12],
                        "SINCE_INCEPTION_GROWTH_RATE": fund_data[13],
                        "ESTABLISH_DATE": fund_data[14],
                        "FUND_TYPE": fund_data[15],
                        "FUND_SIZE": fund_data[16] if len(fund_data) > 16 else "",
                        "MANAGEMENT_FEE": fund_data[17] if len(fund_data) > 17 else "",
                        "CUSTODIAN_FEE": fund_data[18] if len(fund_data) > 18 else "",
                        "SUBSCRIPTION_STATUS": fund_data[19] if len(fund_data) > 19 else "",
                        "SUBSCRIPTION_FEE": fund_data[20] if len(fund_data) > 20 else "",
                        "REDEMPTION_STATUS": fund_data[21] if len(fund_data) > 21 else "",
                        "REDEMPTION_FEE": fund_data[22] if len(fund_data) > 22 else "",
                        "MIN_SUBSCRIPTION_AMOUNT": fund_data[23] if len(fund_data) > 23 else ""
                    }
                    all_fund_data.append(fund_dict)

    # 保存所有数据到CSV
    df = pd.DataFrame(all_fund_data)
    df.to_csv(fn_csv, index=False, encoding='utf-8')
    print(f'基金数据已保存到: {fn_csv}')

def parse_fund(fn):
    '''
    解析基金排名数据
    字段映射:
    - FUND_CODE: 基金代码
    - FUND_NAME: 基金名称
    - FUND_PINYIN: 基金拼音
    - NAV_DATE: 净值日期
    - UNIT_NAV: 单位净值
    - ACCUM_NAV: 累计净值
    - DAILY_GROWTH_RATE: 日增长率
    - WEEKLY_GROWTH_RATE: 近1周增长率
    - MONTHLY_GROWTH_RATE: 近1月增长率
    - QUARTERLY_GROWTH_RATE: 近3月增长率
    - HALF_YEAR_GROWTH_RATE: 近6月增长率
    - YEARLY_GROWTH_RATE: 近1年增长率
    - YEAR_TO_DATE_GROWTH_RATE: 今年以来增长率
    - SINCE_INCEPTION_GROWTH_RATE: 成立以来增长率
    - ESTABLISH_DATE: 成立日期
    - FUND_TYPE: 基金类型
    - FUND_SIZE: 基金规模
    - MANAGEMENT_FEE: 管理费率
    - CUSTODIAN_FEE: 托管费率
    - SUBSCRIPTION_STATUS: 申购状态
    - SUBSCRIPTION_FEE: 申购费率
    - REDEMPTION_STATUS: 赎回状态
    - REDEMPTION_FEE: 赎回费率
    - MIN_SUBSCRIPTION_AMOUNT: 最小申购金额
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取 var rankData = { ... }; 中的内容
    match = re.search(r'var rankData = (\{.*?\});', content, re.DOTALL)
    if not match:
        raise ValueError("未找到基金排名数据")
    
    js_obj_str = match.group(1)
    
    # 使用更简单的方法：直接提取需要的信息
    # 提取 datas 数组
    datas_match = re.search(r'datas:\[(.*?)\]', js_obj_str, re.DOTALL)
    if not datas_match:
        raise ValueError("未找到基金数据数组")
    
    datas_str = datas_match.group(1)
    
    # 提取其他信息
    all_records_match = re.search(r'allRecords:(\d+)', js_obj_str)
    all_pages_match = re.search(r'allPages:(\d+)', js_obj_str)
    page_index_match = re.search(r'pageIndex:(\d+)', js_obj_str)
    page_num_match = re.search(r'pageNum:(\d+)', js_obj_str)
    
    # 解析基金数据字符串
    fund_data_list = []
    # 分割每个基金数据（用","分隔，但要注意字符串内的逗号）
    # 使用正则表达式匹配每个基金数据项
    fund_items = re.findall(r'"([^"]*(?:,[^"]*)*)"', datas_str)
    
    # 构建返回的数据结构
    data = {
        'datas': fund_items,
        'allRecords': int(all_records_match.group(1)) if all_records_match else 0,
        'allPages': int(all_pages_match.group(1)) if all_pages_match else 0,
        'pageIndex': int(page_index_match.group(1)) if page_index_match else 0,
        'pageNum': int(page_num_match.group(1)) if page_num_match else 0
    }
    
    return data

def get_report():
    '''
    获取研究报告数据
    URL: https://reportapi.eastmoney.com/report/list2
    '''
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '61',
        'st_psi': '20250725224944108-113300300975-3122995398',
    }

    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://data.eastmoney.com',
        'Referer': 'https://data.eastmoney.com/report/stock.jshtml',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    # 报告数据字段映射
    report_col_map = {
        "title": "报告标题",
        "stockName": "股票名称",
        "stockCode": "股票代码",
        "orgCode": "机构代码",
        "orgName": "机构名称",
        "orgSName": "机构简称",
        "publishDate": "发布日期",
        "infoCode": "信息代码",
        "column": "栏目",
        "predictNextTwoYearEps": "预测后年每股收益",
        "predictNextTwoYearPe": "预测后年市盈率",
        "predictNextYearEps": "预测明年每股收益",
        "predictNextYearPe": "预测明年市盈率",
        "predictThisYearEps": "预测今年每股收益",
        "predictThisYearPe": "预测今年市盈率",
        "predictLastYearEps": "预测去年每股收益",
        "predictLastYearPe": "预测去年市盈率",
        "actualLastTwoYearEps": "实际后年每股收益",
        "actualLastYearEps": "实际去年每股收益",
        "industryCode": "行业代码",
        "industryName": "行业名称",
        "emIndustryCode": "东方财富行业代码",
        "indvInduCode": "个股行业代码",
        "indvInduName": "个股行业名称",
        "emRatingCode": "东方财富评级代码",
        "emRatingValue": "东方财富评级值",
        "emRatingName": "东方财富评级名称",
        "lastEmRatingCode": "上次东方财富评级代码",
        "lastEmRatingValue": "上次东方财富评级值",
        "lastEmRatingName": "上次东方财富评级名称",
        "ratingChange": "评级变化",
        "reportType": "报告类型",
        "author": "作者",
        "indvIsNew": "个股是否新股",
        "researcher": "研究员",
        "newListingDate": "新股上市日期",
        "newPurchaseDate": "新股申购日期",
        "newIssuePrice": "新股发行价",
        "newPeIssueA": "新股发行市盈率",
        "indvAimPriceT": "个股目标价",
        "indvAimPriceL": "个股目标价下限",
        "attachType": "附件类型",
        "attachSize": "附件大小",
        "attachPages": "附件页数",
        "encodeUrl": "编码URL",
        "sRatingName": "评级名称",
        "sRatingCode": "评级代码",
        "market": "市场",
        "authorID": "作者ID",
        "count": "计数",
        "orgType": "机构类型"
    }

    fn=os.path.join(temp_dir, 'report.txt')
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    fn_csv = f'../generated/em/{dte_short}/report_{nowstr}.csv'
    page_size = 100
    page_no = 1

    # 先获取总页数
    json_data = {
        'beginTime': '2023-08-02',
        'endTime': '2025-08-02',
        'industryCode': '*',
        'ratingChange': None,
        'rating': None,
        'orgCode': None,
        'code': '*',
        'rcode': '',
        'pageSize': page_size,
        'p': page_no,
        'pageNo': page_no,
        'pageNum': page_no,
        'pageNumber': page_no,
    }

    response = requests.post('https://reportapi.eastmoney.com/report/list2', headers=headers, cookies=cookies, json=json_data)
    # 先保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    data = parse_report(fn)
    
    # 解析第一页数据获取总页数
    pageTotal = data.get('TotalPage', 1)
    print(f'Page total {pageTotal}')

    all_report_data = []
    
    for page_no in trange(1, min(pageTotal + 1, 100), desc='抓取研究报告数据进度'):  # 限制最多100页
        json_data = {
            'beginTime': '2023-08-02',
            'endTime': '2025-08-02',
            'industryCode': '*',
            'ratingChange': None,
            'rating': None,
            'orgCode': None,
            'code': '*',
            'rcode': '',
            'pageSize': page_size,
            'p': page_no,
            'pageNo': page_no,
            'pageNum': page_no,
            'pageNumber': page_no,
        }

        response = requests.post('https://reportapi.eastmoney.com/report/list2', headers=headers, cookies=cookies, json=json_data)
        # 每次都保存当前页内容
        open(fn, 'w', encoding='utf8').write(response.text)
        data = parse_report(fn)
        
        # 解析报告数据
        if 'data' in data and data['data']:
            for report_item in data['data']:
                # 处理作者字段（列表转字符串）
                if 'author' in report_item and isinstance(report_item['author'], list):
                    report_item['author'] = ';'.join(report_item['author'])
                
                # 处理作者ID字段（列表转字符串）
                if 'authorID' in report_item and isinstance(report_item['authorID'], list):
                    report_item['authorID'] = ';'.join(report_item['authorID'])
                
                all_report_data.append(report_item)

    # 保存所有数据到CSV
    df = pd.DataFrame(all_report_data)
    df.to_csv(fn_csv, index=False, encoding='utf-8')
    print(f'研究报告数据已保存到: {fn_csv}')

def parse_report(fn):
    '''
    解析研究报告数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"响应内容: {content[:200]}...")
        raise ValueError(f"研究报告数据解析失败: {e}")

def get_profit():
    '''
    获取盈利预测数据
    URL: https://datacenter-web.eastmoney.com/api/data/v1/get?callback=datatable3114652&reportName=RPT_WEB_RESPREDICT&columns=WEB_RESPREDICT&pageNumber=2&pageSize=50&sortTypes=-1&sortColumns=RATING_ORG_NUM&p=2&pageNo=2&pageNum=2&_=1754093555886
    '''
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '61',
        'st_psi': '20250725224944108-113300300975-3122995398',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/report/predict.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    fn=os.path.join(temp_dir, 'profit.txt')
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    fn_csv = f'../generated/em/{dte_short}/profit_{nowstr}.csv'
    page_size = 200
    page_no = 1

    # 先获取总页数
    params = {
        'callback': 'datatable3114652',
        'reportName': 'RPT_WEB_RESPREDICT',
        'columns': 'WEB_RESPREDICT',
        'pageNumber': page_no,
        'pageSize': page_size,
        'sortTypes': '-1',
        'sortColumns': 'RATING_ORG_NUM',
        'p': page_no,
        'pageNo': page_no,
        'pageNum': page_no,
        '_': int(time.time() * 1000),
    }

    response = requests.get('https://datacenter-web.eastmoney.com/api/data/v1/get', params=params, cookies=cookies, headers=headers)
    # 先保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    data = parse_profit(fn)
    
    # 解析第一页数据获取总页数
    pageTotal = data['result']['pages']
    print(f'Page total {pageTotal}')

    all_profit_data = []
    
    for page_no in trange(1, pageTotal + 1, desc='抓取盈利预测数据进度'):
        params = {
            'callback': 'datatable3114652',
            'reportName': 'RPT_WEB_RESPREDICT',
            'columns': 'WEB_RESPREDICT',
            'pageNumber': page_no,
            'pageSize': page_size,
            'sortTypes': '-1',
            'sortColumns': 'RATING_ORG_NUM',
            'p': page_no,
            'pageNo': page_no,
            'pageNum': page_no,
            '_': int(time.time() * 1000),
        }

        response = requests.get('https://datacenter-web.eastmoney.com/api/data/v1/get', params=params, cookies=cookies, headers=headers)
        # 每次都保存当前页内容
        open(fn, 'w', encoding='utf8').write(response.text)
        data = parse_profit(fn)
        
        # 解析盈利预测数据
        if 'result' in data and 'data' in data['result'] and data['result']['data']:
            for profit_item in data['result']['data']:
                all_profit_data.append(profit_item)

    # 保存所有数据到CSV
    df = pd.DataFrame(all_profit_data)
    df.to_csv(fn_csv, index=False, encoding='utf-8')
    print(f'盈利预测数据已保存到: {fn_csv}')

def parse_profit(fn):
    '''
    解析盈利预测数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取 datatable\d+({ ... }) 中的JSON内容
    match = re.search(r'datatable\d+\((\{.*?\})\)', content, re.DOTALL)
    if not match:
        raise ValueError("未找到盈利预测数据")
    
    json_str = match.group(1)
    
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"响应内容: {content[:200]}...")
        raise ValueError(f"盈利预测数据解析失败: {e}")

def get_respredict():
    '''
    获取研究报告预测数据
    URL: https://datacenter-web.eastmoney.com/api/data/v1/get?callback=datatable3114652&reportName=RPT_WEB_RESPREDICT&columns=WEB_RESPREDICT&pageNumber=2&pageSize=50&sortTypes=-1&sortColumns=RATING_ORG_NUM&p=2&pageNo=1
    '''
    
    cookies = {
        'qgqp_b_id': '625b35069288e7d72e8e0178a24c21da',
        'st_si': '45698176550929',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'p_origin': 'https%3A%2F%2Fai.eastmoney.com',
        'mtp': '1',
        'ct': 'ok9b0zb7LL2UVHB9XXfZzMAaJNa1RNYHPIOdXFQP_ZEI7oZFhoxmyh5UIpw0hUSnJVpofNDi9F_3OhRT-nSxf37sQ0F5EvCi0tYWE9COlxZEXn1RDQsmCLhBUXYxBzzt7MyXk9_H02h_N3oj0q3EQyC5UX_a8Gfdr-G3tH2Lqy4',
        'ut': 'FobyicMgeV6GWVhnfroLOKaJfKnxMAuI0NTJNYa60FM5u58rvqWjEpDrXpts3FWwykeEC-IZN7QDlzsu6wiaQ-xoEAmMiKE8tVnhiNJZcbDpWDYZDfdq9F0Hv2aAyvQq86riTbbBiWmOg_mVLeSVRg2x_mPQcey4A4HdHO5FVJBSHP8179F0sXZ_n0OYQ8AW3KiwJ_1ZYxi2lb7MG75ozSIhdftjEO9nCFV2xDMdQZm2pJJ2IBk1UMuWu_hABTCMmqLEWBNoU7U',
        'pi': '7160094286471412%3Bm7160094286471412%3BRedtea%3Bu%2Byvdy4yDRzq8F89rZjBRSP9XRXOy7qnqzfeylSu76FsvEoXTptbdN243JOh1TyhQCMrtIABI197EadI4v%2BKOf3K8q1TqI16AUW9XfJ4ma%2FGU%2FXS2aXHrvwPw7xVF1oT%2FPztuco8bB5Gw3ebw%2BqE2kXeUTvZF%2FZYbfwZcx1yJcFMDBgZ3NF9SQsYMRTfvYu0Hp93OKVA%3BXtMG04nvP8TUrcjejUvekMGjdSyHnxZbAoQw%2BezODquXESVnnRmtsViQDP9n8zDh1p3IDdldH6RTAhy1zHINdGqOvdxkh%2B8I7pXarWeJpUx2yHWEfktbcULhuF%2FIA2NLkeuMzg19V0lQESFuGC9nnVcO1Bethw%3D%3D',
        'uidal': '7160094286471412Redtea',
        'sid': '125088262',
        'vtpst': '|',
        'st_asi': 'delete',
        'st_pvi': '18468462604372',
        'st_sp': '2025-07-09%2022%3A43%3A28',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '52',
        'st_psi': '20250722233738412-113300301003-6901787555',
        'JSESSIONID': '3D543F995B3282FB932B9764A7B7C4E8',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'Referer': 'https://data.eastmoney.com/report/',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }

    fn = os.path.join(temp_dir, 'respredict.txt')
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    fn_csv = f'../generated/em/{dte_short}/respredict_{nowstr}.csv'
    page_size = 50
    pgn = 1

    # 先获取总页数
    params = {
        'callback': 'datatable3114652',
        'reportName': 'RPT_WEB_RESPREDICT',
        'columns': 'WEB_RESPREDICT',
        'pageNumber': pgn,
        'pageSize': page_size,
        'sortTypes': '-1',
        'sortColumns': 'RATING_ORG_NUM',
        'p': pgn,
        'pageNo': pgn,
    }

    response = requests.get('https://datacenter-web.eastmoney.com/api/data/v1/get', params=params, cookies=cookies, headers=headers)
    # 先保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    data = parse_respredict(fn)
    df = pd.concat([pd.Series(t) for t in data['result']['data']], axis=1).T

    pageTotal = data['result']['pages']
    print(f'Page total {pageTotal}')

    # for pgn in trange(1, pageTotal + 1, desc='抓取研究报告预测进度'):
    for pgn in trange(1, 5, desc='抓取研究报告预测进度'):

        params = {
            'callback': 'datatable3114652',
            'reportName': 'RPT_WEB_RESPREDICT',
            'columns': 'WEB_RESPREDICT',
            'pageNumber': pgn,
            'pageSize': page_size,
            'sortTypes': '-1',
            'sortColumns': 'RATING_ORG_NUM',
            'p': pgn,
            'pageNo': pgn,
        }

        response = requests.get('https://datacenter-web.eastmoney.com/api/data/v1/get', params=params, cookies=cookies, headers=headers)
        # 每次都保存当前页内容
        open(fn, 'w', encoding='utf8').write(response.text)
        data = parse_respredict(fn)
        df = pd.concat([pd.Series(t) for t in data['result']['data']], axis=1).T

        if pgn == 1:
            open(fn_csv, 'w', encoding='utf8').write(df.to_csv(index=False))
        else:
            open(fn_csv, 'a', encoding='utf8').write(df.to_csv(header=False, index=False))

    print(f'研究报告预测数据已保存到: {fn_csv}')
    return fn_csv


def parse_respredict(fn):
    '''
    解析研究报告预测数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    # 用正则提取大括号包裹的 JSON 内容
    match = re.search(r'\((\{.*\})\);?$', content, re.DOTALL)
    if not match:
        raise ValueError("未找到 JSON 数据")
    json_str = match.group(1)
    data = json.loads(json_str)
    return data

# https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?cb=jQuery1123041031322205900167_1754116916732&lmt=0&klt=1&fields1=f1%2Cf2%2Cf3%2Cf7&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61%2Cf62%2Cf63%2Cf64%2Cf65&ut=b2884a393a59ad64002292a3e90d46a5&secid=0.000050&_=1754116916733

def get_cap_kline(stock_code):
    '''
    获取股票资金流向K线数据
    URL: https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?cb=jQuery112305425756166095587_1754114749487&lmt=0&klt=101&fields1=f1%2Cf2%2Cf3%2Cf7&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61%2Cf62%2Cf63%2Cf64%2Cf65&ut=b2884a393a59ad64002292a3e90d46a5&secid=0.000050&_=1754114749488
    
    参数:
    stock_code: 股票代码，如 '000050'
    '''
    
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

    fn = os.path.join(temp_dir, f'cap_kline_{stock_code}.txt')
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    fn_csv = f'generated/cache/stockd/cap_kline_{stock_code}_{nowstr}.csv'
    
    # 构建请求参数
    timestamp = int(time.time() * 1000)
    callback = f'jQuery{timestamp}_{timestamp + 1}'
    
    params = {
        'cb': callback,
        'lmt': '0',
        'klt': '101',
        'fields1': 'f1,f2,f3,f7',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65',
        'ut': 'b2884a393a59ad64002292a3e90d46a5',
        'secid': secid,
        '_': timestamp + 2,
    }

    response = requests.get('https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get', params=params, headers=headers)
    
    # 保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    
    # 解析数据
    data = parse_cap_kline(fn)
    
    if data['rc'] != 0:
        raise ValueError(f"API返回错误: {data.get('rt', '未知错误')}")
    
    # 提取K线数据
    klines = data['data']['klines']
    
    # 定义列名（基于图片描述）
    columns = [
        '日期', '收盘价', '涨跌幅', 
        '主力净流入', '主力净流入_净占比',
        '超大单净流入', '超大单净流入_净占比',
        '大单净流入', '大单净流入_净占比',
        '中单净流入', '中单净流入_净占比',
        '小单净流入', '小单净流入_净占比'
    ]
    
    # 解析每行数据
    rows = []
    for kline in klines:
        values = kline.split(',')
        if len(values) >= 13:  # 确保有足够的数据
            try:
                row = {
                    '日期': values[0],
                    '主力净流入': round(float(values[1])/1E4, 2),
                    '主力净流入_净占比': float(values[6]),
                    '超大单净流入': round(float(values[5])/1E4, 2),
                    '超大单净流入_净占比': float(values[10]),
                    '大单净流入': round(float(values[4])/1E4, 2),
                    '大单净流入_净占比': float(values[9]),
                    '中单净流入': round(float(values[3])/1E4, 2),
                    '中单净流入_净占比': float(values[8]),
                    '小单净流入': round(float(values[2])/1E4, 2),
                    '小单净流入_净占比': float(values[7]),
                    '收盘价': float(values[11]),
                    '涨跌幅': float(values[12])
                }
                rows.append(row)
            except (ValueError, IndexError) as e:
                print(f"解析数据行时出错: {e}, 数据: {kline}")
                continue
    
    # 创建DataFrame
    df = pd.DataFrame(rows)
    print(df)
    # 保存到CSV
    df.to_csv(fn_csv, index=False, encoding='utf-8')
    
    print(f'股票 {stock_code} 资金流向K线数据已保存到: {fn_csv}')
    print(f'数据行数: {len(df)}')
    print(f'数据列数: {len(df.columns)}')
    
    return fn_csv


def parse_cap_kline(fn):
    '''
    解析股票资金流向K线数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 用正则提取大括号包裹的 JSON 内容
    match = re.search(r'\((\{.*\})\);?$', content, re.DOTALL)
    if not match:
        raise ValueError("未找到 JSON 数据")
    
    json_str = match.group(1)
    data = json.loads(json_str)
    return data

def get_cap_dayline(stock_code):
    '''
    获取股票实时资金流向的分钟级数据
    URL: https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?cb=jQuery1123041031322205900167_1754116916732&lmt=0&klt=1&fields1=f1%2Cf2%2Cf3%2Cf7&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61%2Cf62%2Cf63%2Cf64%2Cf65&ut=b2884a393a59ad64002292a3e90d46a5&secid=0.000050&_=1754116916733
    
    参数:
    stock_code: 股票代码，如 '000050'
    '''
    
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

    fn = os.path.join(temp_dir, f'cap_dayline_{stock_code}.txt')
    nowstr = datetime.now().strftime('%y%m%d')
    fn_csv = f'generated/cache/stockd/cap_dayline_{stock_code}_{nowstr}.csv'
    
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

    response = requests.get('https://push2.eastmoney.com/api/qt/stock/fflow/kline/get', params=params, headers=headers)
    
    # 保存响应内容到文件
    open(fn, 'w', encoding='utf8').write(response.text)
    
    # 解析数据
    data = parse_cap_dayline(fn)
    
    if data['rc'] != 0:
        raise ValueError(f"API返回错误: {data.get('rt', '未知错误')}")
    
    # 提取K线数据
    klines = data['data']['klines']
    
    # 定义列名（基于图片描述和API数据结构）
    columns = [
        '时间', '主力净流入', '超大单净流入', '大单净流入', '中单净流入', '小单净流入'
    ]
    
    # 解析每行数据
    rows = []
    for kline in klines:
        values = kline.split(',')
        
        if len(values) >= 5:  # 确保有足够的数据
            try:
                row = {
                    '时间': values[0],
                    '主力净流入': round(float(values[1])/1E4, 2),
                    '超大单净流入': round(float(values[5])/1E4, 2),
                    '大单净流入': round(float(values[4])/1E4, 2),
                    '中单净流入': round(float(values[3])/1E4, 2),
                    '小单净流入': round(float(values[2])/1E4, 2)
                }
                rows.append(row)
            except (ValueError, IndexError) as e:
                print(f"解析数据行时出错: {e}, 数据: {kline}")
                continue
    # 创建DataFrame
    df = pd.DataFrame(rows)
    
    # 计算除'主力净流入'外所有数值列的总和
    # df['cksum'] = df.drop(columns=['主力净流入']).select_dtypes(include='number').sum(axis=1)
    # # 计算'超大单净流入'和'大单净流入'的总和
    # df['ckmajor'] = df['超大单净流入'] + df['大单净流入']
    # 保存到CSV
    print(df)

    df.to_csv(fn_csv, index=False, encoding='utf-8')
    
    print(f'股票 {stock_code} 实时资金流向分钟级数据已保存到: {fn_csv}')
    print(f'数据行数: {len(df)}')
    print(f'数据列数: {len(df.columns)}')
    
    return fn_csv


def parse_cap_dayline(fn):
    '''
    解析股票实时资金流向的分钟级数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 用正则提取大括号包裹的 JSON 内容
    match = re.search(r'\((\{.*\})\);?$', content, re.DOTALL)
    if not match:
        raise ValueError("未找到 JSON 数据")
    
    json_str = match.group(1)
    data = json.loads(json_str)
    return data





def parse_respredict(fn):
    '''
    解析研究报告预测数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    # 用正则提取大括号包裹的 JSON 内容
    match = re.search(r'\((\{.*\})\);?$', content, re.DOTALL)
    if not match:
        raise ValueError("未找到 JSON 数据")
    json_str = match.group(1)
    data = json.loads(json_str)
    return data


# get_zjlx()
# get_stockcomment()
# get_fund()
# get_respredict()
# fn=os.path.join(temp_dir, 'qgqp0.txt')
# data=parse_qgqp(fn)['result']['data']
# print(data)

def get_quotes(pages=None):
    # https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    # 按换手率倒排序
    cookies = {
        'qgqp_b_id': 'f5b80cf4eb275bcde79743814cc0d62c',
        'st_nvi': 'J2Nihh4udU39PyJPh9ilO2b8d',
        'nid': '0f512d6ee90e691d53d979bde12a1561',
        'nid_create_time': '1755136802168',
        'gvi': 'gkJ_QB0ISzft8tUK73xl1fb8a',
        'gvi_create_time': '1755136802168',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_si': '58977101050302',
        'st_asi': 'delete',
        'EMFUND1': 'null',
        'EMFUND2': 'null',
        'EMFUND3': 'null',
        'EMFUND4': 'null',
        'EMFUND5': 'null',
        'EMFUND6': 'null',
        'EMFUND7': 'null',
        'EMFUND8': 'null',
        'EMFUND0': 'null',
        'EMFUND9': '09-07 00:45:01@#$%u5706%u4FE1%u6C38%u4E30%u9AD8%u7AEF%u5236%u9020A@%23%24006969',
        'st_pvi': '59192766921846',
        'st_sp': '2025-07-13%2011%3A14%3A04',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '446',
        'st_psi': '20250911001224595-113200301321-9463706968',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6,ja;q=0.5',
        'Connection': 'keep-alive',
        'Referer': 'https://quote.eastmoney.com/center/gridlist.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'qgqp_b_id=f5b80cf4eb275bcde79743814cc0d62c; st_nvi=J2Nihh4udU39PyJPh9ilO2b8d; nid=0f512d6ee90e691d53d979bde12a1561; nid_create_time=1755136802168; gvi=gkJ_QB0ISzft8tUK73xl1fb8a; gvi_create_time=1755136802168; fullscreengg=1; fullscreengg2=1; st_si=58977101050302; st_asi=delete; EMFUND1=null; EMFUND2=null; EMFUND3=null; EMFUND4=null; EMFUND5=null; EMFUND6=null; EMFUND7=null; EMFUND8=null; EMFUND0=null; EMFUND9=09-07 00:45:01@#$%u5706%u4FE1%u6C38%u4E30%u9AD8%u7AEF%u5236%u9020A@%23%24006969; st_pvi=59192766921846; st_sp=2025-07-13%2011%3A14%3A04; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=446; st_psi=20250911001224595-113200301321-9463706968',
    }
    
    page_size = 100
    
    # 先获取第一页来确定总页数
    params = {
        'np': '1',
        'fltt': '1',
        'invt': '2',
        'cb': 'jQuery37104861141259802646_1757520607356',
        'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
        'fields': 'f12,f13,f14,f1,f2,f4,f3,f152,f5,f6,f7,f15,f18,f16,f17,f10,f8,f9,f23',
        'fid': 'f17', #换手率
        'pn': 1,
        'pz': page_size,
        'po': '1',
        'dect': '1',
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'wbp2u': '|0|0|0|web',
        '_': '1757520607366',
    }

    response = requests.get('https://push2delay.eastmoney.com/api/qt/clist/get', params=params, cookies=cookies, headers=headers)
    
    # 保存响应内容
    fn = os.path.join(temp_dir, 'quotes.txt')
    open(fn, 'w', encoding='utf8').write(response.text)
    
    # 解析数据获取总页数
    data = parse_quotes(fn)
    pageTotal = data['data']['total']//page_size + 1
    print(f'总页数: {pageTotal}')
    
    # 准备CSV文件
    nowstr = datetime.now().strftime('%y%m%d%H%M')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    fn_csv = f'../generated/em/{dte_short}/q_{nowstr}.csv'
    
    # 循环所有页面
    # for pgn in trange(1, pageTotal + 1, desc='抓取行情数据进度'):
    if pages is None:
        pages = pageTotal
    else:
        pages = min(pages, pageTotal)
    for pgn in trange(1, pages + 1, desc='抓取行情数据进度'):
        params = {
            'np': '1',
            'fltt': '1',
            'invt': '2',
            'cb': 'jQuery37104861141259802646_1757520607356',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
            'fields': 'f12,f13,f14,f1,f2,f4,f3,f152,f5,f6,f7,f15,f18,f16,f17,f10,f8,f9,f23',
            'fid': 'f3',
            'pn': pgn,
            'pz': page_size,
            'po': '1',
            'dect': '1',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'wbp2u': '|0|0|0|web',
            '_': '1757520607366',
        }

        response = requests.get('https://push2delay.eastmoney.com/api/qt/clist/get', params=params, cookies=cookies, headers=headers)
        
        # 保存响应内容
        open(fn, 'w', encoding='utf8').write(response.text)
        
        # 解析数据
        data = parse_quotes(fn)
        
        # 转换为DataFrame
        df = pd.DataFrame(data['data']['diff'])
        
        # 保存到CSV文件
        if pgn == 1:
            df.to_csv(fn_csv, index=False, encoding='utf-8')
        else:
            df.to_csv(fn_csv, mode='a', header=False, index=False, encoding='utf-8')
    
    print(f'行情数据已保存到: {fn_csv}')
    
    # 生成报告
    fn_report = f'../generated/em/{dte_short}/q_report_{nowstr}.csv'
    gen_q_report(fn_csv, fn_report)
    
    return fn_csv

def parse_quote(response_text):
    '''
    解析单个股票报价数据
    '''
    try:
        # 提取JSON数据
        match = re.search(r'jQuery\d+_\d+\((.*)\);?$', response_text)
        if match:
            json_str = match.group(1)
        else:
            # 尝试直接解析
            json_str = response_text
        
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"响应内容: {response_text[:200]}...")
        raise ValueError(f"股票报价数据解析失败: {e}")

def parse_quotes(fn):
    '''
    解析行情数据
    '''
    with open(fn, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        # 提取JSON数据
        match = re.search(r'jQuery\d+_\d+\((.*)\);?$', content)
        if match:
            json_str = match.group(1)
        else:
            # 尝试直接解析
            json_str = content
        
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"响应内容: {content[:200]}...")
        raise ValueError(f"行情数据解析失败: {e}")

def gen_q_report(input_file, output_file):
    '''
    生成行情报告，按照图片中的字段顺序和格式
    '''
    import pandas as pd
    import os
    
    try:
        # 读取原始数据
        df = pd.read_csv(input_file, encoding='utf-8')
        
        column_mapping = {
            'f12': '股票代码',        # f12 -> 股票代码 (301575)
            'f14': '名称',           # f14 -> 名称 (N艾芬达)
            'f2': '最新价',          # f2 -> 最新价 (7477 -> 74.77)
            'f3': '涨跌幅',          # f3 -> 涨跌幅 (17003 -> 170.03%)
            'f4': '涨跌额',          # f4 -> 涨跌额 (4708 -> 47.08)
            'f5': '成交量(手)',       # f5 -> 成交量(手) (137209 -> 13.72万)
            'f6': '成交额',          # f6 -> 成交额 (1109320808.68 -> 11.09亿)
            'f7': '振幅',            # f7 -> 振幅 (5406 -> 54.06%)
            'f15': '最高',      
            'f16': '最低',  
            'f17': '今开',      
            'f18': '昨收',    
            'f10': '量比',
            'f8':'换手率',
            'f9': '市盈率',      
            'f23': '市净率',
        }

        # 选择需要的字段
        key_columns = list(column_mapping.keys())
        available_columns = [col for col in key_columns if col in df.columns]
        df_report = df[available_columns].copy()
        
        # 数据类型转换
        numeric_columns = ['f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f15', 'f16', 'f17', 'f18', 'f23']
        
        def safe_numeric_convert(x):
            """安全转换数值，处理 '-' 字符串"""
            if pd.isna(x) or x == '-' or x == '':
                return pd.NA
            try:
                return float(x)
            except (ValueError, TypeError):
                return pd.NA
        
        for col in numeric_columns:
            if col in df_report.columns:
                df_report[col] = df_report[col].apply(safe_numeric_convert)
        
        # 格式化数据
        # 股票代码格式化为6位数字字符串
        if 'f12' in df_report.columns:
            df_report['f12'] = df_report['f12'].apply(lambda x: f'{int(x):06d}' if pd.notna(x) and str(x).isdigit() else str(x))
            # 确保股票代码列被保存为字符串格式
            df_report['f12'] = df_report['f12'].astype(str)
        
        # 安全格式化函数
        def safe_format(x, divisor=100, suffix='', format_str='{:.2f}'):
            """安全格式化数值"""
            if pd.isna(x) or x == '-' or x == '':
                return '-' if suffix == '' else x
            try:
                return format_str.format(x/divisor) + suffix
            except (ValueError, TypeError, ZeroDivisionError):
                return '-' if suffix == '' else x
        
        # 价格相关字段需要除以100（API返回的是以分为单位），保留2位小数
        price_columns = ['f2', 'f4', 'f8', 'f9', 'f10', 'f15', 'f16', 'f17', 'f18']
        for col in price_columns:
            if col in df_report.columns:
                df_report[col] = df_report[col].apply(lambda x: safe_format(x, 100, ''))
        
        # 涨跌幅需要除以100，保留2位小数并添加%符号
        if 'f3' in df_report.columns:
            df_report['f3'] = df_report['f3'].apply(lambda x: safe_format(x, 100, '%'))
        
        # 成交量格式化为万手
        if 'f5' in df_report.columns:
            df_report['f5'] = df_report['f5'].apply(lambda x: safe_format(x, 10000, '万'))
        
        # 成交额格式化为亿元
        if 'f6' in df_report.columns:
            df_report['f6'] = df_report['f6'].apply(lambda x: safe_format(x, 100000000, '亿'))
        
        # 振幅需要除以100，保留2位小数并添加%符号
        if 'f7' in df_report.columns:
            df_report['f7'] = df_report['f7'].apply(lambda x: safe_format(x, 100, '%'))
        
        # 换手率需要除以100，保留2位小数并添加%符号
        if 'f17' in df_report.columns:
            df_report['f17'] = df_report['f17'].apply(lambda x: safe_format(x, 100, '%'))
        
        # 量比保留2位小数
        # if 'f16' in df_report.columns:
        #     df_report['f16'] = df_report['f16'].apply(lambda x: safe_format(x, 100, ''))
        
        # 市盈率和市净率保留2位小数
        # ratio_columns = ['f18', 'f23']
        # for col in ratio_columns:
        #     if col in df_report.columns:
        #         df_report[col] = df_report[col].apply(lambda x: safe_format(x, 100, ''))
        
        # 重命名列为中文
        df_report = df_report.rename(columns=column_mapping)
        
        # 按涨跌幅排序（降序）
        if '涨跌幅' in df_report.columns:
            df_report = df_report.sort_values('涨跌幅', ascending=False, na_position='last')
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # 保存报告
        df_report.to_csv(output_file, index=False, encoding='utf-8')
        print(f'行情报告已保存到: {output_file}')
        print(f'报告包含 {len(df_report)} 条记录，{len(df_report.columns)} 个字段')
        
        # 显示前10条记录
        print('\n前10条记录预览:')
        print(df_report.head(10).to_string(index=False))
        
    except Exception as e:
        print(f'生成行情报告时出错: {e}')
        raise
def gen_z_report(input_file, output_file):
    '''
    生成资金流向报告，按照图片中的表格格式
    包含序号、代码、名称、相关、最新价、今日涨跌幅、各类型资金净流入及占比
    '''
    import pandas as pd
    import os
    from datetime import datetime
    pd.set_option('display.unicode.east_asian_width', True)
    
    try:
        # 读取原始数据
        
        df = pd.read_csv(input_file, encoding='utf-8')
        print(df.columns)
        cols=['名称','最新价', '今日涨跌幅', 
        '主力净流入', '主力净占比', '超大单净流入', '超大单净占比',
        '大单净流入', '大单净占比', '中单净流入', '中单净占比', '小单净流入',
        '小单净占比', 
        '所属行业', '所属概念', '未知字段_f146', '未知字段_f147',
        '最高价', '最低价', '开盘价', '昨收价', '总市值',
        '流通市值', '振幅', 
        '-','所属地域', '所属板块', '所属指数', '换手率', '市盈率', '市净率', '最后更新']
        
        cols=['名称','最新价', '今日涨跌幅', 
        '主力净流入', '主力净占比', '超大单净流入', '超大单净占比',
        '大单净流入', '大单净占比', '中单净流入', '中单净占比', '小单净流入',
        '小单净占比', 
        '换手率','流通市值',
        '市值分位',
        ]        
        if '代码' in df.columns:
            df['股票代码'] = df['代码'].apply(lambda x: f'{int(x):06d}' if pd.notna(x) and str(x).isdigit() else str(x))
            df = df.drop(columns=['代码'])

        if '相关' in df.columns:
            df['最后更新'] = df['相关'].apply(lambda x: datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S'))
            df = df.drop(columns=['相关'])
        # 所有含净流入的字段转换为以‘亿‘为单位
        net_inflow_cols = [col for col in df.columns if '净流入' in col]
        for col in net_inflow_cols:
            if col in df.columns:
                # 尝试将列转换为数值型，无法转换的保持原样
                df[col] = round(pd.to_numeric(df[col], errors='coerce') / 1e8,2)

        # 确保'流通市值'为数值型，避免字符串导致的TypeError
        # 按区间计算市值分位
        def calc_mv_quantile(val):
            if 0 < val <= 90:
                return 1
            elif 90 < val <= 500:
                return 2
            elif 500 < val <= 1000:
                return 3
            elif 1000 < val:
                return 4
            else:
                return None

        if '流通市值' in df.columns:
            df['流通市值'] = pd.to_numeric(df['流通市值'], errors='coerce')
            df['流通市值'] = df['流通市值'].apply(lambda t:round(t/1e8,2))
            # 去除流通市值为NaN的行，否则qcut会报错
            df = df[df['流通市值'].notna()]
            # df['市值分位'] = pd.qcut(df['流通市值'], 10, labels=False, duplicates='drop') + 1  # 1为最低分位，10为最高

            # df['市值分位'] = pd.cut(df['流通市值'], 100, labels=False, duplicates='drop') + 1  # 1为最低分位，10为最高

            df['市值分位'] = df['流通市值'].apply(calc_mv_quantile)
        else:
            df['市值分位'] = None

        df = df.set_index('股票代码').sort_values('主力净流入', ascending=False)
        
        print(df[cols].head(50))
        print(f'Writing {df[cols].shape[0]} rows to {output_file}')
        df[cols].to_csv(output_file)

        
    except Exception as e:
        print(f'生成资金流向报告时出错: {e}')
        raise

def get_quote(stock_code, force_refetch=False):
    '''
    获取股票行情数据（带缓存策略）
    
    缓存策略:
    - 非交易时间: 使用缓存文件，避免重复获取
    - 交易时间: 缓存5分钟超时，超时后重新获取
    - 新股票代码: 追加模式写入现有文件
    - 文件不存在: 创建新文件
    
    参数:
    stock_code: 股票代码，如 '000050'
    force_refetch: 是否强制重新获取数据，忽略缓存策略
    返回: 包含股票行情信息的字典
    '''
    
    # 确定市场代码
    if stock_code.startswith('0') or stock_code.startswith('3'):
        market = 0  # 深圳
        secid = f"0.{stock_code}"
    elif stock_code.startswith('6'):
        market = 1  # 上海
        secid = f"1.{stock_code}"
    else:
        raise ValueError(f"不支持的股票代码格式: {stock_code}")
    
    # 缓存策略实现
    tstr = datetime.now().strftime('%Y%m%d')
    dte_short = datetime.now().strftime('%y%m%d')
    os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)
    quote_file = f'../generated/em/{dte_short}/quote_{tstr}.csv'
    
    # 检查是否需要使用缓存
    if not force_refetch:
        trading_time = is_trading_time()
        
        # 检查文件是否存在以及是否包含当前股票代码
        file_exists = os.path.exists(quote_file)
        stock_exists_in_file = False
        
        if file_exists:
            try:
                df = pd.read_csv(quote_file, dtype={'股票代码': str})
                stock_exists_in_file = stock_code in df['股票代码'].tolist()
            except:
                stock_exists_in_file = False
        
        # 非交易时间且股票已存在：使用缓存
        if not trading_time and stock_exists_in_file:
            try:
                df = pd.read_csv(quote_file, dtype={'股票代码': str})
                cached_row = df[df['股票代码'] == stock_code].iloc[0]
                
                # 构建返回数据
                quote_data = {
                    '股票代码': str(cached_row['股票代码']),
                    '股票名称': str(cached_row['股票名称']),
                    '当前价格': float(cached_row['当前价格']),
                    '涨跌额': float(cached_row['涨跌额']),
                    '涨跌幅': float(cached_row['涨跌幅']),
                    '今开': float(cached_row['今开']),
                    '昨收': float(cached_row['昨收']),
                    '最高': float(cached_row['最高']),
                    '最低': float(cached_row['最低']),
                    '涨停价': float(cached_row['涨停价']),
                    '跌停价': float(cached_row['跌停价']),
                    '成交量': int(cached_row['成交量']),
                    '成交额': float(cached_row['成交额']),
                    '换手率': float(cached_row['换手率']),
                    '量比': float(cached_row['量比']),
                    '市盈率(动)': float(cached_row['市盈率(动)']),
                    '市净率': float(cached_row['市净率']),
                    '总市值': float(cached_row['总市值']),
                    '流通市值': float(cached_row['流通市值']),
                    '更新时间': str(cached_row['更新时间'])
                }
                
                print(f"✅ 使用缓存数据: {stock_code} (非交易时间)")
                return quote_data
            except Exception as e:
                print(f"⚠️ 缓存读取失败，将重新获取: {e}")
        
        # 交易时间且股票已存在：检查缓存是否过期（5分钟）
        elif trading_time and stock_exists_in_file:
            try:
                file_mtime = os.path.getmtime(quote_file)
                current_time = time.time()
                time_diff = current_time - file_mtime
                
                if time_diff < 300:  # 5分钟内
                    df = pd.read_csv(quote_file, dtype={'股票代码': str})
                    cached_row = df[df['股票代码'] == stock_code].iloc[0]
                    
                    quote_data = {
                        '股票代码': str(cached_row['股票代码']),
                        '股票名称': str(cached_row['股票名称']),
                        '当前价格': float(cached_row['当前价格']),
                        '涨跌额': float(cached_row['涨跌额']),
                        '涨跌幅': float(cached_row['涨跌幅']),
                        '今开': float(cached_row['今开']),
                        '昨收': float(cached_row['昨收']),
                        '最高': float(cached_row['最高']),
                        '最低': float(cached_row['最低']),
                        '涨停价': float(cached_row['涨停价']),
                        '跌停价': float(cached_row['跌停价']),
                        '成交量': int(cached_row['成交量']),
                        '成交额': float(cached_row['成交额']),
                        '换手率': float(cached_row['换手率']),
                        '量比': float(cached_row['量比']),
                        '市盈率(动)': float(cached_row['市盈率(动)']),
                        '市净率': float(cached_row['市净率']),
                        '总市值': float(cached_row['总市值']),
                        '流通市值': float(cached_row['流通市值']),
                        '更新时间': str(cached_row['更新时间'])
                    }
                    
                    print(f"✅ 使用缓存数据: {stock_code} (交易时间，缓存有效)")
                    return quote_data
                else:
                    print(f"🔄 缓存过期，重新获取: {stock_code} (交易时间，{time_diff:.0f}秒前)")
            except Exception as e:
                print(f"⚠️ 缓存检查失败，将重新获取: {e}")
    
    # 需要重新获取数据
    print(f"🔄 获取最新数据: {stock_code}")
    
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
        'st_asi': 'delete',
        'st_pvi': '59192766921846',
        'st_sp': '2025-07-13%2011%3A14%3A04',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '98',
        'st_psi': '20250802180150988-113200301201-9128259049',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': f'https://quote.eastmoney.com/sz{stock_code}.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    
    # 构建请求参数
    timestamp = int(time.time() * 1000)
    callback = f'jQuery{timestamp}_{timestamp + 1}'
    
    params = {
        'invt': '2',
        'fltt': '1',
        'cb': callback,
        'fields': 'f58,f734,f107,f57,f43,f59,f169,f301,f60,f170,f152,f177,f111,f46,f44,f45,f47,f260,f48,f261,f279,f277,f278,f288,f19,f17,f531,f15,f13,f11,f20,f18,f16,f14,f12,f39,f37,f35,f33,f31,f40,f38,f36,f34,f32,f211,f212,f213,f214,f215,f210,f209,f208,f207,f206,f161,f49,f171,f50,f86,f84,f85,f168,f108,f116,f167,f164,f162,f163,f92,f71,f117,f292,f51,f52,f191,f192,f262,f294,f295,f269,f270,f256,f257,f285,f286,f748,f747',
        'secid': secid,
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'wbp2u': '|0|0|0|web',
        'dect': '1',
        '_': timestamp + 2,
    }

    response = _requests_session_no_proxy().get(
        'https://push2.eastmoney.com/api/qt/stock/get',
        params=params, cookies=cookies, headers=headers, timeout=15,
    )
    
    # 解析数据
    data = parse_quote(response.text)
    
    if data['rc'] != 0:
        raise ValueError(f"API返回错误: {data.get('rt', '未知错误')}")
    
    # 提取股票信息
    stock_data = data['data']
    
    # 构建返回的行情数据字典
    quote_data = {
        '股票代码': str(stock_code),  # 确保股票代码为字符串
        '股票名称': str(stock_data.get('f58', '')),
        '当前价格': float(stock_data.get('f43', 0)) / 100,  # 价格需要除以100
        '涨跌额': float(stock_data.get('f170', 0)) / 100,
        '涨跌幅': float(stock_data.get('f169', 0)) / 100,  # 百分比需要除以100
        '今开': float(stock_data.get('f46', 0)) / 100,
        '昨收': float(stock_data.get('f60', 0)) / 100,
        '最高': float(stock_data.get('f44', 0)) / 100,
        '最低': float(stock_data.get('f45', 0)) / 100,
        '涨停价': float(stock_data.get('f51', 0)) / 100,
        '跌停价': float(stock_data.get('f52', 0)) / 100,
        '成交量': int(stock_data.get('f47', 0)),  # 手
        '成交额': float(stock_data.get('f48', 0)) / 10000,  # 万元
        '换手率': float(stock_data.get('f168', 0)) / 100,  # 百分比需要除以100
        '量比': float(stock_data.get('f50', 0)) / 100,
        '市盈率(动)': float(stock_data.get('f162', 0)) / 100,
        '市净率': float(stock_data.get('f167', 0)) / 100,
        '总市值': float(stock_data.get('f116', 0)) / 100000000,  # 亿元
        '流通市值': float(stock_data.get('f117', 0)) / 100000000,  # 亿元
        '更新时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    def write_quote_to_csv(quote_data, csv_path, append_mode=True):
        import csv
        import os

        # 定义字段顺序，与get_zjlx输出一致
        fieldnames = [
            '股票代码', '股票名称', '当前价格', '涨跌额', '涨跌幅', '今开', '昨收', '最高', '最低',
            '涨停价', '跌停价', '成交量', '成交额', '换手率', '量比', '市盈率(动)', '市净率',
            '总市值', '流通市值', '更新时间'
        ]

        # 确保目录存在
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # 判断是否需要写入表头
        write_header = not os.path.exists(csv_path) or not append_mode

        with open(csv_path, 'a' if append_mode else 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow({k: quote_data.get(k, '') for k in fieldnames})
    
    # 写入CSV文件（使用append模式）
    write_quote_to_csv(quote_data, quote_file, append_mode=True)
    for key, value in quote_data.items():
        print(f'{key}: {value}')
    return quote_data

# K线缓存根目录；交易日内 10 分钟过期，非交易日使用最近一次可用数据（不强制过期）
_REEM_DIR = os.path.dirname(os.path.abspath(__file__))
KLINE_CACHE_ROOT = os.environ.get(
    'KLINE_CACHE_ROOT',
    os.path.join(_REEM_DIR, 'generated', 'cache', 'stockd'),
)
KLINE_CACHE_EXPIRE_TRADING_SECONDS = 10 * 60  # 10 minutes on trading days

def _is_trading_day_weekday():
    """A股交易日：周一至周五（未含节假日）。"""
    return datetime.now().weekday() < 5  # 0=Mon .. 4=Fri

def get_kline(stock_code):
    # 缓存路径: .../stockd/{cde}/kline_{cde}.csv
    cache_dir = os.path.join(KLINE_CACHE_ROOT, stock_code)
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'kline_{stock_code}.csv')

    # 检查本地缓存是否存在且未过期
    if os.path.exists(cache_file):
        try:
            file_mtime = os.path.getmtime(cache_file)
            if file_mtime is None:
                file_mtime = 0
            current_time = datetime.now().timestamp()
            # 交易日：10 分钟过期；非交易日：使用最近可用数据（不设过期）
            if _is_trading_day_weekday():
                max_age = KLINE_CACHE_EXPIRE_TRADING_SECONDS
            else:
                max_age = float('inf')
            if current_time - file_mtime < max_age:
                print(f"从本地缓存读取K线数据: {cache_file}")
                df = pd.read_csv(cache_file)
                df['日期'] = pd.to_datetime(df['日期'])
                return df
        except Exception as e:
            print(f"读取本地缓存失败: {e}，将重新下载数据")
    
    # 本地缓存不存在或已过期，从API下载数据
    print(f"从API下载K线数据: {stock_code}")
    
    if stock_code.startswith('0') or stock_code.startswith('3'):
        market = 0  # 深圳
        secid = f"0.{stock_code}"
    elif stock_code.startswith('6'):
        market = 1  # 上海
        secid = f"1.{stock_code}"
    else:
        raise ValueError(f"不支持的股票代码格式: {stock_code}")

    cookies = {
        'qgqp_b_id': 'f5b80cf4eb275bcde79743814cc0d62c',
        'st_nvi': 'J2Nihh4udU39PyJPh9ilO2b8d',
        'nid': '0f512d6ee90e691d53d979bde12a1561',
        'nid_create_time': '1755136802168',
        'gvi': 'gkJ_QB0ISzft8tUK73xl1fb8a',
        'gvi_create_time': '1755136802168',
        'fullscreengg': '1',
        'fullscreengg2': '1',
        'st_si': '58977101050302',
        'EMFUND1': 'null',
        'EMFUND2': 'null',
        'EMFUND3': 'null',
        'EMFUND4': 'null',
        'EMFUND5': 'null',
        'EMFUND6': 'null',
        'EMFUND7': 'null',
        'EMFUND8': 'null',
        'EMFUND0': 'null',
        'EMFUND9': '09-07 00:45:01@#$%u5706%u4FE1%u6C38%u4E30%u9AD8%u7AEF%u5236%u9020A@%23%24006969',
        'st_pvi': '59192766921846',
        'st_sp': '2025-07-13%2011%3A14%3A04',
        'st_inirUrl': 'https%3A%2F%2Fwww.eastmoney.com%2F',
        'st_sn': '509',
        'st_psi': '20250915055750520-113200301201-8600015143',
        'st_asi': '20250915055750520-113200301201-8600015143-hqzx.hsjAghqdy.dtt.sdKx-1',
    }

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6,ja;q=0.5',
        'Connection': 'keep-alive',
        'Referer': 'https://quote.eastmoney.com/sz000050.html',
        'Sec-Fetch-Dest': 'script',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        # 'Cookie': 'qgqp_b_id=f5b80cf4eb275bcde79743814cc0d62c; st_nvi=J2Nihh4udU39PyJPh9ilO2b8d; nid=0f512d6ee90e691d53d979bde12a1561; nid_create_time=1755136802168; gvi=gkJ_QB0ISzft8tUK73xl1fb8a; gvi_create_time=1755136802168; fullscreengg=1; fullscreengg2=1; st_si=58977101050302; EMFUND1=null; EMFUND2=null; EMFUND3=null; EMFUND4=null; EMFUND5=null; EMFUND6=null; EMFUND7=null; EMFUND8=null; EMFUND0=null; EMFUND9=09-07 00:45:01@#$%u5706%u4FE1%u6C38%u4E30%u9AD8%u7AEF%u5236%u9020A@%23%24006969; st_pvi=59192766921846; st_sp=2025-07-13%2011%3A14%3A04; st_inirUrl=https%3A%2F%2Fwww.eastmoney.com%2F; st_sn=509; st_psi=20250915055750520-113200301201-8600015143; st_asi=20250915055750520-113200301201-8600015143-hqzx.hsjAghqdy.dtt.sdKx-1',
    }

    params = {
        'cb': 'jQuery35109288952070795415_1757887068990',
        'secid': secid,
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',
        'fqt': '1',
        'end': '20500101',
        'lmt': '1000000',
        '_': '1757887069083',
    }

    try:
        response = _requests_session_no_proxy().get(
            'https://push2his.eastmoney.com/api/qt/stock/kline/get',
            params=params, cookies=cookies, headers=headers, timeout=15,
        )
        parsed_data = parse_kline(response.text)
    except Exception as e:
        print(f"获取K线数据失败: {e}")
        if os.path.exists(cache_file):
            print(f"使用过期K线缓存: {cache_file}")
            df = pd.read_csv(cache_file)
            df['日期'] = pd.to_datetime(df['日期'])
            return df
        raise
    
    # 按日期排序
    if '日期' in parsed_data.columns:
        parsed_data['日期'] = pd.to_datetime(parsed_data['日期'])
        parsed_data = parsed_data.sort_values('日期').reset_index(drop=True)
    
    # 保存到本地缓存
    try:
        parsed_data.to_csv(cache_file, index=False, encoding='utf-8')
        print(f"K线数据已保存到本地缓存: {cache_file}")
    except Exception as e:
        print(f"保存本地缓存失败: {e}")

    return parsed_data


def parse_kline(response_text):
    '''
    解析股票行情数据
    '''
    # 用正则提取大括号包裹的 JSON 内容
    match = re.search(r'\((\{.*\})\);?$', response_text, re.DOTALL)
    if not match:
        raise ValueError("未找到 JSON 数据")
    
    json_str = match.group(1)
    data = json.loads(json_str)
    
    # 检查数据结构
    if 'data' not in data or 'klines' not in data['data']:
        raise ValueError("数据格式不正确")
    
    klines = data['data']['klines']
    if not klines:
        raise ValueError("没有K线数据")
    
    # 解析每行K线数据
    data_rows = []
    for kline in klines:
        parts = kline.split(',')
        if len(parts) >= 11:
            data_rows.append([
                parts[0],  # 日期
                float(parts[1]) if parts[1] else 0,  # 开盘价
                float(parts[2]) if parts[2] else 0,  # 收盘价
                float(parts[3]) if parts[3] else 0,  # 最高价
                float(parts[4]) if parts[4] else 0,  # 最低价
                float(parts[5]) if parts[5] else 0,  # 成交量
                float(parts[6]) if parts[6] else 0,  # 成交额
                float(parts[7]) if parts[7] else 0,  # 振幅
                float(parts[8]) if parts[8] else 0,  # 涨跌幅
                float(parts[9]) if parts[9] else 0,  # 涨跌额
                float(parts[10]) if parts[10] else 0,  # 换手率
            ])
    
    # 创建DataFrame
    colnames = ['日期','开盘价','收盘价','最高价','最低价','成交量','成交额','振幅','涨跌幅','涨跌额','换手率']
    df = pd.DataFrame(data_rows, columns=colnames)

    
    # 确保日期列为datetime类型
    df['日期'] = pd.to_datetime(df['日期'])
    
    return df


def parse_starmap_stock_line(stock_str: str) -> Optional[Dict]:
    """Parse one star-map stock line (compact code-first or legacy name-first format)."""
    if not stock_str or 'U2FsdGVk' in stock_str:
        return None

    parts = stock_str.split('|')
    if len(parts) < 12:
        return None

    def _num(idx: int, scale: float = 100.0, default: float = 0.0) -> float:
        if idx >= len(parts) or parts[idx] in ('', '-', None):
            return default
        try:
            return float(parts[idx]) / scale
        except (TypeError, ValueError):
            return default

    # Legacy: 序号|名称|状态|代码|...
    if (
        len(parts) >= 16
        and parts[3].isdigit()
        and len(parts[3]) == 6
        and not (parts[1].isdigit() and len(parts[1]) == 6)
    ):
        code = str(parts[3]).zfill(6)
        return {
            '板块序号': int(parts[0]),
            '股票名称': parts[1],
            '股票代码': code,
            '涨跌额': _num(5),
            '涨跌幅': _num(6),
            '涨跌幅_3': _num(7),
            '涨跌幅_5': _num(8),
            '涨跌幅_10': _num(9),
            '涨跌幅_20': _num(10),
            '涨跌幅_60': _num(11),
            '涨跌幅_nc': _num(12),
            '成交额(亿)': round(_num(13, scale=1e8), 2),
            '换手率': _num(14),
            '当前价': _num(15),
            '流通市值(亿)': round(_num(16), 2),
            '总市值(亿)': round(_num(17), 2),
            '量比': _num(18),
        }

    # Compact: 板块序号|代码|...
    if not (parts[1].isdigit() and len(parts[1]) == 6):
        return None

    code = str(parts[1]).zfill(6)
    sector_idx = int(parts[0])

    def _parse_new_pipe_format() -> Optional[Dict]:
        """2025+ format: market|code|change|rate|...|volume|turnover|price|cap..."""
        if len(parts) < 13:
            return None
        try:
            change = int(parts[2]) / 100.0
            change_rate = int(parts[3]) / 100.0
            price = int(parts[12]) / 100.0
            raw_turn = float(parts[11]) if parts[11] not in ('', '-') else 0.0
            turnover = raw_turn / 100.0 if 0 < raw_turn < 10000 else 0.0
            raw_vol = float(parts[10]) if parts[10] not in ('', '-') else 0.0
            volume_billion = round(raw_vol / 1e8, 2) if raw_vol else 0.0
        except (TypeError, ValueError):
            return None
        if price <= 0 or price > 5000 or abs(change_rate) > 21:
            return None
        expected_change = price * change_rate / 100.0
        if abs(change - expected_change) > max(0.08, abs(expected_change) * 0.2 + 0.03):
            return None
        return {
            '板块序号': sector_idx,
            '股票名称': code,
            '股票代码': code,
            '涨跌额': round(change, 2),
            '涨跌幅': round(change_rate, 2),
            '涨跌幅_3': _num(4),
            '涨跌幅_5': _num(5),
            '涨跌幅_10': _num(6),
            '涨跌幅_20': _num(7),
            '涨跌幅_60': _num(8),
            '涨跌幅_nc': _num(9),
            '成交额(亿)': volume_billion,
            '换手率': turnover,
            '当前价': round(price, 2),
            '流通市值(亿)': round(_num(13), 2) if len(parts) > 13 else 0.0,
            '总市值(亿)': round(_num(14), 2) if len(parts) > 14 else 0.0,
            '量比': _num(15) if len(parts) > 15 and parts[15] not in ('', '-') else 0.0,
        }

    parsed_new = _parse_new_pipe_format()
    if parsed_new:
        return parsed_new

    try:
        a2 = int(parts[2])
    except (TypeError, ValueError):
        a2 = 0

    if a2 < 0:
        change_rate = _num(2)
        change = _num(3)
        price = _num(12)
        turnover = _num(11)
        volume_billion = round(_num(10, scale=1e8), 2)
    else:
        change_rate = _num(6)
        change = _num(5)
        price = _num(13)
        try:
            raw_turn = float(parts[12]) if len(parts) > 12 and parts[12] not in ('', '-') else 0
        except (TypeError, ValueError):
            raw_turn = 0
        turnover = raw_turn / 100.0 if 0 < raw_turn < 10000 else _num(14)
        volume_billion = round(_num(10, scale=1e8), 2) if len(parts) > 10 else 0.0
        if price > 0 and abs(change_rate) <= 30 and abs(change) > max(1.0, abs(price * change_rate / 100.0) * 4):
            change = round(price * change_rate / 100.0, 2)

    return {
        '板块序号': sector_idx,
        '股票名称': code,
        '股票代码': code,
        '涨跌额': change,
        '涨跌幅': change_rate,
        '涨跌幅_3': _num(7),
        '涨跌幅_5': _num(8),
        '涨跌幅_10': _num(9),
        '涨跌幅_20': _num(10),
        '涨跌幅_60': _num(11),
        '涨跌幅_nc': _num(12),
        '成交额(亿)': volume_billion,
        '换手率': turnover,
        '当前价': price,
        '流通市值(亿)': round(_num(15), 2) if len(parts) > 15 else 0.0,
        '总市值(亿)': round(_num(16), 2) if len(parts) > 16 else 0.0,
        '量比': _num(17) if len(parts) > 17 else 0.0,
    }


def getRealtimeQuote(fn=None, force=False):
    """
    获取实时股票行情数据
    URL: https://quote.eastmoney.com/stockhotmap/api/getquotedata?quotedata_hash=500ea9710f4d53124555382def877c9070d86909

    参数:
    fn: 如果不为空，则读取该文件（raw_* 文件），否则实时请求
    force: 强制刷新（仅交易日生效；非交易日始终读最近收盘日缓存）

    返回: 包含实时行情数据的字典
    """

    import os
    import json
    import pandas as pd

    if fn is None or fn == '':
        try:
            from quote_cache import (
                get_cached_realtime_quote,
                quote_save_path,
                should_refresh_quote,
                write_post_close_marker,
            )
            need, reason = should_refresh_quote(force=force)
            if not need:
                cached = get_cached_realtime_quote()
                if cached:
                    quote_file = cached.get('quote_file', '')
                    try:
                        from quote_cache import _quote_csv_looks_corrupt
                        if quote_file and _quote_csv_looks_corrupt(quote_file):
                            print(f"quote 缓存损坏，重新拉取: {quote_file}")
                            need = True
                            reason = 'corrupt_cache'
                    except Exception:
                        pass
                    if not need:
                        print(f"使用 quote 缓存 ({reason}): {cached.get('quote_file')}")
                        return cached
        except Exception as exc:
            print(f"quote 缓存检查跳过: {exc}")

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://quote.eastmoney.com/stockhotmap/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    if fn is not None and fn != "":
        # 只保存csv，不保存json
        # 直接从fn中提取下划线后的时间戳部分作为timestamp_str
        import re
        m = re.search(r'_(\d{10,})', fn)
        timestamp_str = m.group(1) if m else 'unknown'
    else:
        timestamp_str = datetime.now().strftime('%y%m%d%H%M')
    if fn is not None and fn != "":
        if not os.path.exists(fn):
            raise FileNotFoundError(f"文件不存在: {fn}")
        with open(fn, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except Exception:
                f.seek(0)
                text = f.read()
                data = json.loads(text)
        print(f"已从文件读取星图原始数据: {fn}")
    else:
        timestamp = int(time.time() * 1000)
        params = {
            'quotedata_hash': '500ea9710f4d53124555382def877c9070d86909',
            '_': timestamp,
        }

        response = requests.get('https://quote.eastmoney.com/stockhotmap/api/getquotedata', params=params, headers=headers)

        if response.status_code != 200:
            raise ValueError(f"API请求失败: {response.status_code}")

        data = response.json()

        # json_filename = f'generated/em/raw_{timestamp_str}.json'
        # os.makedirs('generated/em', exist_ok=True)
        # with open(json_filename, 'w', encoding='utf-8') as f:
        #     f.write(response.text)
        # print(f"星图数据已保存到: {json_filename}")

    # 解析股票数据
    stock_data = []
    if 'data' in data:
        for stock_str in data['data']:
            try:
                stock_info = parse_starmap_stock_line(stock_str)
                if stock_info:
                    stock_data.append(stock_info)
            except (ValueError, IndexError) as e:
                print(f"解析股票数据时出错: {e}, 数据: {stock_str[:80]}")
                continue

    # 解析板块数据
    sector_data = []
    if 'bk' in data:
        for sector_str in data['bk']:
            try:
                parts = sector_str.split('|')
                if len(parts) >= 3:
                    sector_info = {
                        '板块名称': parts[0],
                        '涨跌幅': float(parts[1]) / 100 if parts[1] != '-' else 0.0,
                        '板块代码': parts[2]
                    }
                    sector_data.append(sector_info)
            except (ValueError, IndexError) as e:
                print(f"解析板块数据时出错: {e}, 数据: {sector_str}")
                continue

    result = {
        'quotetime': data.get('quotetime', 0),
        'hash': data.get('hash', ''),
        'stock_data': stock_data,
        'sector_data': sector_data,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    dtestr = datetime.now().strftime('%y%m%d')
    dte_short = datetime.now().strftime('%y%m%d')
    # 无论fn是否传入，都保存quote_*和bk_*为csv
    try:
        os.makedirs(f'../generated/em/{dte_short}', exist_ok=True)

        if stock_data:
            df_quote = pd.DataFrame(stock_data)
            if fn is None or fn == '':
                try:
                    from quote_cache import quote_save_path, write_post_close_marker
                    quote_csv = quote_save_path()
                    if quote_csv.endswith('_close.csv'):
                        write_post_close_marker()
                except Exception:
                    quote_csv = f"../generated/em/{dte_short}/quote_{timestamp_str}.csv"
            else:
                quote_csv = f"../generated/em/{dte_short}/quote_{timestamp_str}.csv"
            df_quote.to_csv(quote_csv, index=False, encoding='utf-8-sig')
            print(f"股票数据已保存到: {quote_csv}")
            result['quote_file'] = quote_csv
            result['cached'] = False
    except Exception as e:
        print(f"保存CSV文件时出错: {e}")
    try:
        if sector_data:
            bk_csv = f"../generated/em/{dte_short}/bk_{dtestr}.csv"
            if not os.path.exists(bk_csv):
                df_sector = pd.DataFrame(sector_data)
                df_sector.to_csv(bk_csv, index=False, encoding='utf-8-sig')
                print(f"板块数据已保存到: {bk_csv}")
            else:
                print(f"板块数据文件已存在: {bk_csv}")
    except Exception as e:
        print(f"保存板块CSV文件时出错: {e}")

    # # 如果没有fn，额外保存json
    # if not fn:
    #     try:
    #         os.makedirs('generated/em', exist_ok=True)
    #         json_filename = f'generated/em/realtime_quote_{timestamp_str}.json'
    #         with open(json_filename, 'w', encoding='utf-8') as f:
    #             json.dump(result, f, ensure_ascii=False, indent=2)
    #         print(f"实时行情数据已保存到: {json_filename}")
    #     except Exception as e:
    #         print(f"保存JSON文件时出错: {e}")


    try:
        if 'quote_csv' in locals() and quote_csv:
            queryMe(quote_csv)
    except Exception as e:
        print(f"queryMe 跳过: {e}")

    return result

def get_latest_files():
    """
    获取最新的quote和zjlx文件
    
    返回:
    (latest_quote_file, latest_zjlx_file): 最新的quote和zjlx文件路径
    """
    import os
    import glob
    from datetime import datetime

    try:
        from quote_cache import find_latest_quote_file
        latest_quote_file = find_latest_quote_file()
    except Exception:
        latest_quote_file = None

    em_dir = "../generated/em"
    if not latest_quote_file and os.path.exists(em_dir):
        date_dirs = [d for d in os.listdir(em_dir) if os.path.isdir(os.path.join(em_dir, d)) and d.isdigit() and len(d) == 6]
        if date_dirs:
            latest_date_dir = sorted(date_dirs)[-1]
            latest_dir_path = os.path.join(em_dir, latest_date_dir)
            quote_files = glob.glob(os.path.join(latest_dir_path, "quote_*.csv"))
            latest_quote_file = max(quote_files, key=os.path.getmtime) if quote_files else None

    latest_zjlx_file = None
    if os.path.exists(em_dir):
        date_dirs = [d for d in os.listdir(em_dir) if os.path.isdir(os.path.join(em_dir, d)) and d.isdigit() and len(d) == 6]
        if date_dirs:
            latest_date_dir = sorted(date_dirs)[-1]
            latest_dir_path = os.path.join(em_dir, latest_date_dir)
            zjlx_files = glob.glob(os.path.join(latest_dir_path, "zjlx_*.csv"))
            latest_zjlx_file = max(zjlx_files, key=os.path.getmtime) if zjlx_files else None

    return latest_quote_file, latest_zjlx_file

def queryFlow(zjlx_csv):
    """
    查询指定zjlx CSV文件中的资金流向数据，显示各类型净占比的top10和tail10
    
    参数:
    zjlx_csv: zjlx CSV文件路径
    
    返回:
    无返回值，直接打印结果
    """
    import pandas as pd
    import re
    from datetime import datetime
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        print("queryFlow 跳过: 未安装 rich（pip install rich）")
        return
    
    try:
        # 初始化 Rich Console
        console = Console()
        
        # 读取CSV文件
        df = pd.read_csv(zjlx_csv, encoding='utf-8')
        
        # 过滤掉ST、*ST代码和以8、9开头的代码
        code_column = None
        name_column = None
        
        if '代码' in df.columns:
            code_column = '代码'
        elif '股票代码' in df.columns:
            code_column = '股票代码'
            
        if '名称' in df.columns:
            name_column = '名称'
        elif '股票名称' in df.columns:
            name_column = '股票名称'
        
        if code_column:
            # 过滤以8、9开头的代码
            df = df[~df[code_column].astype(str).str.match(r'^[89]', na=False)]
            # 格式化代码为6位数字
            df[code_column] = df[code_column].astype(str).str.zfill(6)
            
        if name_column:
            # 过滤ST和*ST股票
            df = df[~df[name_column].astype(str).str.contains('ST', na=False)]
        
        # 从文件名提取时间信息
        filename = zjlx_csv.split('/')[-1] if '/' in zjlx_csv else zjlx_csv.split('\\')[-1]
        time_match = re.search(r'(\d{6})(\d{4})', filename)
        if time_match:
            date_str = time_match.group(1)  # 250917
            time_str = time_match.group(2)  # 1337
            # 转换为标准格式
            year = '20' + date_str[:2]
            month = date_str[2:4]
            day = date_str[4:6]
            hour = time_str[:2]
            minute = time_str[2:4]
            formatted_time = f"{year}-{month}-{day} {hour}:{minute}"
        else:
            formatted_time = "未知时间"
        
        console.print(f"\n[bold blue]查询资金流向文件: {zjlx_csv}[/bold blue]")
        console.print(f"[bold green]时间: {formatted_time}[/bold green]")
        console.print(f"[bold yellow]总股票数量: {len(df)}[/bold yellow]")
        
        # 定义需要分析的字段
        flow_fields = {
            '超大单净占比': '超大单净占比',
            '主力净占比': '主力净占比', 
            '大单净占比': '大单净占比',
            '小单净占比': '小单净占比'
        }
        
        # 检查字段是否存在
        available_fields = {}
        for display_name, field_name in flow_fields.items():
            if field_name in df.columns:
                available_fields[display_name] = field_name
            else:
                console.print(f"[red]警告: 字段 '{field_name}' 不存在[/red]")
        
        if not available_fields:
            console.print("[red]错误: 没有找到任何可用的资金流向字段[/red]")
            return
        
        # 为每个字段创建分析表格
        for display_name, field_name in available_fields.items():
            console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
            console.print(f"[bold cyan]{display_name} 分析[/bold cyan]")
            console.print(f"[bold cyan]{'='*60}[/bold cyan]")
            
            # 转换相关字段为数值类型
            numeric_fields = [field_name, '最新价', '今日涨跌幅', '换手率', '流通市值']
            for col in numeric_fields:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 过滤有效数据（排除NaN和0值）
            valid_data = df[df[field_name].notna() & (df[field_name] != 0)].copy()
            
            if len(valid_data) == 0:
                console.print(f"[yellow]没有找到有效的 {display_name} 数据[/yellow]")
                continue
            
            # 按字段值排序
            sorted_data = valid_data.sort_values(field_name, ascending=False)
            
            # 创建表格
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("排名", style="dim", width=6)
            table.add_column("代码", style="bold", width=10)
            table.add_column("名称", style="bold", width=15)
            table.add_column(f"{display_name}(%)", justify="right", width=12)
            table.add_column("最新价", justify="right", width=10)
            table.add_column("涨跌幅(%)", justify="right", width=12)
            table.add_column("换手率(%)", justify="right", width=12)
            table.add_column("流通市值(亿)", justify="right", width=15)
            
            # 添加TOP10数据
            console.print(f"\n[bold green]TOP 10 - {display_name}[/bold green]")
            for i, (_, row) in enumerate(sorted_data.head(10).iterrows(), 1):
                # 格式化数值
                flow_value = f"{row[field_name]:.2f}" if pd.notna(row[field_name]) else "N/A"
                price = f"{row['最新价']:.2f}" if pd.notna(row['最新价']) else "N/A"
                change_pct = f"{row['今日涨跌幅']:.2f}" if pd.notna(row['今日涨跌幅']) else "N/A"
                turnover = f"{row['换手率']:.2f}" if pd.notna(row['换手率']) else "N/A"
                
                # 计算流通市值（亿）
                if '流通市值' in row and pd.notna(row['流通市值']):
                    market_cap = f"{row['流通市值']/100000000:.2f}"
                else:
                    market_cap = "N/A"
                
                # 根据涨跌幅设置颜色
                change_color = "green" if pd.notna(row['今日涨跌幅']) and row['今日涨跌幅'] > 0 else "red" if pd.notna(row['今日涨跌幅']) and row['今日涨跌幅'] < 0 else "white"
                
                table.add_row(
                    str(i),
                    str(row['代码']),
                    str(row['名称'])[:14],  # 限制名称长度
                    flow_value,
                    price,
                    f"[{change_color}]{change_pct}[/{change_color}]",
                    turnover,
                    market_cap
                )
            
            console.print(table)
            
            # 添加TAIL10数据（小单净占比需要反向排序）
            if display_name == '小单净占比':
                tail_data = sorted_data.tail(10).sort_values(field_name, ascending=True)
                console.print(f"\n[bold red]TAIL 10 - {display_name} (反向排序)[/bold red]")
            else:
                tail_data = sorted_data.tail(10)
                console.print(f"\n[bold red]TAIL 10 - {display_name}[/bold red]")
            
            tail_table = Table(show_header=True, header_style="bold magenta")
            tail_table.add_column("排名", style="dim", width=6)
            tail_table.add_column("代码", style="bold", width=10)
            tail_table.add_column("名称", style="bold", width=15)
            tail_table.add_column(f"{display_name}(%)", justify="right", width=12)
            tail_table.add_column("最新价", justify="right", width=10)
            tail_table.add_column("涨跌幅(%)", justify="right", width=12)
            tail_table.add_column("换手率(%)", justify="right", width=12)
            tail_table.add_column("流通市值(亿)", justify="right", width=15)
            
            for i, (_, row) in enumerate(tail_data.iterrows(), len(sorted_data)-9):
                # 格式化数值
                flow_value = f"{row[field_name]:.2f}" if pd.notna(row[field_name]) else "N/A"
                price = f"{row['最新价']:.2f}" if pd.notna(row['最新价']) else "N/A"
                change_pct = f"{row['今日涨跌幅']:.2f}" if pd.notna(row['今日涨跌幅']) else "N/A"
                turnover = f"{row['换手率']:.2f}" if pd.notna(row['换手率']) else "N/A"
                
                # 计算流通市值（亿）
                if '流通市值' in row and pd.notna(row['流通市值']):
                    market_cap = f"{row['流通市值']/100000000:.2f}"
                else:
                    market_cap = "N/A"
                
                # 根据涨跌幅设置颜色
                change_color = "green" if pd.notna(row['今日涨跌幅']) and row['今日涨跌幅'] > 0 else "red" if pd.notna(row['今日涨跌幅']) and row['今日涨跌幅'] < 0 else "white"
                
                tail_table.add_row(
                    str(i),
                    str(row['代码']),
                    str(row['名称'])[:14],  # 限制名称长度
                    flow_value,
                    price,
                    f"[{change_color}]{change_pct}[/{change_color}]",
                    turnover,
                    market_cap
                )
            
            console.print(tail_table)
            
            # 显示统计信息
            console.print(f"\n[bold yellow]统计信息:[/bold yellow]")
            console.print(f"  有效数据数量: {len(valid_data)}")
            console.print(f"  平均值: {valid_data[field_name].mean():.2f}%")
            console.print(f"  中位数: {valid_data[field_name].median():.2f}%")
            console.print(f"  最大值: {valid_data[field_name].max():.2f}%")
            console.print(f"  最小值: {valid_data[field_name].min():.2f}%")
        
        console.print(f"\n[bold green]资金流向分析完成！[/bold green]")
        
    except FileNotFoundError:
        console.print(f"[red]错误: 文件 '{zjlx_csv}' 不存在[/red]")
    except Exception as e:
        console.print(f"[red]错误: {str(e)}[/red]")
        import traceback
        traceback.print_exc()

def queryMe(quote_csv):
    """
    查询指定CSV文件中的涨幅、换手率、量比前5名，并按市值分位分类显示
    
    参数:
    quote_csv: CSV文件路径
    
    返回:
    无返回值，直接打印结果
    """
    import pandas as pd
    import re
    from datetime import datetime
    from rich.console import Console
    from rich.table import Table
    
    try:
        # 初始化 Rich Console
        console = Console()
        
        # 读取CSV文件
        df = pd.read_csv(quote_csv, encoding='utf-8')
        
        # 过滤掉ST、*ST代码和以8、9开头的代码
        code_column = None
        name_column = None
        
        if '代码' in df.columns:
            code_column = '代码'
        elif '股票代码' in df.columns:
            code_column = '股票代码'
            
        if '名称' in df.columns:
            name_column = '名称'
        elif '股票名称' in df.columns:
            name_column = '股票名称'
        
        if code_column:
            # 过滤以8、9开头的代码
            df = df[~df[code_column].astype(str).str.match(r'^[89]', na=False)]
            # 格式化代码为6位数字
            df[code_column] = df[code_column].astype(str).str.zfill(6)
            
        if name_column:
            # 过滤ST和*ST股票
            df = df[~df[name_column].astype(str).str.contains('ST', na=False)]
        
        # 从文件名提取时间信息
        filename = quote_csv.split('/')[-1]
        time_match = re.search(r'(\d{6})(\d{4})', filename)
        if time_match:
            date_str = time_match.group(1)  # 250917
            time_str = time_match.group(2)  # 1018
            # 转换为标准格式
            year = '20' + date_str[:2]
            month = date_str[2:4]
            day = date_str[4:6]
            hour = time_str[:2]
            minute = time_str[2:4]
            formatted_time = f"{year}-{month}-{day} {hour}:{minute}"
        else:
            formatted_time = "未知时间"
        
        console.print(f"\n[bold blue]查询文件: {quote_csv}[/bold blue]")
        console.print(f"[bold green]时间: {formatted_time}[/bold green]")
        console.print(f"[bold yellow]总股票数量: {len(df)}[/bold yellow]")
        
        # 计算市值分位 (使用gen_z_report算法)
        def calc_mv_quantile(val):
            if 0 < val <= 90:
                return 1
            elif 90 < val <= 500:
                return 2
            elif 500 < val <= 1000:
                return 3
            elif 1000 < val:
                return 4
            else:
                return None
        
        # 确保流通市值为数值型并转换为亿单位
        df['流通市值(亿)'] = pd.to_numeric(df['流通市值(亿)'], errors='coerce')
        df['市值分位'] = df['流通市值(亿)'].apply(calc_mv_quantile)
        
        def create_table(title, data_rows):
            """创建 Rich 表格 - 紧凑版本用于并排显示"""
            table = Table(title=title, show_header=True, header_style="bold magenta")
            table.add_column("代码", style="cyan", width=6)
            table.add_column("名称", style="white", width=8)
            table.add_column("分位", style="yellow", width=4, justify="center")
            table.add_column("涨幅", style="red", width=7, justify="right")
            table.add_column("现价", style="green", width=7, justify="right")
            table.add_column("换手", style="blue", width=7, justify="right")
            table.add_column("量比", style="magenta", width=7, justify="right")
            
            for idx, row in data_rows.iterrows():
                # 根据涨跌幅设置颜色
                change_style = "red" if row['涨跌幅'] < 0 else "green"
                table.add_row(
                    str(row['股票代码']),
                    str(row['股票名称']),
                    str(int(row['市值分位'])) if pd.notna(row['市值分位']) else "N/A",
                    f"{row['涨跌幅']:>5.1f}%",
                    f"{row['当前价']:>5.1f}",
                    f"{row['换手率']:>5.1f}%",
                    f"{row['量比']:>5.1f}",
                    style=change_style if row['涨跌幅'] < 0 else None
                )
            return table
        
        # 获取数据
        top_gainers = df.nlargest(5, '涨跌幅')
        top_turnover = df.nlargest(5, '换手率')
        top_volume_ratio = df.nlargest(5, '量比')
        top_losers = df.nsmallest(5, '涨跌幅')
        small_cap_turnover = df[df['市值分位'] == 1].nlargest(5, '换手率')
        small_cap_volume = df[df['市值分位'] == 1].nlargest(5, '量比')
        mid_cap_turnover = df[df['市值分位'] == 2].nlargest(5, '换手率')
        mid_cap_volume = df[df['市值分位'] == 2].nlargest(5, '量比')
        
        # 创建并排表格 - 使用简单的水平布局
        from rich.columns import Columns
        
        # 第一行：涨幅前5名 + 换手率前5名
        console.print(Columns([
            create_table("📈 涨幅前5名", top_gainers),
            create_table("🔄 换手率前5名", top_turnover)
        ], equal=True, expand=True, padding=(0, 0)))
        
        # 第二行：量比前5名 + 跌幅前5名
        console.print(Columns([
            create_table("📊 量比前5名", top_volume_ratio),
            create_table("📉 跌幅前5名", top_losers)
        ], equal=True, expand=True, padding=(0, 0)))
        
        # 第三行：小市值换手率前5名 + 小市值量比前5名
        console.print(Columns([
            create_table("🏢 小市值(分位1)换手率前5名", small_cap_turnover),
            create_table("🏢 小市值(分位1)量比前5名", small_cap_volume)
        ], equal=True, expand=True, padding=(0, 0)))
        
        # 第四行：中市值换手率前5名 + 中市值量比前5名
        console.print(Columns([
            create_table("🏭 中市值(分位2)换手率前5名", mid_cap_turnover),
            create_table("🏭 中市值(分位2)量比前5名", mid_cap_volume)
        ], equal=True, expand=True, padding=(0, 0)))
        
        console.print("[bold]=" * 80 + "[/bold]")
        
    except Exception as e:
        console.print(f"[bold red]查询文件时出错: {e}[/bold red]")

def getHistoryQuote(date_str=None, time_str='0930'):
    '''
    获取历史股票行情数据
    URL: https://quote.eastmoney.com/stockhotmap/api/getquotedata_history/日期/时间
    
    参数:
    date_str: 日期字符串，格式如 '2025-08-14'，默认为今天
    time_str: 时间字符串，格式如 '0930' (09:30)，默认为 '0930'

    
    返回: 包含历史行情数据的字典
    '''
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7,de;q=0.6',
        'Connection': 'keep-alive',
        'Referer': 'https://quote.eastmoney.com/stockhotmap/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    
    # 如果未指定日期，使用今天的日期
    if date_str is None:
        from datetime import date
        date_str = date.today().strftime('%Y-%m-%d')
    
    # 构建请求参数
    timestamp = int(time.time() * 1000)


    url = f'https://quote.eastmoney.com/stockhotmap/api/getquotedata_history/{date_str}/{time_str}'
    print(url)
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        raise ValueError(f"API请求失败: {response.status_code}")
    
    data = response.json()
    
    # 解析历史数据（格式与实时数据类似）
    stock_data = []
    print(data.keys())

    print(data['result'].keys())
    if 'result' in data:
        print(data['result']['time'])

        date_strN=data['result']['data']['date']
        time_strN=data['result']['data']['time']

        for stock_str in data['result']['data']['data']:

            try:
                parts = stock_str.split('|')
                if len(parts) >= 15:
                    stock_info = {
                        '序号': parts[0],
                        '股票名称': parts[1],
                        '状态': parts[2],
                        '股票代码': parts[3],
                        '指数': parts[4],
                        '涨跌幅': float(parts[5]) / 100,
                        '涨跌幅_1': float(parts[6]) / 100,
                        '涨跌幅_2': float(parts[7]) / 100,
                        '涨跌幅_3': float(parts[8]) / 100,
                        '涨跌幅_4': float(parts[9]) / 100,
                        '涨跌幅_5': float(parts[10]) / 100,
                        '涨跌幅_6': float(parts[11]) / 100,
                        '涨跌幅_7': float(parts[12]) / 100,
                        '涨跌幅_8': float(parts[13]) / 100,
                        '成交额': float(parts[14]) if parts[14] != '-' else 0,
                        '成交量': parts[15] if len(parts) > 15 else 0,
                        '换手率': parts[16] if len(parts) > 16 else 0,
                        '市盈率': parts[17] if len(parts) > 17 else 0,
                        '市净率': parts[18] if len(parts) > 18 else 0
                    }
                    stock_data.append(stock_info)
            except (ValueError, IndexError) as e:
                print(f"解析历史股票数据时出错: {e}, 数据: {stock_str}")
                continue
    
    # 解析历史板块数据
    sector_data = []
    if 'bk' in data:
        for sector_str in data['bk']:
            try:
                parts = sector_str.split('|')
                if len(parts) >= 3:
                    sector_info = {
                        '板块名称': parts[0],
                        '涨跌幅': float(parts[1]) / 100,
                        '板块代码': parts[2]
                    }
                    sector_data.append(sector_info)
            except (ValueError, IndexError) as e:
                print(f"解析历史板块数据时出错: {e}, 数据: {sector_str}")
                continue
    
    result = {
        'date': date_strN,
        'time': time_strN,
        'quotetime': data.get('quotetime', 0),
        'hash': data.get('hash', ''),
        'stock_data': stock_data,
        'sector_data': sector_data,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return result


# def get_starMap(
#     board: str = "沪深京A股",
#     color_represents: str = "涨跌幅",
#     area_represents: str = "流通市值"
# ) -> Dict[str, Any]:
#     """
#     获取股票热力图（星图）数据
    
#     Args:
#         board: 市场板块 (沪深京A股, 上证A股, 深证A股, 北证A股, 科创板, 创业板, 沪深300, 中证500, 中证1000)
#         color_represents: 颜色代表 (涨跌幅, 涨跌额, 换手率, 量比)
#         area_represents: 面积代表 (流通市值, 总市值, 成交量, 成交额)
    
#     Returns:
#         包含股票热力图数据的字典
#     """
#     try:
#         # 获取实时行情数据
#         realtime_data = getRealtimeQuote()
        
#         # 根据板块筛选数据
#         filtered_stocks = []
#         for stock in realtime_data['stock_data']:
#             stock_code = stock['股票代码']
            
#             # 根据板块筛选
#             if board == "沪深京A股":
#                 # 包含所有A股
#                 filtered_stocks.append(stock)
#             elif board == "上证A股" and stock_code.startswith('6'):
#                 filtered_stocks.append(stock)
#             elif board == "深证A股" and (stock_code.startswith('0') or stock_code.startswith('3')):
#                 filtered_stocks.append(stock)
#             elif board == "北证A股" and stock_code.startswith('8'):
#                 filtered_stocks.append(stock)
#             elif board == "科创板" and stock_code.startswith('688'):
#                 filtered_stocks.append(stock)
#             elif board == "创业板" and stock_code.startswith('300') or stock_code.startswith('301'):
#                 filtered_stocks.append(stock)
#             elif board == "沪深300" and "hs300" in stock.get('指数', ''):
#                 filtered_stocks.append(stock)
#             elif board == "中证500" and "zz500" in stock.get('指数', ''):
#                 filtered_stocks.append(stock)
#             elif board == "中证1000" and "zz1000" in stock.get('指数', ''):
#                 filtered_stocks.append(stock)
        
#         # 构建板块分组数据
#         sector_groups = {}
#         for stock in filtered_stocks:
#             # 从指数字段提取板块信息
#             indices = stock.get('指数', '').split(',')
#             sector = "其他"
            
#             # 根据指数判断板块
#             if 'hsj' in indices:
#                 sector = "沪深京"
#             elif 'sz' in indices:
#                 sector = "深圳"
#             elif 'sh' in indices:
#                 sector = "上海"
#             elif 'bj' in indices:
#                 sector = "北京"
            
#             if sector not in sector_groups:
#                 sector_groups[sector] = []
#             sector_groups[sector].append(stock)
        
#         # 构建热力图数据结构
#         starmap_data = {
#             "metadata": {
#                 "board": board,
#                 "color_represents": color_represents,
#                 "area_represents": area_represents,
#                 "update_time": realtime_data['update_time'],
#                 "total_stocks": len(filtered_stocks)
#             },
#             "market_indices": {
#                 "上证指数": {"value": 0, "change": 0, "change_rate": 0},
#                 "深证成指": {"value": 0, "change": 0, "change_rate": 0},
#                 "创业板指": {"value": 0, "change": 0, "change_rate": 0},
#                 "科创综指": {"value": 0, "change": 0, "change_rate": 0},
#                 "北证50": {"value": 0, "change": 0, "change_rate": 0}
#             },
#             "sectors": []
#         }
        
#         # 构建板块数据
#         for sector_name, stocks in sector_groups.items():
#             sector_data = {
#                 "name": sector_name,
#                 "stocks": [],
#                 "total_market_cap": 0,
#                 "avg_change_rate": 0,
#                 "up_count": 0,
#                 "down_count": 0,
#                 "flat_count": 0
#             }
            
#             total_change_rate = 0
#             up_count = 0
#             down_count = 0
#             flat_count = 0
            
#             for stock in stocks:
#                 # 计算流通市值（这里使用成交额作为近似值）
#                 market_cap = stock.get('成交额', 0)
                
#                 # 计算涨跌幅
#                 change_rate = stock.get('涨跌幅', 0)
                
#                 # 统计涨跌数量
#                 if change_rate > 0:
#                     up_count += 1
#                 elif change_rate < 0:
#                     down_count += 1
#                 else:
#                     flat_count += 1
                
#                 total_change_rate += change_rate
                
#                 stock_data = {
#                     "code": stock['股票代码'],
#                     "name": stock['股票名称'],
#                     "change_rate": change_rate,
#                     "change_amount": stock.get('涨跌额', 0),
#                     "turnover_rate": stock.get('换手率', 0),
#                     "volume_ratio": stock.get('量比', 0),
#                     "market_cap": market_cap,
#                     "volume": stock.get('成交量', 0),
#                     "amount": stock.get('成交额', 0),
#                     "pe_ratio": stock.get('市盈率', 0),
#                     "pb_ratio": stock.get('市净率', 0)
#                 }
                
#                 sector_data["stocks"].append(stock_data)
#                 sector_data["total_market_cap"] += market_cap
            
#             # 计算平均涨跌幅
#             if len(stocks) > 0:
#                 sector_data["avg_change_rate"] = total_change_rate / len(stocks)
#                 sector_data["up_count"] = up_count
#                 sector_data["down_count"] = down_count
#                 sector_data["flat_count"] = flat_count
            
#             starmap_data["sectors"].append(sector_data)
        
#         # 按板块总市值排序
#         starmap_data["sectors"].sort(key=lambda x: x["total_market_cap"], reverse=True)
        
#         # 添加市场统计信息
#         total_up = sum(sector["up_count"] for sector in starmap_data["sectors"])
#         total_down = sum(sector["down_count"] for sector in starmap_data["sectors"])
#         total_flat = sum(sector["flat_count"] for sector in starmap_data["sectors"])
        
#         starmap_data["market_summary"] = {
#             "total_stocks": len(filtered_stocks),
#             "up_count": total_up,
#             "down_count": total_down,
#             "flat_count": total_flat,
#             "up_ratio": total_up / len(filtered_stocks) if len(filtered_stocks) > 0 else 0,
#             "down_ratio": total_down / len(filtered_stocks) if len(filtered_stocks) > 0 else 0,
#             "flat_ratio": total_flat / len(filtered_stocks) if len(filtered_stocks) > 0 else 0
#         }
        
#         # 保存结果到JSON文件，格式与get_zjlx类似
#         try:
#             # 创建必要的目录
#             os.makedirs('generated/em', exist_ok=True)
            
#             # 生成文件名，格式：starmap_YYMMDDHHMM.json
#             timestamp_str = datetime.now().strftime('%y%m%d%H%M')
#             json_filename = f'generated/em/starmap_{timestamp_str}.json'
            
#             # 保存为JSON文件
#             with open(json_filename, 'w', encoding='utf-8') as f:
#                 json.dump(starmap_data, f, ensure_ascii=False, indent=2)
            
#             print(f"星图数据已保存到: {json_filename}")
            
#         except Exception as e:
#             print(f"保存JSON文件时出错: {e}")
        
#         return {
#             "success": True,
#             "data": starmap_data
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": f"获取星图数据失败: {str(e)}"
#         }


def get_tick(code: str):
    """
    Fetches real-time stock data from Eastmoney for a given stock code.
    """
    market_id = ''
    if code.startswith('60') or code.startswith('688'):
        market_id = '1'
    elif code.startswith('00') or code.startswith('300'):
        market_id = '0'
    else:
        # Default to Shanghai for other cases, or could raise an error
        market_id = '1'

    secid = f"{market_id}.{code}"
    url = f"https://85.push2delay.eastmoney.com/api/qt/stock/trends2/sse?fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f17&fields2=f51,f52,f53,f54,f55,f56,f57,f58&mpi=1000&ut=fa5fd1943c7b386f172d6893dbfba10b&secid={secid}&ndays=1&iscr=0&iscca=0&wbp2u=|0|0|0|web"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            text = b''
            while True:
                try:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    text += chunk
                except IncompleteRead as e:
                    text += e.partial
                    break
            text = text.decode('utf-8')
            
            # Find the first line that starts with 'data:'
            lines = text.split('\n')
            data_line = None
            for line in lines:
                if line.startswith('data:'):
                    data_line = line
                    break
            
            if data_line:
                json_str = data_line[len('data:'):]
                data = json.loads(json_str)
                return data
            else:
                print("Error: No 'data:' line found in the response.")
                return None

    except urllib.error.URLError as e:
        print(f"Error fetching data: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None

# if __name__ == "__main__":
#     code = "688189"
#     tick_data = get_tick(code)
#     if tick_data:
#         print(json.dumps(tick_data, indent=4, ensure_ascii=False))


def main():
    """主函数 - 提供所有功能的演示选项"""
    # python stock/utils_reem.py --demo query_flow --input-file generated/em/250917/zjlx_zlp_2509171434.csv 
    parser = argparse.ArgumentParser(description='东方财富网数据获取工具演示')
    parser.add_argument('--demo', type=str, help='选择要演示的功能', 
                       choices=[
                           'fetch_sections', 'zjlx', 'zjlx_all', 'zjlx_complete', 'zjlx_by_tov',
                           'capreal', 'capreal_bk', 'capreal_stock', 'capreal_ext', 'stockcomment', 'fund',
                           'report', 'profit', 'respredict', 'quotes', 'quote', 'kline',
                           'realtime_quote', 'history_quote', 'star_map', 'tick', 'query_flow', 'query_quote'
                       ])
    parser.add_argument('--max-pages', type=int, default=5, help='最大页数（用于zjlx相关功能）')
    parser.add_argument('--sort-by-zlp', action='store_true', help='按主力净占比排序')
    parser.add_argument('--sort-by-tov', action='store_true', help='按换手率排序')
    parser.add_argument('--extensive', action='store_true', help='使用扩展模式')
    parser.add_argument('--get-all', action='store_true', help='获取所有数据')
    parser.add_argument('--min-tov', type=float, default=1.5, help='最小换手率阈值')
    parser.add_argument('--sector-type', type=str, default='industry', choices=['industry', 'concept'], 
                       help='板块类型：industry(行业) 或 concept(概念)，用于capreal_ext功能')
    parser.add_argument('--stock-code', type=str, help='股票代码')
    parser.add_argument('--date', type=str, help='日期（YYYY-MM-DD格式）')
    parser.add_argument('--time', type=str, default='0930', help='时间（HHMM格式）')
    parser.add_argument('--board', type=str, default='沪深京A股', help='板块名称')
    parser.add_argument('--color-rep', type=str, default='涨跌幅', help='颜色代表指标')
    parser.add_argument('--area-rep', type=str, default='流通市值', help='面积代表指标')
    parser.add_argument('--input-file', type=str, help='输入文件路径')
    parser.add_argument('--output-file', type=str, help='输出文件路径')
    parser.add_argument('--url', type=str, help='URL地址')
    parser.add_argument('--md-path', type=str, help='Markdown文件路径')
    parser.add_argument('--list', action='store_true', help='列出所有可用功能')
    
    args = parser.parse_args()
    
    if args.list:
        print("可用的演示功能：")
        print("1. fetch_sections    - 获取东方财富网页面章节")
        print("2. zjlx             - 获取主力资金流向数据")
        print("3. zjlx_all         - 获取所有主力资金流向数据")
        print("4. zjlx_complete    - 获取完整的主力资金流向数据")
        print("5. zjlx_by_tov      - 按换手率获取主力资金流向数据")
        print("6. capreal          - 获取市值数据")
        print("7. capreal_bk       - 获取板块市值数据")
        print("8. capreal_stock    - 获取股票市值数据")
        print("9. capreal_ext      - 获取板块数据（扩展版，使用save_all_data的API和字段映射）")
        print("10. stockcomment     - 获取股票评论数据")
        print("11. fund            - 获取基金数据")
        print("12. report          - 获取报告数据")
        print("13. profit          - 获取利润数据")
        print("14. respredict      - 获取业绩预测数据")
        print("15. quotes          - 获取行情数据")
        print("16. quote           - 获取单只股票行情")
        print("17. kline           - 获取K线数据")
        print("18. realtime_quote  - 获取实时行情")
        print("19. history_quote   - 获取历史行情")
        print("20. tick            - 获取分时数据")
        print("21. query_flow      - 分析资金流向数据（--input-file参数可选，未指定时自动选择最新文件）")
        print("22. query_quote     - 分析行情数据（--input-file参数可选，未指定时自动选择最新文件）")
        return
    
    if not args.demo:
        print("请使用 --demo 参数选择要演示的功能，或使用 --list 查看所有可用功能")
        return
    
    print(f"开始演示功能: {args.demo}")
    print("=" * 50)
    
    try:
        if args.demo == 'fetch_sections':
            url = args.url or "https://data.eastmoney.com/zjlx/"
            print(f"获取页面章节: {url}")
            sections = fetch_eastmoney_sections(url)
            if sections:
                print(f"成功获取 {len(sections)} 个章节")
                for key, value in sections.items():
                    print(f"  {key}: {len(value)} 项")
            else:
                print("获取失败")
        
        elif args.demo == 'zjlx':
            print(f"获取主力资金流向数据 (页数: {args.max_pages}, 按主力净占比排序: {args.sort_by_zlp}, 获取全部: {args.get_all})")
            get_zjlx(max_pages=args.max_pages, sort_by_zlp=args.sort_by_zlp, get_all=args.get_all)
        
        elif args.demo == 'zjlx_all':
            print(f"获取所有主力资金流向数据 (按主力净占比排序: {args.sort_by_zlp})")
            get_zjlx_all(sort_by_zlp=args.sort_by_zlp)
        
        elif args.demo == 'zjlx_complete':
            print(f"获取完整主力资金流向数据 (页数: {args.max_pages}, 按换手率排序: {args.sort_by_tov}, 扩展模式: {args.extensive})")
            get_zjlx_complete(max_pages=args.max_pages, sort_by_tov=args.sort_by_tov, extensive=args.extensive)
        
        elif args.demo == 'zjlx_by_tov':
            print(f"按换手率获取主力资金流向数据 (最小换手率: {args.min_tov})")
            get_zjlx_by_tov(min_tov=args.min_tov)
        
        elif args.demo == 'capreal':
            print("获取市值数据")
            get_capreal()
        
        elif args.demo == 'capreal_bk':
            print("获取板块市值数据")
            get_capreal_bk()
        
        elif args.demo == 'capreal_stock':
            print("获取股票市值数据")
            get_capreal_stock()
        
        elif args.demo == 'capreal_ext':
            print(f"获取板块数据（扩展版）- sector_type: {args.sector_type}")
            # get_capreal_ext(sector_type=args.sector_type)
            get_capreal_ext(sector_type='industry')
            get_capreal_ext(sector_type='concept')
        
        elif args.demo == 'stockcomment':
            print("获取股票评论数据")
            get_stockcomment()
        
        elif args.demo == 'fund':
            print("获取基金数据")
            get_fund()
        
        elif args.demo == 'report':
            print("获取报告数据")
            get_report()
        
        elif args.demo == 'profit':
            print("获取利润数据")
            get_profit()
        
        elif args.demo == 'respredict':
            print("获取业绩预测数据")
            get_respredict()
        
        elif args.demo == 'quotes':
            print(f"获取行情数据 (页数: {args.max_pages})")
            get_quotes(pages=args.max_pages)
        
        elif args.demo == 'quote':
            if not args.stock_code:
                print("错误: 获取单只股票行情需要指定 --stock-code 参数")
                return
            print(f"获取股票 {args.stock_code} 的行情数据")
            get_quote(args.stock_code)
        
        elif args.demo == 'kline':
            if not args.stock_code:
                print("错误: 获取K线数据需要指定 --stock-code 参数")
                return
            print(f"获取股票 {args.stock_code} 的K线数据")
            get_kline(args.stock_code)
        
        elif args.demo == 'realtime_quote':
            print("获取实时行情数据")
            getRealtimeQuote()
        
        elif args.demo == 'history_quote':
            print(f"获取历史行情数据 (日期: {args.date}, 时间: {args.time})")
            getHistoryQuote(date_str=args.date, time_str=args.time)
        
        elif args.demo == 'tick':
            if not args.stock_code:
                print("错误: 获取分时数据需要指定 --stock-code 参数")
                return
            print(f"获取股票 {args.stock_code} 的分时数据")
            tick_data = get_tick(args.stock_code)
            if tick_data:
                print(f"成功获取分时数据，包含 {len(tick_data.get('data', []))} 条记录")
            else:
                print("获取分时数据失败")
        
        elif args.demo == 'query_flow':
            if not args.input_file:
                # 自动选择最新的zjlx文件
                _, latest_zjlx_file = get_latest_files()
                if not latest_zjlx_file:
                    print("错误: 未找到zjlx CSV文件，请指定 --input-file 参数")
                    return
                print(f"自动选择最新的zjlx文件: {latest_zjlx_file}")
                queryFlow(latest_zjlx_file)
            else:
                print(f"分析资金流向文件: {args.input_file}")
                queryFlow(args.input_file)
        
        elif args.demo == 'query_quote':
            if not args.input_file:
                # 自动选择最新的quote文件
                latest_quote_file, _ = get_latest_files()
                if not latest_quote_file:
                    print("错误: 未找到quote CSV文件，请指定 --input-file 参数")
                    return
                print(f"自动选择最新的quote文件: {latest_quote_file}")
                queryMe(latest_quote_file)
            else:
                print(f"分析行情数据文件: {args.input_file}")
                queryMe(args.input_file)
        
        print("=" * 50)
        print("演示完成！")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


