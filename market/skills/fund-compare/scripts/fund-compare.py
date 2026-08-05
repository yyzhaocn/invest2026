#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund-compare: 多基金横向对比（收益/回撤/波动/规模/经理 + 重仓重叠矩阵）。

用法:
  python3 fund-compare.py <代码1> <代码2> [...N] [--holdings-top 15] [--json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from fund import annualized_vol, fetch_fund, fetch_holdings, max_drawdown, period_returns  # noqa: E402


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


def main():
    ap = argparse.ArgumentParser(description="多基金对比")
    ap.add_argument("codes", nargs="+", help="基金代码（至少 2 个）")
    ap.add_argument("--holdings-top", type=int, default=15, help="重叠矩阵每只基金前 N 大重仓，0=关闭")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if len(args.codes) < 2:
        sys.exit("❌ 至少需要 2 个基金代码")

    funds = []
    for code in args.codes:
        f = fetch_fund(str(code).zfill(6))
        if not f:
            sys.exit(f"❌ 无法获取基金 {code} 数据")
        pr = period_returns(f["points"])
        f["periods"] = pr
        f["maxdd"] = max_drawdown(f["points"], 250)
        f["vol"] = annualized_vol(f["points"], 250)
        funds.append(f)

    asof = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for f in funds:
        last = f["points"][-1]
        rows.append({
            "code": f["code"], "name": f["name"], "nav": last["nav"], "date": last["date"],
            "periods": f["periods"], "maxdd": round(f["maxdd"], 2),
            "vol": round(f["vol"], 2) if f["vol"] else None,
            "scale": f["scale"], "manager": f["manager"],
        })

    # 重仓重叠
    overlap = None
    if args.holdings_top > 0:
        holdings = []
        for f in funds:
            h = fetch_holdings(f["code"])
            top = sorted(h, key=lambda x: float(x.get("netasset_ratio") or 0), reverse=True)[:args.holdings_top]
            holdings.append({str(x.get("stock_code", "")).zfill(6): {
                "name": x.get("stock_name", ""),
                "ratio": float(x.get("netasset_ratio") or 0),
            } for x in top})
        # 并集：至少出现在 2 只基金中
        from collections import Counter
        cnt = Counter()
        for h in holdings:
            cnt.update(h.keys())
        union = sorted([c for c, n in cnt.items() if n >= 2],
                       key=lambda c: -sum(h[c]["ratio"] for h in holdings if c in h))
        overlap = {"funds": [f["code"] for f in funds], "stocks": []}
        for c in union:
            overlap["stocks"].append({"code": c, "name": holdings[0].get(c, {}).get("name", ""),
                                      "ratios": [round(h.get(c, {}).get("ratio", 0), 2) for h in holdings]})

    if args.json:
        print(json.dumps({"asof": asof, "funds": rows, "overlap": overlap},
                         ensure_ascii=False, indent=2))
        return

    print(f"基金对比（{asof}）:")
    header = (pad("代码", 8) + pad("名称", 22) + " " + pad("净值", 8, "right") + pad("1月", 9, "right")
              + pad("3月", 9, "right") + pad("6月", 9, "right") + pad("1年", 9, "right")
              + pad("回撤", 9, "right") + pad("波动", 8, "right") + pad("规模亿", 8, "right") + " 经理")
    print(header)
    print("-" * display_width(header))
    for r in rows:
        nm = r["name"]
        if display_width(nm) > 22:
            nm = nm[:10] + ".."
        pr = r["periods"]
        scale_str = f"{r['scale']:.1f}" if r["scale"] else "--"
        print(pad(r["code"], 8) + pad(nm, 22) + " " + pad(f"{r['nav']:.4f}", 8, "right")
              + pad(fmt_pct(pr.get("1月")), 9, "right") + pad(fmt_pct(pr.get("3月")), 9, "right")
              + pad(fmt_pct(pr.get("6月")), 9, "right") + pad(fmt_pct(pr.get("1年")), 9, "right")
              + pad(fmt_pct(r["maxdd"]), 9, "right") + pad(fmt_pct(r["vol"]), 8, "right")
              + pad(scale_str, 8, "right") + " " + str(r["manager"]))

    if overlap:
        print(f"\n重仓股重叠（{len(overlap['funds'])} 只基金前 {args.holdings_top} 大重仓并集中重叠 {len(overlap['stocks'])} 只，按合计占比排序）:")
        h = pad("代码", 8) + pad("名称", 16)
        for c in overlap["funds"]:
            h += pad(c, 9, "right")
        print(h)
        print("-" * display_width(h))
        for s in overlap["stocks"][:15]:
            line = pad(s["code"], 8) + pad(s["name"], 16)
            for r in s["ratios"]:
                line += pad(f"{r:.1f}" if r > 0 else "--", 9, "right")
            print(line)


if __name__ == "__main__":
    main()
