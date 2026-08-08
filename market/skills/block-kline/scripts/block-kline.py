#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
block-kline: 为指定板块生成 embed HTML，嵌入东财官方 K 线图（RSI 副图）与分时快照图。

官方图片接口（webquoteklinepic / webquotepic，返回 PNG）：
  K线:  https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=90.BKxxxx&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={ts}
  分时: https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token=44c9d251add88e27b65ed86506f6e5da&nid=90.BKxxxx&timespan={ts}
  timespan = 当前 epoch 秒，保证图片刷新。

用法:
  python3 block-kline.py <BK代码或名称> [--out 路径] [--top 10] [--json]
  python3 block-kline.py BK0459
  python3 block-kline.py 元件
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Referer": "https://quote.eastmoney.com/"}
TOKEN = "44c9d251add88e27b65ed86506f6e5da"  # 东财 web 版公开 token


def resolve_bk(query: str) -> str:
    """BK代码 或 板块名称 → BKxxxx。"""
    q = query.strip()
    if q.upper().startswith("BK") and q[2:].isdigit():
        return q.upper()
    # 名称 → 板块代码：搜行业/概念板块列表
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
    from boards import load_boards
    for bt in ("行业", "概念"):
        for b in load_boards(bt):
            if b.get("name") == q:
                return b["code"]
    raise SystemExit(f"❌ 未找到板块: {q}")


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=12))




def build_stock(code: str) -> dict:
    """个股数据：名称/现价 + 官方 K线/分时图 URL。nid=1.沪/0.深。"""
    code = code.strip().zfill(6)
    nid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    ts = int(time.time())
    q = get_json(f"https://push2delay.eastmoney.com/api/qt/stock/get?secid={nid}&fields=f57,f58,f43,f170")
    d = q.get("data") or {}
    name = d.get("f58") or code
    price = (d.get("f43") or 0) / 100
    chg = (d.get("f170") or 0) / 100
    kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={ts}"
    flash_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token={TOKEN}&nid={nid}&timespan={ts}"
    page_url = f"https://quote.eastmoney.com/{'sh' if code.startswith('6') else 'sz'}{code}.html"
    return {"code": code, "nid": nid, "name": name, "price": price, "chg": chg,
            "kline_url": kline_url, "flash_url": flash_url, "page_url": page_url}


def build_stocks_embed(codes, out):
    """股票代码列表模式：每只一个卡片（官方K线+分时+链接），抽屉TOC。"""
    infos = [build_stock(c) for c in codes]
    ts = int(time.time())
    cards = ""
    for i, s in enumerate(infos):
        pos = "pos" if s["chg"] >= 0 else "neg"
        cards += f'''<section class="blk" id="sec-{i}">
<div class="top"><h2>{s["name"]}</h2><span class="code">{s["code"]}</span>
<span class="pct {pos}">{s["chg"]:+.2f}%</span><span class="price">现价 <b>{s["price"]}</b></span></div>
<div class="links">
<a class="btn btn-fs" href="{s["page_url"]}#fullScreenChart" target="_blank">📈 全屏K线</a>
<a class="btn btn-page" href="{s["page_url"]}" target="_blank">🔗 个股主页</a>
</div>
<div class="charts">
<div class="chart"><img src="{s["kline_url"]}" alt="{s["name"]} K线"><div class="cap">📈 日K线 · RSI（东财官方）</div></div>
<div class="chart"><img src="{s["flash_url"]}" alt="{s["name"]} 分时"><div class="cap">⏱ 分时快照</div></div>
</div></section>'''
    toc = "".join(f'<a href="#sec-{i}" class="toc-item"><span class="toc-idx">{i+1}</span>{s["name"]}<span class="toc-code">{s["code"]}</span></a>'
                  for i, s in enumerate(infos))
    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>股票组 embed</title>
