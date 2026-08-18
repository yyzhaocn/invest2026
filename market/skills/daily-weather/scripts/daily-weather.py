#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily-weather: 全市场行情天气速览（weather report）。

输入:
  --date YYYY-MM-DD      指定交易日（默认用可用的最新收盘快照）
  --slot HHMM            快照时点（默认自动选最新可用；可用 0930/1000/1030/1100/1130/1400/1430/1500）
  --snapshot <路径>      直接给全市场快照 CSV（market,code,chg_pct,...），跳过自动选档
  --sector [二级行业|一级行业|概念]  统计粒度（默认 二级行业）
  --json                 JSON 输出

输出内容:
  1. 市场广度：涨/跌/平家数、占比、平均/中位涨跌、涨停/跌停
  2. 温度判定：强强/偏强/震荡/偏弱/弱势（按涨跌家数比 + 平均涨幅）
  3. 分板块统计：各板块涨/跌/平家数 + 平均涨跌（领涨/领跌板块）
  4. 主线总结

依赖:
  - 全市场快照存档 generated/heatmap_snapshots/（由 market-snapshot 技能写入）
  - _shared/boards.py（板块列表 + 成分股）
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

REPO = Path(__file__).resolve().parents[4]
SNAP_DIR = REPO / "generated" / "heatmap_snapshots"
SLOTS = ["0930", "1000", "1030", "1100", "1130", "1400", "1430", "1500"]


def pick_snapshot(date_s: str, slot_s: str) -> Path:
    """选择快照文件：指定或自动挑最新。"""
    if date_s and slot_s:
        p = SNAP_DIR / f"snapshot_{date_s.replace('-', '')}_{slot_s}.csv"
        if p.exists():
            return p
        sys.exit(f"❌ 快照不存在: {p}")
    # auto: latest for given date (or any date)
    files = sorted(SNAP_DIR.glob("snapshot_*.csv"))
    if date_s:
        d = date_s.replace("-", "")
        files = [f for f in files if f.name.startswith(f"snapshot_{d}")]
    if not files:
        sys.exit(f"❌ {SNAP_DIR} 下无快照，请先用 market-snapshot 技能抓取")
    return files[-1]


def load_snapshot(path: Path):
    """返回 {code: chg_pct}。"""
    snap = {}
    with open(path, encoding="utf-8") as f:
        import csv
        for r in csv.DictReader(f):
            try:
                snap[r["code"]] = float(r["chg_pct"])
            except (ValueError, KeyError):
                continue
    return snap


def market_breadth(snap: dict):
    from statistics import median
    chgs = list(snap.values())
    up = sum(1 for c in chgs if c > 0)
    dn = sum(1 for c in chgs if c < 0)
    fl = len(chgs) - up - dn
    avg = sum(chgs) / len(chgs) if chgs else 0.0
    med = median(chgs) if chgs else 0.0
    zt = sum(1 for c in chgs if c >= 9.8)     # 涨停近似（10%/20cm按9.8起算粗口径）
    dt = sum(1 for c in chgs if c <= -9.8)    # 跌停近似
    big_up = sum(1 for c in chgs if c > 5)
    big_dn = sum(1 for c in chgs if c < -5)
    return {
        "n": len(chgs), "up": up, "down": dn, "flat": fl,
        "up_pct": up / len(chgs) * 100 if chgs else 0,
        "down_pct": dn / len(chgs) * 100 if chgs else 0,
        "avg": round(avg, 2), "median": round(med, 2),
        "limit_up": zt, "limit_down": dt,
        "big_up": big_up, "big_dn": big_dn,
    }


def weather_verdict(b: dict) -> str:
    ratio = b["up"] / (b["down"] + 1)
    avg = b["avg"]
    if b["n"] == 0:
        return "无数据"
    if ratio >= 3 and avg >= 1.5:
        return "🔥 强势普涨"
    if ratio >= 1.5 and avg >= 0.5:
        return "🌤 偏强"
    if ratio >= 0.8 and avg >= -0.3:
        return "🌥 震荡"
    if ratio >= 0.5:
        return "🌧 偏弱"
    return "⛈ 弱势"


