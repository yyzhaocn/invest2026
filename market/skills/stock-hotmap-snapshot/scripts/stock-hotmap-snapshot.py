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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

REPO_ROOT = Path("/Users/yyz/pydev/invest2026")
SNAP_DIR = REPO_ROOT / "generated" / "heatmap_snapshots"
STOCK_DIR = REPO_ROOT / "stock"

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
FS = "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:7"

# 历史快照节奏（与 heatmap_snapshots/ 现有文件一致）: 开盘1分钟后 + 每30分钟（午休跳过）
SCHEDULE = ["09:31", "10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00"]


def fetch_market():
    """分页拉取全市场。返回 [[market, code, chg, fcap_million, mcap_million]]。"""
    from httpget import httpget
    rows, total, pn = [], None, 1
    while True:
        resp = httpget("https://push2delay.eastmoney.com/api/qt/clist/get", params={
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


def is_trading_day(now=None):
    """交易日判断（复用 stock/trading_calendar.py）。"""
    import sys
    if str(STOCK_DIR) not in sys.path:
        sys.path.insert(0, str(STOCK_DIR))
    try:
        from trading_calendar import is_trading_day as _td
        return _td(now)
    except Exception:
        return (now or datetime.now()).weekday() < 5


def take_snapshot():
    """拉取并落盘一张快照，返回 (path, rows, up, down)。"""
    rows = fetch_market()
    if not rows:
        return None, 0, 0, 0
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = SNAP_DIR / f"snapshot_{ts}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["market", "code", "chg_pct", "vol_rank", "amt_rank"])
        w.writerows(rows)
    up = sum(1 for r in rows if r[2] > 0)
    down = sum(1 for r in rows if r[2] < 0)
    return out, len(rows), up, down


def run_watch():
    """交易时段按 SCHEDULE 自动打快照，直到收盘。"""
    import time
    print(f"📡 watch 模式启动（节奏: {' / '.join(SCHEDULE)}，交易日自动）")
    if not is_trading_day():
        print("今天是休息日，无可打快照时点。退出。")
        return
    done = set()
    while True:
        now = datetime.now()
        hm = now.strftime("%H:%M")
        if hm >= "15:00":
            print(f"✅ 已收盘（{now.strftime('%H:%M')}），共生成 {len(done)} 张快照")
            return
        if hm in SCHEDULE and hm not in done:
            out, n, up, down = take_snapshot()
            if out:
                print(f"📸 {hm} → {out.name}（{n} 只，涨 {up} / 跌 {down}）")
                done.add(hm)
            else:
                print(f"⚠️  {hm} 快照失败（网络/限流），稍后重试")
                time.sleep(60)
                continue
        # 睡到下一个计划时点（最多 60s 醒来检查一次，兼容错过时点立即补拍）
        time.sleep(30)


def main():
    ap = argparse.ArgumentParser(description="全市场热力图数据快照")
    ap.add_argument("--out", "-o", default="",
                    help="输出路径（默认 generated/heatmap_snapshots/snapshot_<时间>.csv）")
    ap.add_argument("--watch", action="store_true", help="交易时段每 30 分钟自动打快照直到收盘")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.watch:
        run_watch()
        return

    if args.out:
        rows = fetch_market()
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["market", "code", "chg_pct", "vol_rank", "amt_rank"])
            w.writerows(rows)
        total, up, down = len(rows), sum(1 for r in rows if r[2] > 0), sum(1 for r in rows if r[2] < 0)
    else:
        out, total, up, down = take_snapshot()
        if out is None:
            sys.exit("❌ 未获取到行情数据")

    if args.json:
        print(json.dumps({"out": str(out), "total": total, "up": up, "down": down},
                         ensure_ascii=False, indent=2))
        return

    print(f"✅ 快照已生成: {out}")
    print(f"   共 {total} 只 ｜ 涨 {up} / 跌 {down}")


if __name__ == "__main__":
    main()
