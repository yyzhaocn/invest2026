#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
portfolio: 纸面交易组合管理（init / buy / sell / add-cash / show）。

用法:
  python3 portfolio.py init [--cash N] [--force]
  python3 portfolio.py buy <code> <qty> [--price P] [--note TEXT] [--allow-odd]
  python3 portfolio.py sell <code> <qty> [--price P] [--note TEXT]
  python3 portfolio.py add-cash <amount>
  python3 portfolio.py show [--json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from paper import (  # noqa: E402
    append_trade, get_price, load_portfolio, load_trades, save_portfolio,
)


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def fmt_money(v):
    return f"{v:,.2f}"


def fmt_pct(v):
    return f"{v:+.2f}%"


def do_init(args):
    from paper import init_portfolio
    pf = init_portfolio(args.cash, force=args.force)
    print(f"✅ 组合已初始化：初始资金 {pf['base_capital']:,.2f}（{pf['created']}）")
    print("买入示例: portfolio.py buy 600600 100 --note 理由")


def do_buy(args):
    pf = load_portfolio()
    code = str(args.code).zfill(6)
    qty = int(args.qty)
    if qty <= 0:
        sys.exit("❌ 数量必须为正")

    price, name, kind, extra = get_price(code)
    if price is None:
        if args.price is None:
            sys.exit(f"❌ 无行情且未指定 --price（{extra.get('error', '')}）")
        price, name = float(args.price), (extra.get("name") or code)
    elif args.price is not None:
        price = float(args.price)

    if kind == "stock" and qty % 100 != 0 and not args.allow_odd:
        sys.exit(f"❌ A 股数量须为 100 的整数倍（收到 {qty}）；确认用 --allow-odd")
    amount = round(price * qty, 2)
    if amount > pf["cash"]:
        sys.exit(f"❌ 现金不足：需 {fmt_money(amount)}，现有 {fmt_money(pf['cash'])}")

    pos = pf["positions"].get(code)
    if pos:
        total_qty = pos["qty"] + qty
        pos["avg_cost"] = round((pos["avg_cost"] * pos["qty"] + amount) / total_qty, 4)
        pos["qty"] = total_qty
    else:
        pf["positions"][code] = {"name": name, "kind": kind, "qty": qty,
                                 "avg_cost": round(price, 4), "buy_date": datetime.now().strftime("%Y-%m-%d")}
    pf["cash"] = round(pf["cash"] - amount, 2)
    save_portfolio(pf)
    append_trade({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "date": datetime.now().strftime("%Y-%m-%d"),
                  "side": "buy", "code": code, "name": name, "kind": kind, "qty": qty,
                  "price": round(price, 4), "amount": amount, "note": args.note or "", "realized_pnl": ""})
    print(f"✅ 买入 {name} ({code}) {qty} 股 @ {price:.4f} = {fmt_money(amount)}")
    print(f"   现金剩余 {fmt_money(pf['cash'])}；持仓均价 {pf['positions'][code]['avg_cost']:.4f}")
    if kind == "fund":
        print(f"   （按 {extra.get('nav_date', '')} 净值成交）")


def do_sell(args):
    pf = load_portfolio()
    code = str(args.code).zfill(6)
    qty = int(args.qty)
    pos = pf["positions"].get(code)
    if not pos:
        sys.exit(f"❌ 无 {code} 持仓")
    if qty <= 0 or qty > pos["qty"]:
        sys.exit(f"❌ 数量非法：持仓 {pos['qty']} 股")

    price, name, kind, extra = get_price(code)
    if price is None:
        if args.price is None:
            sys.exit(f"❌ 无行情且未指定 --price")
        price = float(args.price)
    elif args.price is not None:
        price = float(args.price)

    amount = round(price * qty, 2)
    realized = round((price - pos["avg_cost"]) * qty, 2)
    pos["qty"] -= qty
    pf["cash"] = round(pf["cash"] + amount, 2)
    if pos["qty"] == 0:
        del pf["positions"][code]
    save_portfolio(pf)
    append_trade({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "date": datetime.now().strftime("%Y-%m-%d"),
                  "side": "sell", "code": code, "name": name, "kind": kind, "qty": qty,
                  "price": round(price, 4), "amount": amount, "note": args.note or "",
                  "realized_pnl": round(realized, 2)})
    print(f"✅ 卖出 {name} ({code}) {qty} 股 @ {price:.4f} = {fmt_money(amount)}")
    print(f"   已实现盈亏 {fmt_pct(realized)}（{fmt_money(realized)}）；现金 {fmt_money(pf['cash'])}")


def do_add_cash(args):
    pf = load_portfolio()
    pf["cash"] = round(pf["cash"] + args.amount, 2)
    save_portfolio(pf)
    print(f"✅ {'入金' if args.amount >= 0 else '出金'} {fmt_money(abs(args.amount))}，现金 {fmt_money(pf['cash'])}")


def do_show(args):
    pf = load_portfolio()
    positions = pf.get("positions", {})
    if not positions:
        print(f"💰 空仓 ｜ 现金 {fmt_money(pf['cash'])}（初始 {fmt_money(pf['base_capital'])}）")
        print("  买入示例: portfolio.py buy 600600 100 --note 理由")
        return

    from paper import batch_quotes, get_fund_nav
    stock_codes = [c for c, p in positions.items() if p["kind"] == "stock"]
    quotes = batch_quotes(stock_codes)
    rows = []
    mkt_total = 0.0
    for code, pos in positions.items():
        if pos["kind"] == "fund":
            nav, name, nav_date = get_fund_nav(code)
            if nav is None:
                nav, day_pct = pos["avg_cost"], 0.0
            else:
                day_pct = 0.0  # 基金按日净值，当日涨跌暂不展示
            price = nav
            name = name or pos.get("name", code)
        else:
            q = quotes.get(code)
            if q:
                price, name, day_pct = q["price"], q["name"], q["pct"]
            else:
                price, name, day_pct = pos["avg_cost"], pos.get("name", code), 0.0
        mkt = round(price * pos["qty"], 2)
        cost = round(pos["avg_cost"] * pos["qty"], 2)
        pnl = round(mkt - cost, 2)
        pnl_pct = (pnl / cost * 100) if cost else 0.0
        mkt_total += mkt
        rows.append({"code": code, "name": name, "kind": pos["kind"], "qty": pos["qty"],
                     "cost": pos["avg_cost"], "price": price, "mkt": mkt, "pnl": pnl,
                     "pnl_pct": pnl_pct, "day_pct": day_pct})

    total = pf["cash"] + mkt_total
    total_pnl = total - pf["base_capital"]
    total_pct = (total_pnl / pf["base_capital"] * 100) if pf["base_capital"] else 0.0
    day_pnl = sum(r["mkt"] * (r["day_pct"] / 100) for r in rows)

    if args.json:
        print(json.dumps({"base_capital": pf["base_capital"], "cash": pf["cash"],
                          "market_value": round(mkt_total, 2), "total_value": round(total, 2),
                          "total_pnl": round(total_pnl, 2), "total_pct": round(total_pct, 4),
                          "day_pnl": round(day_pnl, 2), "positions": rows}, ensure_ascii=False, indent=2))
        return

    print(f"现金 {fmt_money(pf['cash'])} ｜ 持仓市值 {fmt_money(mkt_total)} ｜ 总市值 {fmt_money(total)}")
    print(f"总盈亏 {fmt_pct(total_pct)}（{fmt_money(total_pnl)}）｜ 当日浮动 {fmt_money(day_pnl)}")
    print()
    header = (pad("代码", 8) + pad("名称", 22) + " " + pad("类型", 6) + pad("数量", 8, "right")
              + pad("成本", 10, "right") + pad("现价", 10, "right") + pad("市值", 12, "right")
              + pad("浮动盈亏", 12, "right") + pad("盈亏%", 10, "right") + pad("仓位%", 8, "right"))
    print(header)
    print("-" * display_width(header))
    for r in rows:
        weight = (r["mkt"] / total * 100) if total else 0
        nm = r["name"]
        if display_width(nm) > 22:
            nm = nm[:10] + ".."
        print(pad(r["code"], 8) + pad(nm, 22) + " " + pad(r["kind"], 6)
              + pad(str(r["qty"]), 8, "right") + pad(f"{r['cost']:.4f}", 10, "right")
              + pad(f"{r['price']:.2f}", 10, "right") + pad(fmt_money(r["mkt"]), 12, "right")
              + pad(fmt_money(r["pnl"]), 12, "right") + pad(fmt_pct(r["pnl_pct"]), 10, "right")
              + pad(f"{weight:.1f}", 8, "right"))
    print("-" * display_width(header))
    print(f"合计持仓 {len(rows)} 个 ｜ 交易流水 {len(load_trades())} 笔（trade-journal 查看复盘）")


def main():
    ap = argparse.ArgumentParser(description="纸面交易组合管理")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="初始化组合")
    p_init.add_argument("--cash", type=float, default=100000.0, help="初始资金，默认 10 万")
    p_init.add_argument("--force", action="store_true", help="已存在时重置")
    p_init.set_defaults(func=do_init)

    p_buy = sub.add_parser("buy", help="买入")
    p_buy.add_argument("code"); p_buy.add_argument("qty")
    p_buy.add_argument("--price", type=float, help="成交价（默认实时行情/最新净值）")
    p_buy.add_argument("--note", help="买入理由")
    p_buy.add_argument("--allow-odd", action="store_true", help="允许非整手数量")
    p_buy.set_defaults(func=do_buy)

    p_sell = sub.add_parser("sell", help="卖出")
    p_sell.add_argument("code"); p_sell.add_argument("qty")
    p_sell.add_argument("--price", type=float, help="成交价（默认实时行情/最新净值）")
    p_sell.add_argument("--note", help="卖出理由")
    p_sell.set_defaults(func=do_sell)

    p_cash = sub.add_parser("add-cash", help="入金/出金")
    p_cash.add_argument("amount", type=float, help="金额（正数入金，负数出金）")
    p_cash.set_defaults(func=do_add_cash)

    p_show = sub.add_parser("show", help="查看持仓")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=do_show)

    args = ap.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
