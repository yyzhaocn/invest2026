#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund-codes-html: 将东方财富基金代码列表生成为自包含的可搜索 HTML 页面。

用法:
  python3 fund-codes-html.py [--output 路径] [--refresh] [--top N]

数据源: fund/fundcode_search.js (var r = [[代码, 简拼, 名称, 类型, 全拼], ...])
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FUND_DIR = REPO_ROOT / "fund"
JS_FILE = FUND_DIR / "fundcode_search.js"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>基金代码列表</title>
<style>
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; background: #f5f6f8; color: #222; }
  .wrap { max-width: 1000px; margin: 0 auto; padding: 16px; }
  header { position: sticky; top: 0; background: #fff; padding: 12px 16px; border-bottom: 1px solid #e3e5e8; z-index: 10; }
  header h1 { font-size: 18px; margin: 0 0 8px; }
  input[type=search] { width: 100%; padding: 10px 12px; font-size: 15px; border: 1px solid #ccc; border-radius: 8px; box-sizing: border-box; }
  .meta { color: #888; font-size: 13px; margin: 10px 2px; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
  th, td { padding: 8px 12px; text-align: left; font-size: 14px; }
  th { background: #f0f1f4; position: sticky; top: 96px; }
  tbody tr:nth-child(even) { background: #fafbfc; }
  td.code { font-family: Menlo, Consolas, monospace; color: #1a56db; }
  td.type { color: #666; font-size: 13px; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<header>
  <h1>基金代码列表 <span id="count" style="color:#888;font-weight:normal;font-size:14px"></span></h1>
  <input type="search" id="q" placeholder="搜索：代码 / 名称 / 拼音简拼 / 类型，如 161631、人工智能、ZHRGZN、指数型" autofocus>
</header>
<div class="wrap">
  <div class="meta">数据来源：东方财富 fundcode_search.js（__ASOF__ 刷新，共 __TOTAL__ 只）。点击代码打开基金主页。</div>
  <table>
    <thead><tr><th style="width:90px">代码</th><th>基金名称</th><th style="width:180px">类型</th></tr></thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
<script>
const FUNDS = __DATA__;
const tb = document.getElementById('tbody');
const cnt = document.getElementById('count');
const q = document.getElementById('q');
function render(list) {
  cnt.textContent = '共 ' + FUNDS.length + ' 只，显示 ' + list.length + ' 只';
  tb.innerHTML = list.map(f =>
    '<tr><td class="code"><a href="https://fund.eastmoney.com/' + f.c + '.html" target="_blank">' + f.c + '</a></td>' +
    '<td><a href="https://fund.eastmoney.com/' + f.c + '.html" target="_blank">' + esc(f.n) + '</a></td>' +
    '<td class="type">' + esc(f.t) + '</td></tr>').join('');
}
function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function apply() {
  const s = q.value.trim().toLowerCase();
  if (!s) return render(FUNDS);
  const out = [];
  for (const f of FUNDS) {
    if (f.c.indexOf(s) === 0 || f.n.toLowerCase().indexOf(s) !== -1 ||
        f.p.toLowerCase().indexOf(s) !== -1 || f.t.toLowerCase().indexOf(s) !== -1) out.push(f);
  }
  render(out);
}
q.addEventListener('input', apply);
render(FUNDS);
</script>
</body>
</html>
"""


def refresh_from_network():
    """从东方财富刷新 fundcode_search.js 缓存。"""
    import requests
    url = "http://fund.eastmoney.com/js/fundcode_search.js"
    print(f"📡 正在从网络刷新: {url}")
    r = requests.get(url, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    JS_FILE.write_text(r.text, encoding="utf-8")
    print(f"✅ 已刷新缓存: {JS_FILE} ({len(r.text) // 1024} KB)")


def load_funds(limit=None, exclude_bonds=True):
    """解析本地 fundcode_search.js 为 fund dict 列表。

    exclude_bonds=True 时过滤掉债券类基金（默认）：类型含「债」或「固收」的
    全部排除（债券型-*、QDII-纯债/混合债、混合型-偏债、指数型-固收等），
    货币型保留。
    """
    if not JS_FILE.exists():
        raise FileNotFoundError(f"本地缓存不存在: {JS_FILE}，请先运行 --refresh")
    content = JS_FILE.read_text(encoding="utf-8")
    start, end = content.find("["), content.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("缓存格式异常，无法解析")
    data = json.loads(content[start:end + 1])
    funds = []
    for it in data:
        if len(it) < 5:
            continue
        ftype = it[3]
        if exclude_bonds and ("债" in ftype or "固收" in ftype):
            continue
        funds.append({"c": it[0], "n": it[2], "t": ftype, "p": it[4]})
    if limit:
        funds = funds[:limit]
    return funds


def main():
    ap = argparse.ArgumentParser(description="生成基金代码列表 HTML")
    ap.add_argument("--output", "-o", default="/tmp/fund_codes.html", help="输出路径，默认 /tmp/fund_codes.html")
    ap.add_argument("--refresh", action="store_true", help="先从网络更新本地缓存")
    ap.add_argument("--top", type=int, default=0, help="仅嵌入前 N 只（调试），0=全部")
    ap.add_argument("--include-bonds", action="store_true", help="包含债券类基金（默认排除，货币型始终保留）")
    args = ap.parse_args()

    if args.refresh:
        refresh_from_network()

    exclude_bonds = not args.include_bonds
    funds = load_funds(args.top if args.top > 0 else None, exclude_bonds=exclude_bonds)
    total = len(funds)
    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(funds, ensure_ascii=False))
            .replace("__ASOF__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__TOTAL__", str(total)))
    if exclude_bonds:
        html = html.replace(f"共 {total} 只", f"共 {total} 只（已排除债券类）")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"✅ 已生成: {out} ({out.stat().st_size / 1024:.0f} KB, {total} 只基金"
          + ("，已排除债券类)" if exclude_bonds else ")"))


if __name__ == "__main__":
    main()
