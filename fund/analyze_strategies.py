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
    # Use raw column indices because header is misaligned
    df = pd.read_csv(file_path)
    
    # Based on manual inspection of 022364 row:
    # 0: CODE
    # 1: NAME
    # 7: WEEKLY
    # 8: MONTHLY
    # 9: QUARTERLY
    # 10: HALF_YEAR
    # 11: YEARLY
    # 16: ESTABLISH_DATE (actual value "2024-10-30")
    # 19: MANAGEMENT_FEE (actual value "1.50%")
    
    # Map correct columns
    cols = list(df.columns)
    df['WEEKLY'] = df.iloc[:, 7].apply(parse_pct)
    df['MONTHLY'] = df.iloc[:, 8].apply(parse_pct)
    df['QUARTERLY'] = df.iloc[:, 9].apply(parse_pct)
    df['HALF_YEAR'] = df.iloc[:, 10].apply(parse_pct)
    df['YEARLY'] = df.iloc[:, 11].apply(parse_pct)
    df['ESTABLISH_DT'] = pd.to_datetime(df.iloc[:, 16], errors='coerce')
    df['FEE'] = df.iloc[:, 19].apply(parse_pct)
    
    results = {}
    
    # 1. Stable Growth (稳健增长型)
    stable = df[(df['QUARTERLY'] > 1.0) & (df['HALF_YEAR'] > 2.0) & (df['YEARLY'] > 5.0)].copy()
    stable['score'] = stable['QUARTERLY'] * 0.5 + stable['HALF_YEAR'] * 0.3 + stable['YEARLY'] * 0.2
    results['Stable Growth'] = stable.sort_values('score', ascending=False).head(5)
    
    # 2. Value/Low Fee (低费率精英型)
    low_fee = df[(df['FEE'] <= 0.8) & (df['FEE'] > 0)].copy()
    results['Low Fee Elite'] = low_fee.sort_values('YEARLY', ascending=False).head(5)
    
    # 3. Emerging Stars (新星起航型)
    today = datetime.now()
    emerging = df[(df['ESTABLISH_DT'] > (today - pd.Timedelta(days=1095))) & (df['YEARLY'] > 30)].copy()
    results['Emerging Stars'] = emerging.sort_values('YEARLY', ascending=False).head(5)
    
    # 4. Bottom Reversal (超跌反转型)
    reversal = df[(df['YEARLY'] < -15) & (df['WEEKLY'] > 2)].copy()
    results['Bottom Reversal'] = reversal.sort_values('WEEKLY', ascending=False).head(5)
    
    for strategy, data in results.items():
        print(f"\n--- {strategy} ---")
        if data.empty:
            print("No funds match criteria.")
        else:
            # Use iloc for Name and Code as well to be safe
            print(data.iloc[:, [0, 1, 7, 11, 19, 16]].to_string(index=False, header=['CODE', 'NAME', 'WEEKLY', 'YEARLY', 'FEE', 'EST_DATE']))

if __name__ == "__main__":
    analyze()
