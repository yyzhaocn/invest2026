# -*- coding: utf-8 -*-
import argparse
import random
import time
from fund.fund_fetcher import FundFetcher
from fund.fund_generator import FundReportGenerator

def main():
    parser = argparse.ArgumentParser(description="Fund Data Tracker & Report Generator")
    parser.add_argument('--limit', type=int, default=None, help="Limit number of funds to process details")
    args = parser.parse_args()

    print("Initializing Fund Tracker...")
    fetcher = FundFetcher()
    generator = FundReportGenerator()

    # 1. Fetch Fund List
    print("Fetching Fund list...")
    fund_list = fetcher.fetch_fund_list()
    print(f"Total Funds found: {len(fund_list)}")

    # 2. Generate Summary
    print("Generating summary.md...")
    generator.generate_summary(fund_list)

    # 3. Process Individual Funds
    if args.limit:
        print(f"Randomly selecting {args.limit} Funds to process...")
        random.shuffle(fund_list)
    
    count = 0
    for fund in fund_list:
        if args.limit and count >= args.limit:
            break
            
        code = fund.get('code')
        name = fund.get('name')
        print(f"[{count+1}] Processing {code} - {name}...")
        
        # Fetch Detail
        detail = fetcher.fetch_fund_detail(code)
        
        # Generate Detail Report
        generator.generate_fund_detail(fund, detail)
        
        count += 1
        # Moderate rate limit if fetching from network (but detail fetcher manages cache)
        # time.sleep(0.1) 

    print("All tasks completed.")

if __name__ == '__main__':
    main()
