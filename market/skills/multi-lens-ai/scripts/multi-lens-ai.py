#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multi-lens-ai: 批量 7 维信号 + 本地 LLM 解读 → 汇总报告。

流程: 股票列表/组合账户/板块 → 逐个跑 multi-lens --json → 构建信号摘要
      → 调本地模型 (默认 8080 llama.cpp) 逐只解读 → 输出 Markdown 报告。

用法:
  python3 multi-lens-ai.py 603435 002709              # 指定代码
  python3 multi-lens-ai.py --account 7维选股           # 读组合持仓
  python3 multi-lens-ai.py --block BK1036 --top 10    # 板块内市值/涨幅前N
  python3 multi-lens-ai.py 603435 --url http://localhost:8080 --out report.md
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ML = "/Users/yyz/.agents/skills/stock/multi-lens/scripts/multi-lens.py"
PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def run_multi_lens(code: str) -> dict | None:
    p = subprocess.run(["python3", ML, code, "--json"], capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        return None
    return json.loads(p.stdout)


def summarize(d: dict) -> str:
    sig = [f"{l['lens']}({l['summary']}){'看涨' if l['direction']>0 else '看跌' if l['direction']<0 else ''}"
           for l in d['lenses'] if l['direction'] != 0]
    return d['name'] + "(" + d['code'] + ") 综合:" + d['verdict'] + " | 信号:" + "; ".join(sig)


def ask_model(prompt: str, url: str, model: str, max_tokens: int = 450, timeout: int = 150) -> str:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 0.3})
    p = subprocess.run(["curl", "-sS", "--max-time", str(timeout),
                        "-H", "Content-Type: application/json",
                        "-d", body, url], capture_output=True, text=True, timeout=timeout + 20)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:150])
    return json.loads(p.stdout)["choices"][0]["message"]["content"].strip()


def detect_model(url: str) -> str:
    try:
        p = subprocess.run(["curl", "-sS", "--max-time", "5",
                            url.replace("/chat/completions", "/models")],
                           capture_output=True, text=True, timeout=10)
        return json.loads(p.stdout)["data"][0]["id"] if p.returncode == 0 else ""
    except Exception:
        return ""


def codes_from_account(account: str) -> list:
    p = subprocess.run(["python3", PORTFOLIO, "--account", account, "show", "--json"],
                       capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise SystemExit(f"读取账户失败: {p.stderr[:200]}")
    d = json.loads(p.stdout)
    return [(pos["code"], pos["name"]) for pos in d.get("positions", [])]


def codes_from_block(bk: str, top: int) -> list:
    import urllib.parse
    url = (f"https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz={top}&po=1&np=1&fltt=2&invt=2"
           f"&fid=f20&fs=b:{bk}&fields=f12,f14")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=12) as r:
        d = json.loads(r.read())
    return [(x["f12"], x["f14"]) for x in (d.get("data", {}).get("diff") or [])]


def main():
    ap = argparse.ArgumentParser(description="批量 7 维 + 本地 LLM 解读报告")
    ap.add_argument("codes", nargs="*", help="股票代码（6位，空格分隔）")
    ap.add_argument("--account", help="组合账户名（读持仓）")
    ap.add_argument("--block", help="板块代码 BKxxxx")
    ap.add_argument("--top", type=int, default=10, help="板块取前N只")
    ap.add_argument("--url", default="http://localhost:8080/v1/chat/completions", help="本地模型端点")
    ap.add_argument("--out", default=None, help="报告输出路径（默认 cwd/generated/lens_ai_report.md）")
    ap.add_argument("--max-tokens", type=int, default=450)
    args = ap.parse_args()

    # 收集标的
    targets = []
    if args.account:
        targets = codes_from_account(args.account)
    elif args.block:
        targets = codes_from_block(args.block, args.top)
    else:
        targets = [(c, "") for c in args.codes]
    if not targets:
        raise SystemExit("❌ 无标的：提供 codes / --account / --block 之一")

    model = detect_model(args.url)
    print(f"本地模型: {model or '?'} | 标的 {len(targets)} 只")

    sections = []
    for i, (code, name) in enumerate(targets):
        d = run_multi_lens(code)
        if not d:
            sections.append(f"\n### {name or code} ({code})\n\n⚠️ multi-lens 失败")
            continue
        summary = summarize(d)
        prompt = ("你是A股技术分析师。解读以下个股的7维技术信号（kaabar方法），用中文分3点："
                  "1)信号强弱排序 2)关键支撑/压力位 3)操作建议（≤80字）。信号：\n" + summary)
        try:
            ai = ask_model(prompt, args.url, model, args.max_tokens)
        except Exception as e:
            ai = f"⚠️ 本地模型调用失败: {str(e)[:100]}"
        sections.append(f"\n### {d['name']} ({d['code']})\n\n**7维信号**：{summary}\n\n**本地模型解读**：\n{ai}")
        print(f"  [{i+1}/{len(targets)}] {d['name']} 完成")
        time.sleep(0.5)

    report = (f"# 7维信号 × 本地模型解读报告\n\n"
              f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M')}\n"
              f"- 本地模型: {model or 'N/A'}\n"
              f"- 标的: {len(targets)} 只" + "".join(sections))
    out = Path(args.out) if args.out else Path.cwd() / "generated" / "lens_ai_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\n✅ 报告: {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
