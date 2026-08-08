#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock-hotmap: 把板块内全部股票生成为热力图 HTML（treemap）。

方块面积 = 市值/流通市值/成交额，颜色 = 当日涨跌幅（红涨绿跌）。

用法:
  python3 stock-hotmap.py <板块代码或名称> [--size 市值|流通市值|成交额] [--top N] [--output 路径] [--json]
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from boards import HOTMAP_FIELDS, fetch_block_stocks, resolve_block  # noqa: E402

SIZE_FIELDS = {
    "市值": "mcap",
    "流通市值": "fcap",
    "成交额": "amount",
}
SIZE_LABELS = {"市值": "总市值", "流通市值": "流通市值", "成交额": "成交额"}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; background: #101418; color: #e8eaed; }
  .wrap { max-width: 1400px; margin: 0 auto; padding: 16px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .meta { color: #9aa0a6; font-size: 13px; margin-bottom: 12px; }
  .stats { display: flex; gap: 16px; font-size: 13px; margin-bottom: 12px; }
  .stats b.up { color: #ff4d4f; } .stats b.down { color: #2ecc71; } .stats b.flat { color: #9aa0a6; }
  .ai-note { background: #1a2230; border: 1px solid #2a3a52; border-radius: 10px; padding: 12px 16px;
    margin-bottom: 14px; font-size: 13px; line-height: 1.7; color: #cdd5e0; }
  .ai-note .ai-tag { display: inline-block; background: #3a5a8a; color: #fff; font-size: 11px;
    border-radius: 5px; padding: 1px 7px; margin-right: 8px; vertical-align: 1px; }
  .legend { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #9aa0a6; margin-bottom: 8px; }
  .legend .bar { width: 160px; height: 10px; border-radius: 3px;
    background: linear-gradient(90deg, #1f8b4c, #9aa0a6, #d63031); }
  #hm { position: relative; width: 100%; height: 78vh; background: #1a1e24; border-radius: 10px; overflow: hidden; }
  .cell { position: absolute; box-sizing: border-box; border: 1px solid rgba(16,20,24,.9); border-radius: 3px;
    overflow: hidden; cursor: pointer; display: flex; flex-direction: column; justify-content: center;
    align-items: center; text-align: center; transition: filter .15s; }
  .cell:hover { filter: brightness(1.25); z-index: 5; }
  .cell .nm { font-size: 12px; font-weight: 600; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,.7); }
  .cell .chg { font-size: 11px; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,.7); }
  .cell.small .nm { font-size: 10px; } .cell.tiny .nm { font-size: 8px; } .cell.tiny .chg { display: none; }
  #tip { position: absolute; pointer-events: none; background: rgba(0,0,0,.85); color: #fff; padding: 8px 10px;
    border-radius: 6px; font-size: 12px; line-height: 1.6; display: none; z-index: 10; white-space: nowrap; }
  .tip-name { font-weight: 600; font-size: 13px; }
  .tip-row { display: grid; grid-template-columns: auto auto; gap: 0 12px; }
  .tip-row .k { color: #b0b6bc; }
  .foot { color: #6b7075; font-size: 11px; margin-top: 8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>__TITLE__</h1>
  <div class="meta">数据时间 __ASOF__ ｜ 面积 = __SIZELABEL__，颜色 = 当日涨跌幅（红涨绿跌）｜ 点击方块查看个股</div>
  __AI__
  <div class="stats">
    <span>共 <b>__TOTAL__</b> 只</span>
    <span>上涨 <b class="up">__UP__</b></span>
    <span>下跌 <b class="down">__DOWN__</b></span>
    <span>平盘 <b class="flat">__FLAT__</b></span>
  </div>
  <div class="legend"><span>-10%</span><div class="bar"></div><span>0</span><div class="bar" style="width:4px"></div><span>+10%</span></div>
  <div id="hm"><div id="tip"></div></div>
  <div class="foot">方块面积按 __SIZELABEL__，颜色深浅按涨跌幅（±10% 封顶）。数据为实时/延迟行情快照。</div>
</div>
<script>
const DATA = __DATA__;
const SIZE_KEY = "__SIZEKEY__";
const money = v => v == null ? '--' : (v >= 1e8 ? (v/1e8).toFixed(2)+'亿' : (v/1e4).toFixed(0)+'万');
function color(pct) {
  if (pct == null) return '#5b616a';
  const t = Math.max(-10, Math.min(10, pct)) / 10;   // -1..1
  const c = t < 0 ? [47,140,86] : [214,48,49];       // 绿 / 红
  const g = t < 0 ? [0x9a,0xa0,0xa6] : [0x9a,0xa0,0xa6];
  // mix: |t|: 0 -> gray, 1 -> full color
  const a = Math.abs(t);
  const rgb = c.map((v,i) => Math.round(g[i] + (v - g[i]) * a));
  return 'rgb(' + rgb.join(',') + ')';
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
// ---- squarified treemap (Bruls et al.) ----
function treemap(items, x, y, w, h) {
  const out = [];
  function worst(row, length) {
    let sum = 0, min = Infinity, max = 0;
    for (const it of row) { sum += it.size; if (it.size < min) min = it.size; if (it.size > max) max = it.size; }
    const s2 = sum * sum, l2 = length * length;
    return Math.max(l2 * max / s2, s2 / (l2 * min));
  }
  (function layout(r, list) {
    if (!list.length) return;
    const total = list.reduce((s, it) => s + it.size, 0) || 1;
    const length = Math.min(r.w, r.h);
    let row = [], i = 0;
    while (i < list.length) {
      if (!row.length || worst(row.concat([list[i]]), length) <= worst(row, length)) { row.push(list[i]); i++; }
      else break;
    }
    const rowSum = row.reduce((s, it) => s + it.size, 0) || 1;
    if (r.w >= r.h) {
      const thick = (r.w * r.h) * (rowSum / total) / (r.h || 1);
      let off = r.y;
      for (const it of row) {
        const hh = it.size / rowSum * r.h;
        out.push({data: it.data, x: r.x, y: off, w: thick, h: hh});
        off += hh;
      }
      r.x += thick; r.w -= thick;
    } else {
      const thick = (r.w * r.h) * (rowSum / total) / (r.w || 1);
      let off = r.x;
      for (const it of row) {
        const ww = it.size / rowSum * r.w;
        out.push({data: it.data, x: off, y: r.y, w: ww, h: thick});
        off += ww;
      }
      r.y += thick; r.h -= thick;
    }
    layout(r, list.slice(i));
  })({x, y, w, h}, items.slice());
  return out;
}
// ---- render ----
const hm = document.getElementById('hm');
const tip = document.getElementById('tip');
const items = DATA.stocks.map(s => ({size: Math.max(s[SIZE_KEY] || 1, 1e4), data: s}))
  .sort((a, b) => b.size - a.size);
const W = hm.clientWidth, H = hm.clientHeight;
const cells = treemap(items, 0, 0, W, H);
const minArea = W * H / Math.max(items.length, 1) * 0.12;
cells.forEach(c => {
  const s = c.data;
  const el = document.createElement('div');
  el.className = 'cell' + (c.w * c.h < minArea ? ' tiny' : (c.w < 46 || c.h < 34 ? ' small' : ''));
  el.style.left = c.x + 'px'; el.style.top = c.y + 'px';
  el.style.width = c.w + 'px'; el.style.height = c.h + 'px';
  el.style.background = color(s.pct);
  const pct = s.pct == null ? '--' : (s.pct > 0 ? '+' : '') + s.pct.toFixed(2) + '%';
  el.innerHTML = '<div class="nm">' + esc(s.name) + '</div><div class="chg">' + esc(pct) + '</div>';
  el.addEventListener('mousemove', e => {
    tip.innerHTML = '<div class="tip-name">' + esc(s.name) + ' <span style="color:#b0b6bc">' + s.code + '</span></div>' +
      '<div class="tip-row"><span class="k">现价</span><span>' + (s.price ?? '--') + '</span>' +
      '<span class="k">涨跌</span><span style="color:' + color(s.pct) + '">' + pct + '</span>' +
      '<span class="k">成交额</span><span>' + money(s.amount) + '</span>' +
      '<span class="k">换手</span><span>' + (s.turnover == null ? '--' : s.turnover.toFixed(2) + '%') + '</span>' +
      '<span class="k">' + '__SIZELABEL__' + '</span><span>' + money(s[SIZE_KEY]) + '</span></div>';
    tip.style.display = 'block';
    tip.style.left = Math.min(e.clientX - hm.getBoundingClientRect().left + 12, W - 220) + 'px';
    tip.style.top = Math.max(e.clientY - hm.getBoundingClientRect().top - 10, 4) + 'px';
  });
  el.addEventListener('mouseleave', () => tip.style.display = 'none');
  el.addEventListener('click', () => {
    const prefix = s.code.startsWith('6') ? 'sh' : (s.code.startsWith('4') || s.code.startsWith('8') || s.code.startsWith('9') ? 'bj' : 'sz');
    window.open('https://quote.eastmoney.com/' + prefix + s.code + '.html', '_blank');
  });
  hm.appendChild(el);
});
</script>
</body>
</html>
"""


def fmt_pct(v):
    return f"{v:+.2f}%" if v is not None else "--"


def llm_review(name, bcode, rows, up, down, flat, url):
    """本地 LLM 板块解读（curl 子进程，勿用 urllib/requests——会走代理 502）。"""
    by_pct = sorted([r for r in rows if r.get("pct") is not None], key=lambda r: r["pct"], reverse=True)
    avg = sum(r.get("pct") or 0 for r in rows) / len(rows) if rows else 0
    amt = sum(r.get("amount") or 0 for r in rows) / 1e8
    top = "、".join(f"{r['name']}({fmt_pct(r['pct'])})" for r in by_pct[:5])
    bot = "、".join(f"{r['name']}({fmt_pct(r['pct'])})" for r in by_pct[-5:])
    prompt = (f"你是A股板块分析师。解读板块 {name}({bcode}) 今日行情（{len(rows)}只成分，涨{up}/跌{down}/平{flat}，"
              f"平均涨幅{avg:+.2f}%，总成交额{amt:.0f}亿）。领涨：{top}；领跌：{bot}。"
              "用中文分3点，各≤60字：1)板块强弱与资金方向 2)领涨结构含义 3)次日关注要点")
    body = json.dumps({"model": "", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 350, "temperature": 0.3})
    try:
        p = subprocess.run(["curl", "-sS", "--max-time", "150",
                            "-H", "Content-Type: application/json", "-d", body, url],
                           capture_output=True, text=True, timeout=170)
        if p.returncode != 0:
            return f"⚠️ 本地模型不可用: {p.stderr[:80]}"
        return json.loads(p.stdout)["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ 本地模型调用失败: {str(e)[:80]}"


def llm_render_html(name, bcode, rows, asof, url):
    """本地 LLM 直接生成热力图 HTML（treemap）。返回 (html, 是否成功)。"""
    stocks = [{"c": r["code"], "n": r["name"], "p": r.get("pct"),
               "m": round((r.get("mcap") or 0) / 1e8, 1)} for r in rows]
    data_json = json.dumps(stocks, ensure_ascii=False)
    prompt = (f"你是前端工程师。根据下面 JSON 股票数据，生成一个自包含 HTML 热力图（treemap）页面：\n"
              f"1) 单文件内联 CSS/JS，暗色主题(#101418底)，红涨绿跌(#ff4d4f/#2ecc71)，方块面积=市值m(亿)，颜色=涨跌幅p\n"
              f"2) 顶部标题 '{name} ({bcode}) 热力图' + 时间 {asof}，底部图例与涨跌统计\n"
              f"3) 方块悬停显示 名称/涨跌幅/市值，点击跳转 https://quote.eastmoney.com/（按代码自动加市场前缀：6开头sh其余sz）\n"
              f"4) 布局：可用 flex 网格或绝对定位 treemap，方块大小正比于市值，最小方块不小于 30px\n"
              f"5) 直接输出完整 HTML 代码（<html>...</html>），不要任何解释文字。\n数据：{data_json}")
    body = json.dumps({"model": "", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 6000, "temperature": 0.2})
    try:
        p = subprocess.run(["curl", "-sS", "--max-time", "400",
                            "-H", "Content-Type: application/json", "-d", body, url],
                           capture_output=True, text=True, timeout=420)
        if p.returncode != 0:
            return "", False
        html = json.loads(p.stdout)["choices"][0]["message"]["content"].strip()
        # 提取代码块
        if "```html" in html:
            html = html.split("```html")[1].split("```")[0].strip()
        elif html.startswith("```"):
            html = html.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if "<html" in html or "<!DOCTYPE" in html:
            return html, True
        return "", False
    except Exception:
        return "", False


def main():
    ap = argparse.ArgumentParser(description="生成板块股票热力图 HTML")
    ap.add_argument("block", help="板块代码 (BKxxxx) 或名称")
    ap.add_argument("--size", default="市值", choices=list(SIZE_FIELDS.keys()), help="方块面积字段，默认 市值")
    ap.add_argument("--top", type=int, default=0, help="只取面积前 N 只，0=全部")
    ap.add_argument("--output", "-o", default="/tmp/stock_hotmap.html", help="输出路径，默认 /tmp/stock_hotmap.html")
    ap.add_argument("--json", action="store_true", help="输出 JSON 数据（不生成 HTML）")
    ap.add_argument("--llm", action="store_true", help="用本地 LLM 生成板块解读（默认 8080）")
    ap.add_argument("--llm-render", action="store_true", help="用本地 LLM 直接生成整个热力图 HTML（实验性，失败回退模板）")
    ap.add_argument("--llm-url", default="http://localhost:8080/v1/chat/completions",
                    help="本地 LLM 端点（需 --llm 或 --llm-render）")
    args = ap.parse_args()

    block = args.block.strip()
    if block.upper().startswith("BK"):
        bcode, bname = block.upper(), None
    else:
        resolved = resolve_block(block)
        if not resolved:
            print(f"❌ 未找到板块 {block!r}（可用 block-list 确认）", file=sys.stderr)
            sys.exit(1)
        bcode, bname = resolved

    total, rows = fetch_block_stocks(bcode, fields=HOTMAP_FIELDS)
    if not rows:
        print(f"❌ 板块 {bcode} 无成分股数据", file=sys.stderr)
        sys.exit(1)

    sizefield = SIZE_FIELDS[args.size]
    rows = [r for r in rows if r.get(sizefield)]
    rows.sort(key=lambda r: r.get(sizefield) or 0, reverse=True)
    if args.top > 0:
        rows = rows[:args.top]

    name = bname or rows[0]["name"] if False else (bname or bcode)
    asof = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    up = sum(1 for r in rows if (r.get("pct") or 0) > 0)
    down = sum(1 for r in rows if (r.get("pct") or 0) < 0)
    flat = len(rows) - up - down

    if args.json:
        print(json.dumps({
            "block_code": bcode, "block_name": name, "asof": asof,
            "size_field": sizefield, "total": len(rows),
            "up": up, "down": down, "flat": flat,
            "stocks": rows,
        }, ensure_ascii=False, indent=2))
        return

    if args.llm_render:
        llm_html, ok = llm_render_html(name, bcode, rows, asof, args.llm_url)
        if ok:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(llm_html, encoding="utf-8")
            print(f"✅ 已生成(LLM渲染): {out} ({out.stat().st_size / 1024:.0f} KB, {len(rows)} 只)")
            return
        print("⚠️ LLM 渲染失败/超时，回退脚本模板", file=sys.stderr)

    ai_html = ""
    if args.llm:
        review = llm_review(name, bcode, rows, up, down, flat, args.llm_url)
        safe = review.replace("<", "&lt;").replace("\n", "<br>")
        ai_html = f'<div class="ai-note"><span class="ai-tag">AI解读</span>{safe}</div>'

    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps({"stocks": rows}, ensure_ascii=False))
            .replace("__TITLE__", f"{name} ({bcode}) 热力图")
            .replace("__ASOF__", asof)
            .replace("__SIZELABEL__", SIZE_LABELS[args.size])
            .replace("__SIZEKEY__", sizefield)
            .replace("__AI__", ai_html)
            .replace("__TOTAL__", str(len(rows)))
            .replace("__UP__", str(up)).replace("__DOWN__", str(down)).replace("__FLAT__", str(flat)))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    by_pct = sorted([r for r in rows if r.get("pct") is not None], key=lambda r: r["pct"], reverse=True)
    print(f"✅ 已生成: {out} ({out.stat().st_size / 1024:.0f} KB, {len(rows)} 只, 涨 {up} / 跌 {down} / 平 {flat})")
    print(f"板块: {name} ({bcode}) ｜ 面积={SIZE_LABELS[args.size]} ｜ 时间 {asof}")
    if by_pct:
        print("领涨:", "  ".join(f"{r['name']} {fmt_pct(r['pct'])}" for r in by_pct[:3]))
        print("领跌:", "  ".join(f"{r['name']} {fmt_pct(r['pct'])}" for r in by_pct[-3:]))
    print("打开: open /tmp/stock_hotmap.html")


if __name__ == "__main__":
    main()
