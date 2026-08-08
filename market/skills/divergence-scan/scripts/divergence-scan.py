#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
divergence-scan: 批量 RSI 背离扫描（板块/组合/代码列表）。

算法与 multi-lens 的 RSI 背离维度一致（kaabar ch03/11）：
  win=5 摆动极值 + Wilder 平滑 RSI(14)，比较最后两个摆动低点/高点。

输入（三选一）:
  --block BKxxxx   板块全部成分
  --account <名>   组合持仓
  codes...         股票代码列表

用法:
  python3 divergence-scan.py --block BK0448
  python3 divergence-scan.py --account 7维选股
  python3 divergence-scan.py 600775 300620 --json
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"


def get_block_stocks(bk: str) -> list:
    out, pn = [], 1
    while True:
        p = subprocess.run(["curl", "-sS", "--max-time", "12", "-H", f"User-Agent: {UA}",
                            "-H", "Referer: https://quote.eastmoney.com/",
                            f"https://push2delay.eastmoney.com/api/qt/clist/get?pn={pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f20&fs=b:{bk}&fields=f12,f14"],
                           capture_output=True, text=True)
        if p.returncode != 0 or not p.stdout.strip():
            break
        d = json.loads(p.stdout)
        diff = (d.get("data") or {}).get("diff") or []
        out += [(r["f12"], r["f14"]) for r in diff]
        if len(out) >= ((d.get("data") or {}).get("total") or 0):
            break
        pn += 1
    return out


def get_account_codes(account: str) -> list:
    p = subprocess.run(["python3", PORTFOLIO, "--account", account, "show", "--json"],
                       capture_output=True, text=True, timeout=30)
    pf = json.loads(p.stdout)
    pos = pf["positions"]
    if isinstance(pos, dict):
        return [(k, v.get("name", k)) for k, v in pos.items()]
    return [(x["code"], x["name"]) for x in pos]


def rsi_series(closes, n=14):
    rsi_s = [None] * len(closes)
    if len(closes) > n:
        gains = losses = 0.0
        for i in range(1, n + 1):
            d = closes[i] - closes[i - 1]
            gains += max(d, 0); losses += max(-d, 0)
        for i in range(n, len(closes)):
            if i > n:
                d = closes[i] - closes[i - 1]
                gains = gains * (n - 1) / n + max(d, 0)
                losses = losses * (n - 1) / n + max(-d, 0)
            rsi_s[i] = 100 - 100 / (1 + gains / losses) if losses > 0 else 50.0
    return rsi_s


def find_divergence(df, win=5, rsi_n=14):
    closes = df["close"].astype(float).tolist()
    rsi_s = rsi_series(closes, rsi_n)
    highs = [(i, df["high"].iloc[i]) for i in range(win, len(df) - win)
             if df["high"].iloc[i] == df["high"].iloc[i - win:i + win + 1].max()]
    lows = [(i, df["low"].iloc[i]) for i in range(win, len(df) - win)
            if df["low"].iloc[i] == df["low"].iloc[i - win:i + win + 1].min()]
    out = []
    if len(highs) >= 2:
        (i1, p1), (i2, p2) = highs[-2], highs[-1]
        if p2 > p1 and rsi_s[i2] < rsi_s[i1]:
            out.append(("顶背离", df["date"].iloc[i1], p1, rsi_s[i1], df["date"].iloc[i2], p2, rsi_s[i2]))
    if len(lows) >= 2:
        (i1, p1), (i2, p2) = lows[-2], lows[-1]
        if p2 < p1 and rsi_s[i2] > rsi_s[i1]:
            out.append(("底背离", df["date"].iloc[i1], p1, rsi_s[i1], df["date"].iloc[i2], p2, rsi_s[i2]))
    return out


def main():
    ap = argparse.ArgumentParser(description="批量 RSI 背离扫描（底/顶背离）")
    ap.add_argument("codes", nargs="*", help="股票代码列表")
    ap.add_argument("--block", help="板块代码 BKxxxx")
    ap.add_argument("--account", help="组合账户")
    ap.add_argument("--window", type=int, default=5, help="摆动窗口（默认 5）")
    ap.add_argument("--rsi", type=int, default=14, help="RSI 周期（默认 14）")
    ap.add_argument("--lmt", type=int, default=120, help="K线数据长度（默认 120）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if args.block:
        targets = get_block_stocks(args.block)
        label = f"板块 {args.block}"
    elif args.account:
        targets = get_account_codes(args.account)
        label = f"组合 {args.account}"
    elif args.codes:
        targets = [(c.strip(), "") for c in args.codes]
        label = "代码列表"
    else:
        raise SystemExit("❌ 需提供 --block / --account / 代码列表")

    print(f"{label}：{len(targets)} 只，扫描中…", file=sys.stderr)
    import pandas as pd
    results = []
    for i, (code, name) in enumerate(targets):
        try:
            nm, pts = fetch_kline(code, lmt=args.lmt)
            if not pts:
                continue
            df = pd.DataFrame(pts)
            for t, d1, p1, r1, d2, p2, r2 in find_divergence(df, args.window, args.rsi):
                results.append({"code": code, "name": name or nm, "type": t,
                                "p1_date": d1, "p1": round(p1, 2), "p1_rsi": round(r1, 1),
                                "p2_date": d2, "p2": round(p2, 2), "p2_rsi": round(r2, 1)})
        except Exception:
            pass
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(targets)}", file=sys.stderr, flush=True)

    if args.json:
        print(json.dumps({"scanned": len(targets), "results": results}, ensure_ascii=False, indent=1))
        return

    n_b = sum(1 for r in results if r["type"] == "底背离")
    n_t = len(results) - n_b
    print(f"\n=== {label} RSI 背离 {len(results)} 条（底 {n_b} / 顶 {n_t}）===")
    for r in results:
        icon = "🔴底背离" if r["type"] == "底背离" else "🟢顶背离"
        print(f"{icon} {r['code']} {r['name']:8s} {r['p1_date']}({r['p1']},{r['p1_rsi']}) "
              f"→ {r['p2_date']}({r['p2']},{r['p2_rsi']})")


if __name__ == "__main__":
    main()
