#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
performance: 纸面交易组合绩效（snapshot / report / list）。

- snapshot: 记录今日组合净值（幂等）
- report: 终端摘要 + 自包含 HTML 净值曲线（含沪深300 基准）
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from paper import (  # noqa: E402
    batch_quotes, get_fund_nav, load_portfolio, load_snapshots, record_snapshot,
)

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}


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


def current_value():
    """组合当前总市值、现金、持仓市值。"""
    pf = load_portfolio()
    positions = pf.get("positions", {})
    mkt_total = 0.0
    stock_codes = [c for c, p in positions.items() if p["kind"] == "stock"]
    quotes = batch_quotes(stock_codes)
    for code, pos in positions.items():
        if pos["kind"] == "fund":
            nav, _, _ = get_fund_nav(code)
            price = nav if nav is not None else pos["avg_cost"]
        else:
            q = quotes.get(code)
            price = q["price"] if q else pos["avg_cost"]
        mkt_total += price * pos["qty"]
    total = pf["cash"] + mkt_total
    return total, pf["cash"], mkt_total


def do_snapshot(args):
    total, cash, mkt = current_value()
    base = load_portfolio()["base_capital"]
    total_pnl = total - base
    prev = load_snapshots()
    day_pnl = None
    if prev:
        day_pnl = total - float(prev[-1]["total_value"])
    row = record_snapshot(total, cash, mkt, total_pnl, day_pnl=day_pnl)
    print(f"✅ 快照已记录 {row['date']}: 总市值 {fmt_money(row['total_value'])}"
          f" ｜ 当日 {fmt_pct(row['day_pct'])} ｜ 累计 {fmt_pct(row['total_pct'])}")


def fetch_benchmark():
    """沪深300 日 K（收盘指数），返回 {date: close}。失败返回 None。"""
    from httpget import httpget
    try:
        resp = httpget("https://push2his.eastmoney.com/api/qt/stock/kline/get",
                            params={"secid": "1.000300", "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                                    "fields1": "f1,f2,f3,f4,f5,f6",
                                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                                    "klt": "101", "fqt": "1", "beg": "0", "end": "20500101", "lmt": "500"},
                            timeout=15, headers=UA)
        resp.raise_for_status()
        klines = (resp.json().get("data") or {}).get("klines") or []
        return {k.split(",")[0]: float(k.split(",")[2]) for k in klines if len(k.split(",")) >= 3}
    except Exception:
        return None


def do_list(args):
    rows = load_snapshots()
    if not rows:
        print("暂无快照（先运行 performance snapshot）")
        return
    print(f"组合净值快照（共 {len(rows)} 天）:")
    header = pad("日期", 12) + pad("总市值", 12, "right") + pad("当日", 10, "right") \
        + pad("累计", 10, "right") + pad("最大回撤", 10, "right")
    print(header)
    print("-" * display_width(header))
    peak = 0.0
    for r in rows:
        total = float(r["total_value"])
        peak = max(peak, total)
        dd = (total / peak - 1) * 100
        print(pad(r["date"], 12) + pad(fmt_money(total), 12, "right")
              + pad(fmt_pct(float(r["day_pct"])), 10, "right")
              + pad(fmt_pct(float(r["total_pct"])), 10, "right")
              + pad(fmt_pct(dd), 10, "right"))