def sector_weather(snap: dict, btype: str):
    """按板块统计涨/跌/平家数 + 平均涨跌。btype: 二级行业/一级行业/概念。"""
    from boards import fetch_block_stocks, load_boards
    blocks = [r for r in load_boards(btype)]
    out = []
    for b in blocks:
        code, name = b["code"], b.get("name", b["code"])
        try:
            total, stocks = fetch_block_stocks(code)
            time.sleep(0.25)
        except Exception:
            continue
        up = dn = fl = cnt = 0
        sumc = 0.0
        for s in stocks:
            c = snap.get(s["code"])
            if c is None:
                continue
            cnt += 1; sumc += c
            if c > 0: up += 1
            elif c < 0: dn += 1
            else: fl += 1
        out.append({
            "name": name, "code": code, "member": total, "matched": cnt,
            "up": up, "down": dn, "flat": fl,
            "avg_chg": round(sumc / cnt, 2) if cnt else None,
        })
    out.sort(key=lambda x: -(x["avg_chg"] if x["avg_chg"] is not None else -999))
    return out


def print_report(date_lbl, path, b, sectors, top_n=12):
    print(f"===== 全市场行情天气 · {date_lbl} =====")
    print(f"快照: {path.name}")
    print(f"样本: {b['n']} 只")
    print(f"📊 广度  涨 {b['up']} ({b['up_pct']:.1f}%) ｜ 跌 {b['down']} ({b['down_pct']:.1f}%) ｜ 平 {b['flat']}")
    print(f"     平均 {b['avg']:+.2f}% ｜ 中位 {b['median']:+.2f}% ｜ 涨停≈{b['limit_up']} 跌停≈{b['limit_down']}")
    print(f"     大涨>5% {b['big_up']} ｜ 大跌<-5% {b['big_dn']}")
    print(f"☁️ 温度: {weather_verdict(b)}")
    print()
    print("🏆 领涨板块 (按平均涨幅):")
    print(f"{'板块':<18s}{'成分':>4s} {'覆盖':>4s} {'涨':>3s} {'跌':>3s} {'平':>2s} {'均涨跌%':>8s}")
    for r in sectors[:top_n]:
        avg = f"{r['avg_chg']:+.2f}" if r['avg_chg'] is not None else "--"
        print(f"{r['name']:<18s}{r['member']:>4d} {r['matched']:>4d} {r['up']:>3d} {r['down']:>3d} {r['flat']:>2d} {avg:>8s}")
    print()
    print("📉 领跌板块:")
    print(f"{'板块':<18s}{'成分':>4s} {'覆盖':>4s} {'涨':>3s} {'跌':>3s} {'平':>2s} {'均涨跌%':>8s}")
    for r in sectors[-top_n:][::-1]:
        avg = f"{r['avg_chg']:+.2f}" if r['avg_chg'] is not None else "--"
        print(f"{r['name']:<18s}{r['member']:>4d} {r['matched']:>4d} {r['up']:>3d} {r['down']:>3d} {r['flat']:>2d} {avg:>8s}")


def qq(url, hdr=None):
    """HTTP GET helper。"""
    from httpget import httpget
    return httpget(url, timeout=15, headers=hdr or {
        'User-Agent': 'Mozilla/5.0 Chrome/126 Safari/537.36',
        'Referer': 'https://quote.eastmoney.com/'})


_K_TIP_CSS = """
.k-tip{position:fixed;z-index:99;background:#14181f;border:1px solid #2a313d;border-radius:8px;padding:4px;display:none;pointer-events:none;box-shadow:0 4px 16px rgba(0,0,0,.6)}
.k-tip img{width:280px;height:auto;display:block;border-radius:5px}
.k-tip .k-name{color:#9aa0a6;font-size:11px;padding:3px 6px}
tr.hover-row{cursor:pointer}
tr.hover-row:hover td{background:#1c2530}
"""

