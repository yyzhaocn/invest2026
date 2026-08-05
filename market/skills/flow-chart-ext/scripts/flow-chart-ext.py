#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow-chart-ext: 个股资金流向深度图表（复用 stock/app.py generate_flow_chart）。

- 生成 8 面板 matplotlib PNG（实时资金流/主力趋势/涨幅/K线/量/RSI/MACD）
- 复用 hist_chart_cache 缓存策略（--force/--clear）
- 终端输出按接口真实口径的资金流摘要

用法:
  python3 flow-chart-ext.py <代码> [--days N] [--out 路径] [--force] [--clear] [--no-cache] [--json]
"""
import argparse
import contextlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
STOCK_DIR = REPO_ROOT / "stock"
GENERATED = REPO_ROOT / "generated"
sys.path.insert(0, str(STOCK_DIR))


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


def fmt_wan(v):
    return f"{v / 1e4:+,.1f}"


def fetch_flow_raw(code: str, lmt: int = 80):
    """按接口真实口径拉取日频资金流（用于终端摘要）。带重试。"""
    import time as _t
    import requests
    code = str(code).zfill(6)
    secid = f"{'1' if code.startswith('6') else '0'}.{code}"
    last_err = None
    for _ in range(3):
        try:
            resp = requests.get("https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
                                params={"lmt": "0", "klt": "101", "secid": secid,
                                        "fields1": "f1,f2,f3,f7",
                                        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                                        "ut": "b2884a393a59ad64002292a3e90d46a5"},
                                timeout=15, headers={"User-Agent": "Mozilla/5.0",
                                                     "Referer": "https://data.eastmoney.com/"})
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            rows = []
            for line in (data.get("klines") or [])[-lmt:]:
                p = line.split(",")
                if len(p) < 15:
                    continue
                rows.append({"date": p[0], "main": float(p[1]), "small": float(p[2]),
                             "mid": float(p[3]), "big": float(p[4]), "xbig": float(p[5]),
                             "main_pct": float(p[6]), "close": float(p[11]), "pct": float(p[12])})
            if rows:
                return data.get("name") or code, rows
        except Exception as e:
            last_err = e
            _t.sleep(1.5)
    raise ConnectionError(f"资金流接口失败: {last_err}")


def main():
    ap = argparse.ArgumentParser(description="个股资金流向深度图表（PNG）")
    ap.add_argument("code", help="股票代码")
    ap.add_argument("--days", type=int, default=80, help="最近 N 个交易日，默认 80")
    ap.add_argument("--out", "-o", default="", help="PNG 输出路径（默认 generated/cache/stockd/charts/）")
    ap.add_argument("--force", action="store_true", help="忽略图表缓存强制重新生成")
    ap.add_argument("--clear", action="store_true", help="清除该股图表缓存后重新生成")
    ap.add_argument("--no-cache", action="store_true", help="资金流数据不用 CSV 缓存")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)

    # ---- 终端摘要（真实口径）----
    name, rows = code, []
    try:
        name, rows = fetch_flow_raw(code, lmt=max(args.days, 20))
    except Exception as e:
        print(f"⚠️  资金流摘要获取失败（图表仍将生成）: {e}", file=sys.stderr)

    if rows:
        def _sum(n):
            return sum(r["main"] for r in rows[-n:]) if len(rows) >= n else None

        cum = {"5日": _sum(5), "10日": _sum(10), "20日": _sum(20)}
        up_days = sum(1 for r in rows if r["main"] > 0)
        last = rows[-1]

    # ---- 生成 PNG 图表（复用 app.py 逻辑）----
    from hist_chart_cache import (clear_hist_chart_cache, find_hist_chart,
                                  hist_chart_path, should_refresh_hist_chart,
                                  write_hist_chart_marker)
    from quote_cache import effective_quote_date_short
    from utils_cap import plot_hist_flow

    if args.clear:
        clear_hist_chart_cache(code)
        args.force = True

    need, reason = should_refresh_hist_chart(code, force=args.force)
    chart_path = None
    cached = False
    if not need:
        hit = find_hist_chart(code)
        if hit and os.path.isfile(hit):
            chart_path, cached = hit, True

    if chart_path is None:
        eff = effective_quote_date_short()
        if args.out:
            chart_path = str(Path(args.out))
        else:
            chart_path = hist_chart_path(code, eff)
        os.makedirs(os.path.dirname(chart_path), exist_ok=True)
        with contextlib.redirect_stdout(sys.stderr):
            fig = plot_hist_flow(code, save_path=chart_path, use_cache=not args.no_cache, ndays=args.days)
        if not fig or not os.path.exists(chart_path):
            sys.exit("❌ 图表生成失败")
        write_hist_chart_marker(code)

    if args.json:
        out = {"code": code, "name": name, "chart_path": chart_path,
               "cached": cached, "reason": reason, "days": len(rows)}
        if rows:
            out.update({"last": last, "cum5": cum["5日"], "cum10": cum["10日"],
                        "cum20": cum["20日"], "main_positive_days": up_days})
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if rows:
        print(f"{name} ({code}) ｜ 最近 {len(rows)} 日资金流摘要（单位: 万元）")
        header = " ".join([pad("日期", 12), pad("收盘", 8, "right"), pad("涨跌", 8, "right"),
                           pad("主力净流入", 13, "right"), pad("主力占比", 9, "right"),
                           pad("超大单", 11, "right"), pad("大单", 11, "right")])
        print(header)
        print("-" * display_width(header))
        for r in rows[-10:]:
            print(" ".join([pad(r["date"], 12), pad(f"{r['close']:.2f}", 8, "right"),
                            pad(fmt_pct(r["pct"]), 8, "right"),
                            pad(fmt_wan(r["main"]), 13, "right"),
                            pad(f"{r['main_pct']:+.2f}", 9, "right"),
                            pad(fmt_wan(r["xbig"]), 11, "right"),
                            pad(fmt_wan(r["big"]), 11, "right")]))
        print()
        print(f"主力累计: " + " ｜ ".join(f"{k} {fmt_wan(v)}" for k, v in cum.items() if v is not None))
        print(f"主力净流入天数: {up_days}/{len(rows)} ｜ 最新 {last['date']}: {fmt_wan(last['main'])}（{last['main_pct']:+.2f}%）")
    else:
        print(f"{name} ({code}) ｜ 资金流摘要暂不可用（接口限流/网络），图表已生成")
    print(f"📊 图表({'缓存命中' if cached else '已生成'}): {chart_path}（open {chart_path}）")
    if args.out:
        print("（--out 指定路径，未写 Web 缓存标记）")


if __name__ == "__main__":
    main()
