#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund-trend: 按基金代码列出近期净值走势。

数据源: https://fund.eastmoney.com/pingzhongdata/{code}.js
  - Data_netWorthTrend: [{x: ms, y: 单位净值, equityReturn: 日涨跌%}]
  - syl_1y/syl_3y/syl_6y/syl_1n: 官方区间涨幅 (近1月/3月/6月/1年)

用法:
  python3 fund-trend.py <基金代码> [--days N] [--json]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
BASE_URL = "https://fund.eastmoney.com/pingzhongdata/{}.js"

SPARK_CHARS = "▁▂▃▄▅▆▇█"


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


def fetch_and_parse(fundcode: str):
    """拉取并解析 pingzhongdata.js。返回 (basic, net_worth_list, period_returns)。"""
    from httpget import httpget
    url = BASE_URL.format(fundcode)
    r = httpget(url, timeout=15, headers={"User-Agent": UA})
    r.raise_for_status()
    text = r.text

    def _var(name):
        m = re.search(rf'var {name}\s*=\s*"?([^";]+)"?;', text)
        return m.group(1) if m else None

    def _json(name):
        m = re.search(rf'var {name}\s*=\s*(\[.*?\]|\{{.*?\}});', text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None

    name = _var("fS_name") or fundcode
    code = _var("fS_code") or fundcode

    # 官方区间涨幅 (字符串带引号)
    syl = {"1月": _var("syl_1y"), "3月": _var("syl_3y"), "6月": _var("syl_6y"), "1年": _var("syl_1n")}

    trend = _json("Data_netWorthTrend") or []
    points = []
    for item in trend:
        if not isinstance(item, dict) or "x" not in item or "y" not in item:
            continue
        try:
            ts = int(item["x"]) / 1000
            nav = float(item["y"])
        except (TypeError, ValueError):
            continue
        er = item.get("equityReturn")
        try:
            er = float(er) if er not in (None, "") else None
        except (TypeError, ValueError):
            er = None
        points.append({
            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
            "ts": ts,
            "nav": nav,
            "day_pct": er,
        })

    if not points:
        raise ValueError(f"基金 {fundcode} 无净值日序列数据")

    basic = {"name": name, "code": code}
    return basic, points, syl


def period_return(points, n):
    """按交易日数推算区间涨幅%。"""
    if len(points) < n + 1:
        return None
    return (points[-1]["nav"] / points[-n - 1]["nav"] - 1) * 100


def sparkline(points):
    """窗口内净值相对高低走势图，每字符一个交易日。"""
    if len(points) < 2:
        return ""
    navs = [p["nav"] for p in points]
    lo, hi = min(navs), max(navs)
    span = hi - lo or 1.0
    return "".join(SPARK_CHARS[min(7, int((v - lo) / span * 8))] for v in navs)


def main():
    ap = argparse.ArgumentParser(description="列出基金近期净值走势")
    ap.add_argument("fundcode", help="基金代码 (如 161631)")
    ap.add_argument("--days", type=int, default=15, help="走势表天数，默认 15，最大 60")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    fundcode = str(args.fundcode).zfill(6)
    days = max(1, min(args.days, 60))

    try:
        basic, points, syl = fetch_and_parse(fundcode)
    except Exception as e:
        print(f"❌ 获取基金 {fundcode} 趋势数据失败: {e}", file=sys.stderr)
        sys.exit(1)

    latest = points[-1]
    last_pct = latest["day_pct"] if latest["day_pct"] is not None else period_return(points, 1)

    # 区间表现: 官方优先，缺失用推算
    periods = {"1日": last_pct}
    for label, n in [("1月", 22), ("3月", 66), ("6月", 132), ("1年", 250)]:
        official = syl.get(label)
        try:
            official = float(official) if official not in (None, "") else None
        except (TypeError, ValueError):
            official = None
        periods[label] = official if official is not None else period_return(points, n)

    if args.json:
        out = {
            "fundcode": fundcode,
            "name": basic["name"],
            "asof": latest["date"],
            "latest_nav": latest["nav"],
            "latest_day_pct": last_pct,
            "periods": {k: (round(v, 4) if v is not None else None) for k, v in periods.items()},
            "recent": [{"date": p["date"], "nav": p["nav"], "day_pct": p["day_pct"]}
                       for p in points[-days:]],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # 表格输出
    print(f"{basic['name']} ({basic['code']}) ｜ 数据截至 {latest['date']} ｜ "
          f"单位净值 {latest['nav']:.4f} ({fmt_pct(last_pct)})")

    period_str = " ｜ ".join(f"{k} {fmt_pct(v) if v is not None else 'N/A'}"
                            for k, v in periods.items())
    print(f"\n区间表现: {period_str}")

    win = points[-60:]
    hi, lo = max(win, key=lambda p: p["nav"]), min(win, key=lambda p: p["nav"])
    print(f"近60日高/低: {hi['nav']:.4f} ({hi['date'][5:]}) / {lo['nav']:.4f} ({lo['date'][5:]})")

    shown = points[-days:]
    print(f"\n近{days}日净值走势:")
    header = pad("日期", 12) + pad("单位净值", 10, "right") + pad("日涨跌", 10, "right") + "方向"
    print(header)
    print("-" * display_width(header))
    for p in shown:
        pct = p["day_pct"] if p["day_pct"] is not None else None
        pct_str = fmt_pct(pct) if pct is not None else "  --"
        if pct is None:
            arrow = "·"
        elif pct > 0:
            arrow = "▲"
        elif pct < 0:
            arrow = "▼"
        else:
            arrow = "▬"
        print(pad(p["date"], 12) + pad(f"{p['nav']:.4f}", 10, "right")
              + pad(pct_str, 10, "right") + " " + arrow)
    print()
    print(f"近{days}日走势缩略: {sparkline(shown)}")


if __name__ == "__main__":
    main()
