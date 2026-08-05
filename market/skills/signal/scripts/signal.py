#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signal: 技术信号扫描（金叉/死叉/N日新高新低/RSI/放量）。

输入: 代码列表 / --block 板块 / --portfolio 当前持仓。

用法:
  python3 signal.py <代码...> [--block 板块] [--portfolio] [--breakout-window 20]
                    [--only 金叉,死叉,新高,新低,超买,超卖,放量] [--top N] [--json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import atr, fetch_kline, ma, rsi, vol_avg  # noqa: E402


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def fmt_pct(v):
    return f"{v:+.2f}%" if v is not None else "--"


def compute_signals(code, points, win):
    """返回 (name, price, pct, [signals], details)。"""
    sigs = []
    ma5, ma20 = ma(points, 5), ma(points, 20)
    if ma5[-1] is not None and ma20[-1] is not None:
        if ma5[-2] <= ma20[-2] and ma5[-1] > ma20[-1]:
            sigs.append("金叉")
        if ma5[-2] >= ma20[-2] and ma5[-1] < ma20[-1]:
            sigs.append("死叉")
    window = points[-win:]
    closes = [p["close"] for p in window]
    last_close = closes[-1]
    if last_close >= max(closes):
        sigs.append(f"新高{win}")
    if last_close <= min(closes):
        sigs.append(f"新低{win}")
    r = rsi(points)
    if r is not None:
        if r > 70:
            sigs.append("超买")
        elif r < 30:
            sigs.append("超卖")
    if len(points) >= 21 and points[-1]["volume"] > 1.5 * vol_avg(points, 20):
        sigs.append("放量")
    last = points[-1]
    return last["close"], last["pct"], sigs


def main():
    ap = argparse.ArgumentParser(description="技术信号扫描")
    ap.add_argument("codes", nargs="*", help="股票代码（空格分隔）")
    ap.add_argument("--block", default="", help="板块（代码或名称）")
    ap.add_argument("--portfolio", action="store_true", help="当前模拟盘持仓")
    ap.add_argument("--breakout-window", type=int, default=20, help="新高/新低窗口，默认 20")
    ap.add_argument("--only", default="", help="只显示指定信号，逗号分隔")
    ap.add_argument("--top", type=int, default=50, help="最多输出条数")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else None

    codes = list(args.codes)
    if args.block:
        from boards import fetch_block_stocks, resolve_block
        block = args.block.strip()
        if block.upper().startswith("BK"):
            bcode, bname = block.upper(), None
        else:
            resolved = resolve_block(block)
            if not resolved:
                sys.exit(f"❌ 未找到板块 {block!r}")
            bcode, bname = resolved
        _, stks = fetch_block_stocks(bcode)
        codes = [s["code"] for s in stks]
        print(f"板块 {bname or bcode} 共 {len(codes)} 只:", file=sys.stderr)
    if args.portfolio:
        from paper import load_portfolio
        codes = list(load_portfolio().get("positions", {}).keys())
        print(f"当前持仓 {len(codes)} 个:", file=sys.stderr)

    if not codes:
        sys.exit("❌ 请提供代码 / --block / --portfolio")

    results = []
    for code in codes:
        code = str(code).zfill(6)
        name, points = fetch_kline(code, lmt=120)
        if not points:
            continue
        price, pct, sigs = compute_signals(code, points, args.breakout_window)
        if only:
            sigs = [s for s in sigs if any(s.startswith(o) or o in s for o in only)]
        results.append({"code": code, "name": name, "price": price, "pct": pct, "signals": sigs})

    # 有信号的在前，按信号数排序
    results.sort(key=lambda r: (-len(r["signals"]), r["code"]))

    if args.json:
        print(json.dumps({"asof": points[-1]["date"] if points else None,
                          "total": len(results),
                          "results": [r for r in results if r["signals"]]},
                         ensure_ascii=False, indent=2))
        return

    if args.only:
        print(f"信号扫描（{args.only}，共 {sum(1 for r in results if r['signals'])} 只命中）:")
    else:
        print(f"信号扫描（共 {sum(1 for r in results if r['signals'])} 只有信号 / 扫描 {len(results)} 只）:")
    header = pad("代码", 8) + pad("名称", 16) + pad("收盘", 10, "right") + pad("涨跌", 9, "right") + " 信号"
    print(header)
    print("-" * display_width(header))
    for r in results:
        if args.only and not r["signals"]:
            continue
        if not args.only and not r["signals"]:
            continue  # 默认只显示有信号的
        print(pad(r["code"], 8) + pad(r["name"], 16) + pad(f"{r['price']:.2f}", 10, "right")
              + pad(fmt_pct(r["pct"]), 9, "right") + " " + ", ".join(r["signals"]))


if __name__ == "__main__":
    main()