def do_report(args):
    rows = load_snapshots()
    if not rows:
        print("❌ 暂无快照（先运行 performance snapshot）", file=sys.stderr)
        sys.exit(1)
    if args.days > 0:
        rows = rows[-args.days:]

    start_val, end_val = float(rows[0]["total_value"]), float(rows[-1]["total_value"])
    total_ret = (end_val / start_val - 1) * 100
    peak = 0.0
    max_dd, max_dd_date = 0.0, ""
    for r in rows:
        v = float(r["total_value"])
        peak = max(peak, v)
        dd = (v / peak - 1) * 100
        if dd < max_dd:
            max_dd, max_dd_date = dd, r["date"]
    days = len(rows)
    avg_day = sum(float(r["day_pct"]) for r in rows) / days if days else 0.0

    # 基准
    bench = None
    if not args.no_benchmark:
        bench = fetch_benchmark()
    bench_ret = None
    if bench:
        s, e = rows[0]["date"], rows[-1]["date"]
        s_close = bench.get(s)
        # 对齐：取 <= 快照日期最近的一天
        dates = sorted(bench.keys())
        import bisect
        i = bisect.bisect_right(dates, s) - 1
        j = bisect.bisect_right(dates, e) - 1
        if i >= 0 and j > i:
            bench_ret = (bench[dates[j]] / bench[dates[i]] - 1) * 100

    print(f"组合绩效报告（{rows[0]['date']} ~ {rows[-1]['date']}，{days} 个快照）")
    print(f"区间收益: {fmt_pct(total_ret)} ｜ 最大回撤: {fmt_pct(max_dd)}（{max_dd_date}）")
    print(f"日均涨跌: {fmt_pct(avg_day)} ｜ 期末总市值: {fmt_money(end_val)}")
    if bench_ret is not None:
        diff = total_ret - bench_ret
        print(f"沪深300 同期: {fmt_pct(bench_ret)} ｜ 超额: {fmt_pct(diff)}")
    out = Path(args.out)
    _write_html(rows, bench, out, total_ret, max_dd, bench_ret)
    print(f"📊 净值曲线已生成: {out}（open {out}）")


