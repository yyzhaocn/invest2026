#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund_pl: 按基金代码计算基金当日持仓预计盈亏(estimated P&L)及贡献表。

数据流:
  1. FundAnalyzer.stockHolding()  -> 东方财富最新季度报告持仓 (写入 generated/em/fundHoldings.csv 缓存)
  2. fetch_daily_change_pct()     -> 各持仓股当日涨跌幅 (批量实时行情)
  3. 贡献% = 净值占比 x 当日涨跌幅 / 100

用法:
  python3 fund_pl.py <基金代码> [--date YYYY-MM-DD] [--top N] [--json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FUND_DIR = REPO_ROOT / "fund"
sys.path.insert(0, str(FUND_DIR))

from fund_analyzer import FundAnalyzer  # noqa: E402
from anyFund import fetch_daily_change_pct  # noqa: E402

# 每个已完成季度的季末日期: month in [4,5,6]->03-31, [7,8,9]->06-30, [10,11,12]->09-30, [1,2,3]->上年12-31
QUARTER_END = {
    0: ("12", "31"),  # Jan-Mar -> 上年 Q4
    1: ("03", "31"),  # Apr-Jun -> 本年 Q1
    2: ("06", "30"),  # Jul-Sep -> 本年 Q2
    3: ("09", "30"),  # Oct-Dec -> 本年 Q3
}


def latest_quarter_end() -> str:
    """最近一个已结束的季度末（基金季报最可能的披露报告期）。"""
    today = datetime.now()
    q = (today.month - 1) // 3  # 0..3: 当前所在季度
    month, day = QUARTER_END[q]
    year = today.year - 1 if q == 0 else today.year
    return f"{year}-{month}-{day}"


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def fmt_pct(v):
    """+6.74 / -3.38 / 0.00"""
    return f"{v:+.2f}"


def main():
    ap = argparse.ArgumentParser(description="计算基金当日持仓预计盈亏及贡献表")
    ap.add_argument("fundcode", help="基金代码 (如 161631)")
    ap.add_argument("--date", default=None, help="报告日期 YYYY-MM-DD，默认最新季度末")
    ap.add_argument("--top", type=int, default=0, help="只显示贡献绝对值前 N 名，0=全部")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    fundcode = str(args.fundcode).zfill(6)
    report_date = args.date or latest_quarter_end()

    # 1. 获取持仓（FundAnalyzer 的内部日志重定向到 stderr，保持 stdout 纯净）
    analyzer = FundAnalyzer()
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):
        result = analyzer.stockHolding(fundcode, report_date=report_date, page_num=1, page_size=200)
    if not result or not result.get("stocks"):
        print(f"❌ 未获取到基金 {fundcode} 报告期 {report_date} 的持仓数据。"
              f"可能尚未披露该季度持仓，尝试 --date 更早季度。", file=sys.stderr)
        sys.exit(1)

    stocks = result["stocks"]
    fund_name = stocks[0].get("holder_name") or stocks[0].get("org_name_abbr") or fundcode

    # 2. 获取当日涨跌幅
    codes = [str(s.get("stock_code", "")).zfill(6) for s in stocks]
    change_map = fetch_daily_change_pct(codes)

    # 3. 计算贡献
    rows = []
    for s in stocks:
        code = str(s.get("stock_code", "")).zfill(6)
        name = s.get("stock_name", "")
        netasset_ratio = float(s.get("netasset_ratio") or 0.0)
        hold_value = float(s.get("hold_value") or 0.0)
        change_pct = change_map.get(code, 0.0)
        contribution = netasset_ratio * change_pct / 100.0
        rows.append({
            "code": code,
            "name": name,
            "netasset_ratio": round(netasset_ratio, 2),
            "change_pct": round(change_pct, 2),
            "contribution_pct": round(contribution, 4),
            "hold_value": hold_value,
        })

    rows.sort(key=lambda r: abs(r["contribution_pct"]), reverse=True)
    total = round(sum(r["contribution_pct"] for r in rows), 4)
    quoted = sum(1 for c in codes if c in change_map)

    if args.json:
        out = {
            "fundcode": fundcode,
            "fund_name": fund_name,
            "report_date": report_date,
            "asof": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_contribution_pct": total,
            "holdings": len(rows),
            "quoted": quoted,
            "stocks": rows,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # 表格输出
    print(f"{fund_name} ({fundcode}) ｜ 报告期 {report_date} ｜ 行情 {datetime.now().strftime('%H:%M')}")
    shown = rows if args.top <= 0 else rows[:args.top]
    header = " ".join([
        pad("股票代码", 10), pad("股票名称", 18),
        pad("净值占比%", 10, "right"), pad("今日涨跌%", 10, "right"),
        pad("贡献%", 10, "right"), pad("持仓市值(万)", 16, "right"),
    ])
    print(header)
    print("-" * display_width(header))
    for r in shown:
        print(" ".join([
            pad(r["code"], 10), pad(r["name"], 18),
            pad(f"{r['netasset_ratio']:.2f}", 10, "right"),
            pad(fmt_pct(r["change_pct"]), 10, "right"),
            pad(fmt_pct(r["contribution_pct"]), 10, "right"),
            pad(f"{r['hold_value'] / 10000:,.2f}", 16, "right"),
        ]))
    if args.top > 0 and len(rows) > args.top:
        print(f"… 还有 {len(rows) - args.top} 只（--top 0 显示全部）")
    print("-" * display_width(header))
    print(f"预计盈亏(合计): {fmt_pct(total)}%   ({len(rows)} 只持仓, {quoted}/{len(codes)} 取到行情)")


if __name__ == "__main__":
    main()
