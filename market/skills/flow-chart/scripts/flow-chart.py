#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow-chart: 个股资金流向分析（日频主力/超大单/大单/中单/小单净流入）。

数据: push2his fflow/daykline (klt=101)。
输出: 逐日资金流表 + N 日累计 + 自包含 HTML 柱状图。

用法:
  python3 flow-chart.py <代码> [--days N] [--out 路径] [--json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/"}
FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
LABELS = ["主力", "小单", "中单", "大单", "超大单"]


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


def fmt_wan(v):
    return f"{v / 1e4:+,.1f}"


def fetch_flow(code: str, lmt: int = 60):
    """日频资金流。返回 (name, [{date, close, pct, main, xl, dl, zl, sl, main_pct}])。带重试。"""
    import time as _t
    from httpget import httpget
    code = str(code).zfill(6)
    secid = f"{'1' if code.startswith('6') else '0'}.{code}"
    last_err = None
    for _ in range(3):
        try:
            resp = httpget("https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
                                params={"lmt": "0", "klt": "101", "secid": secid,
                                        "fields1": "f1,f2,f3,f7", "fields2": FIELDS2,
                                        "ut": "b2884a393a59ad64002292a3e90d46a5"},
                                timeout=15, headers=UA)
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            rows = []
            for line in (data.get("klines") or [])[-lmt:]:
                p = line.split(",")
                if len(p) < 15:
                    continue
                rows.append({
                    "date": p[0],
                    "main": float(p[1]),      # 主力净流入
                    "small": float(p[2]),     # 小单
                    "mid": float(p[3]),       # 中单
                    "big": float(p[4]),       # 大单
                    "xbig": float(p[5]),      # 超大单
                    "main_pct": float(p[6]),  # 主力净占比 %
                    "close": float(p[11]),    # 收盘
                    "pct": float(p[12]),      # 涨跌幅
                })
            if rows:
                return data.get("name") or code, rows
        except Exception as e:
            last_err = e
            _t.sleep(1.5)
    raise ConnectionError(f"资金流接口失败: {last_err}")


def write_html(name, code, rows, out):
    pts = [{"d": r["date"], "main": r["main"] / 1e4, "main_pct": r["main_pct"],
            "close": r["close"], "pct": r["pct"]} for r in rows]
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>__TITLE__</title>
<style>body{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#101418;color:#e8eaed}
.wrap{max-width:1000px;margin:0 auto;padding:20px}h1{font-size:19px;margin-bottom:4px}
.meta{color:#9aa0a6;font-size:13px;margin-bottom:16px}
svg{width:100%;height:440px;background:#1a1e24;border-radius:10px}
.legend{color:#9aa0a6;font-size:12px;margin:8px 0}
.legend i{display:inline-block;width:14px;height:3px;margin-right:6px;vertical-align:middle}
.bar{display:inline-block;vertical-align:middle;width:10px;height:10px;border-radius:2px;margin-right:6px}
table{width:100%;border-collapse:collapse;background:#1a1e24;border-radius:10px;overflow:hidden;margin-top:14px}
th,td{padding:6px 10px;font-size:12px;text-align:right}th{background:#232830}td:first-child,th:first-child{text-align:left}
.pos{color:#ff4d4f}.neg{color:#2ecc71}</style></head><body><div class="wrap">
<h1>__TITLE__</h1><div class="meta">主力净流入（万元）日频柱状图 ｜ 红=净流入 绿=净流出 ｜ 蓝线=5日主力均线 ｜ 黄线=收盘价</div>
<svg id="c" viewBox="0 0 960 440" preserveAspectRatio="none"></svg>
<div class="legend">
<span><span class="bar" style="background:#ff4d4f"></span>主力净流入</span>
<span><i style="background:#3b82f6"></i>5日均线</span>
<span><i style="background:#f59e0b"></i>收盘价</span>
</div>
<table><thead><tr><th>日期</th><th>收盘</th><th>涨跌%</th><th>主力(万)</th><th>主力占比%</th><th>超大单(万)</th><th>大单(万)</th></tr></thead>
<tbody id="tb"></tbody></table>
</div><script>
const D=__DATA__;
const svg=document.getElementById('c'),NS='http://www.w3.org/2000/svg';
const n=D.length,X=i=>30+(i/(n-1||1))*900;
const mains=D.map(d=>d.main);const M=Math.max(...mains.map(Math.abs))*1.1;
const closes=D.map(d=>d.close);const cmin=Math.min(...closes),cmax=Math.max(...closes);
const Y=v=>220-(v/M)*180;   // 0 线在 220
const CY=v=>400-((v-cmin)/(cmax-cmin||1))*170;
// bars
D.forEach((d,i)=>{
  const h=Math.abs(d.main)/M*180;
  const el=document.createElementNS(NS,'rect');
  el.setAttribute('x',X(i)-9);el.setAttribute('y',d.main>=0?220-h:220);
  el.setAttribute('width',18);el.setAttribute('height',Math.max(h,1));
  el.setAttribute('fill',d.main>=0?'#ff4d4f':'#2ecc71');
  el.setAttribute('opacity','0.85');
  svg.appendChild(el);
});
function line(pts,color,w){
  let s='';pts.forEach((p,i)=>{s+=(i?'L':'M')+X(i).toFixed(1)+' '+p.toFixed(1)});
  const el=document.createElementNS(NS,'path');el.setAttribute('d',s);el.setAttribute('stroke',color);
  el.setAttribute('stroke-width',w);el.setAttribute('fill','none');el.setAttribute('vector-effect','non-scaling-stroke');
  svg.appendChild(el);
}
// 5日主力均线
const ma5=[];D.forEach((d,i)=>{const seg=D.slice(Math.max(0,i-4),i+1);ma5.push(Y(seg.reduce((s,x)=>s+x.main,0)/seg.length));});
line(ma5,'#3b82f6',1.5);
// 收盘价线
line(closes.map((c,i)=>CY(c)),'#f59e0b',1.2);
// 0 轴
const ax=document.createElementNS(NS,'line');
ax.setAttribute('x1',20);ax.setAttribute('y1',220);ax.setAttribute('x2',940);ax.setAttribute('y2',220);
ax.setAttribute('stroke','#555b66');ax.setAttribute('stroke-width','1');
svg.appendChild(ax);
// 日期标签
const t0=document.createElementNS(NS,'text');t0.setAttribute('x',30);t0.setAttribute('y',435);t0.setAttribute('fill','#9aa0a6');t0.setAttribute('font-size','10');t0.textContent=D[0].d;
svg.appendChild(t0);
const t1=document.createElementNS(NS,'text');t1.setAttribute('x',X(n-1)-50);t1.setAttribute('y',435);t1.setAttribute('fill','#9aa0a6');t1.setAttribute('font-size','10');t1.textContent=D[n-1].d;
svg.appendChild(t1);
// table
const tb=document.getElementById('tb');
D.slice().reverse().forEach(d=>{
  const tr=document.createElement('tr');
  tr.innerHTML='<td>'+d.d+'</td><td>'+d.close.toFixed(2)+'</td><td class="'+(d.pct>=0?'pos':'neg')+'">'+(d.pct>=0?'+':'')+d.pct.toFixed(2)+'</td>'+
    '<td class="'+(d.main>=0?'pos':'neg')+'">'+(d.main>=0?'+':'')+d.main.toFixed(1)+'</td><td>'+(d.main_pct>=0?'+':'')+d.main_pct.toFixed(2)+'</td>'+
    '<td class="'+(d.xbig>=0?'pos':'neg')+'">'+(d.xbig>=0?'+':'')+d.xbig.toFixed(1)+'</td><td class="'+(d.big>=0?'pos':'neg')+'">'+(d.big>=0?'+':'')+d.big.toFixed(1)+'</td>';
  tb.appendChild(tr);
});
</script></body></html>"""
    html = (html.replace("__TITLE__", f"{name} ({code}) 资金流向")
            .replace("__DATA__", json.dumps(pts)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description="个股资金流向分析")
    ap.add_argument("code", help="股票代码")
    ap.add_argument("--days", type=int, default=20, help="分析最近 N 日，默认 20，最大 60")
    ap.add_argument("--out", "-o", default="/tmp/flow_chart.html", help="HTML 输出路径")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    days = max(5, min(args.days, 60))
    name, rows = fetch_flow(args.code, lmt=days)
    if not rows:
        sys.exit(f"❌ 无法获取 {args.code} 资金流数据")

    def _sum(n):
        return sum(r["main"] for r in rows[-n:]) if len(rows) >= n else None

    sums = {"5日": _sum(5), "10日": _sum(10), "20日": _sum(20)}
    up_days = sum(1 for r in rows if r["main"] > 0)
    last = rows[-1]

    if args.json:
        print(json.dumps({"code": args.code, "name": name, "days": len(rows),
                          "last": last, "cum5": sums["5日"], "cum10": sums["10日"],
                          "cum20": sums["20日"], "main_positive_days": up_days,
                          "rows": rows}, ensure_ascii=False, indent=2))
        return

    print(f"{name} ({args.code}) ｜ 最近 {len(rows)} 日资金流（单位: 万元）")
    header = " ".join([pad("日期", 12), pad("收盘", 8, "right"), pad("涨跌", 8, "right"),
                       pad("主力净流入", 13, "right"), pad("主力占比", 9, "right"),
                       pad("超大单", 11, "right"), pad("大单", 11, "right")])
    print(header)
    print("-" * display_width(header))
    for r in rows[-days:]:
        print(" ".join([pad(r["date"], 12), pad(f"{r['close']:.2f}", 8, "right"),
                        pad(fmt_pct(r["pct"]), 8, "right"),
                        pad(fmt_wan(r["main"]), 13, "right"),
                        pad(f"{r['main_pct']:+.2f}", 9, "right"),
                        pad(fmt_wan(r["xbig"]), 11, "right"),
                        pad(fmt_wan(r["big"]), 11, "right")]))

    print()
    print(f"主力累计: " + " ｜ ".join(f"{k} {fmt_wan(s)}" for k, s in sums.items() if s is not None))
    print(f"主力净流入天数: {up_days}/{len(rows)} ｜ 最新: {last['date']} {fmt_wan(last['main'])}（{last['main_pct']:+.2f}%）")

    # 解读
    cum5 = sums.get("5日")
    verdict = []
    if cum5 is not None:
        if cum5 > 0 and last["pct"] > 0:
            verdict.append("近5日主力净流入 + 股价上行 → 吸筹，趋势健康")
        elif cum5 < 0 and last["pct"] > 0:
            verdict.append("股价涨但近5日主力净流出 → 警惕派发/冲高出货")
        elif cum5 < 0:
            verdict.append("近5日主力净流出 → 弱势，谨慎")
        else:
            verdict.append("近5日主力小幅净流入，方向待确认")
    print("\n解读: " + "；".join(verdict))

    out = write_html(name, args.code, rows, Path(args.out))
    print(f"📊 资金流图: {out}（open {out}）")


if __name__ == "__main__":
    main()