<style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#0f1216;color:#e8eaed}}
#drawer{{position:fixed;top:0;left:0;bottom:0;width:230px;background:#161b22;border-right:1px solid #262d38;transform:translateX(-100%);transition:transform .25s;z-index:50;overflow-y:auto;padding:18px 0}}
#drawer.open{{transform:translateX(0)}}
.toc-item{{display:flex;align-items:center;gap:8px;padding:7px 18px;color:#d6dae0;text-decoration:none;font-size:13px;border-left:3px solid transparent}}
.toc-item:hover{{background:#1c222b;color:#fff}}.toc-item.active{{border-left-color:#ff4d4f;background:#1a2029;color:#fff}}
.toc-idx{{width:18px;height:18px;border-radius:5px;background:#232a35;color:#9aa0a6;font-size:11px;display:flex;align-items:center;justify-content:center}}
.toc-code{{margin-left:auto;color:#5c6572;font-size:11px}}
#overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}}
#overlay.show{{opacity:1;pointer-events:auto}}
#menu-btn{{position:fixed;top:14px;left:14px;z-index:60;width:38px;height:38px;border-radius:9px;border:1px solid #2a313d;background:#161b22;color:#e8eaed;font-size:17px;cursor:pointer}}
.wrap{{max-width:960px;margin:0 auto;padding:20px 20px 60px}}
.page-title{{text-align:center;padding:6px 0 12px}}.page-title h1{{font-size:20px;margin:0}}.page-title .sub{{color:#7c8490;font-size:12px}}
.blk{{margin-top:14px;padding:20px;background:#11151b;border:1px solid #1e252f;border-radius:14px}}
.blk .top{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}.blk h2{{font-size:19px;margin:0}}
.code{{color:#9aa0a6;font-size:13px}}.pct{{font-size:22px;font-weight:700}}.price{{color:#b6bcc4;font-size:14px}}
.pos{{color:#ff4d4f}}.neg{{color:#2ecc71}}
.links{{display:flex;gap:10px;margin:12px 0}}
.btn{{display:inline-block;padding:7px 14px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600}}
.btn-fs{{background:#ff4d4f;color:#fff}}.btn-page{{background:#232830;color:#d6dae0}}
.charts{{display:flex;gap:14px;flex-wrap:wrap}}
.chart{{background:#14181f;border-radius:10px;padding:10px;flex:1;min-width:320px}}
.chart img{{width:100%;height:auto;border-radius:6px}}.chart .cap{{color:#9aa0a6;font-size:12px;margin-top:6px}}
</style></head><body>
<button id="menu-btn" title="目录">☰</button><nav id="drawer">{toc}</nav><div id="overlay"></div>
<div class="wrap"><div class="page-title"><h1>📈 股票组（{len(infos)} 只）</h1><div class="sub">点击 ☰ 查看目录</div></div>{cards}</div>
<script>
const drawer=document.getElementById('drawer'),overlay=document.getElementById('overlay'),btn=document.getElementById('menu-btn');
btn.onclick=()=>{{drawer.classList.add('open');overlay.classList.add('show');}};
overlay.onclick=()=>{{drawer.classList.remove('open');overlay.classList.remove('show');}};
const items=[...document.querySelectorAll('.toc-item')];
items.forEach(it=>it.onclick=()=>{{items.forEach(x=>x.classList.remove('active'));it.classList.add('active');drawer.classList.remove('open');overlay.classList.remove('show');document.querySelector(it.getAttribute('href')).scrollIntoView({{behavior:'smooth'}});}});
</script></body></html>'''
    out = Path(out) if out else Path.cwd() / "generated" / "embed_stocks.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ 股票组 embed: {out} ({len(infos)} 只)")

def build(bk: str, top: int = 10) -> dict:
    nid = f"90.{bk}"
    ts = int(time.time())
    # 板块概览
    q = get_json(f"https://push2delay.eastmoney.com/api/qt/stock/get?secid={nid}&fields=f57,f58,f43,f48,f170")
    d = q.get("data") or {}
    name = d.get("f58") or bk
    idx = (d.get("f43") or 0) / 1000
    chg = (d.get("f170") or 0) / 100
    amt = (d.get("f48") or 0) / 1e8
    # 成分 top（今日涨跌幅）
    c = get_json(f"https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz={top}&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:{bk}&fields=f12,f14,f2,f3,f20")
    stocks = [{"c": r["f12"], "n": r["f14"], "p": r["f2"], "pct": r["f3"],
               "mcap": round((r.get("f20") or 0) / 1e8, 0)} for r in (c.get("data", {}).get("diff") or [])]
    total = (c.get("data") or {}).get("total")
    kline_url = f"https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid={nid}&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan={ts}"
    flash_url = f"https://webquotepic.eastmoney.com/GetPic.aspx?imageType=r&type=&token={TOKEN}&nid={nid}&timespan={ts}"
    page_url = f"https://quote.eastmoney.com/bk/{nid}.html"
    fs_url = f"{page_url}#fullScreenChart"
    return {"bk": bk, "nid": nid, "name": name, "idx": round(idx, 2), "chg": round(chg, 2),
            "amt": round(amt, 0), "total": total, "stocks": stocks,
            "kline_url": kline_url, "flash_url": flash_url, "page_url": page_url, "fs_url": fs_url}


K_TIP_CSS = """
.k-tip{position:fixed;z-index:99;background:#14181f;border:1px solid #2a313d;border-radius:8px;padding:4px;display:none;pointer-events:none;box-shadow:0 4px 16px rgba(0,0,0,.6)}
.k-tip img{width:260px;height:auto;display:block;border-radius:5px}
.k-tip .k-name{color:#9aa0a6;font-size:11px;padding:3px 6px}
tr.hover-row{cursor:pointer}
tr.hover-row:hover td{background:#1c2530}
"""

K_TIP_JS = """
const KTS=__KTS__;
const ktip=document.createElement('div');ktip.className='k-tip';document.body.appendChild(ktip);
ktip.innerHTML='<div class="k-name">加载中…</div><img alt="K线">';
const kimg=ktip.querySelector('img'),kname=ktip.querySelector('.k-name');
document.querySelectorAll('tr.hover-row,.hold-code').forEach(tr=>{
  tr.addEventListener('mouseenter',()=>{
    const code=tr.dataset.code;
    kname.textContent=tr.dataset.name+' ('+code+') · 东财K线';
    kimg.src='https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid='+(code[0]==='6'?'1.':'0.')+code+'&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan='+KTS;
    ktip.style.display='block';
  });
  tr.addEventListener('mousemove',e=>{
    let x=e.clientX+16,y=e.clientY+12;
    if(x+270>innerWidth)x=e.clientX-276;
    if(y+220>innerHeight)y=e.clientY-210;
    ktip.style.left=x+'px';ktip.style.top=y+'px';
  });
  tr.addEventListener('mouseleave',()=>{ktip.style.display='none'});
});
"""

def make_table(stocks) -> str:
    """成分表：行带 data-code/data-name，配合 hover K 线 tooltip。"""
    rows = "".join(
        f'<tr class="hover-row" data-code="{s["c"]}" data-name="{s["n"]}">'
        f'<td>{s["c"]}</td><td>{s["n"]}</td><td>{s["p"]}</td>'
        f'<td class="{"pos" if s["pct"] >= 0 else "neg"}">{s["pct"]:+.2f}%</td><td>{s["mcap"]}</td></tr>'
        for s in stocks)
    return (f"<table><thead><tr><th>代码</th><th>名称</th><th>现价</th><th>涨跌%</th>"
            f"<th>总市值(亿)</th></tr></thead><tbody>{rows}</tbody></table>")


def render_html(info: dict) -> str:
    n, bk = info["name"], info["bk"]
    pos = "pos" if info["chg"] >= 0 else "neg"
    chg = f"{info['chg']:+.2f}%"
    up = f"<span class=\"pct {pos}\">{chg}</span>"
    ts = int(time.time())
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>{n}({bk}) 板块行情 · embed</title>
<style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#0f1216;color:#e8eaed}}
.wrap{{max-width:980px;margin:0 auto;padding:16px}}
.top{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}
h1{{font-size:20px;margin:0}} .code{{color:#9aa0a6;font-size:13px}}
.pct{{font-size:24px;font-weight:700}} .pos{{color:#ff4d4f}}.neg{{color:#2ecc71}}
.metrics{{display:flex;gap:26px;margin:12px 0;color:#b6bcc4;font-size:13px}}
.metrics b{{color:#e8eaed;font-size:15px}}
.links{{display:flex;gap:10px;margin:10px 0}}
.btn{{display:inline-block;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600}}
.btn-fs{{background:#ff4d4f;color:#fff}} .btn-page{{background:#232830;color:#d6dae0}} .btn:hover{{opacity:.85}}
.charts{{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px}}
.chart{{background:#14181f;border-radius:10px;padding:10px;flex:1;min-width:340px}}
.chart img{{width:100%;height:auto;border-radius:6px}}
.chart .cap{{color:#9aa0a6;font-size:12px;margin-top:6px}}
table{{width:100%;border-collapse:collapse;background:#14181f;border-radius:10px;overflow:hidden;margin-top:12px}}
th,td{{padding:6px 10px;font-size:12px;text-align:right}} th{{background:#1c2129}} td:first-child,th:first-child{{text-align:left}}
h2{{font-size:15px;margin:18px 0 6px;color:#c9ced6}}
{K_TIP_CSS}
</style></head><body><div class="wrap">
<div class="top"><h1>{n}</h1><span class="code">{bk} · 东财板块</span>{up}</div>
<div class="metrics"><span>指数 <b>{info['idx']:,}</b></span><span>成交额 <b>{info['amt']:.0f}亿</b></span><span>成分 <b>{info['total']} 只</b></span></div>
<div class="links">
<a class="btn btn-fs" href="{info['fs_url']}" target="_blank">📈 东财全屏K线图</a>
<a class="btn btn-page" href="{info['page_url']}" target="_blank">🔗 东财板块主页</a>
</div>
<div class="charts">
<div class="chart"><a href="{info['page_url']}" target="_blank"><img src="{info['kline_url']}" alt="{n} K线(RSI)"></a>
<div class="cap">📈 日K线 · RSI 副图（东财官方图，点击放大）</div></div>
<div class="chart"><a href="{info['page_url']}" target="_blank"><img src="{info['flash_url']}" alt="{n} 分时"></a>
<div class="cap">⏱ 分时快照（东财官方图，点击放大）</div></div>
</div>
<h2>成分股今日涨幅榜（悬停查看个股K线）</h2>
{make_table(info['stocks'])}
</div>
<script>{K_TIP_JS.replace('__KTS__', str(ts))}</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description="为板块生成 embed HTML（东财官方K线/分时图）")
    ap.add_argument("query", nargs="*", default=None, help="板块代码（BKxxxx）/名称/股票代码列表（空格分隔）；与 --account 二选一")
    ap.add_argument("--account", default=None, help="组合账户：读持仓→去重板块→合并 embed（抽屉TOC）")
    ap.add_argument("--hot-cold", type=int, default=0, metavar="N",
                    help="今日板块榜：热/冷各前 N 个（二级行业，按涨跌幅）")
    ap.add_argument("--out", default=None, help="输出路径（默认 generated/embed_<BK>.html 或 embed_<账户>_blocks.html）")
    ap.add_argument("--top", type=int, default=10, help="成分榜条数")
    ap.add_argument("--json", action="store_true", help="输出 JSON 信息（含图片URL）")
    args = ap.parse_args()

    if args.hot_cold:
        build_hot_cold_embed(args.hot_cold, args.out)
        return
    q = " ".join(args.query) if args.query else ""
    if args.account and not q:
        build_account_embed(args.account, args.top, args.out)
        return
    if not q:
        raise SystemExit("❌ 需提供板块代码/名称/股票代码 或 --account")

    # 股票代码列表模式：一个或多个 6 位数字
    codes = q.replace(",", " ").split()
    if codes and all(c.isdigit() and len(c) == 6 for c in codes):
        build_stocks_embed(codes, args.out)
        return

    bk = resolve_bk(q)
    info = build(bk, args.top)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    out = Path(args.out) if args.out else Path.cwd() / "generated" / f"embed_{bk}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(info), encoding="utf-8")
    print(f"✅ embed HTML: {out}")
    print(f"   K线图: {info['kline_url']}")
    print(f"   分时图: {info['flash_url']}")


def build_hot_cold_embed(n: int, out):
    """今日板块榜：热/冷各前 N（二级行业），合并抽屉TOC embed（成分表 hover K线）。"""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
    from boards import load_boards
    rows = load_boards("二级行业")
    valid = [r for r in rows if r.get("pct") is not None]
    valid.sort(key=lambda r: r["pct"], reverse=True)
    hot, cold = valid[:n], valid[-n:][::-1]
    items = [(r["code"], r["name"], r["pct"]) for r in hot + cold]
    groups = [("hot", "🔥 热门板块", hot), ("cold", "🥶 冷门板块", cold)]

    infos = []
    for code, name, pct in items:
        try:
            i = build(code, 6)
            i["_pct"] = pct
            infos.append(i)
        except Exception as e:
            print(f"✗ {code}: {e}", file=_sys.stderr)

    ts = int(time.time())
    def sec(info, sidx):
        pos = "pos" if info["chg"] >= 0 else "neg"
        return f'''<section class="blk" id="sec-{sidx}">
<div class="top"><h2>{info["name"]}</h2><span class="code">{info["bk"]}</span>
<span class="pct {pos}">{info["_pct"]:+.2f}%</span></div>
<div class="metrics"><span>指数 <b>{info["idx"]:,}</b></span><span>成交额 <b>{info["amt"]:.0f}亿</b></span><span>成分 <b>{info["total"]} 只</b></span></div>
<div class="links">
<a class="btn btn-fs" href="{info["fs_url"]}" target="_blank">📈 全屏K线</a>
<a class="btn btn-page" href="{info["page_url"]}" target="_blank">🔗 板块主页</a>
</div>
<div class="charts">
<div class="chart"><img src="{info["kline_url"]}" alt="K线"><div class="cap">📈 日K线 · RSI</div></div>
<div class="chart"><img src="{info["flash_url"]}" alt="分时"><div class="cap">⏱ 分时快照</div></div>
</div>
<h3>成分股涨幅榜（悬停看K线）</h3>
{make_table(info["stocks"])}</section>'''

    toc = ""
    for gkey, gname, glist in groups:
        toc += f'<div class="toc-grp">{gname}</div>'
        for r in glist:
            idx = next(i for i, info in enumerate(infos) if info["bk"] == r["code"])
            toc += f'<a href="#sec-{idx}" class="toc-item"><span class="toc-idx">{idx+1}</span>{r["name"]}<span class="toc-code">{r["code"]}</span></a>'
    sections = "".join(sec(info, i) for i, info in enumerate(infos))
    now = time.strftime("%Y-%m-%d %H:%M")
    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>今日板块热冷榜</title>
<style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#0f1216;color:#e8eaed}}
#drawer{{position:fixed;top:0;left:0;bottom:0;width:240px;background:#161b22;border-right:1px solid #262d38;transform:translateX(-100%);transition:transform .25s;z-index:50;overflow-y:auto;padding:18px 0}}
#drawer.open{{transform:translateX(0)}}
.toc-grp{{font-size:12px;color:#9aa0a6;font-weight:700;margin:14px 18px 6px}}
.toc-item{{display:flex;align-items:center;gap:8px;padding:7px 18px;color:#d6dae0;text-decoration:none;font-size:13px;border-left:3px solid transparent}}
.toc-item:hover{{background:#1c222b;color:#fff}}.toc-item.active{{border-left-color:#ff4d4f;background:#1a2029;color:#fff}}
.toc-idx{{width:18px;height:18px;border-radius:5px;background:#232a35;color:#9aa0a6;font-size:11px;display:flex;align-items:center;justify-content:center}}
.toc-code{{margin-left:auto;color:#5c6572;font-size:11px}}
#overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}}
#overlay.show{{opacity:1;pointer-events:auto}}
#menu-btn{{position:fixed;top:14px;left:14px;z-index:60;width:38px;height:38px;border-radius:9px;border:1px solid #2a313d;background:#161b22;color:#e8eaed;font-size:17px;cursor:pointer}}
.wrap{{max-width:960px;margin:0 auto;padding:20px 20px 60px}}
.page-title{{text-align:center;padding:6px 0 12px}}.page-title h1{{font-size:20px;margin:0}}.page-title .sub{{color:#7c8490;font-size:12px}}
.blk{{margin-top:14px;padding:20px;background:#11151b;border:1px solid #1e252f;border-radius:14px}}
.blk .top{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}.blk h2{{font-size:19px;margin:0}}
.code{{color:#9aa0a6;font-size:13px}}.pct{{font-size:22px;font-weight:700}}.pos{{color:#ff4d4f}}.neg{{color:#2ecc71}}
.metrics{{display:flex;gap:24px;margin:12px 0;color:#b6bcc4;font-size:13px}}.metrics b{{color:#e8eaed;font-size:15px}}
.links{{display:flex;gap:10px;margin:10px 0}}
.btn{{display:inline-block;padding:7px 14px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600}}
.btn-fs{{background:#ff4d4f;color:#fff}}.btn-page{{background:#232830;color:#d6dae0}}
.charts{{display:flex;gap:14px;flex-wrap:wrap}}.chart{{background:#14181f;border-radius:10px;padding:10px;flex:1;min-width:320px}}
.chart img{{width:100%;height:auto;border-radius:6px}}.chart .cap{{color:#9aa0a6;font-size:12px;margin-top:6px}}
.blk h3{{font-size:14px;margin:16px 0 6px;color:#c9ced6}}
table{{width:100%;border-collapse:collapse;background:#14181f;border-radius:10px;overflow:hidden;margin-top:8px}}
th,td{{padding:6px 10px;font-size:12px;text-align:right}}th{{background:#1c2129}}td:first-child,th:first-child{{text-align:left}}
{K_TIP_CSS}
</style></head><body>
<button id="menu-btn" title="目录">☰</button><nav id="drawer">{toc}</nav><div id="overlay"></div>
<div class="wrap"><div class="page-title"><h1>今日板块热冷榜（{now}）</h1>
<div class="sub">🔥 涨幅前 {n} ｜ 🥶 跌幅前 {n} ｜ 点击 ☰ 目录 ｜ 悬停成分股看K线</div></div>{sections}</div>
<script>{K_TIP_JS.replace("__KTS__", str(ts))}</script>
<script>
const drawer=document.getElementById("drawer"),overlay=document.getElementById("overlay"),btn=document.getElementById("menu-btn");
btn.onclick=()=>{{drawer.classList.add("open");overlay.classList.add("show");}};
overlay.onclick=()=>{{drawer.classList.remove("open");overlay.classList.remove("show");}};
const items=[...document.querySelectorAll(".toc-item")];
items.forEach(it=>it.onclick=()=>{{items.forEach(x=>x.classList.remove("active"));it.classList.add("active");drawer.classList.remove("open");overlay.classList.remove("show");document.querySelector(it.getAttribute("href")).scrollIntoView({{behavior:"smooth"}});}});
</script></body></html>'''
    outp = Path(out) if out else Path.cwd() / "generated" / "embed_hot_cold.html"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"✅ 今日板块热冷榜 embed: {outp} ({len(infos)} 板块)")


def build_account_embed(account: str, top: int, out: str):
    """读组合持仓 → block-lookup 每只 → 去重板块 → 合并抽屉TOC embed。"""
    import subprocess as _sp
    import urllib.parse as _up
    PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"
    LOOKUP = "/Users/yyz/.agents/skills/stock/block-lookup/scripts/block-lookup.py"

    # 1. 持仓
    p = _sp.run(["python3", PORTFOLIO, "--account", account, "show", "--json"],
                capture_output=True, text=True, timeout=30)
    pf = json.loads(p.stdout)
    positions = pf["positions"]
    if isinstance(positions, dict):
        positions = [{"code": k, "name": v["name"]} for k, v in positions.items()]

    # 2. 板块归属（block-lookup）→ 去重
    blocks = {}
    for pos in positions:
        r = _sp.run(["python3", LOOKUP, pos["code"], "--json"], capture_output=True, text=True, timeout=60)
        try:
            d = json.loads(r.stdout)
            l2 = (d.get("industry") or {}).get("二级") or {}
            bk = l2.get("code")
            if not bk:
                continue
            blocks.setdefault(bk, {"name": l2.get("name") or bk, "stocks": []})
            blocks[bk]["stocks"].append(f"{pos['name']}({pos['code']})")
        except Exception:
            pass

    # 3. 逐个 build
    infos = []
    for bk, info in blocks.items():
        try:
            i = build(bk, top)
            i["_stocks"] = info["stocks"]
            infos.append(i)
        except Exception as e:
            print(f"✗ {bk}: {e}", file=sys.stderr)

    # 4. 合并渲染（抽屉 TOC）
    def sec(info, sidx):
        pos = "pos" if info["chg"] >= 0 else "neg"
        hold_spans = "、".join(
            f'<span class="hold-code" data-code="{st.split(chr(40))[1].rstrip(chr(41))}" '
            f'data-name="{st.split(chr(40))[0]}">{st}</span>' for st in info["_stocks"])
        return f"""<section class=\"blk\" id=\"sec-{sidx}\"><div class=\"top\"><h2>{info['name']}</h2><span class=\"code\">{info['bk']}</span><span class=\"pct {pos}\">{info['chg']:+.2f}%</span></div>""" + \
            f"""<div class=\"metrics\"><span>指数 <b>{info['idx']:,}</b></span><span>成交额 <b>{info['amt']:.0f}亿</b></span><span>成分 <b>{info['total']} 只</b></span><span class="hold">📌 {hold_spans}</span></div>""" + \
            f"""<div class=\"links\"><a class=\"btn btn-fs\" href=\"{info['fs_url']}\">📈 全屏K线</a><a class=\"btn btn-page\" href=\"{info['page_url']}\">🔗 板块主页</a></div>""" + \
            f"""<div class=\"charts\"><div class=\"chart\"><img src=\"{info['kline_url']}\" alt=\"K线\"></div><div class=\"chart\"><img src=\"{info['flash_url']}\" alt=\"分时\"></div></div>""" + \
            f"""{make_table(info["stocks"])}</section>"""

    toc = "".join(f'<a href="#sec-{i}" class="toc-item"><span class="toc-idx">{i+1}</span>{info["name"]}<span class="toc-n">{len(info["_stocks"])}只</span><span class="toc-code">{info["bk"]}</span></a>'
                   for i, info in enumerate(infos))
    sections = "".join(sec(info, i) for i, info in enumerate(infos))
    html = f"""<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"><title>{account} 持仓板块</title>
<style>body{{font-family:-apple-system,\"PingFang SC\",sans-serif;margin:0;background:#0f1216;color:#e8eaed}}
#drawer{{position:fixed;top:0;left:0;bottom:0;width:240px;background:#161b22;border-right:1px solid #262d38;transform:translateX(-100%);transition:transform .25s;z-index:50;overflow-y:auto;padding:18px 0}}
#drawer.open{{transform:translateX(0)}}
.toc-item{{display:flex;align-items:center;gap:8px;padding:7px 18px;color:#d6dae0;text-decoration:none;font-size:13px;border-left:3px solid transparent}}
.toc-item:hover{{background:#1c222b;color:#fff}}.toc-item.active{{border-left-color:#ff4d4f;background:#1a2029;color:#fff}}
.toc-idx{{width:18px;height:18px;border-radius:5px;background:#232a35;color:#9aa0a6;font-size:11px;display:flex;align-items:center;justify-content:center}}
.toc-n{{background:#3a2d12;color:#f0b45a;font-size:10px;border-radius:4px;padding:1px 5px}}
.toc-code{{margin-left:auto;color:#5c6572;font-size:11px}}
#overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);opacity:0;pointer-events:none;transition:opacity .2s;z-index:40}}
#overlay.show{{opacity:1;pointer-events:auto}}
#menu-btn{{position:fixed;top:14px;left:14px;z-index:60;width:38px;height:38px;border-radius:9px;border:1px solid #2a313d;background:#161b22;color:#e8eaed;font-size:17px;cursor:pointer}}
.wrap{{max-width:960px;margin:0 auto;padding:20px 20px 60px}}
.page-title{{text-align:center;padding:6px 0 12px}}.page-title h1{{font-size:20px;margin:0}}.page-title .sub{{color:#7c8490;font-size:12px}}
.blk{{margin-top:14px;padding:20px;background:#11151b;border:1px solid #1e252f;border-radius:14px}}
.blk .top{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}}.blk h2{{font-size:19px;margin:0}}
.code{{color:#9aa0a6;font-size:13px}}.pct{{font-size:22px;font-weight:700}}.pos{{color:#ff4d4f}}.neg{{color:#2ecc71}}
.metrics{{display:flex;gap:24px;margin:12px 0;color:#b6bcc4;font-size:13px;flex-wrap:wrap}}.metrics b{{color:#e8eaed;font-size:15px}}
.hold{{color:#f0b45a;background:#2a2410;border-radius:6px;padding:2px 10px;font-size:12px}}
.links{{display:flex;gap:10px;margin:10px 0}}.btn{{display:inline-block;padding:7px 14px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600}}
.btn-fs{{background:#ff4d4f;color:#fff}}.btn-page{{background:#232830;color:#d6dae0}}
.charts{{display:flex;gap:14px;flex-wrap:wrap}}.chart{{background:#14181f;border-radius:10px;padding:10px;flex:1;min-width:320px}}
.chart img{{width:100%;height:auto;border-radius:6px}}
table{{width:100%;border-collapse:collapse;background:#14181f;border-radius:10px;overflow:hidden;margin-top:12px}}
th,td{{padding:6px 10px;font-size:12px;text-align:right}}th{{background:#1c2129}}td:first-child,th:first-child{{text-align:left}}
{K_TIP_CSS}
</style></head><body><button id=\"menu-btn\" title=\"目录\">☰</button><nav id=\"drawer\">{toc}</nav><div id=\"overlay\"></div><div class=\"wrap\"><div class=\"page-title\"><h1>📁 {account} 持仓板块</h1><div class=\"sub\">{len(positions)} 只持仓 → {len(infos)} 板块 ｜ 点击 ☰ 查看目录</div></div>{sections}</div>
<script>
const drawer=document.getElementById('drawer'),overlay=document.getElementById('overlay'),btn=document.getElementById('menu-btn');
btn.onclick=()=>{{drawer.classList.add('open');overlay.classList.add('show');}};
overlay.onclick=()=>{{drawer.classList.remove('open');overlay.classList.remove('show');}};
const items=[...document.querySelectorAll('.toc-item')];
{K_TIP_JS.replace('__KTS__', str(int(time.time())))}
items.forEach(it=>it.onclick=()=>{{items.forEach(x=>x.classList.remove('active'));it.classList.add('active');drawer.classList.remove('open');overlay.classList.remove('show');document.querySelector(it.getAttribute('href')).scrollIntoView({{behavior:'smooth'}});}});
</script></body></html>"""

    out = Path(out) if out else Path.cwd() / "generated" / f"embed_{account}_blocks.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ 持仓板块 embed: {out} ({len(infos)} 板块, {len(positions)} 只持仓)")


if __name__ == "__main__":
    main()
