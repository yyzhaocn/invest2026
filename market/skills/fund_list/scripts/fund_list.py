#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund_list: 查询东方财富基金代码列表。

数据源（本地优先）:
  - fund/fundcode_search.js  -> [代码, 拼音简拼, 名称, 类型, 全拼]
  - fund/fundcode.csv        -> fundcode,fundname,holders

用法:
  python3 fund_list.py [查询词] [--top N] [--type 类型] [--refresh]
"""
import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FUND_DIR = REPO_ROOT / "fund"
JS_FILE = FUND_DIR / "fundcode_search.js"
CSV_FILE = FUND_DIR / "fundcode.csv"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"


def display_width(text: str) -> int:
    """终端显示宽度：中文/全角占 2，其他占 1。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def load_js_list():
    """从 fundcode_search.js 解析基金列表。"""
    if not JS_FILE.exists():
        return []
    try:
        content = JS_FILE.read_text(encoding="utf-8")
        start, end = content.find("["), content.rfind("]")
        if start == -1 or end == -1:
            return []
        data = json.loads(content[start:end + 1])
        return [
            {"code": item[0], "abbr": item[1], "name": item[2], "type": item[3], "pinyin": item[4]}
            for item in data if len(item) >= 5
        ]
    except Exception as e:
        print(f"⚠️  解析 fundcode_search.js 失败: {e}", file=sys.stderr)
        return []


def load_csv_map():
    """从 fundcode.csv 解析 {code: {name, holders}}。"""
    if not CSV_FILE.exists():
        return {}
    result = {}
    try:
        for line in CSV_FILE.read_text(encoding="utf-8-sig").splitlines():
            parts = line.split(",")
            if len(parts) >= 2 and parts[0].strip().isdigit():
                result[parts[0].strip()] = {
                    "name": parts[1].strip(),
                    "holders": parts[2].strip() if len(parts) > 2 else "",
                }
    except Exception as e:
        print(f"⚠️  解析 fundcode.csv 失败: {e}", file=sys.stderr)
    return result


def refresh_from_network():
    """从东方财富刷新 fundcode_search.js 缓存。"""
    import requests
    url = "http://fund.eastmoney.com/js/fundcode_search.js"
    print(f"📡 正在从网络刷新: {url}")
    r = requests.get(url, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    JS_FILE.write_text(r.text, encoding="utf-8")
    print(f"✅ 已刷新缓存: {JS_FILE} ({len(r.text) // 1024} KB)")


def search(funds, query=None, ftype=None):
    query = (query or "").strip().lower()
    ftype = (ftype or "").strip()
    matched = []
    for f in funds:
        if query:
            ql = query.lower()
            if not (f["code"].startswith(query) or query in f["name"].lower()
                    or ql in f["abbr"].lower() or ql in f["pinyin"].lower()):
                continue
        if ftype and ftype not in f["type"]:
            continue
        matched.append(f)
    return matched


def main():
    ap = argparse.ArgumentParser(description="查询东方财富基金代码列表")
    ap.add_argument("query", nargs="?", default="", help="代码前缀 / 名称子串 / 拼音简拼（可省略）")
    ap.add_argument("--top", type=int, default=20, help="显示条数，默认 20，-1 显示全部")
    ap.add_argument("--type", dest="ftype", default="", help="类型过滤，如 指数型/混合型/股票型（模糊包含）")
    ap.add_argument("--refresh", action="store_true", help="先从网络刷新本地缓存")
    args = ap.parse_args()

    if args.refresh:
        refresh_from_network()

    funds = load_js_list()
    if not funds:
        print("❌ 本地无基金列表缓存。请先运行: python3 fund_list.py --refresh")
        sys.exit(1)

    csv_map = load_csv_map()
    matched = search(funds, args.query, args.ftype)

    total = len(funds)
    print(f"共 {total} 只基金，匹配 {len(matched)} 条" + (f"（查询: {args.query!r}" + (f"，类型: {args.ftype}" if args.ftype else "") + "）" if (args.query or args.ftype) else ""))

    limit = len(matched) if args.top == -1 else min(args.top, len(matched))
    shown = matched[:limit] if args.top != -1 else matched

    if not shown:
        print("无匹配结果，试试 --refresh 更新缓存，或换个查询词。")
        return

    header = pad("代码", 8) + pad("基金名称", 36) + pad("类型", 24) + "持仓图"
    print(header)
    print("-" * display_width(header))
    for f in shown:
        holders = csv_map.get(f["code"], {}).get("holders", "")
        print(pad(f["code"], 8) + pad(f["name"], 36) + pad(f["type"], 24) + holders)

    if args.top != -1 and len(matched) > limit:
        print(f"… 还有 {len(matched) - limit} 条（用 --top -1 显示全部）")


if __name__ == "__main__":
    main()
