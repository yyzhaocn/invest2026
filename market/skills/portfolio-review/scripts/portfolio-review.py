#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio-review: 组合持仓综合复盘表 —— 建仓时间 + 7维级别 + 技术信号 + 减仓建议。

数据源:
  - portfolio show --json          持仓/现价/浮盈/仓位
  - shared/paper/<账户>/trades.csv 建仓时间 (ts)
  - signal --portfolio --account   技术信号 (signals 列表)
  - --lens 可选: "code:label,..." 7维级别映射（不传则显示 ?）

建议规则（Grimes 纪律简化）:
  超买+新高+浮盈>0  → 止盈1/3
  超买+浮盈>0       → 减1/4
  浮亏<-2.5%        → 破位减半(设止损)
  浮亏<0            → 守成本观察
  新高+放量         → 持有观察
  其他              → 持有

用法:
  python3 portfolio-review.py --account 7维选股
  python3 portfolio-review.py --account 7维选股 --lens "603435:3多0空,300409:3多1空"
  python3 portfolio-review.py --account 基金持仓 --json
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"
SIGNAL = "/Users/yyz/.agents/skills/stock/signal/scripts/signal.py"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise SystemExit(p.stderr[:300])
    return json.loads(p.stdout)


def build_time(code, account) -> str:
    """读 trades.csv 取建仓时间 ts（精确到分）。"""
    path = Path.cwd() / "shared" / "paper" / account / "trades.csv"
    if not path.exists():
        return "?"
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("code") == code:
                return (r.get("ts") or r.get("date") or "?")[5:16].replace("-", "/")
    return "?"


def advice(code, pnl, pct, signals):
    s = " ".join(signals or [])
    if "超买" in s and "新高" in s and pnl > 0:
        return "🔴 止盈1/3(超买+新高+浮盈)"
    if "超买" in s and pnl > 0:
        return "🟡 减1/4(超买)"
    if pnl < 0 and pct <= -2.5:
        return "🟢 破位减半(设止损)"
    if pnl < 0:
        return "🟢 浮亏观察(守成本)"
    if "新高" in s and "放量" in s:
        return "🟠 新高放量·持有观察"
    return "✅ 持有"


def main():
    ap = argparse.ArgumentParser(description="组合持仓综合复盘表（建仓时间+信号+建议）")
    ap.add_argument("--account", default="main", help="组合账户名")
    ap.add_argument("--lens", default="", help="7维级别映射 code:label,code:label（可选）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    lens_map = {}
    for item in args.lens.split(","):
        if ":" in item:
            c, l = item.split(":", 1)
            lens_map[c.strip()] = l.strip()

    pf = run(["python3", PORTFOLIO, "--account", args.account, "show", "--json"])
    pos = pf["positions"]
    if isinstance(pos, dict):
        pos = [dict(code=k, **v) for k, v in pos.items()]

    sig_res = run(["python3", SIGNAL, "--portfolio", "--account", args.account, "--json"]).get("results", [])
    sig_map = {r["code"]: r.get("signals", []) for r in sig_res}

    rows = []
    for p in pos:
        code = p["code"]
        rows.append({
            "code": code,
            "name": p.get("name", code),
            "built": build_time(code, args.account),
            "lens": lens_map.get(code, "?"),
            "price": p.get("price", 0),
            "pnl": p.get("pnl", 0),
            "pnl_pct": p.get("pnl_pct", 0),
            "weight": p.get("mkt", 0) / pf.get("total_value", 1) * 100 if p.get("mkt") else 0,
            "signals": sig_map.get(code, []),
            "advice": advice(code, p.get("pnl", 0), p.get("pnl_pct", 0), sig_map.get(code, [])),
        })

    if args.json:
        print(json.dumps({"account": args.account, "total_value": pf.get("total_value"),
                          "rows": rows}, ensure_ascii=False, indent=2))
        return

    rows.sort(key=lambda r: r["built"])
    print(f"账户[{args.account}] 总市值 {pf.get('total_value',0):,.0f} ｜ {len(rows)} 只")
    print(f"{'代码':7s}{'名称':9s}{'建仓':12s}{'7维':7s}{'现价':>8s}{'浮盈':>9s}{'仓':>5s} 减仓建议")
    print("-" * 100)
    for r in rows:
        sig = f" [{'+'.join(r['signals'])}]" if r["signals"] else ""
        print(f"{r['code']:7s}{(r['name'] or '')[:8]:9s}{r['built']:12s}{r['lens']:7s}"
              f"{r['price']:>8.2f}{r['pnl']:>+9.0f}{r['weight']:>4.1f}% {r['advice']}{sig}")


if __name__ == "__main__":
    main()
