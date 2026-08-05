#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trade-journal: 纸面交易复盘（list / review / note / clear）。

数据来自 shared/paper/trades.csv + portfolio.json（portfolio 技能写入）。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from paper import (  # noqa: E402
    TRADES_FILE, load_portfolio, load_trades, save_portfolio,
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


def do_list(args):
    trades = load_trades()
    if not trades:
        print("暂无交易流水（先用 portfolio buy/sell 记账）")
        return
    shown = trades if args.all else [t for t in trades if t.get("side") == "sell"]
    shown = shown[::-1]  # 最新在前
    if args.all:
        print(f"全部流水（共 {len(trades)} 笔，最新在前）:")
    else:
        print(f"卖出/已实现盈亏（共 {len(shown)} 笔，最新在前；--all 显示全部）:")
    header = pad("日期", 12) + pad("方向", 6) + pad("代码", 8) + pad("名称", 16) \
        + pad("数量", 8, "right") + pad("价格", 10, "right") + pad("金额", 12, "right") \
        + pad("已实现", 10, "right") + " 备注"
    print(header)
    print("-" * display_width(header))
    for t in shown:
        rp = t.get("realized_pnl")
        rp_str = fmt_money(float(rp)) if rp not in ("", None) else "--"
        side = "买入" if t.get("side") == "buy" else "卖出"
        print(pad(t.get("date", ""), 12) + pad(side, 6) + pad(t.get("code", ""), 8)
              + pad(t.get("name", ""), 16) + pad(str(t.get("qty", "")), 8, "right")
              + pad(str(t.get("price", "")), 10, "right") + pad(str(t.get("amount", "")), 12, "right")
              + pad(rp_str, 10, "right") + " " + str(t.get("note", "")))


def do_review(args):
    trades = load_trades()
    pf = load_portfolio()
    sells = [t for t in trades if t.get("side") == "sell"]
    realized = [float(t.get("realized_pnl") or 0) for t in sells]
    wins = [v for v in realized if v > 0]
    losses = [v for v in realized if v < 0]

    stats = {
        "total_trades": len(trades),
        "buys": len([t for t in trades if t.get("side") == "buy"]),
        "sells": len(sells),
        "realized_pnl": round(sum(realized), 2),
        "win_rate": round(len(wins) / len(sells) * 100, 2) if sells else None,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) else None,
        "largest_win": round(max(wins), 2) if wins else None,
        "largest_loss": round(min(losses), 2) if losses else None,
        "open_positions": len(pf.get("positions", {})),
    }
    # 持仓天数（同一代码按时间配对）
    holds = []
    for code in sorted(set(t.get("code") for t in trades)):
        bt = [t for t in trades if t.get("code") == code and t.get("side") == "buy"]
        st = [t for t in trades if t.get("code") == code and t.get("side") == "sell"]
        bt.sort(key=lambda t: t.get("date", ""))
        st.sort(key=lambda t: t.get("date", ""))
        for b, s in zip(bt, st):
            try:
                d0 = datetime.strptime(b["date"], "%Y-%m-%d")
                d1 = datetime.strptime(s["date"], "%Y-%m-%d")
                holds.append((d1 - d0).days)
            except (ValueError, KeyError):
                continue
    stats["avg_holding_days"] = round(sum(holds) / len(holds), 1) if holds else None

    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    def _v(x, suffix=""):
        return f"{x}{suffix}" if x is not None else "--"

    print(f"交易复盘（流水 {stats['total_trades']} 笔：买入 {stats['buys']} / 卖出 {stats['sells']}）")
    print(f"已实现盈亏: {fmt_money(stats['realized_pnl'])}")
    print(f"胜率: {_v(stats['win_rate'], '%')} ｜ 平均盈利 {_v(stats['avg_win'])} ｜ 平均亏损 {_v(stats['avg_loss'])}")
    print(f"盈亏比: {_v(stats['profit_factor'])} ｜ 最大单笔盈利 {_v(stats['largest_win'])} ｜ 最大单笔亏损 {_v(stats['largest_loss'])}")
    print(f"平均持仓 {_v(stats['avg_holding_days'], ' 天')} ｜ 当前持仓 {stats['open_positions']} 个")


def do_note(args):
    pf = load_portfolio()
    code = str(args.code).zfill(6)
    if code not in pf.get("positions", {}):
        sys.exit(f"❌ 无 {code} 持仓（备注仅限当前持仓）")
    pf["positions"][code]["note"] = args.note
    save_portfolio(pf)
    print(f"✅ 已为 {code} 添加备注: {args.note}")


def do_clear(args):
    if not args.force:
        sys.exit("❌ 确认清空请加 --force")
    if TRADES_FILE.exists():
        TRADES_FILE.unlink()
    pf = load_portfolio()
    pf["positions"] = {}
    save_portfolio(pf)
    print("✅ 已清空交易流水与持仓")


def main():
    ap = argparse.ArgumentParser(description="纸面交易复盘")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="交易流水")
    p_list.add_argument("--all", action="store_true", help="显示全部（含买入）")
    p_list.set_defaults(func=do_list)

    p_rev = sub.add_parser("review", help="复盘统计")
    p_rev.add_argument("--json", action="store_true")
    p_rev.set_defaults(func=do_review)

    p_note = sub.add_parser("note", help="给持仓加备注")
    p_note.add_argument("code"); p_note.add_argument("note")
    p_note.set_defaults(func=do_note)

    p_clr = sub.add_parser("clear", help="清空流水与持仓")
    p_clr.add_argument("--force", action="store_true")
    p_clr.set_defaults(func=do_clear)

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
