#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
block-list: 查询 A 股板块列表（行业/概念）。

用法:
  python3 block-list.py [查询词] [--type 行业|概念] [--top N] [--refresh] [--json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from boards import BOARD_FS, load_boards, search_boards  # noqa: E402


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def main():
    ap = argparse.ArgumentParser(description="查询 A 股板块列表")
    ap.add_argument("query", nargs="?", default="", help="板块代码前缀或名称子串（可省略，缺省按涨跌幅降序列出）")
    ap.add_argument("--type", default="概念", choices=["行业", "概念"], help="板块类型，默认 概念")
    ap.add_argument("--top", type=int, default=15, help="显示条数，默认 15")
    ap.add_argument("--refresh", action="store_true", help="强制从网络刷新板块缓存")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    query = args.query.strip()

    if query:
        rows = search_boards(query, btype=args.type, refresh=args.refresh)
    else:
        rows = load_boards(args.type, refresh=args.refresh)

    if args.json:
        print(json.dumps({"query": query or None, "type": args.type, "total": len(rows),
                          "results": rows[:args.top]}, ensure_ascii=False, indent=2))
        return

    if not rows:
        print(f"❌ 未找到 {args.type}板块（缓存可能为空，试试 --refresh）", file=sys.stderr)
        sys.exit(1)

    shown = rows[:args.top]
    if query:
        print(f"搜索 {query!r}（{args.type}板块，匹配 {len(rows)} 条）:")
    else:
        print(f"{args.type}板块（共 {len(rows)} 个，按涨跌幅降序）:")

    header = pad("代码", 10) + pad("名称", 18) + pad("今日涨跌幅", 12, "right") + " 领涨股"
    print(header)
    print("-" * display_width(header))
    for r in shown:
        pct_str = f"{r['pct']:+.2f}%" if r.get("pct") is not None else "--"
        print(pad(r["code"], 10) + pad(r["name"], 18) + pad(pct_str, 12, "right") + " " + str(r.get("leader", "")))
    if len(rows) > args.top:
        print(f"… 共 {len(rows)} 条（用 --top -1 显示全部）" if args.top > 0 else "")


if __name__ == "__main__":
    main()
