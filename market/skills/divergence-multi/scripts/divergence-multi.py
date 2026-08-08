#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
divergence-multi: 多指标共振背离检测（MACD+RSI+KDJ+量价）。

对每只股票的最后两个摆动低点/高点，分别判断 4 个指标的背离：
  RSI(14)   — 指标低点抬高 / 高点降低
  MACD DIF  — DIF 低点抬高 / 高点降低
  KDJ K     — K 值低点抬高 / 高点降低
  量价      — 低点缩量（地量）/ 高点缩量

共振评分 = 背离指标数（0-4）。共振越强信号越可靠（底背离.md 多指标共振原则）。

作用域: 全部已缓存 kline 的股票（generated/cache/kline/*.json），或 --block/--account/代码列表。

用法:
  python3 divergence-multi.py                  # 扫全部缓存股票
  python3 divergence-multi.py --min-score 3    # 只看≥3指标共振
  python3 divergence-multi.py --account 7维选股
  python3 divergence-multi.py --block BK0448 --top 20
  python3 divergence-multi.py 600775 300620 --json
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import kline_cache_dir, fetch_kline, resolve_name  # noqa: E402

_name_cache = {}
_plot_ready = False


def _init_plot():
    global _plot_ready
    if _plot_ready:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    _plot_ready = True


def plot_multi(code: str, win: int = 5, out=None):
    """多指标背离标注图：K线 + RSI + MACD + KDJ 四面板 + 背离连线。"""
    _init_plot()
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    name, pts = fetch_kline(code, lmt=120)
    if not pts:
        return None
    df = pd.DataFrame(pts)
    df["date"] = pd.to_datetime(df["date"])
    name = fix_name(code, name)
    closes = df["close"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    rsi_s = rsi_series(closes)
    dif_s = macd_dif_series(closes)
    k_s = kdj_k_series(highs, lows, closes)
    hi, lo = swings(highs, lows, win)
    dets = detect_multi(df, win)
    xn = mdates.date2num(df["date"])

    fig, axes = plt.subplots(4, 1, figsize=(13, 13), sharex=True,
                             gridspec_kw={"height_ratios": [3.2, 1, 1, 1]})
    title_parts = [f"{name} ({code})"]
    for det in dets:
        icon = "底背离" if det["type"] == "底背离" else "顶背离"
        title_parts.append(f"{icon} {'+'.join(det['indicators'])} {det['p1_date']}→{det['p2_date']}")
    fig.suptitle(" | ".join(title_parts), fontsize=12, fontweight="bold", color="#222")

    ax = axes[0]
    for i, r in df.iterrows():
        up = r["close"] >= r["open"]
        c = "#d63031" if up else "#2ecc71"
        ax.vlines(xn[i], r["low"], r["high"], color=c, lw=1)
        ax.add_patch(plt.Rectangle((xn[i] - 0.3, min(r["open"], r["close"])), 0.6,
                                   abs(r["close"] - r["open"]) or 0.01, color=c, alpha=0.9))
    for det in dets:
        i1 = (df["date"] == pd.Timestamp(det["p1_date"])).idxmax()
        i2 = (df["date"] == pd.Timestamp(det["p2_date"])).idxmax()
        ax.plot([xn[i1], xn[i2]], [det["p1"], det["p2"]], color="#f03e3e", lw=1.6, ls="--")
        ax.scatter([xn[i1], xn[i2]], [det["p1"], det["p2"]], color="#f03e3e", s=35, zorder=5)
    ax.set_ylabel("价格"); ax.grid(alpha=0.2)

    panels = [("RSI", rsi_s, axes[1]), ("MACD", dif_s, axes[2]), ("KDJ", k_s, axes[3])]
    for pname, series, axp in panels:
        axp.plot(xn, series, color="#7048e8", lw=1.1)
        for det in dets:
            if pname in det["indicators"]:
                i1 = (df["date"] == pd.Timestamp(det["p1_date"])).idxmax()
                i2 = (df["date"] == pd.Timestamp(det["p2_date"])).idxmax()
                axp.plot([xn[i1], xn[i2]], [series[i1], series[i2]], color="#f03e3e", lw=1.6, ls="--")
        axp.set_ylabel(pname); axp.grid(alpha=0.2)
    if dets:
        det = dets[0]
        i1 = (df["date"] == pd.Timestamp(det["p1_date"])).idxmax()
        i2 = (df["date"] == pd.Timestamp(det["p2_date"])).idxmax()
        axd = axes[1]
        axd.axhline(30, color="#888", lw=0.6, ls="--"); axd.axhline(70, color="#888", lw=0.6, ls="--")
        axk = axes[3]
        axk.axhline(20, color="#888", lw=0.6, ls="--"); axk.axhline(80, color="#888", lw=0.6, ls="--")
    axes[2].axhline(0, color="#888", lw=0.5)
    axes[3].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    fig.tight_layout()
    outp = Path(out) if out else Path.cwd() / "generated" / f"divergence_multi_{code}.png"
    outp.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outp, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return str(outp)


def fix_name(code, name):
    """名称兜底：name==code 时用 suggest 接口解析（带缓存）。"""
    if name and name != code:
        return name
    if code not in _name_cache:
        try:
            _name_cache[code] = resolve_name(code)
        except Exception:
            _name_cache[code] = code
    return _name_cache[code]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"


# ---------- 指标 ----------
def rsi_series(closes, n=14):
    rsi_s = [None] * len(closes)
    if len(closes) > n:
        gains = losses = 0.0
        for i in range(1, n + 1):
            d = closes[i] - closes[i - 1]
            gains += max(d, 0); losses += max(-d, 0)
        for i in range(n, len(closes)):
            if i > n:
                d = closes[i] - closes[i - 1]
                gains = gains * (n - 1) / n + max(d, 0)
                losses = losses * (n - 1) / n + max(-d, 0)
            rsi_s[i] = 100 - 100 / (1 + gains / losses) if losses > 0 else 50.0
    return rsi_s


def ema_series(vals, n):
    out = [None] * len(vals)
    k = 2 / (n + 1)
    prev = None
    for i, v in enumerate(vals):
        prev = v if prev is None else v * k + prev * (1 - k)
        out[i] = prev
    return out


def macd_dif_series(closes, fast=12, slow=26):
    e12 = ema_series(closes, fast)
    e26 = ema_series(closes, slow)
    return [None if (a is None or b is None) else a - b for a, b in zip(e12, e26)]


def kdj_k_series(highs, lows, closes, n=9):
    k_out = [None] * len(closes)
    prev_k = 50.0
    for i in range(len(closes)):
        if i < n - 1:
            continue
        hh = max(highs[i - n + 1:i + 1])
        ll = min(lows[i - n + 1:i + 1])
        rsv = (closes[i] - ll) / (hh - ll) * 100 if hh > ll else 50.0
        prev_k = prev_k * 2 / 3 + rsv / 3
        k_out[i] = prev_k
    return k_out


def swings(highs, lows, win=5, live=False):
    """摆动极值。live=True: 右窗口截断到数据末尾（最后一根可作候选摆动点=即时检测）。"""
    if live:
        N = len(highs)
        hi = [(i, highs[i]) for i in range(win, N)
              if highs[i] == max(highs[max(0, i - win):min(N, i + win + 1)])]
        lo = [(i, lows[i]) for i in range(win, N)
              if lows[i] == min(lows[max(0, i - win):min(N, i + win + 1)])]
        return hi, lo
    hi = [(i, highs[i]) for i in range(win, len(highs) - win)
          if highs[i] == max(highs[i - win:i + win + 1])]
    lo = [(i, lows[i]) for i in range(win, len(lows) - win)
          if lows[i] == min(lows[i - win:i + win + 1])]
    return hi, lo


def check_div(ind_series, p1_idx, p2_idx, direction):
    """direction='low' 底背离 / 'high' 顶背离。返回 True/False。"""
    a, b = ind_series[p1_idx], ind_series[p2_idx]
    if a is None or b is None:
        return False
    if direction == "low":
        return b > a  # 指标低点抬高
    return b < a  # 指标高点降低


# ---------- 检测 ----------
def detect_multi(df, win=5, live=False):
    """返回 {type, score, indicators, points}。live=True 时含"待确认"摆动点。"""
    import pandas as pd
    closes = df["close"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    vols = df["volume"].astype(float).tolist() if "volume" in df else [None] * len(closes)

    rsi_s = rsi_series(closes)
    dif_s = macd_dif_series(closes)
    k_s = kdj_k_series(highs, lows, closes)

    hi, lo = swings(highs, lows, win, live=live)
    out = []
    # 底背离（方向 low）
    if len(lo) >= 2:
        (i1, p1), (i2, p2) = lo[-2], lo[-1]
        if p2 < p1:
            inds = []
            if check_div(rsi_s, i1, i2, "low"): inds.append("RSI")
            if check_div(dif_s, i1, i2, "low"): inds.append("MACD")
            if check_div(k_s, i1, i2, "low"): inds.append("KDJ")
            if vols[i2] is not None and vols[i1] is not None and vols[i2] < vols[i1] * 0.97:
                inds.append("量价")
            if inds:
                out.append({"type": "底背离", "score": len(inds), "indicators": inds,
                            "p1_date": df["date"].iloc[i1], "p1": round(p1, 2),
                            "p2_date": df["date"].iloc[i2], "p2": round(p2, 2)})
    # 顶背离（方向 high）
    if len(hi) >= 2:
        (i1, p1), (i2, p2) = hi[-2], hi[-1]
        if p2 > p1:
            inds = []
            if check_div(rsi_s, i1, i2, "high"): inds.append("RSI")
            if check_div(dif_s, i1, i2, "high"): inds.append("MACD")
            if check_div(k_s, i1, i2, "high"): inds.append("KDJ")
            if vols[i2] is not None and vols[i1] is not None and vols[i2] < vols[i1] * 0.97:
                inds.append("量价")
            if inds:
                out.append({"type": "顶背离", "score": len(inds), "indicators": inds,
                            "p1_date": df["date"].iloc[i1], "p1": round(p1, 2),
                            "p2_date": df["date"].iloc[i2], "p2": round(p2, 2)})
    return out


# ---------- 目标收集 ----------
def cached_stocks():
    out = []
    for f in kline_cache_dir().glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("points"):
                out.append((f.stem, d.get("name") or f.stem))
        except Exception:
            pass
    return out


def block_stocks(bk):
    out, pn = [], 1
    while True:
        p = subprocess.run(["curl", "-sS", "--max-time", "12", "-H", f"User-Agent: {UA}",
                            "-H", "Referer: https://quote.eastmoney.com/",
                            f"https://push2delay.eastmoney.com/api/qt/clist/get?pn={pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f20&fs=b:{bk}&fields=f12,f14"],
                           capture_output=True, text=True)
        if p.returncode != 0 or not p.stdout.strip():
            break
        d = json.loads(p.stdout)
        diff = (d.get("data") or {}).get("diff") or []
        out += [(r["f12"], r["f14"]) for r in diff]
        if len(out) >= ((d.get("data") or {}).get("total") or 0):
            break
        pn += 1
    return out


def account_stocks(account):
    p = subprocess.run(["python3", PORTFOLIO, "--account", account, "show", "--json"],
                       capture_output=True, text=True, timeout=30)
    pf = json.loads(p.stdout)
    pos = pf["positions"]
    if isinstance(pos, dict):
        return [(k, v.get("name", k)) for k, v in pos.items()]
    return [(x["code"], x["name"]) for x in pos]


def render_view(results, scanned, out=None):
    """生成背离看板 HTML（筛选 + 悬停东财K线）。"""
    import time
    from datetime import datetime
    n_b = sum(1 for r in results if r["type"] == "底背离")
    n_t = len(results) - n_b
    n3 = sum(1 for r in results if r["score"] >= 3)
    R = json.dumps(results, ensure_ascii=False)
    TS = int(time.time())
    css = """body{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#0f1216;color:#e8eaed}
.wrap{max-width:1100px;margin:0 auto;padding:20px}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#9aa0a6;font-size:12px;margin-bottom:16px}
.cards{display:flex;gap:14px;margin-bottom:18px;flex-wrap:wrap}
.card{background:#14181f;border-radius:12px;padding:14px 20px;min-width:130px;border:1px solid #1e252f}
.card .num{font-size:26px;font-weight:700}
.card .lab{color:#9aa0a6;font-size:12px;margin-top:2px}
.card.red .num{color:#ff6b6b}.card.green .num{color:#2ecc71}.card.blue .num{color:#4aa8ff}
.filters{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.fbtn{padding:6px 16px;border-radius:8px;border:1px solid #2a313d;background:#161b22;color:#d6dae0;cursor:pointer;font-size:13px}
.fbtn.active{background:#3a5a8a;border-color:#3a5a8a;color:#fff}
table{width:100%;border-collapse:collapse;background:#14181f;border-radius:12px;overflow:hidden}
th,td{padding:9px 12px;font-size:13px;text-align:left;border-bottom:1px solid #1c2129}
th{background:#1c2129;color:#9aa0a6;font-weight:600}
tr.hover-row{cursor:pointer}
tr.hover-row:hover td{background:#1a2230}
.sc{display:inline-block;border-radius:6px;padding:2px 8px;font-weight:700;font-size:12px}
.sc3{background:#3a1d1f;color:#ff6b6b}.sc2{background:#232a35;color:#9aa0a6}
.tag{display:inline-block;border-radius:5px;padding:1px 7px;font-size:11px;margin-right:4px}
.tag-rsi{background:#3a2d12;color:#f0b45a}.tag-macd{background:#123a3a;color:#4ad0d0}
.tag-kdj{background:#1d3a12;color:#8ae05a}.tag-vol{background:#2a123a;color:#c05ad0}
.bull{color:#ff6b6b}.bear{color:#4aa8ff}
.hint{color:#5c6572;font-size:12px;margin-bottom:10px}
.k-tip{position:fixed;z-index:99;background:#14181f;border:1px solid #2a313d;border-radius:8px;padding:4px;display:none;pointer-events:none;box-shadow:0 4px 16px rgba(0,0,0,.6)}
.k-tip img{width:260px;height:auto;display:block;border-radius:5px}
.k-tip .k-name{color:#9aa0a6;font-size:11px;padding:3px 6px}"""
    head = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>多指标共振背离看板</title>
<style>{css}</style></head><body><div class="wrap">
<h1>📊 多指标共振背离看板（MACD+RSI+KDJ+量价）</h1>
<div class="sub">股票池 {scanned} 只 ｜ 生成 {datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 共振分 = 背离指标数</div>
<div class="cards">
<div class="card"><div class="num">{len(results)}</div><div class="lab">背离总数</div></div>
<div class="card red"><div class="num">{n_b}</div><div class="lab">🔴 底背离</div></div>
<div class="card green"><div class="num">{n_t}</div><div class="lab">🟢 顶背离</div></div>
<div class="card blue"><div class="num">{n3}</div><div class="lab">⭐ 三重共振</div></div>
</div>
<div class="filters">
<button class="fbtn active" data-f="all">全部</button>
<button class="fbtn" data-f="底背离">🔴 底背离</button>
<button class="fbtn" data-f="顶背离">🟢 顶背离</button>
<button class="fbtn" data-f="3">⭐ ≥3 共振</button>
</div>
<div class="hint">🖱 悬停股票行查看东财K线图</div>
<table><thead><tr><th>股票</th><th>方向</th><th>共振</th><th>指标</th><th>摆动1</th><th>摆动2</th></tr></thead>
<tbody id="tb"></tbody></table>
</div>"""
    js = f"""<script>
const R=__DATA__, KTS={TS};
const tb=document.getElementById('tb');
const IN={{RSI:'tag-rsi',MACD:'tag-macd',KDJ:'tag-kdj','量价':'tag-vol'}};
const ktip=document.createElement('div');ktip.className='k-tip';document.body.appendChild(ktip);
ktip.innerHTML='<div class="k-name"></div><img alt="K线">';
const kimg=ktip.querySelector('img'),kname=ktip.querySelector('.k-name');
function bindHover(){{
  document.querySelectorAll('tr.hover-row').forEach(tr=>{{
    tr.onmouseenter=()=>{{
      const c=tr.dataset.code;
      kname.textContent=tr.dataset.name+' ('+c+') · 东财K线';
      kimg.src='https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid='+(c[0]==='6'?'1.':'0.')+c+'&type=&unitWidth=-6&ef=&formula=RSI&AT=1&imageType=KXL&timespan='+KTS;
      ktip.style.display='block';
    }};
    tr.onmousemove=e=>{{
      let x=e.clientX+16,y=e.clientY+12;
      if(x+270>innerWidth)x=e.clientX-276;
      if(y+220>innerHeight)y=e.clientY-210;
      ktip.style.left=x+'px';ktip.style.top=y+'px';
    }};
    tr.onmouseleave=()=>{{ktip.style.display='none'}};
  }});
}}
function render(f){{
  let rs=R.filter(r=>{{
    if(f==='all')return true;
    if(f==='3')return r.score>=3;
    return r.type===f;
  }}).sort((a,b)=>b.score-a.score);
  tb.innerHTML=rs.map(r=>{{
    const tags=r.indicators.map(i=>'<span class="tag '+(IN[i]||'')+'">'+i+'</span>').join('');
    const sc=r.score>=3?'<span class="sc sc3">'+r.score+'重</span>':'<span class="sc sc2">'+r.score+'重</span>';
    const dir=r.type==='底背离'?'<span class="bull">🔴 底背离</span>':'<span class="bear">🟢 顶背离</span>';
    return '<tr class="hover-row" data-code="'+r.code+'" data-name="'+r.name+'">'+
      '<td><b>'+r.name+'</b> <span style="color:#5c6572">'+r.code+'</span></td>'+
      '<td>'+dir+'</td><td>'+sc+'</td><td>'+tags+'</td>'+
      '<td>'+r.p1_date+' ('+r.p1+')</td><td>'+r.p2_date+' ('+r.p2+')</td></tr>';
  }}).join('')||'<tr><td colspan="6" style="text-align:center;color:#5c6572">无匹配</td></tr>';
  bindHover();
}}
render('all');
document.querySelectorAll('.fbtn').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.fbtn').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');render(b.dataset.f);
}});
</script></body></html>"""
    html = head + js.replace("__DATA__", R)
    outp = Path(out) if out else Path.cwd() / "generated" / "divergence_multi_view.html"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"✅ 看板: {outp} ({outp.stat().st_size/1024:.0f} KB)")


def main():
    ap = argparse.ArgumentParser(description="多指标共振背离检测（MACD+RSI+KDJ+量价）")
    ap.add_argument("codes", nargs="*", help="代码列表")
    ap.add_argument("--block", help="板块")
    ap.add_argument("--account", help="组合账户")
    ap.add_argument("--cache", action="store_true", default=True, help="扫全部缓存股票（默认）")
    ap.add_argument("--min-score", type=int, default=2, help="最低共振分（默认 2）")
    ap.add_argument("--recent", type=int, default=0, help="只看最近 N 天内新形成的背离（按摆动2日期）")
    ap.add_argument("--live", action="store_true", help="即时检测：右窗口截断，捕捉当天新背离（待确认）")
    ap.add_argument("--end-date", default="", help="数据截断日（YYYY-MM-DD）——生成该日收盘后视角")
    ap.add_argument("--top", type=int, default=0, help="输出条数（0=全部）")
    ap.add_argument("--window", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--view", action="store_true", help="生成看板 HTML（含 hover 东财K线）")
    ap.add_argument("--plot", action="store_true", help="对指定代码出多指标背离图（PNG）")
    args = ap.parse_args()

    if args.block:
        targets = block_stocks(args.block); label = f"板块 {args.block}"
    elif args.account:
        targets = account_stocks(args.account); label = f"组合 {args.account}"
    elif args.codes:
        targets = [(c, "") for c in args.codes]; label = "代码列表"
    else:
        targets = cached_stocks(); label = f"缓存股票池"

    print(f"{label}：{len(targets)} 只，检测中…", file=sys.stderr)
    import pandas as pd
    all_res = []
    for i, (code, name) in enumerate(targets):
        try:
            nm, pts = fetch_kline(code, lmt=120)
            if not pts:
                continue
            df = pd.DataFrame(pts)
            if args.end_date:
                df["date"] = pd.to_datetime(df["date"])
                df = df[df["date"] <= pd.Timestamp(args.end_date)]
            for d in detect_multi(df, args.window, live=args.live):
                d = {"code": code, "name": fix_name(code, name or nm), **d}
                if d["score"] >= args.min_score:
                    all_res.append(d)
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(targets)}", file=sys.stderr, flush=True)

    if args.recent > 0:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=args.recent)).strftime("%Y-%m-%d")
        all_res = [r for r in all_res if r["p2_date"] >= cutoff]
        print(f"  [--recent {args.recent}] 筛选: 摆动2 ≥ {cutoff} → {len(all_res)} 条", file=sys.stderr)

    all_res.sort(key=lambda r: (-r["score"], r["type"]))
    if args.top > 0:
        all_res = all_res[:args.top]

    if args.plot:
        for code, _ in targets:
            p = plot_multi(code, args.window)
            print(f"  {p}" if p else f"  {code} 无数据")
        return
    if args.view:
        render_view(all_res, len(targets), None)
        return
    if args.json:
        print(json.dumps({"scanned": len(targets), "results": all_res}, ensure_ascii=False, indent=1))
        return

    n_b = sum(1 for r in all_res if r["type"] == "底背离")
    n_t = len(all_res) - n_b
    print(f"\n=== {label} 多指标共振背离 {len(all_res)} 条（底 {n_b} / 顶 {n_t}，≥{args.min_score}指标共振）===")
    for r in all_res:
        icon = "🔴底" if r["type"] == "底背离" else "🟢顶"
        inds = "+".join(r["indicators"])
        print(f"{icon} 共振{r['score']} [{inds:12s}] {r['code']} {r['name']:8s} "
              f"{r['p1_date']}({r['p1']}) → {r['p2_date']}({r['p2']})")


if __name__ == "__main__":
    main()
