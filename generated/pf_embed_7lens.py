#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成持仓 embed HTML：每只股票 = 东财官方K线(RSI)+分时图 + 7维结论 TOC 抽屉。
东财个股图 nid = 1.沪 / 0.深；board/个股复用同一 webquoteklinepic 接口。
"""
import json, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ACC = "7维选股"
PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"
ML = "/Users/yyz/.agents/skills/stock/multi-lens/scripts/multi-lens.py"
TS = int(time.time())

def get_positions():
    p = subprocess.run(["python3", PORTFOLIO, "--account", ACC, "show", "--json"],
                       capture_output=True, text=True)
    return json.loads(p.stdout)["positions"]

def market_prefix(code):
    return "1" if code.startswith("6") else "0"

def run_lens(code):
    try:
        p = subprocess.run(["python3", ML, code, "--json"], capture_output=True,
                           text=True, timeout=120)
        return json.loads(p.stdout)
    except Exception as e:
        return {"code": code, "name": code, "verdict": f"ERR {e}",
                "lenses": [{"lens": "错误", "summary": str(e)[:50], "direction": 0}]}

def analyze(pos):
    code = pos["code"]
    lens = run_lens(code)
    return {**pos, "lens": lens}

def build_html(items, outp):
    ts = TS
    total_mkt = sum(it["mkt"] for it in items) or 1
    cards = []
    for it in items:
        code = it["code"]; name = it["name"]; pref = market_prefix(code)
        L = it["lens"]
        verdict = L.get("verdict", "")
        lenses = L.get("lenses", [])
        kurl = (f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={pref}.{code}"
                f"&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={ts}")
        furl = (f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type="
                f"&token=44c9d251add88e27b65ed86506f6e5da&nid={pref}.{code}&timespan={ts}")
        # 方向色
        vc = "#c92a2a" if "看多" in verdict else ("#2f9e44" if "看空" in verdict else "#495057")
        rows = ""
        for x in lenses:
            d = x["direction"]
            arrow = '🔴看多' if d==1 else ('🟢看空' if d==-1 else '➖中性')
            c = '#c92a2a' if d==1 else ('#2f9e44' if d==-1 else '#868e96')
            rows += (f'<tr><td class="ll">{x["lens"]}</td>'
                     f'<td>{x.get("summary","")}</td>'
                     f'<td style="color:{c};font-weight:600">{arrow}</td></tr>')
        pnl = it["pnl_pct"]; pc = '#c92a2a' if pnl>=0 else '#2f9e44'
        cards.append(f'''
<section class="card" id="s{code}">
  <div class="card-head">
    <a class="anchor" href="#s{code}"></a>
    <div><span class="code">{code}</span> {name}</div>
    <div class="meta">仓位 {it['mkt']/total_mkt*100:.1f}% 市值 {it['mkt']:,.0f}　盈亏 <span style="color:{pc}">{pnl:+.2f}%</span>　现价 {it['price']}</div>
  </div>
  <div class="verdict" style="border-left:4px solid {vc};background:{vc}15">{verdict}</div>
  <div class="imgs">
    <figure><a href="https://quote.eastmoney.com/{ 'sh' if pref=='1' else 'sz' }{code}.html" target="_blank"><img src="{kurl}" alt="K线"></a><figcaption>东财K线(RSI)</figcaption></figure>
    <figure><img src="{furl}" alt="分时"><figcaption>分时</figcaption></figure>
  </div>
  <table class="lens"><thead><tr><th>维度</th><th>摘要</th><th>方向</th></tr></thead><tbody>{rows}</tbody></table>
</section>''')
    body = "\n".join(cards)
    nav = "\n".join(
        f'<li><a href="#s{c["code"]}">{c["code"]} {c["name"]}</a> '
        f'<span class="vbadge" style="color:{("#c92a2a" if "看多" in c["lens"]["verdict"] else ("#2f9e44" if "看空" in c["lens"]["verdict"] else "#868e96"))}">'
        f'{"多" if "看多" in c["lens"]["verdict"] else ("空" if "看空" in c["lens"]["verdict"] else "中")}</span></li>'
        for c in items)
    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{ACC} 持仓 7维 · 东财K线 embed</title>
<style>
:root{{--accent:#3b5bdb;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f3f4f6;color:#222}}
header{{position:sticky;top:0;background:#212529;color:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;z-index:20}}
header h1{{font-size:17px;margin:0}} header .sub{{font-size:12px;color:#adb5bd}}
#btn{{background:var(--accent);border:none;color:#fff;padding:8px 14px;border-radius:8px;cursor:pointer;font-size:14px}}
#drawer{{position:fixed;top:0;left:-340px;width:320px;height:100%;background:#fff;box-shadow:2px 0 14px rgba(0,0,0,.2);transition:left .25s;overflow-y:auto;z-index:30;padding:16px}}
#drawer.open{{left:0}}
#drawer h2{{font-size:14px;margin:0 0 8px;color:#495057}}
#drawer ul{{list-style:none;margin:0;padding:0}}
#drawer li{{padding:7px 8px;border-bottom:1px solid #eee;font-size:13px}}
#drawer a{{color:#212529;text-decoration:none}}
#drawer .vbadge{{font-weight:700;margin-left:6px}}
#veil{{position:fixed;inset:0;background:rgba(0,0,0,.35);display:none;z-index:25}}
.wrap{{max-width:1080px;margin:20px auto;padding:0 16px}}
.card{{background:#fff;border-radius:12px;margin:18px 0;padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,.08);scroll-margin-top:70px}}
.card-head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}}
.card-head .code{{font-weight:800;color:var(--accent)}} .card-head .meta{{font-size:12px;color:#868e96}}
.verdict{{padding:8px 12px;border-radius:8px;font-weight:700;margin:6px 0 12px}}
.imgs{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px}}
.imgs figure{{margin:0;flex:1 1 480px}}
.imgs img{{width:100%;height:auto;border:1px solid #e0e0e0;border-radius:8px}}
figcaption{{font-size:12px;color:#868e96;text-align:center;margin-top:4px}}
table.lens{{border-collapse:collapse;width:100%;font-size:13px}}
table.lens th,table.lens td{{border:1px solid #e9ecef;padding:6px 10px;text-align:left}}
table.lens th{{background:#f1f3f5}} table.lens td.ll{{font-weight:600;white-space:nowrap}}
</style></head><body>
<header><button id="btn">☰ 目录 / TOC ({len(items)})</button>
<div><h1>{ACC} 持仓 · 7维结论 + 东财K线 embed</h1>
<div class="sub">共 {len(items)} 只 · 东财官方K线(RSI)+分时 · {time.strftime('%Y-%m-%d %H:%M')}</div></div></header>
<nav id="drawer"><h2>持仓 7 维 TOC</h2><ul>{nav}</ul></nav>
<div id="veil"></div>
<div class="wrap">{body}</div>
<script>
var d=document.getElementById('drawer'),b=document.getElementById('btn'),veil=document.getElementById('veil');
function open2(){{d.classList.add('open');veil.style.display='block'}}
function close2(){{d.classList.remove('open');veil.style.display='none'}}
b.onclick=open2;veil.onclick=close2;
d.addEventListener('click',function(e){{if(e.target.tagName==='A')close2();}});
</script></body></html>'''
    Path(outp).write_text(html, encoding="utf-8")
    print(f"✅ {outp} ({len(items)} stocks, {Path(outp).stat().st_size/1024:.1f} KB)")

def main():
    pos = get_positions()
    with ThreadPoolExecutor(max_workers=6) as ex:
        items = list(ex.map(analyze, pos))
    items.sort(key=lambda c: c["code"])
    outp = Path(__file__).resolve().parent / f"embed_portfolio_{ACC}_7lens.html"
    build_html(items, outp)

if __name__ == "__main__":
    main()
