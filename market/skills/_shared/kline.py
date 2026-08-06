#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K 线数据与指标助手 (signal / backtest / position-size 共用)。

- fetch_kline: 东方财富日 K（前复权 klt=101），返回 (name, points)
  points: [{date, open, high, low, close, volume, amount, pct}]
- 指标: ma / rsi / atr / true_range / 区间涨幅
"""
import json
import re

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def fetch_kline(code: str, lmt: int = 500):
    """东方财富日 K（前复权）。返回 (name, points) 或 (None, None)。"""
    from httpget import httpget
    code = str(code).zfill(6)
    secid = f"{'1' if code.startswith('6') else '0'}.{code}"
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
                           headers={"User-Agent": UA,
                                    "Referer": f"https://quote.eastmoney.com/{'sh' if secid.startswith('1.') else 'sz'}{code}.html"})
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            klines = data.get("klines") or []
            if not klines:
                continue
            points = []
            for k in klines:
                parts = k.split(",")
                if len(parts) < 11:
                    continue
                try:
                    points.append({
                        "date": parts[0],
                        "open": float(parts[1]),
                        "close": float(parts[2]),
                        "high": float(parts[3]),
                        "low": float(parts[4]),
                        "volume": float(parts[5]),
                        "amount": float(parts[6]),
                        "pct": float(parts[8]) if parts[8] not in ("", "-") else None,
                    })
                except (TypeError, ValueError):
                    continue
            if points:
                return data.get("name") or code, points
        except Exception:
            continue
    return fetch_kline_sina(code, lmt)


def fetch_kline_sina(code: str, lmt: int = 500):
    """新浪日 K 兜底（东财接口限流/不可用时）。返回 (name, points) 或 (None, None)。
    points 结构与东财一致（无 amount/pct，由收盘价推算 pct）。"""
    import json
    from httpget import httpget
    code = str(code).zfill(6)
    symbol = ("sh" if code.startswith("6") else
              "bj" if code.startswith(("4", "8")) else "sz") + code
    try:
        resp = httpget(
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
            params={"symbol": symbol, "scale": 240, "ma": "no", "datalen": str(lmt)},
            timeout=15, headers={"User-Agent": UA, "Referer": "https://finance.sina.com.cn/"})
        resp.raise_for_status()
        rows = json.loads(resp.text)
        if not rows:
            return None, None
        points = []
        prev_close = None
        for r in rows:
            try:
                close = float(r["close"])
            except (TypeError, ValueError):
                continue
            pct = ((close / prev_close - 1) * 100) if prev_close else None
            points.append({
                "date": r.get("day", ""),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": close,
                "volume": float(r["volume"]),
                "amount": None,
                "pct": pct,
            })
            prev_close = close
        return code, points
    except Exception:
        return None, None


def closes(points):
    return [p["close"] for p in points]


def ma(points, n):
    """简单移动平均序列（与 points 等长，前 n-1 为 None）。"""
    vals = closes(points)
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= n:
            s -= vals[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def rsi(points, n=14):
    """当前 RSI(n)。返回 float 或 None。"""
    vals = closes(points)
    if len(vals) <= n:
        return None
    gains = losses = 0.0
    for i in range(len(vals) - n, len(vals)):
        d = vals[i] - vals[i - 1]
        if d > 0:
            gains += d
        else:
            losses -= d
    if gains + losses == 0:
        return 50.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def true_range(points):
    trs = []
    for i in range(1, len(points)):
        h, l, pc = points[i]["high"], points[i]["low"], points[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return trs


def atr(points, n=14):
    """当前 ATR(n)。返回 float 或 None。"""
    trs = true_range(points)
    if len(trs) < n:
        return None
    return sum(trs[-n:]) / n


def vol_avg(points, n=20):
    """最近 n 日均量。"""
    vols = [p["volume"] for p in points[-n:]]
    return sum(vols) / len(vols) if vols else 0


def period_return(points, n):
    if len(points) < n + 1:
        return None
    return (points[-1]["close"] / points[-1 - n]["close"] - 1) * 100


def resolve_name(code: str) -> str:
    """通过东方财富 suggest 接口补股票名称（东财行情被限流/新浪兜底无名称时用）。"""
    from httpget import httpget
    code = str(code).zfill(6)
    try:
        r = httpget("https://searchapi.eastmoney.com/api/suggest/get",
                         params={"input": code, "type": "14", "count": "1",
                                 "token": "D43BF722C8E33BDC906FB84D85E326E8"},
                         timeout=10, headers={"User-Agent": UA, "Referer": "https://www.eastmoney.com/"})
        rows = ((r.json().get("QuotationCodeTable") or {}).get("Data")) or []
        for x in rows:
            if str(x.get("Code")).zfill(6) == code:
                return str(x.get("Name") or code)
    except Exception:
        pass
    return code


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "688256"
    name, pts = fetch_kline(code, lmt=120)
    print(f"{name} ({code}): {len(pts)} bars, last {pts[-1]['date']} close={pts[-1]['close']}")
    print(f"MA5={ma(pts, 5)[-1]:.2f} MA20={ma(pts, 20)[-1]:.2f} "
          f"RSI14={rsi(pts):.1f} ATR14={atr(pts):.2f} 均量20={vol_avg(pts):.0f}")
