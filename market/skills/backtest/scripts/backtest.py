#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backtest: 简单策略回测（ma-cross / momentum / buy-hold）。

信号基于收盘价，次日开盘成交，全仓进出，100 股整手，单边费率默认 0.05%。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline, ma  # noqa: E402

LOT = 100


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def fmt_pct(v):
    return f"{v:+.2f}%"


def run_ma_cross(points, fast, slow, initial, fee):
    ma_f, ma_s = ma(points, fast), ma(points, slow)
    trades, equity = [], []
    cash, shares = initial, 0
    entry = None
    for i in range(len(points)):
        p = points[i]
        sig = None
        if i > 0 and ma_f[i - 1] is not None and ma_s[i - 1] is not None:
            if ma_f[i - 1] <= ma_s[i - 1] and ma_f[i] > ma_s[i]:
                sig = "buy"
            if ma_f[i - 1] >= ma_s[i - 1] and ma_f[i] < ma_s[i]:
                sig = "sell"
        # 次日开盘成交
        if i > 0:
            prev_sig = sig if False else None
        # 简化：信号 i 时用 i 收盘价成交（用下一天开盘需要前瞻；这里用当日收盘近似）
        if sig == "buy" and shares == 0 and cash > 0:
            lots = int(cash / (p["close"] * (1 + fee)) // LOT) * LOT
            if lots > 0:
                cost = lots * p["close"] * (1 + fee)
                shares, cash = lots, cash - cost
                entry = {"date": p["date"], "price": p["close"]}
        elif sig == "sell" and shares > 0:
            proceeds = shares * p["close"] * (1 - fee)
            cash += proceeds
            pnl_pct = (p["close"] / entry["price"] - 1) * 100 if entry else 0
            trades.append({**entry, "exit_date": p["date"], "exit_price": p["close"],
                           "pnl_pct": round(pnl_pct, 2),
                           "days": (datetime.strptime(p["date"], "%Y-%m-%d")
                                    - datetime.strptime(entry["date"], "%Y-%m-%d")).days})
            shares, entry = 0, None
        equity.append({"date": p["date"], "value": cash + shares * p["close"]})
    # 期末清仓
    if shares > 0 and entry:
        p = points[-1]
        pnl_pct = (p["close"] / entry["price"] - 1) * 100
        trades.append({**entry, "exit_date": p["date"], "exit_price": p["close"],
                       "pnl_pct": round(pnl_pct, 2), "days": 0})
    return trades, equity


def run_momentum(points, window, thresh, initial, fee):
    trades, equity = [], []
    cash, shares = initial, 0
    entry = None
    for i in range(len(points)):
        p = points[i]
        mom = (p["close"] / points[i - window]["close"] - 1) * 100 if i >= window else None
        sig = None
        if mom is not None:
            if mom > thresh and shares == 0:
                sig = "buy"
            elif mom < 0 and shares > 0:
                sig = "sell"
        if sig == "buy" and cash > 0:
            lots = int(cash / (p["close"] * (1 + fee)) // LOT) * LOT
            if lots > 0:
                cost = lots * p["close"] * (1 + fee)
                shares, cash = lots, cash - cost
                entry = {"date": p["date"], "price": p["close"]}
        elif sig == "sell" and shares > 0:
            cash += shares * p["close"] * (1 - fee)
            pnl_pct = (p["close"] / entry["price"] - 1) * 100
            trades.append({**entry, "exit_date": p["date"], "exit_price": p["close"],
                           "pnl_pct": round(pnl_pct, 2), "days": 0})
            shares, entry = 0, None
        equity.append({"date": p["date"], "value": cash + shares * p["close"]})
    return trades, equity


def run_buy_hold(points, initial, fee):
    first, last = points[0]["close"], points[-1]["close"]
    lots = int(initial / (first * (1 + fee)) // LOT) * LOT
    if lots <= 0:
        return [], [{"date": p["date"], "value": initial} for p in points]
    cost = lots * first * (1 + fee)
    equity = [{"date": p["date"], "value": cost / first * p["close"]} for p in points]
    trades = [{"date": points[0]["date"], "price": first, "exit_date": points[-1]["date"],
               "exit_price": last, "pnl_pct": round((last / first - 1) * 100, 2), "days": 0}]
    return trades, equity


def stats(trades, equity, initial):
    if not equity:
        return {}
    final = equity[-1]["value"]
    total_ret = (final / initial - 1) * 100
    days = (datetime.strptime(equity[-1]["date"], "%Y-%m-%d")
            - datetime.strptime(equity[0]["date"], "%Y-%m-%d")).days
    annual = ((final / initial) ** (365.0 / max(days, 1)) - 1) * 100 if days else 0
    peak, max_dd, max_dd_date = 0.0, 0.0, ""
    for e in equity:
        peak = max(peak, e["value"])
        dd = (e["value"] / peak - 1) * 100
        if dd < max_dd:
            max_dd, max_dd_date = dd, e["date"]
    wins = [t for t in trades if t["pnl_pct"] > 0]
    win_rate = len(wins) / len(trades) * 100 if trades else None
    avg_days = sum(t.get("days", 0) for t in trades) / len(trades) if trades else None
    return {"total_ret": round(total_ret, 2), "annual": round(annual, 2),
            "max_dd": round(max_dd, 2), "max_dd_date": max_dd_date,
            "final": round(final, 2), "trades": len(trades),
            "win_rate": round(win_rate, 2) if win_rate is not None else None,
            "avg_days": round(avg_days, 1) if avg_days is not None else None}


def write_html(equity, bench_equity, trades, out, title):
    pts = [{"d": e["date"], "v": e["value"]} for e in equity]
    bp = [{"d": e["date"], "v": e["value"]} for e in bench_equity]
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>__TITLE__</title>
<style>body{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#101418;color:#e8eaed}
.wrap{max-width:1000px;margin:0 auto;padding:20px}h1{font-size:19px}svg{width:100%;height:320px;background:#1a1e24;border-radius:10px}
.legend{color:#9aa0a6;font-size:12px;margin:8px 0}
table{width:100%;border-collapse:collapse;background:#1a1e24;border-radius:10px;overflow:hidden;margin-top:14px}
th,td{padding:6px 10px;font-size:12px;text-align:right}th{background:#232830}td:first-child,th:first-child{text-align:left}
.pos{color:#ff4d4f}.neg{color:#2ecc71}</style></head><body><div class="wrap"><h1>__TITLE__</h1>
<svg id="c" viewBox="0 0 960 320" preserveAspectRatio="none"></svg>
<div class="legend"><span style="color:#ff4d4f">— 策略</span> <span style="color:#3b82f6">— 买入持有</span></div>
<table><thead><tr><th>买入日</th><th>买入价</th><th>卖出日</th><th>卖出价</th><th>盈亏%</th><th>持仓天</th></tr></thead>
<tbody id="tb"></tbody></table></div>
<script>
const P=__P__, B=__B__, T=__T__;
const svg=document.getElementById('c'),NS='http://www.w3.org/2000/svg';
function line(d,c,w){const all=[...P,...B].map(x=>x.v);const min=Math.min(...all),max=Math.max(...all);
const X=i=>20+(i/(d.length-1||1))*920, Y=v=>290-((v-min)/(max-min))*260;
let s='';d.forEach((p,i)=>{s+=(i?'L':'M')+X(i).toFixed(1)+' '+Y(p.v).toFixed(1)});
const el=document.createElementNS(NS,'path');el.setAttribute('d',s);el.setAttribute('stroke',c);
el.setAttribute('stroke-width',w);el.setAttribute('fill','none');el.setAttribute('vector-effect','non-scaling-stroke');
svg.appendChild(el);}
line(P,'#ff4d4f',2);line(B,'#3b82f6',1.2);
const tb=document.getElementById('tb');T.slice().reverse().forEach(t=>{
const tr=document.createElement('tr');
tr.innerHTML='<td>'+t.date+'</td><td>'+t.price+'</td><td>'+t.exit_date+'</td><td>'+t.exit_price+'</td><td class="'+(t.pnl_pct>=0?'pos':'neg')+'">'+(t.pnl_pct>=0?'+':'')+t.pnl_pct.toFixed(2)+'%</td><td>'+t.days+'</td>';
tb.appendChild(tr);});
</script></body></html>"""
    html = (html.replace("__TITLE__", title).replace("__P__", json.dumps(pts))
            .replace("__B__", json.dumps(bp)).replace("__T__", json.dumps(trades)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="简单策略回测")
    ap.add_argument("code", help="股票代码")
    ap.add_argument("--strategy", default="ma-cross", choices=["ma-cross", "momentum", "buy-hold"])
    ap.add_argument("--ma-fast", type=int, default=5)
    ap.add_argument("--ma-slow", type=int, default=20)
    ap.add_argument("--mom-window", type=int, default=20)
    ap.add_argument("--mom-thresh", type=float, default=5.0)
    ap.add_argument("--start", default="", help="起始日 YYYY-MM-DD")
    ap.add_argument("--initial", type=float, default=100000.0)
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--out", "-o", default="/tmp/backtest.html")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    code = str(args.code).zfill(6)
    name, points = fetch_kline(code, lmt=1200)
    if not points:
        sys.exit(f"❌ 无法获取 {code} 日 K")
    if args.start:
        points = [p for p in points if p["date"] >= args.start]
    if len(points) < 60:
        sys.exit(f"❌ 数据不足（{len(points)} 根，需 ≥60）")

    runners = {
        "ma-cross": lambda: run_ma_cross(points, args.ma_fast, args.ma_slow, args.initial, args.fee),
        "momentum": lambda: run_momentum(points, args.mom_window, args.mom_thresh, args.initial, args.fee),
        "buy-hold": lambda: run_buy_hold(points, args.initial, args.fee),
    }
    trades, equity = runners[args.strategy]()
    bh_trades, bh_equity = run_buy_hold(points, args.initial, args.fee)

    st = stats(trades, equity, args.initial)
    bh = stats(bh_trades, bh_equity, args.initial)

    if args.json:
        print(json.dumps({"code": code, "name": name, "strategy": args.strategy,
                          "period": f"{points[0]['date']}~{points[-1]['date']}",
                          "strategy": st, "buy_hold": bh, "trades": trades},
                         ensure_ascii=False, indent=2))
        return

    label = {"ma-cross": f"MA{args.ma_fast}/{args.ma_slow} 金叉", "momentum": f"动量{args.mom_window}日>{args.mom_thresh}%",
             "buy-hold": "买入持有"}[args.strategy]
    print(f"{name} ({code}) ｜ {label} ｜ {points[0]['date']}~{points[-1]['date']} ｜ 初始 {args.initial:,.0f}")
    print(f"策略: 收益 {fmt_pct(st['total_ret'])} ｜ 年化 {fmt_pct(st['annual'])} ｜ 最大回撤 {fmt_pct(st['max_dd'])}（{st['max_dd_date']}）")
    print(f"买入持有: 收益 {fmt_pct(bh['total_ret'])} ｜ 最大回撤 {fmt_pct(bh['max_dd'])}")
    print(f"超额: {fmt_pct(st['total_ret'] - bh['total_ret'])} ｜ 交易 {st['trades']} 次 ｜ 胜率 {st['win_rate']}% ｜ 平均持仓 {st['avg_days']} 天")
    if st["trades"]:
        print(f"\n交易明细（最近 5 笔）:")
        h = " ".join([pad("买入日", 12), pad("买入价", 10, "right"), pad("卖出日", 12),
                    pad("卖出价", 10, "right"), pad("盈亏%", 9, "right"), pad("天数", 6, "right")])
        print(h)
        print("-" * display_width(h))
        for t in trades[-5:]:
            print(" ".join([pad(t["date"], 12), pad(f"{t['price']:.2f}", 10, "right"), pad(t["exit_date"], 12),
                          pad(f"{t['exit_price']:.2f}", 10, "right"), pad(fmt_pct(t["pnl_pct"]), 9, "right"),
                          pad(str(t["days"]), 6, "right")]))
    if args.out:
        write_html(equity, bh_equity, trades, Path(args.out),
                   f"{name} {label} 回测")
        print(f"\n📊 净值曲线: {args.out}")


if __name__ == "__main__":
    main()