def _write_html(rows, bench, out, total_ret, max_dd, bench_ret):
    pts = [{"d": r["date"], "v": float(r["total_value"]), "p": float(r["total_pct"])} for r in rows]
    if bench:
        dates = sorted(bench.keys())
        import bisect
        bp = []
        for r in rows:
            i = bisect.bisect_right(dates, r["date"]) - 1
            if i >= 0:
                bp.append({"d": r["date"], "v": bench[dates[i]]})
        if bp:
            base = bp[0]["v"]
            for b in bp:
                b["p"] = (b["v"] / base - 1) * 100
            bench = bp
    else:
        bench = None

    html = HTML_TEMPLATE \
        .replace("__TITLE__", "纸面组合净值曲线") \
        .replace("__DATA__", json.dumps(pts, ensure_ascii=False)) \
        .replace("__BENCH__", json.dumps(bench, ensure_ascii=False)) \
        .replace("__TOTAL_RET__", f"{total_ret:+.2f}%") \
        .replace("__MAX_DD__", f"{max_dd:+.2f}%") \
        .replace("__BENCH_RET__", f"{bench_ret:+.2f}%" if bench_ret is not None else "--") \
        .replace("__ASOF__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
  body { font-family: -apple-system,"PingFang SC","Microsoft YaHei",sans-serif; margin:0; background:#101418; color:#e8eaed; }
  .wrap { max-width: 1000px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .meta { color:#9aa0a6; font-size:13px; margin-bottom:16px; }
  .cards { display:flex; gap:16px; margin-bottom:20px; }
  .card { flex:1; background:#1a1e24; border-radius:10px; padding:14px 16px; }
  .card .k { color:#9aa0a6; font-size:12px; }
  .card .v { font-size:22px; font-weight:700; margin-top:4px; }
  .pos { color:#ff4d4f; } .neg { color:#2ecc71; }
  svg { width:100%; height:360px; background:#1a1e24; border-radius:10px; }
  .legend { display:flex; gap:20px; font-size:12px; color:#9aa0a6; margin:8px 0 0; }
  .legend i { display:inline-block; width:14px; height:3px; margin-right:6px; vertical-align:middle; }
  table { width:100%; border-collapse:collapse; margin-top:16px; background:#1a1e24; border-radius:10px; overflow:hidden; }
  th,td { padding:7px 12px; font-size:13px; text-align:right; }
  th { background:#232830; } td:first-child, th:first-child { text-align:left; }
  .foot { color:#6b7075; font-size:11px; margin-top:10px; }
</style>
</head>
<body><div class="wrap">
  <h1>__TITLE__</h1>
  <div class="meta">数据时间 __ASOF__</div>
  <div class="cards">
    <div class="card"><div class="k">区间收益</div><div class="v __TOTAL_RET_CLS__">__TOTAL_RET__</div></div>
    <div class="card"><div class="k">最大回撤</div><div class="v neg">__MAX_DD__</div></div>
    <div class="card"><div class="k">沪深300 同期</div><div class="v __BENCH_RET_CLS__">__BENCH_RET__</div></div>
  </div>
  <svg id="chart" viewBox="0 0 960 360" preserveAspectRatio="none"></svg>
  <div class="legend"><span><i style="background:#ff4d4f"></i>组合累计收益%</span>
    <span><i style="background:#3b82f6"></i>沪深300%</span></div>
  <table id="tbl"><thead><tr><th>日期</th><th>总市值</th><th>当日%</th><th>累计%</th></tr></thead><tbody></tbody></table>
  <div class="foot">组合净值 = 现金 + 持仓市值（实时行情/基金净值估值）。基准为沪深300收盘指数，按快照日期对齐。</div>
</div>
<script>
const DATA = __DATA__, BENCH = __BENCH__;
const svg = document.getElementById('chart');
const NS = 'http://www.w3.org/2000/svg';
function line(pts, color, w) {
  const xs = DATA.map(p => p.d), ys = [0, ...DATA.map(p => p.p), ...(BENCH?BENCH.map(b=>b.p):[])];
  const min = Math.min(...ys) - 1, max = Math.max(...ys) + 1;
  const X = i => 30 + (i / (DATA.length - 1 || 1)) * 900;
  const Y = v => 330 - ((v - min) / (max - min)) * 290;
  let d = '';
  pts.forEach((p, i) => { d += (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(p).toFixed(1); });
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('d', d); path.setAttribute('stroke', color);
  path.setAttribute('stroke-width', w); path.setAttribute('fill', 'none'); path.setAttribute('vector-effect','non-scaling-stroke');
  svg.appendChild(path);
  const text = document.createElementNS(NS,'text');
  text.setAttribute('x', X(0)); text.setAttribute('y', 348); text.setAttribute('fill','#9aa0a6'); text.setAttribute('font-size','11');
  text.textContent = DATA[0].d;
  svg.appendChild(text);
  const t2 = document.createElementNS(NS,'text');
  t2.setAttribute('x', X(DATA.length-1)-60); t2.setAttribute('y', 348); t2.setAttribute('fill','#9aa0a6'); t2.setAttribute('font-size','11');
  t2.textContent = DATA[DATA.length-1].d;
  svg.appendChild(t2);
}
line(DATA, '#ff4d4f', 2);
if (BENCH) line(BENCH, '#3b82f6', 1.2);
const tb = document.querySelector('#tbl tbody');
DATA.slice().reverse().forEach(r => {
  const tr = document.createElement('tr');
  tr.innerHTML = '<td>' + r.d + '</td><td>' + r.v.toLocaleString('zh-CN',{minimumFractionDigits:2}) + '</td><td>' + (r.p>=0?'+':'') + r.p.toFixed(2) + '%</td><td>' + (r.p>=0?'+':'') + r.p.toFixed(2) + '%</td>';
  tb.appendChild(tr);
});
</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="纸面交易组合绩效")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_snap = sub.add_parser("snapshot", help="记录今日净值")
    p_snap.set_defaults(func=do_snapshot)
    p_list = sub.add_parser("list", help="快照明细")
    p_list.set_defaults(func=do_list)
    p_rep = sub.add_parser("report", help="生成绩效报告")
    p_rep.add_argument("--days", type=int, default=0, help="最近 N 个快照，0=全部")
    p_rep.add_argument("--out", "-o", default="/tmp/portfolio_perf.html")
    p_rep.add_argument("--no-benchmark", action="store_true")
    p_rep.set_defaults(func=do_report)
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
