import pandas as pd
import numpy as np
from datetime import datetime

def parse_pct(val):
    if pd.isna(val) or val == '' or val == '--':
        return 0.0
    try:
        return float(str(val).replace('%', '').strip())
    except:
        return 0.0

def analyze():
    file_path = 'generated/em/fund_2512311802.csv'
    df = pd.read_csv(file_path)
    
    # Map correct columns based on previous findings
    df['CODE'] = df.iloc[:, 0].astype(str).str.zfill(6)
    df['NAME'] = df.iloc[:, 1]
    df['WEEKLY'] = df.iloc[:, 7].apply(parse_pct)
    df['MONTHLY'] = df.iloc[:, 8].apply(parse_pct)
    df['QUARTERLY'] = df.iloc[:, 9].apply(parse_pct)
    df['HALF_YEAR'] = df.iloc[:, 10].apply(parse_pct)
    df['YEARLY'] = df.iloc[:, 11].apply(parse_pct)
    df['YTD'] = df.iloc[:, 12].apply(parse_pct)
    df['EST_DATE'] = df.iloc[:, 16]
    df['TYPE'] = df.iloc[:, 15]

    print("\n" + "="*50)
    print("1. 底部反弹期基金筛选 (Yearly < -15%, Weekly > 3%)")
    print("="*50)
    reversal = df[(df['YEARLY'] < -15) & (df['WEEKLY'] > 3)].copy()
    if reversal.empty:
        print("未找到符合条件的超跌反弹基金。")
    else:
        # Sort by weekly momentum
        top_reversal = reversal.sort_values('WEEKLY', ascending=False).head(10)
        print(top_reversal[['CODE', 'NAME', 'WEEKLY', 'YEARLY', 'TYPE']].to_string(index=False))

    target_code = '020482'
    print("\n" + "="*50)
    print(f"2. 基金 {target_code} (招商中证机器人) 板块排名分析")
    print("="*50)
    
    # Identify target fund info
    target_fund = df[df['CODE'] == target_code]
    if target_fund.empty:
        print(f"在数据集中未找到代码为 {target_code} shall be the code.")
    else:
        # Search for robotics theme in name for "peer group"
        robot_peers = df[df['NAME'].str.contains('机器人', na=False)].copy()
        
        # Rankings within Robotics peers
        for period in ['WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY']:
            robot_peers[f'{period}_RANK'] = robot_peers[period].rank(ascending=False, method='min')
            
        final_target = robot_peers[robot_peers['CODE'] == target_code].iloc[0]
        total = len(robot_peers)
        
        print(f"所属板块: 机器人产业相关 (共 {total} 只基金)")
        print(f"{'周期':<8} | {'数值':<8} | {'排名':<8} | {'百分比前列':<8}")
        print("-" * 45)
        for period in ['WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY']:
            rank = int(final_target[f'{period}_RANK'])
            pct = (rank / total) * 100
            val = final_target[period]
            print(f"{period:<10} | {val:>7.2f}% | {rank:>4}/{total:<3} | {pct:>6.2f}%")

if __name__ == "__main__":
    analyze()
