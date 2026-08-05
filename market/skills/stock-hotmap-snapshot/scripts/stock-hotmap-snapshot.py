#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock-hotmap-snapshot: 全市场热力图数据快照（market,code,chg_pct,流通市值,总市值）。

格式与 generated/heatmap_snapshots/ 历史快照一致（按流通市值降序）。

用法:
  python3 stock-hotmap-snapshot.py [--out 路径] [--json]
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SNAP_DIR = REPO_ROOT / "generated" / "heatmap_snapshots"

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
FS = "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:7"


def fetch_market():
    """分页拉取全市场。返回 [[market, code, chg, fcap_million, mcap_million]]。"""
    import requests
    rows, total, pn = [], None, 1
    while True:
        resp = requests.get("https://push2delay.eastmoney.com/api/qt/clist/get", params={
            "fid": "f12", "po": "0", "pz": "100", "pn": str(pn), "np": "1",
            "fltt": "2", "invt": "2", "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": FS, "fields": "f12,f3,f20,f21",
        }, timeout=20, headers=UA)
        resp.raise_for_status()
        data = resp.json().get("data") or {}
        total = data.get("total", 0)
        diff = data.get("diff") or []
        if not diff:
            break
        for x in diff:
            code = str(x.get("f12", "")).zfill(6)
            try:
                pct = float(x.get("f3"))
            except (TypeError, ValueError):
                pct = 0.0
            try:
                fcap = int(float(x.get("f21")) / 1e6)
            except (TypeError, ValueError):
                fcap = 0
            try:
                mcap = int(float(x.get("f20")) / 1e6)
            except (TypeError, ValueError):
                mcap = 0
            rows.append([("SH" if code.startswith("6") else "SZ"), code, pct, fcap, mcap])
        if total and len(rows) >= total:
            break
        pn += 1

    seen, dedup = set(), []
    for row in rows:
        if row[1] in seen:
            continue
        seen.add(row[1])
        dedup.append(row)
    dedup.sort(key=lambda r: -r[3])  # 按流通市值降序，与原快照一致
    return dedup


def main():
    ap = argparse.ArgumentParser(description="全市场热力图数据快照")
    ap.add_argument("--out", "-o", default="",
                    help="输出路径（默认 generated/heatmap_snapshots/snapshot_<时间>.csv）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = fetch_market()
    if not rows:
        sys.exit("❌ 未获取到行情数据")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = Path(args.out) if args.out else SNAP_DIR / f"snapshot_{ts}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["market", "code", "chg_pct", "vol_rank", "amt_rank"])
        w.writerows(rows)

    up = sum(1 for r in rows if r[2] > 0)
    down = sum(1 for r in rows if r[2] < 0)

    if args.json:
        print(json.dumps({"out": str(out), "total": len(rows), "up": up, "down": down,
                          "top5": rows[:5]}, ensure_ascii=False, indent=2))
        return

    print(f"✅ 快照已生成: {out}")
    print(f"   共 {len(rows)} 只 ｜ 涨 {up} / 跌 {down}")
    print("   流通市值 TOP5:")
    for r in rows[:5]:
        print(f"     {r[0]} {r[1]}  chg {r[2]:+.2f}%  流通 {r[3] / 1e4:,.0f}亿 / 总 {r[4] / 1e4:,.0f}亿")


if __name__ == "__main__":
    main()
