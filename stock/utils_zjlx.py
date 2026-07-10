import requests
import json
import os
import pandas as pd
import tqdm
import time
from datetime import datetime


def get_zjlxB(start_page=1, batchNumber=5, sort_by_zlp=True):
    """
    https://data.eastmoney.com/zjlx/detail.html

    获取主力资金流向数据（增强版，包含换手率、板块、概念等字段）
    
    参数:
    start_page: 开始下载的页码，默认1
    batchNumber: 下载的批次数，默认5次
    sort_by_zlp: 是否按主力净占比倒序排序，默认True
    
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

    # 固定页面大小为100
    page_size = 100
    
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
    
    all_data = []
    total_fetched = 0
    ttl = None
    pbar = None
    
    # 创建临时目录用于调试
    temp_dir = 'temp'
    os.makedirs(temp_dir, exist_ok=True)
    
    print(f"✓ 开始下载 {batchNumber} 批数据，从第 {start_page} 页开始，每页 {page_size} 条")
    
    # 下载指定批次数
    for batch in range(batchNumber):
        current_page = start_page + batch
        url0 = f'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery1123009417707123185337_1753454455066&fid={sort_field}&po={sort_order}&pz={page_size}&pn={current_page}&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A13%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A7%2Bf%3A!2%2Cm%3A1%2Bt%3A3%2Bf%3A!2&fields=f12%2Cf14%2Cf2%2Cf3%2Cf8%2Cf9%2Cf10%2Cf15%2Cf16%2Cf17%2Cf18%2Cf20%2Cf21%2Cf23%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf100%2Cf101%2Cf102%2Cf103%2Cf104%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13'
        
        try:
            response = requests.get(url0, cookies=cookies, headers=headers, timeout=30)
            
            # 保存原始响应用于调试（仅第一页）
            if batch == 0:
                open(os.path.join(temp_dir, 'zjlx.txt'), 'w', encoding='utf8').write(response.text)
            
            data = json.loads(response.text.strip('jQuery1123009417707123185337_1753454455066(').strip(');'))
            
            # 初始化进度条（仅第一次）
            if batch == 0:
                ttl = data['data']['total']
                max_items = batchNumber * page_size
                pbar = tqdm(total=max_items, desc=f'抓取主力资金流向数据 (批次: {batchNumber}, 页面大小: {page_size}, 目标: {max_items}条)')
                print(f"✓ 总数据量: {ttl} 条，将下载 {max_items} 条")
                
            df = pd.DataFrame(data['data']['diff'])
            all_data.append(df)
            total_fetched += df.shape[0]
            pbar.update(df.shape[0])
            
            print(f"✓ 第 {batch + 1}/{batchNumber} 批完成，页面 {current_page}，获取 {df.shape[0]} 条数据")
            
            # 添加延迟避免请求过于频繁
            if batch < batchNumber - 1:  # 最后一批不需要延迟
                time.sleep(2)
            
        except Exception as e:
            print(f"第 {batch + 1} 批（页面 {current_page}）请求失败: {e}")
            # 继续下一批，不中断整个下载过程
            continue
    
    # 关闭进度条
    if pbar is not None:
        pbar.close()
    
    df2=pd.concat(all_data, ignore_index=True)
    
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
    filename = f'generated/em/zjlx_{sort_suffix}_{tstr}.csv'
    df2.to_csv(filename, index=False, encoding='utf-8-sig')
    
    print(f"主力资金流向数据已保存到: {filename}")
    print(f"数据总量: {len(df2)} 条")
    print(f"排序方式: {'主力净占比倒序' if sort_by_zlp else '主力净流入倒序'}")
    print(f"下载批次: {batchNumber} 批，从第 {start_page} 页开始")
    print(f"页面大小: {page_size} 条/页")
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
    input_filename = f'generated/em/zjlx_{sort_suffix}_{tstr}.csv'
    report_filename = f'generated/em/flow_{tstr}.csv'
    
    
    return df2