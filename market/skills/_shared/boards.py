#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块数据共享助手 (block-list / block-trend / stock-list --block 共用)。

- 板块列表: 东方财富 clist (行业 m:90+t:2+f:!50 / 概念 m:90+t:3+f:!50)，缓存到
  generated/em/boards_<type>.csv（git 忽略），超 1 小时自动刷新，--refresh 强制
- 板块内股票: clist fs=b:BKxxxx
- 板块 K 线: push2his 90.BKxxxx (klt=101)
"""
import csv
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "generated" / "em"
CACHE_TTL = 3600  # 1 小时

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}

BOARD_FS = {
    "概念": "m:90+t:3+f:!50",
    "一级行业": "m:90+s:2+f:!50",
    "二级行业": "m:90+s:4+f:!50",
    "三级行业": "m:90+s:8+f:!50",
}
INDUSTRY_LEVELS = ["一级行业", "二级行业", "三级行业"]
LEVEL_TAG = {"一级行业": "一级", "二级行业": "二级", "三级行业": "三级"}
BOARD_FIELDS = "f12,f14,f3,f2,f128,f140"
STOCK_FIELDS = "f12,f14,f3,f2"
HOTMAP_FIELDS = "f12,f14,f2,f3,f6,f8,f20,f21"


def _cache_path(btype: str) -> Path:
    return CACHE_DIR / f"boards_{btype}.csv"


def _http_get(url, params, timeout=15):
    import requests
    resp = requests.get(url, params=params, timeout=timeout, headers=UA)
    resp.raise_for_status()
    return resp.json()


def fetch_boards_live(btype: str, max_pages: int = 20):
    """拉取全部板块列表。返回 [{code,name,pct,price,leader}]。"""
    fs = BOARD_FS.get(btype, BOARD_FS["概念"])
    total, rows = None, []
    for pn in range(1, max_pages + 1):
        data = _http_get("https://push2delay.eastmoney.com/api/qt/clist/get", {
            "fid": "f3", "po": "1", "pz": "100", "pn": str(pn), "np": "1",
            "fltt": "2", "invt": "2", "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fs": fs, "fields": BOARD_FIELDS,
        }).get("data") or {}
        total = data.get("total", 0)
        diff = data.get("diff") or []
        if not diff:
            break
        for x in diff:
            try:
                pct = float(x.get("f3")) if x.get("f3") not in (None, "-") else None
            except (TypeError, ValueError):
                pct = None
            rows.append({
                "code": str(x.get("f12", "")),
                "name": str(x.get("f14", "")),
                "pct": pct,
                "price": x.get("f2"),
                "leader": str(x.get("f128", "")),
            })
        if total and len(rows) >= total:
            break
    return rows


def save_boards_cache(btype: str, rows):
    _cache_path(btype).parent.mkdir(parents=True, exist_ok=True)
    asof = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_cache_path(btype), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["asof"] + list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({"asof": asof, **r})


def load_boards(btype: str, refresh: bool = False):
    """加载板块列表：优先本地缓存（TTL 内），否则拉取并落盘。

    btype="行业" 时合并一级/二级/三级行业并标注级别。
    """
    if btype == "行业":
        rows = []
        for lv in INDUSTRY_LEVELS:
            for r in load_boards(lv, refresh=refresh):
                rows.append({**r, "level": LEVEL_TAG[lv]})
        return rows

    path = _cache_path(btype)
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL:
        with open(path, encoding="utf-8") as f:
            rows = [dict(r) for r in csv.DictReader(f)]
        for r in rows:
            try:
                r["pct"] = float(r["pct"]) if r.get("pct") not in (None, "") else None
            except (TypeError, ValueError):
                r["pct"] = None
        return rows
    rows = fetch_boards_live(btype)
    if rows:
        save_boards_cache(btype, rows)
    return rows


def search_boards(query: str, btype: str = None, refresh: bool = False):
    """按代码前缀 / 名称子串搜索板块。返回匹配列表（含类型）。"""
    out = []
    types = [btype] if btype else list(BOARD_FS.keys())
    q = query.strip().lower()
    for t in types:
        for b in load_boards(t, refresh=refresh):
            if not q:
                out.append({**b, "type": t})
            elif b["code"].lower().startswith(q) or q in b["name"].lower():
                out.append({**b, "type": t})
    return out


def resolve_block(query: str, refresh: bool = False):
    """把 BK 代码或板块名解析为 (code, name)。返回 None 表示未找到。"""
    q = query.strip()
    matches = search_boards(q, refresh=refresh)
    if not matches:
        return None
    if len(matches) > 1:
        # 精确代码或精确名称优先
        for m in matches:
            if m["code"] == q or m["name"] == q:
                return m["code"], m["name"]
    return matches[0]["code"], matches[0]["name"]


def fetch_block_stocks(block_code: str, max_pages: int = 5, fields: str = None):
    """拉取板块内全部股票（按涨跌幅降序）。返回 (total, [{code,name,pct,price,...}])。

    fields 默认 f12,f14,f3,f2；额外可用 f6(成交额) f8(换手率) f20(总市值) f21(流通市值)。
    """
    code = block_code.upper() if block_code.upper().startswith("BK") else block_code
    fields = fields or STOCK_FIELDS
    fmap = {"f12": "code", "f14": "name", "f2": "price", "f3": "pct",
            "f6": "amount", "f8": "turnover", "f20": "mcap", "f21": "fcap"}
    total, rows = None, []
    for pn in range(1, max_pages + 1):
        data = _http_get("https://push2delay.eastmoney.com/api/qt/clist/get", {
            "fid": "f3", "po": "1", "pz": "100", "pn": str(pn), "np": "1",
            "fltt": "2", "invt": "2", "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": f"b:{code}", "fields": fields,
        }).get("data") or {}
        total = data.get("total", 0)
        diff = data.get("diff") or []
        if not diff:
            break
        for x in diff:
            try:
                pct = float(x.get("f3")) if x.get("f3") not in (None, "-") else None
            except (TypeError, ValueError):
                pct = None
            row = {
                "code": str(x.get("f12", "")).zfill(6),
                "name": str(x.get("f14", "")),
                "pct": pct,
                "price": x.get("f2"),
            }
            for f, key in fmap.items():
                if f not in ("f12", "f14", "f3") and x.get(f) not in (None, "-"):
                    try:
                        row[key] = float(x.get(f))
                    except (TypeError, ValueError):
                        pass
            rows.append(row)
        if total and len(rows) >= total:
            break
    return total or len(rows), rows


def fetch_board_kline(block_code: str, lmt: int = 500):
    """拉取板块日 K（指数）。返回 (name, [{date, close, pct}]) 或 (None, None)。"""
    import requests
    params = {
        "secid": f"90.{block_code}", "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101", "fqt": "1", "beg": "0", "end": "20500101", "lmt": str(lmt),
    }
    for url in ("https://push2his.eastmoney.com/api/qt/stock/kline/get",
                "https://push2.eastmoney.com/api/qt/stock/kline/get"):
        try:
            resp = requests.get(url, params=params, timeout=15,
                                headers={"User-Agent": UA["User-Agent"],
                                         "Referer": f"https://quote.eastmoney.com/bk/{block_code}.html"})
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            klines = data.get("klines") or []
            if not klines:
                continue
            name = data.get("name") or block_code
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


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    q = sys.argv[2] if len(sys.argv) > 2 else ""
    if mode == "stocks":
        total, rows = fetch_block_stocks(q)
        print(f"{q}: {total} 只")
        for r in rows[:10]:
            print(r)
    elif mode == "resolve":
        print(resolve_block(q, refresh=True))
    else:
        for b in search_boards(q, refresh=True)[:10]:
            print(b)
