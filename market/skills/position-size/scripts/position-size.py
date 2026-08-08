#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
position-size: 仓位与风控计算（ATR 止损 + 固定比例/风险预算/凯利 仓位）。

用法:
  python3 position-size.py <代码> [--capital N] [--risk-pct N] [--atr-mult N]
                           [--method fixed|risk|kelly] [--fixed-pct N]
                           [--win-rate N] [--payoff N] [--target-price N]
                           [--allow-odd] [--json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import atr, fetch_kline  # noqa: E402

LOT = 100


def fmt_pct(v):
    return f"{v:+.2f}%"


def main():
    ap = argparse.ArgumentParser(description="仓位与风控计算")
    ap.add_argument("code", help="股票代码")
    ap.add_argument("--capital", type=float, default=100000.0, help="可用资金，默认 10 万")
    ap.add_argument("--risk-pct", type=float, default=2.0, help="单笔风险预算 %%，默认 2")
    ap.add_argument("--atr-mult", type=float, default=2.0, help="止损距离 = 倍数×ATR14，默认 2")
    ap.add_argument("--method", default="risk", choices=["fixed", "risk", "kelly"])
    ap.add_argument("--fixed-pct", type=float, default=0.20, help="fixed 法仓位比例，默认 0.2")
    ap.add_argument("--win-rate", type=float, default=0.5, help="凯利: 胜率")
    ap.add_argument("--payoff", type=float, default=2.0, help="凯利: 平均盈利/平均亏损")
    ap.add_argument("--target-price", type=float, help="目标止盈价（输出盈亏比）")
    ap.add_argument("--allow-odd", action="store_true", help="允许非 100 股整数倍（科创板等）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, points = fetch_kline(code, lmt=60)
    if not points:
        sys.exit(f"❌ 无法获取 {code} 日 K")
    price = points[-1]["close"]
    atr14 = atr(points, 14)
    if atr14 is None:
        sys.exit("❌ 数据不足，无法计算 ATR14")

    stop_dist = args.atr_mult * atr14
    stop_price = price - stop_dist
    risk_amt = args.capital * args.risk_pct / 100
    risk_pct_stop = stop_dist / price * 100

    # 股数计算
    capped = False
    if args.method == "fixed":
        budget = args.capital * args.fixed_pct
        shares_raw = budget / price
    elif args.method == "kelly":
        f = args.win_rate - (1 - args.win_rate) / args.payoff
        f = max(0.0, min(f, 1.0))
        budget = args.capital * f
        shares_raw = min(budget / price, risk_amt / stop_dist)
        capped = budget / price > risk_amt / stop_dist
    else:  # risk
        shares_raw = risk_amt / stop_dist

    shares = int(shares_raw)
    if not args.allow_odd:
        shares = (shares // LOT) * LOT
    position_value = shares * price
    position_pct = position_value / args.capital * 100
    actual_risk = shares * stop_dist
    if shares <= 0 and not args.allow_odd:
        print(f"⚠️  风险预算不足一整手（100 股）：理论 {shares_raw:.0f} 股。"
              f"可 --allow-odd 按 {int(shares_raw)} 股买入，或提高 --risk-pct / 降低 --atr-mult。")
        if not args.json:
            print(f"   按整手则无法建仓，输出理论股数供参考：{shares_raw:.0f} 股 ≈ {shares_raw * price:,.0f}（{shares_raw * price / args.capital * 100:.1f}% 资金）")
            return

    out = {
        "code": code, "name": name, "price": round(price, 2), "atr14": round(atr14, 2),
        "stop_price": round(stop_price, 2), "stop_pct": round(-risk_pct_stop, 2),
        "method": args.method, "shares": shares, "position_value": round(position_value, 2),
        "position_pct": round(position_pct, 2), "risk_amt": round(risk_amt, 2),
        "actual_risk": round(actual_risk, 2),
    }
    if args.target_price:
        rr = (args.target_price - price) / stop_dist
        out["target_price"] = args.target_price
        out["reward_risk"] = round(rr, 2)

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"{name} ({code}) ｜ 现价 {price:.2f} ｜ ATR14 {atr14:.2f}")
    print(f"建议止损价: {stop_price:.2f}（{fmt_pct(-risk_pct_stop)}，{args.atr_mult:.1f}×ATR）")
    print(f"风险预算: {risk_amt:,.2f}（资金 {args.risk_pct:.1f}%）")
    method_label = {"fixed": f"固定比例 {args.fixed_pct * 100:.0f}%", "risk": "风险预算", "kelly": f"凯利(w={args.win_rate},b={args.payoff})"}[args.method]
    print(f"{method_label}仓位: {shares} 股 ≈ {position_value:,.2f}（{position_pct:.1f}% 资金）｜ 实际单笔风险 {actual_risk:,.2f}")
    if args.target_price:
        print(f"止盈目标 {args.target_price} → 盈亏比 {out['reward_risk']:.2f}")
    if args.method == "kelly" and capped:
        print("（凯利仓位已按风险预算封顶）")


if __name__ == "__main__":
    main()
