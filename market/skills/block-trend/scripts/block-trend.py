#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
block-trend: 按板块代码或名称列出近期走势（板块指数日 K）。

用法:
  python3 block-trend.py <板块代码或名称> [--days N] [--json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from boards import fetch_board_kline, resolve_block  # noqa: E402

SPARK_CHARS = "▁▂▃▄▅▆▇█"
PERIODS = [("5日", 5), ("20日", 20), ("60日", 60), ("120日", 120), ("250日", 250)]


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def fmt_pct(v):
    return f"{v:+.2f}%"


def sparkline(points):
    if len(points) < 2:
        return ""
    vals = [p["close"] for p in points]
    lo, hi = min(vals), max(vals)
    span = hi - lo or 1.0
    return "".join(SPARK_CHARS[min(7, int((v - lo) / span * 8))] for v in vals)


def main():
    ap = argparse.ArgumentParser(description="列出板块近期走势")
    ap.add_argument("block", help="板块代码 (BKxxxx) 或板块名称")
    ap.add_argument("--days", type=int, default=15, help="走势表天数，默认 15，最大 60")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    days = max(1, min(args.days, 60))
    block = args.block.strip()

    # 解析为 BK 代码
    code, name = None, None
    if block.upper().startswith("BK"):
        code = block.upper()
    else:
        resolved = resolve_block(block)
        if not resolved:
            print(f"❌ 未找到板块 {block!r}（可用 block-list 确认名称/代码）", file=sys.stderr)
            sys.exit(1)
        code, name = resolved

    kname, points = fetch_board_kline(code)
    if not points:
        print(f"❌ 获取板块 {code} K 线失败（板块可能已下线）", file=sys.stderr)
        sys.exit(1)

    display_name = name or kname or code
    latest = points[-1]
    last_pct = latest["pct"]

    periods = {}
    for label, n in PERIODS:
        if len(points) < n + 1:
            periods[label] = None
        else:
            periods[label] = (points[-1]["close"] / points[-1 - n]["close"] - 1) * 100

    if args.json:
        print(json.dumps({
            "block_code": code,
            "name": display_name,
            "asof": latest["date"],
            "latest_close": latest["close"],
            "latest_day_pct": last_pct,
            "periods": {k: (round(v, 4) if v is not None else None) for k, v in periods.items()},
            "recent": points[-days:],
        }, ensure_ascii=False, indent=2))
        return

    print(f"{display_name} ({code}) ｜ 数据截至 {latest['date']} ｜ "
          f"收盘 {latest['close']:.2f} ({fmt_pct(last_pct) if last_pct is not None else '--'})")

    period_str = " ｜ ".join(f"{k} {fmt_pct(v) if v is not None else 'N/A'}"
                            for k, v in periods.items())
    print(f"\n区间表现: {period_str}")

    win = points[-60:]
    hi, lo = max(win, key=lambda p: p["close"]), min(win, key=lambda p: p["close"])
    print(f"近60日高/低: {hi['close']:.2f} ({hi['date'][5:]}) / {lo['close']:.2f} ({lo['date'][5:]})")

    shown = points[-days:]
    print(f"\n近{days}日收盘走势:")
    header = pad("日期", 12) + pad("收盘", 12, "right") + pad("日涨跌", 10, "right") + "方向"
    print(header)
    print("-" * display_width(header))
    for p in shown:
        pct = p["pct"]
        pct_str = fmt_pct(pct) if pct is not None else "  --"
        if pct is None:
            arrow = "·"
        elif pct > 0:
            arrow = "▲"
        elif pct < 0:
            arrow = "▼"
        else:
            arrow = "▬"
        print(pad(p["date"], 12) + pad(f"{p['close']:.2f}", 12, "right")
              + pad(pct_str, 10, "right") + " " + arrow)
    print()
    print(f"近{days}日走势缩略: {sparkline(shown)}")


if __name__ == "__main__":
    main()
