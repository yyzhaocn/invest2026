#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock-trend: 按股票代码列出近期走势（日 K 前复权）。

数据源:
  - 主: 东方财富 push2his kline (klt=101, fqt=1)
  - 备: 新浪 CN_MarketData.getKLineData

用法:
  python3 stock-trend.py <股票代码> [--days N] [--json]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SPARK_CHARS = "▁▂▃▄▅▆▇█"

# 区间: (标签, 交易日数)
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


def em_secid(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"1.{code}"
    if code.startswith(("4", "8")):
        return f"0.{code}"  # 北交所走深市前缀不通时再降级
    return f"0.{code}"


def fetch_kline_em(code: str, lmt: int = 500):
    """东方财富日 K（前复权）。返回 (name, [{date,close,pct}...]) 或 (None, None)。"""
    from httpget import httpget
    secid = em_secid(code)
    params = {
        "secid": secid, "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1", "beg": "0", "end": "20500101", "lmt": str(lmt),
    }
    for url in ("https://push2his.eastmoney.com/api/qt/stock/kline/get",
                "https://push2.eastmoney.com/api/qt/stock/kline/get"):
        try:
            resp = httpget(url, params=params, timeout=15,
                                headers={"User-Agent": UA, "Referer": f"https://quote.eastmoney.com/{'sh' if secid.startswith('1.') else 'sz'}{code}.html"})
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or {}
            klines = data.get("klines") or []
            if not klines:
                continue
            name = data.get("name") or code
            points = []
            for k in klines:
                parts = k.split(",")
                if len(parts) < 11:
                    continue
                try:
                    points.append({
                        "date": parts[0],
                        "close": float(parts[2]),
                        "pct": float(parts[8]) if parts[8] not in ("", "-") else None,
                    })
                except (TypeError, ValueError):
                    continue
            if points:
                return name, points
        except Exception:
            continue
    return None, None


def fetch_kline_sina(code: str, datalen: int = 500):
    """新浪日 K 兜底。返回 (name, points)。"""
    from httpget import httpget
    symbol = ("sh" if code.startswith(("6", "9")) else
              "bj" if code.startswith(("4", "8")) else "sz") + code
    try:
        resp = httpget(
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
            params={"symbol": symbol, "scale": 240, "ma": "no", "datalen": datalen},
            timeout=15, headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"})
        resp.raise_for_status()
        rows = json.loads(resp.text)
        if not rows:
            return None, None
        points = []
        prev = None
        for r in rows:
            try:
                close = float(r["close"])
            except (TypeError, ValueError):
                continue
            pct = ((close - prev) / prev * 100) if prev else None
            points.append({"date": r.get("day", ""), "close": close, "pct": pct})
            prev = close
        return code, points
    except Exception:
        return None, None


def sparkline(points):
    if len(points) < 2:
        return ""
    navs = [p["close"] for p in points]
    lo, hi = min(navs), max(navs)
    span = hi - lo or 1.0
    return "".join(SPARK_CHARS[min(7, int((v - lo) / span * 8))] for v in navs)


def main():
    ap = argparse.ArgumentParser(description="列出股票近期走势")
    ap.add_argument("stockcode", help="股票代码 (如 688256)")
    ap.add_argument("--days", type=int, default=15, help="走势表天数，默认 15，最大 60")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    code = str(args.stockcode).zfill(6)
    days = max(1, min(args.days, 60))

    name, points = fetch_kline_em(code)
    if not points:
        name, points = fetch_kline_sina(code)
    if not points:
        print(f"❌ 获取股票 {code} 日 K 数据失败（代码可能不存在，可用 stock-list 确认）", file=sys.stderr)
        sys.exit(1)

    latest = points[-1]
    last_pct = latest["pct"] if latest["pct"] is not None else None

    periods = {}
    for label, n in PERIODS:
        if len(points) < n + 1:
            periods[label] = None
        else:
            periods[label] = (points[-1]["close"] / points[-1 - n]["close"] - 1) * 100

    if args.json:
        print(json.dumps({
            "stockcode": code,
            "name": name,
            "asof": latest["date"],
            "latest_close": latest["close"],
            "latest_day_pct": last_pct,
            "periods": {k: (round(v, 4) if v is not None else None) for k, v in periods.items()},
            "recent": points[-days:],
        }, ensure_ascii=False, indent=2))
        return

    print(f"{name} ({code}) ｜ 数据截至 {latest['date']} ｜ "
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