_K_TIP_JS = """
const KTS=__KTS__;
const ktip=document.createElement('div');ktip.className='k-tip';document.body.appendChild(ktip);
ktip.innerHTML='<div class="k-name">加载中…</div><img alt="K线">';
const kimg=ktip.querySelector('img'),kname=ktip.querySelector('.k-name');
document.querySelectorAll('tr.hover-row').forEach(tr=>{
  tr.addEventListener('mouseenter',()=>{
    const bk=tr.dataset.bk, name=tr.dataset.name;
    kname.textContent=name+' ('+bk+') · 东财K线(RSI)';
    kimg.src='https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=90.'+bk+'&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan='+KTS;
    ktip.style.display='block';
  });
  tr.addEventListener('mousemove',e=>{
    let x=e.clientX+16,y=e.clientY+12;
    if(x+292>innerWidth)x=e.clientX-296;
    if(y+240>innerHeight)y=e.clientY-230;
    ktip.style.left=x+'px';ktip.style.top=y+'px';
  });
  tr.addEventListener('mouseleave',()=>{ktip.style.display='none'});
});
"""


def sect_table(rows, label) -> str:
    thead = ("<thead><tr><th>板块</th><th>成分</th><th>覆盖</th>"
             "<th>涨</th><th>跌</th><th>平</th><th>平均涨跌%</th></tr></thead>")
    body = ""
    for r in rows:
        avg = f"{r['avg_chg']:+.2f}" if r['avg_chg'] is not None else "--"
        cls = "pos" if (r['avg_chg'] or 0) >= 0 else "neg"
        page = f"https://quote.eastmoney.com/bk/90.{r['code']}.html"
        body += (
            f'<tr class="hover-row" data-bk="{r['code']}" data-name="{r['name']}">'
            f"<td><a href='{page}' target='_blank'>{r['name']}</a> "
            f"<a class='stk-hot' data-bk='{r['code']}' data-name='{r['name']}' title='查看该板块成分股（按当日PL降序）'>个股</a></td>"
            f"<td>{r['member']}</td><td>{r['matched']}</td>"
            f"<td class='pos'>{r['up']}</td><td class='neg'>{r['down']}</td><td>{r['flat']}</td>"
            f"<td class='{cls}'>{avg}</td></tr>")
    return f"<h2>{label}</h2><table>{thead}<tbody>{body}</tbody></table>"


