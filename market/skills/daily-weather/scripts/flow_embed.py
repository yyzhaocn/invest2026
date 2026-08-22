#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow-embed: 生成 N 日主力/超大单/大单资金流 embed HTML（自包含，可 iframe 嵌入笔记/网页）。
柱状图（主力/超大单/大单/中单/小单）+ 收盘价折线。
数据源：东财 push2his fflow（新浪兜底），与 flow-chart 技能一致。
"""
import argparse, json, sys, time
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

REPO = Path(__file__).resolve().parents[4]


def fetch_flow(code, days):
    """优先东财 fflow，失败用新浪兜底，统一返回 rows 列表。"""
    fc = Path('/Users/yyz/.agents/skills/stock/flow-chart/scripts/flow-chart.py')
    spec = importlib.util.spec_from_file_location("fc", fc)
    fcmod = importlib.util.module_from_spec(spec)
    sys.modules["fc"] = fcmod
    spec.loader.exec_module(fcmod)
    try:
        name, rows = fcmod.fetch_flow(code, lmt=days)
        return name, rows
    except Exception:
        pass
    # sina fallback
    from httpget import httpget
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs'
    params = {'daima': ('sh' if code[0] == '6' else 'sz') + code, 'num': str(days), 'sort': 'opendate', 'asc': '0'}
    r = httpget(url, params=params, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
    data = json.loads(r.text)[::-1]
    rows = []
    for x in data:
        try:
            rows.append({
                "date": x["opendate"],
                "main": float(x["r0_net"]),
                "xbig": float(x.get("r0x_net") or 0),
                "big": float(x.get("r0_na") or 0),
                "mid": float(x.get("r0_mid") or 0),
                "small": float(x.get("r0_small") or 0),
                "close": float(x["trade"]),
                "pct": float(x["changeratio"]) * 100,
            })
        except Exception:
            continue
    return code, rows[-days:]


def render(name, code, rows, out, title=None):
    ts = int(time.time())
    if not rows:
        out.write_text("no data", encoding="utf-8")
        print("❌ 无数据"); return
    # rows chronological oldest->newest (flow-chart returns that order)
    r = rows
    dates = [x["date"][5:] for x in r]
    close = [x["close"] for x in r]
    main = [x["main"] / 1e4 for x in r]
    xbig = [x["xbig"] / 1e4 for x in r]
    big = [x["big"] / 1e4 for x in r]
    mid = [x["mid"] / 1e4 for x in r]
    small = [x["small"] / 1e4 for x in r]
    # cumulative 大单 (9日)
    cbig2 = [0.0]
    for v in big[1:]:
        cbig2.append(cbig2[-1] + v)
    tt = title or f"{name}({code}) · {len(r)}日大单资金流"
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{tt}</title>
<style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;background:#101418;color:#e8eaed}}
.wrap{{max-width:760px;margin:0 auto;padding:14px}}
h1{{font-size:16px;margin:0 0 4px}} .sub{{color:#9aa0a6;font-size:11px}}
.legend{{display:flex;gap:14px;font-size:11px;color:#9aa0a6;margin:8px 0}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px}}
table{{width:100%;border-collapse:collapse;background:#14181f;border-radius:8px;overflow:hidden;font-size:11px}}
th,td{{padding:5px 6px;text-align:right}} th{{background:#1c2129}} td:first-child,th:first-child{{text-align:left}}
.pos{{color:#ff4d4f}}.neg{{color:#2ecc71}}.dim{{color:#8a919b}}
.bar{{display:flex;align-items:center;gap:6px}} .brow{{height:8px;border-radius:2px;min-width:1px}}
</style></head><body><div class="wrap">
<h1>{tt}</h1>
<div class="sub">单位: 万元 ｜ 柱状=超大单/大单/中单/小单净流入 ｜ 折线=收盘价</div>
<div class="legend"><span><span class="dot" style="background:#ff4d4f"></span>超大单</span><span><span class="dot" style="background:#ffb020"></span>大单</span><span><span class="dot" style="background:#5aa6ff"></span>中单</span><span><span class="dot" style="background:#9aa0a6"></span>小单</span></div>
<table>
<thead><tr><th>日期</th><th>收盘</th><th>主力</th><th>超大单</th><th>大单</th><th>中单</th><th>小单</th></tr></thead>
<tbody>"""
    for i in range(len(r)):
        def c(v):
            return "pos" if v > 0 else ("neg" if v < 0 else "dim")
        html += (f"<tr><td>{dates[i]}</td>"
                 f"<td>{close[i]:.2f} ({r[i]['pct']:+.1f}%)</td>"
                 f"<td class=\"{c(main[i])}\">{main[i]:+.0f}</td>"
                 f"<td class=\"{c(xbig[i])}\">{xbig[i]:+.0f}</td>"
                 f"<td class=\"{c(big[i])}\">{big[i]:+.0f}</td>"
                 f"<td class=\"{c(mid[i])}\">{mid[i]:+.0f}</td>"
                 f"<td class=\"{c(small[i])}\">{small[i]:+.0f}</td></tr>")
    c9 = sum(big)
    html += f"""</tbody></table>
<div class="sub" style="margin-top:8px">9日大单累计: <b class="{"pos" if c9>=0 else "neg"}">{c9:+.0f}万</b></div>
<div class="foot" style="color:#6b7280;font-size:10px;margin-top:12px">drv:{name}({code}) · 生成 {time.strftime('%m-%d %H:%M')}</div>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"📄 HTML: {out}")
    try:
        import subprocess
        subprocess.Popen(["open", str(out)])
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("--days", type=int, default=9)
    ap.add_argument("--out", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--json-input", default="", help="直接读东财flow JSON文件(含 rows)，避免接口风控")
    args = ap.parse_args()
    code = str(args.code).zfill(6)
    if args.json_input:
        d = json.loads(Path(args.json_input).read_text(encoding="utf-8"))
        name = d.get("name") or code
        rows = d["rows"][-args.days:]
    else:
        name, rows = fetch_flow(code, args.days)
    out = Path(args.out) if args.out else REPO / "generated" / f"flow_embed_{code}_{args.days}d.html"
    render(name, code, rows, out, args.title)


if __name__ == "__main__":
    main()
