#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock-list: 查询 A 股股票代码并搜索个股。

数据源:
  - 东方财富 suggest 接口 (实时): searchapi.eastmoney.com/api/suggest/get
  - 本地行情快照: generated/em/<date>/quote_<date>_latest.csv (代码 + 涨跌幅)

用法:
  python3 stock-list.py <查询词> [--top N] [--market 市场] [--json] [--all]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
STOCK_DIR = REPO_ROOT / "stock"
sys.path.insert(0, str(STOCK_DIR))

SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def suggest(query: str, count: int = 20):
    """东方财富 suggest 搜索，返回 [{'code','name','pinyin','market'}]。"""
    import requests
    params = {
        "input": query, "type": "14", "count": str(count),
        "token": SUGGEST_TOKEN, "markettype": "", "mktnum": "",
    }
    r = requests.get(SUGGEST_URL, params=params, timeout=10,
                     headers={"User-Agent": UA, "Referer": "https://www.eastmoney.com/"})
    r.raise_for_status()
    data = (r.json().get("QuotationCodeTable") or {}).get("Data") or []
    return [{
        "code": str(x.get("Code", "")),
        "name": str(x.get("Name", "")),
        "pinyin": str(x.get("PinYin", "")),
        "market": str(x.get("SecurityTypeName", "")),
    } for x in data]


def load_local_snapshot():
    """读取本地最新行情快照，返回 {'asof': date, 'quotes': {code: {'name':.., 'pct':..}}}。"""
    try:
        from quote_cache import find_latest_quote_file
        import pandas as pd
        path = find_latest_quote_file()
        if not path:
            return None
        df = pd.read_csv(path, dtype={"股票代码": str, "股票名称": str})
        quotes = {}
        for _, row in df.iterrows():
            code = str(row["股票代码"]).zfill(6)
            try:
                pct = float(row.get("涨跌幅", 0) or 0)
            except (TypeError, ValueError):
                pct = None
            quotes[code] = {"pct": pct}
        from pathlib import Path as _P
        asof = _P(path).name.replace("quote_", "").replace("_latest.csv", "")
        return {"asof": asof, "quotes": quotes}
    except Exception:
        return None


def fetch_full_list(top: int = 20):
    """从 push2delay clist 拉全市场 A 股列表（代码/名称/现价/涨跌幅）。
    返回 (total, rows)。"""
    import requests
    fs = "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:7"
    params = {
        "fid": "f12", "po": "0", "pz": str(max(top, 50)), "pn": "1", "np": "1",
        "fltt": "2", "invt": "2", "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
        "fs": fs, "fields": "f12,f14,f3,f2",
    }
    r = requests.get("https://push2delay.eastmoney.com/api/qt/clist/get",
                     params=params, timeout=20,
                     headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"})
    r.raise_for_status()
    data = r.json().get("data") or {}
    rows = []
    for item in data.get("diff") or []:
        try:
            pct = float(item.get("f3")) if item.get("f3") not in (None, "-") else None
        except (TypeError, ValueError):
            pct = None
        rows.append({"code": str(item.get("f12", "")).zfill(6),
                     "name": str(item.get("f14", "")),
                     "pct": pct,
                     "price": item.get("f2")})
    return data.get("total", len(rows)), rows


def main():
    ap = argparse.ArgumentParser(description="查询 A 股股票代码")
    ap.add_argument("query", nargs="?", default="", help="股票代码前缀或名称子串，如 688256 / 寒武纪（可省略，缺省列出全市场前 N 只）")
    ap.add_argument("--top", type=int, default=15, help="显示条数，默认 15")
    ap.add_argument("--market", default="", help="市场过滤（模糊包含），如 沪/深/科创/创业/北")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--all", action="store_true", help="包含三板/退市股（默认排除）")
    args = ap.parse_args()

    query = args.query.strip()

    if not query:
        # 无查询词：全市场列表（按代码序）
        total, rows = fetch_full_list(args.top)
        if args.json:
            print(json.dumps({"query": None, "total": total, "results": rows[:args.top]},
                             ensure_ascii=False, indent=2))
            return
        print(f"A 股全市场 {total} 只（按代码序前 {min(args.top, len(rows))} 只）:")
        header = pad("代码", 10) + pad("名称", 16) + pad("现价", 10, "right") + "涨跌幅"
        print(header)
        print("-" * display_width(header))
        for r in rows[:args.top]:
            pct_str = f"{r['pct']:+.2f}%" if r["pct"] is not None else "--"
            price_str = f"{r['price']}" if r["price"] not in (None, "-") else "--"
            print(pad(r["code"], 10) + pad(r["name"], 16) + pad(price_str, 10, "right") + pct_str)
        return

    results = suggest(query, count=max(args.top * 2, 20))

    # 数字查询：严格按代码前缀匹配（过滤掉 suggest 的模糊命中）
    if query.isdigit():
        strict = [r for r in results if r["code"].startswith(query)]
        if strict:
            results = strict

    # 默认仅 A 股（沪A/深A/京A/科创板/创业板），排除港股/美股/日股/三板/债券/基金/B股/退市
    A_SHARE_MARKETS = ("沪A", "深A", "京A", "科创板", "创业板")
    if not args.all:
        results = [r for r in results
                   if r["market"] in A_SHARE_MARKETS and not r["name"].startswith("退")]

    if args.market:
        results = [r for r in results if args.market in r["market"]]

    snap = load_local_snapshot()
    if snap:
        for r in results:
            q = snap["quotes"].get(r["code"])
            r["pct"] = q["pct"] if q else None

    results = results[:args.top]

    if args.json:
        print(json.dumps({
            "query": query,
            "asof": snap["asof"] if snap else None,
            "results": results,
        }, ensure_ascii=False, indent=2))
        return

    asof = f"，本地快照 {snap['asof']}" if snap else ""
    print(f"搜索 {query!r}（匹配 {len(results)} 条{asof}）:")
    if not results:
        print("无匹配结果，换个查询词试试。")
        return
    header = pad("代码", 10) + pad("名称", 16) + pad("市场", 10) + pad("拼音", 10) + "最新涨跌幅"
    print(header)
    print("-" * display_width(header))
    for r in results:
        pct = r.get("pct")
        pct_str = f"{pct:+.2f}%" if pct is not None else "--"
        print(pad(r["code"], 10) + pad(r["name"], 16) + pad(r["market"], 10)
              + pad(r["pinyin"], 10) + pct_str)


if __name__ == "__main__":
    main()