def render_html(date_lbl, b, sectors, top_n, out) -> str:
    ts = int(time.time())
    up = sum(1 for s in sectors if (s['avg_chg'] or 0) > 0)
    dn = len(sectors) - up
    leaders = [s for s in sectors if s['avg_chg'] is not None][:top_n]
    laggers = [s for s in sectors if s['avg_chg'] is not None][-top_n:]
    top_tbl = sect_table(leaders, "🏆 领涨板块（悬停查看东财K线）")
    bot_tbl = sect_table(laggers[::-1], "📉 领跌板块（悬停查看东财K线）")
    pos_c = ("pos" if b['avg'] >= 0 else "neg")
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>全市场天气 · {date_lbl}</title>
<style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#101418;color:#e8eaed}}
.wrap{{max-width:1000px;margin:0 auto;padding:18px}}
.top{{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}
h1{{font-size:20px;margin:0}} .date{{color:#9aa0a6;font-size:13px}}
.verdict{{font-size:22px;font-weight:700}}
.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0}}
.card{{background:#151a21;border-radius:10px;padding:12px 16px;min-width:120px}}
.card b{{font-size:18px;color:#fff}} .card span{{color:#8a919b;font-size:11px}}
.pos{{color:#ff4d4f}}.neg{{color:#2ecc71}}.mid{{color:#d6b35c}}
table{{width:100%;border-collapse:collapse;background:#14181f;border-radius:10px;overflow:hidden;margin:8px 0 20px}}
th,td{{padding:7px 10px;font-size:12px;text-align:right}} th{{background:#1c2129}} td:first-child,th:first-child{{text-align:left}}
td a{{color:#8ab4ff;text-decoration:none}} td a:hover{{text-decoration:underline}}
h2{{font-size:15px;margin:16px 0 4px;color:#c9ced6}}
.foot{{color:#6b7280;font-size:11px;margin-top:18px}}
.stk-hot{{color:#ffc94d;font-size:11px;text-decoration:none;border:1px solid #ffc94d44;border-radius:4px;padding:1px 5px;margin-left:6px;cursor:pointer}}
.stk-hot:hover{{background:#ffc94d22}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:999;justify-content:center;align-items:flex-start;overflow:auto}}
.modal.show{{display:flex}}
.modal-box{{background:#14181f;border:1px solid #2a313d;border-radius:10px;margin:4vh auto;width:min(860px,92vw);max-height:80vh;display:flex;flex-direction:column}}
.modal-head{{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #2a313d}}
.modal-head #modal-title{{font-weight:700;font-size:14px}}
.modal-x{{background:none;border:none;color:#ff4d4f;font-size:20px;cursor:pointer}}
.modal-body{{overflow:auto;padding:6px 10px}}
.loading{{color:#9aa0a6;padding:20px;text-align:center}}
{_K_TIP_CSS}
</style></head><body><div class="wrap">
<div class="top"><h1>☁️ 全市场行情天气</h1><span class="date">{date_lbl}</span></div>
<div class="verdict ">{weather_verdict(b)}</div>
<div class="cards">
<div class="card"><span>样本</span><br><b>{b['n']}</b></div>
<div class="card"><span>上涨</span><br><b class="pos">{b['up']} ({b['up_pct']:.1f}%)</b></div>
<div class="card"><span>下跌</span><br><b class="neg">{b['down']} ({b['down_pct']:.1f}%)</b></div>
<div class="card"><span>平盘</span><br><b>{b['flat']}</b></div>
<div class="card"><span>平均涨跌</span><br><b class="{pos_c}">{b['avg']:+.2f}%</b></div>
<div class="card"><span>中位数</span><br><b>{b['median']:+.2f}%</b></div>
<div class="card"><span>涨停≈/跌停≈</span><br><b class="pos">{b['limit_up']}</b><b> / </b><b class="neg">{b['limit_down']}</b></div>
</div>
{top_tbl}
{bot_tbl}
<div id="stk-modal" class="modal"><div class="modal-box"><div class="modal-head"><span id="modal-title">个股</span><button class="modal-x" onclick="closeStk()">×</button></div><div class="modal-body" id="modal-body"><div class="loading">加载中…</div></div></div></div>
<div class="foot">数据: {out.name} · 东财官方K线悬停预览 · {up}涨/{dn}跌板块 · 纯技术参考</div>
</div>
<script>{_K_TIP_JS.replace('__KTS__', str(ts))}{_STK_JS}</script>
</body></html>"""
    return html


_STK_JS = """
// 个股弹窗：点击板块行内"个股"，拉取该板块成分股（按当日涨跌幅PL降序）
const modal=document.getElementById('stk-modal'),mtitle=document.getElementById('modal-title'),mbody=document.getElementById('modal-body');
function closeStk(){modal.classList.remove('show')}
// ESC 关闭弹窗 / 隐藏K线 tooltip
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeStk();if(ktip)ktip.style.display='none';}});
modal.addEventListener('click',e=>{if(e.target===modal||e.target.classList.contains('modal-x'))closeStk();});
document.querySelectorAll('.stk-hot').forEach(btn=>{
  btn.addEventListener('click',async e=>{
    e.preventDefault();e.stopPropagation();
    const bk=btn.dataset.bk,name=btn.dataset.name;
    mtitle.textContent=name+' ('+bk+') 成分股 · 按当日PL降序';mbody.innerHTML='<div class="loading">加载中…</div>';
    modal.classList.add('show');
    const url='https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=200&po=1&np=1&fltt=2&invt=2&fid=f3&fs=b:'+bk+'&fields=f12,f14,f2,f3,f20';
    try{
      const r=await fetch(url);const j=await r.json();const diff=j.data.diff;
      if(!diff||!diff.length){mbody.innerHTML='<div class="loading">无数据</div>';return;}
      const fmt=v=>{v=Number(v);return isNaN(v)?'--':v.toFixed(2);};
      const fmtm=v=>{v=Number(v);return isNaN(v)?'--':(v/1e8).toFixed(2)+'亿';};
      const rows=diff.map(s=>{
        const pct=Number(s.f3)||0;
        return '<tr class="hover-row" data-bk="'+s.f12+'" data-name="'+s.f14+'" data-market="'+(String(s.f12)[0]==='6'?'1':'0')+'">'
          +'<td>'+s.f12+'</td><td>'+s.f14+'</td><td>'+fmt(s.f2)+'</td>'
          +'<td class="'+(pct>=0?'pos':'neg')+'">'+(pct>0?'+':'')+fmt(pct)+'%</td><td>'+fmtm(s.f20)+'</td></tr>';
      }).join('');
      mbody.innerHTML='<table><thead><tr><th>代码</th><th>名称</th><th>现价</th><th>涨跌%</th><th>总市值</th></tr></thead><tbody>'+rows+'</tbody></table>';
      // 弹窗内个股行绑定悬停K线
      mbody.querySelectorAll('tr.hover-row').forEach(tr=>{
        tr.addEventListener('mouseenter',()=>{
          const code=tr.dataset.bk, name=tr.dataset.name, mkt=tr.dataset.market||(String(code)[0]==='6'?'1':'0');
          kname.textContent=name+' ('+code+') · 东财K线';
          kimg.src='https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid='+mkt+'.'+code+'&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan='+KTS;
          ktip.style.display='block';
        });
        tr.addEventListener('mousemove',e=>{
          let x=e.clientX+16,y=e.clientY+12;
          if(x+292>innerWidth)x=e.clientX-296;
          if(y+240>innerHeight)y=e.clientY-230;
          ktip.style.left=x+'px';ktip.style.top=y+'px';
        });
        tr.addEventListener('mouseleave',()=>{ktip.style.display='none'});
      });
    }catch(err){mbody.innerHTML='<div class="loading">加载失败: '+err+'</div>';}
  });
});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="交易日 YYYY-MM-DD")
    ap.add_argument("--slot", default="", help="时点 0930..1500")
    ap.add_argument("--snapshot", default="", help="直接指定快照 CSV")
    ap.add_argument("--sector", default="二级行业", help="板块粒度 二级行业/一级行业/概念")
    ap.add_argument("--top", type=int, default=12, help="前后各显示板块数")
    ap.add_argument("--out", default="", help="HTML 输出路径")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--html", action="store_true", help="生成 embed HTML（板块悬停东财K线图）")
    args = ap.parse_args()

    path = Path(args.snapshot) if args.snapshot else pick_snapshot(args.date, args.slot)
    if not Path(path).exists():
        sys.exit(f"❌ 快照不存在: {path}")
    snap = load_snapshot(path)
    b = market_breadth(snap)
    sec = sector_weather(snap, args.sector)

    if args.json:
        print(json.dumps({
            "snapshot": str(path), "breadth": b,
            "verdict": weather_verdict(b), "sectors": sec,
        }, ensure_ascii=False, indent=2))
        return

    date_lbl = path.stem.replace("snapshot_", "")
    if args.html:
        out = Path(args.out) if args.out else REPO / "generated" / f"weather_{date_lbl}_{args.sector}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(date_lbl, b, sec, args.top, out), encoding="utf-8")
        print(f"📄 HTML 已生成: {out}")
        try:
            import subprocess
            subprocess.Popen(["open", str(out)])
        except Exception:
            pass
        return

    print_report(date_lbl, path, b, sec, args.top)


if __name__ == "__main__":
    main()
