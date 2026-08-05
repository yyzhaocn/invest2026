#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan: 全市场策略选股扫描（涨跌幅/成交额/换手/市值/板块过滤）。

数据: push2delay clist 全市场（缓存 10 分钟）+ 本地 zjlx 主力资金 join。

用法:
  python3 scan.py [--block 板块] [--min-pct -3] [--max-pct 5] [--min-amount 10]
                  [--min-turnover 3] [--min-mcap 100] [--sort pct|amount|turnover|mcap|code]
                  [--top 30] [--json] [--refresh]
"""
import argparse
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from boards import resolve_block  # noqa: E402

CACHE_DIR = REPO_ROOT / "generated" / "em"
CACHE_TTL = 600  # 10 分钟

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
FIELDS = "f12,f14,f2,f3,f6,f8,f20,f21"
SORTS = {"pct": "f3", "amount": "f6", "turnover": "f8", "mcap": "f20", "code": "f12"}


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


def fetch_market(refresh: bool = False):
    """拉取全市场 A 股行情（缓存 10 分钟）。返回 (asof, rows)。"""
    import requests
    date = datetime.now().strftime("%Y%m%d")
    cache = CACHE_DIR / f"scan_{date}.csv"
    if not refresh and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        with open(cache, encoding="utf-8") as f:
            rows = [dict(r) for r in csv.DictReader(f)]
        for r in rows:
            for k in ("pct", "amount", "turnover", "mcap", "fcap"):
                try:
                    r[k] = float(r[k]) if r.get(k) not in (None, "") else None
                except (TypeError, ValueError):
                    r[k] = None
        return date, rows

    fs = "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:7"
    rows, total, pn = [], None, 1
    while True:
        resp = requests.get("https://push2delay.eastmoney.com/api/qt/clist/get", params={
            "fid": "f3", "po": "0", "pz": "100", "pn": str(pn), "np": "1",
            "fltt": "2", "invt": "2", "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": fs, "fields": FIELDS,
        }, timeout=20, headers=UA)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
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
                "code": str(x.get("f12", "")).zfill(6),
                "name": str(x.get("f14", "")),
                "price": x.get("f2"),
                "pct": pct,
                "amount": _f(x, "f6"),
                "turnover": _f(x, "f8"),
                "mcap": _f(x, "f20"),
                "fcap": _f(x, "f21"),
            })
        if total and len(rows) >= total:
            break
        pn += 1
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return date, rows


def _f(x, key):
    v = x.get(key)
    try:
        return float(v) if v not in (None, "-") else None
    except (TypeError, ValueError):
        return None


def load_zjlx_flow():
    """本地 zjlx 快照主力净流入 {code: 亿}。返回 (asof, map)。"""
    files = sorted(glob.glob(str(CACHE_DIR / "*" / "zjlx_*.csv")), reverse=True)
    if not files:
        return None, {}
    path = files[0]
    flow = {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                code = str(row.get("代码", "")).zfill(6)
                try:
                    flow[code] = float(row.get("主力净流入", 0) or 0) / 1e8
                except (TypeError, ValueError):
                    pass
    except Exception:
        return None, {}
    asof = os.path.basename(path).replace("zjlx_zlb_", "").replace("zjlx_", "").replace(".csv", "")
    return asof, flow


def main():
    ap = argparse.ArgumentParser(description="全市场策略选股扫描")
    ap.add_argument("--block", default="", help="限定板块（代码或名称）")
    ap.add_argument("--min-pct", type=float, help="最小涨跌幅 %%")
    ap.add_argument("--max-pct", type=float, help="最大涨跌幅 %%")
    ap.add_argument("--min-amount", type=float, help="最小成交额（亿）")
    ap.add_argument("--min-turnover", type=float, help="最小换手率 %%")
    ap.add_argument("--min-mcap", type=float, help="最小总市值（亿）")
    ap.add_argument("--sort", default="pct", choices=list(SORTS.keys()), help="排序字段，默认 pct")
    ap.add_argument("--top", type=int, default=30, help="输出条数，默认 30，0=全部")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--refresh", action="store_true", help="忽略缓存强制拉取")
    args = ap.parse_args()

    date, rows = fetch_market(args.refresh)

    if args.block:
        block = args.block.strip()
        if block.upper().startswith("BK"):
            bcode, bname = block.upper(), None
        else:
            resolved = resolve_block(block)
            if not resolved:
                sys.exit(f"❌ 未找到板块 {block!r}")
            bcode, bname = resolved
        # 板块内扫描：用 b: 过滤单独拉取
        from boards import fetch_block_stocks
        total, bstocks = fetch_block_stocks(bcode, fields=FIELDS)
        rows = []
        for s in bstocks:
            rows.append({"code": s["code"], "name": s["name"], "price": s.get("price"),
                         "pct": s.get("pct"), "amount": s.get("amount"),
                         "turnover": s.get("turnover"), "mcap": s.get("mcap"),
                         "fcap": s.get("fcap")})
        print(f"板块 {bname or bcode} 内 {len(rows)} 只:", file=sys.stderr)

    # 过滤
    conds = []
    if args.min_pct is not None:
        rows = [r for r in rows if (r["pct"] or -999) >= args.min_pct]; conds.append(f"涨跌幅≥{args.min_pct}%")
    if args.max_pct is not None:
        rows = [r for r in rows if (r["pct"] or 999) <= args.max_pct]; conds.append(f"涨跌幅≤{args.max_pct}%")
    if args.min_amount is not None:
        rows = [r for r in rows if (r["amount"] or 0) >= args.min_amount * 1e8]; conds.append(f"成交额≥{args.min_amount}亿")
    if args.min_turnover is not None:
        rows = [r for r in rows if (r["turnover"] or 0) >= args.min_turnover]; conds.append(f"换手≥{args.min_turnover}%")
    if args.min_mcap is not None:
        rows = [r for r in rows if (r["mcap"] or 0) >= args.min_mcap * 1e8]; conds.append(f"市值≥{args.min_mcap}亿")

    # 去重（分页拉取时实时数据可能跨页重复）
    seen, dedup = set(), []
    for r in rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        dedup.append(r)
    rows = dedup

    key = {"pct": "pct", "amount": "amount", "turnover": "turnover", "mcap": "mcap", "code": "code"}[args.sort]
    rows.sort(key=lambda r: ((r.get(key) if key == "code" else (r.get(key) or -1e18)), -r.get("pct", 0) if key == "code" else 0),
              reverse=(key != "code"))
    if key == "code":
        rows.sort(key=lambda r: r["code"])

    flow_asof, flow = load_zjlx_flow()
    for r in rows:
        r["flow"] = flow.get(r["code"]) if flow_asof else None

    shown = rows if args.top <= 0 else rows[:args.top]
    if args.json:
        print(json.dumps({"asof": date, "matched": len(rows), "conditions": conds,
                          "flow_asof": flow_asof, "results": shown}, ensure_ascii=False, indent=2))
        return

    cond_str = ("，条件: " + "，".join(conds)) if conds else ""
    print(f"A 股扫描（{date}，共 {len(rows)} 只命中{cond_str}）:")
    header = (pad("代码", 8) + pad("名称", 14) + pad("现价", 9, "right") + pad("涨跌幅", 9, "right")
              + pad("成交额(亿)", 10, "right") + pad("换手%", 8, "right") + pad("市值(亿)", 10, "right"))
    if flow_asof:
        header += pad("主力净流入(亿)", 14, "right")
        print(f"（主力资金快照 {flow_asof}）")
    print(header)
    print("-" * display_width(header))
    for r in shown:
        row = (pad(r["code"], 8) + pad(r["name"], 14)
               + pad(str(r["price"] or "--"), 9, "right") + pad(fmt_pct(r["pct"]), 9, "right")
               + pad(f"{(r['amount'] or 0) / 1e8:.2f}", 10, "right")
               + pad(f"{(r['turnover'] or 0):.2f}", 8, "right")
               + pad(f"{(r['mcap'] or 0) / 1e8:.1f}", 10, "right"))
        if flow_asof:
            f = r.get("flow")
            row += pad(f"{f:+.2f}" if f is not None else "--", 14, "right")
        print(row)
    if args.top > 0 and len(rows) > args.top:
        print(f"… 共 {len(rows)} 只命中（--top 0 显示全部）")
    print("候选可直接: portfolio buy <代码> <数量> --note scan命中")


if __name__ == "__main__":
    main()
