# -*- coding: utf-8 -*-
import os
import time
from pathlib import Path

class FundReportGenerator:
    def __init__(self, output_dir='fund/md'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_summary(self, fund_list):
        """
        Generates fund/md/summary.md
        fund_list: List of dicts {'code', 'name', 'type', ...}
        """
        file_path = self.output_dir / 'summary.md'
        
        content = ["# Fund Market Summary\n"]
        content.append(f"Total Funds: {len(fund_list)}\n")
        content.append("| Code | Name | Type | Links |")
        content.append("|------|------|------|-------|")
        
        # To avoid massive file size, maybe we limit or just list all. 
        # listing 10k+ lines is heavy but manageable for markdown viewers.
        # Let's list top 2000 or so if list is huge, or just all.
        # User requested "like etf", etf had ~1300. Funds have ~10000+.
        # I'll list all but be concise.
        
        for fund in fund_list:
            code = fund.get('code')
            name = fund.get('name')
            ftype = fund.get('type')
            
            link = f"[{code}](file://{os.path.abspath(self.output_dir)}/{code}.md)"
            content.append(f"| {link} | {name} | {ftype} | [Detail]({code}.md) |")
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(content))
        
        print(f"Generated summary at {file_path}")

    def generate_fund_detail(self, fund_info, detail_data):
        """
        Generates fund/md/{code}.md
        fund_info: basic list info
        detail_data: detailed holdings holding info
        """
        code = fund_info.get('code')
        name = fund_info.get('name')
        
        ts = str(int(time.time() * 1000))
        
        # Charts (standard EastMoney fund charts)
        # Net value growth: http://j4.dfcfw.com/charts/pic/LJSYL/{code}.png
        # Net value: http://j4.dfcfw.com/charts/pic/LJJZ/{code}.png
        net_worth_chart = f"http://j4.dfcfw.com/charts/pic/LJJZ/{code}.png"
        growth_chart = f"http://j4.dfcfw.com/charts/pic/LJSYL/{code}.png"
        
        content = []
        content.append(f"# {name} ({code})")
        content.append(f"**Type:** {fund_info.get('type')}")
        content.append("\n---")
        
        content.append("## Performance Charts")
        content.append(f"![Net Worth]({net_worth_chart})")
        content.append(f"![Growth]({growth_chart})")
        
        content.append("\n## Top Stock Holdings")
        if detail_data and 'stock_codes' in detail_data and detail_data['stock_codes']:
            content.append("| Stock Code | Link |")
            content.append("|------------|------|")
            for scode in detail_data['stock_codes']:
                # Link to stock detail if possible? Or just list.
                # ETf linked to internal anchors. 
                # Ideally we link to EastMoney stock page or similar.
                # http://quote.eastmoney.com/{market}.{code}.html
                # Infer market:
                market = 'sh' if scode.startswith(('6', '5', '7', '9')) else 'sz'
                link = f"http://quote.eastmoney.com/{market}{scode}.html"
                content.append(f"| {scode} | [EastMoney Quote]({link}) |")
        else:
            content.append("No stock holding data available (might be Bond/Money Market fund).")
            
        if detail_data and 'managers' in detail_data:
            content.append("\n## Managers")
            for mgr in detail_data['managers']:
                content.append(f"- **{mgr.get('name')}** (Tenure: {mgr.get('workTime')})")

        file_path = self.output_dir / f"{code}.md"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(content))
