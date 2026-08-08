#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
divergence-monitor: 每日盘后背离监控——扫描目标（组合/板块），与上次结果对比，
报告新增/消失的 RSI 背离，输出 Markdown 报告（terminal + 文件）。

用法:
  python3 divergence-monitor.py --account 7维选股
  python3 divergence-monitor.py --account 7维选股 --blocks BK0448,BK1033
  python3 divergence-monitor.py --blocks BK0448 --out report.md
  python3 divergence-monitor.py --account 7维选股 --full    # 报告全部背离（非仅新增）

配合 cron 每日盘后运行（见 SKILL.md 末尾）。
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import fetch_kline  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
SCAN = Path(__file__).resolve().parents[2] / "divergence-scan" / "scripts" / "divergence-scan.py"
REPORT_DIR = Path.cwd() / "generated" / "divergence_monitor"


def scan_target(args) -> list:
    """复用 divergence-scan 逻辑（importlib 加载，文件名带横线）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ds", str(SCAN))
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    import pandas as pd
    if args.blocks:
        targets = []
        for bk in args.blocks.split(","):
            targets += ds.get_block_stocks(bk.strip())
        label = f"板块 {args.blocks}"
    elif args.account:
        targets = ds.get_account_codes(args.account)
        label = f"组合 {args.account}"
    else:
        raise SystemExit("❌ 需 --account 或 --blocks")

    results = []
    for i, (code, name) in enumerate(targets):
        try:
            nm, pts = fetch_kline(code, lmt=120)
            if not pts:
                continue
            df = pd.DataFrame(pts)
            for t, d1, p1, r1, d2, p2, r2 in ds.find_divergence(df, 5, 14):
                results.append({"code": code, "name": name or nm, "type": t,
                                "p1_date": d1, "p1": round(p1, 2), "p1_rsi": round(r1, 1),
                                "p2_date": d2, "p2": round(p2, 2), "p2_rsi": round(r2, 1)})
        except Exception:
            pass
    return label, results


def main():
    ap = argparse.ArgumentParser(description="每日盘后背离监控（新增背离对比）")
    ap.add_argument("--account", default="", help="组合账户")
    ap.add_argument("--blocks", default="", help="板块代码逗号分隔")
    ap.add_argument("--out", default="", help="报告输出路径（默认 generated/divergence_monitor/<date>.md）")
    ap.add_argument("--full", action="store_true", help="报告全部背离（默认仅新增）")
    args = ap.parse_args()

    label, results = scan_target(args)
    today = datetime.now().strftime("%Y-%m-%d")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 对比上次
    prev = None
    prev_file = None
    for f in sorted(REPORT_DIR.glob("*.json"), reverse=True):
        if f.stem != today:
            prev = json.loads(f.read_text())
            prev_file = f.stem
            break

    prev_keys = {(r["code"], r["type"]) for r in prev} if prev else set()
    cur_keys = {(r["code"], r["type"]) for r in results}
    new = [r for r in results if (r["code"], r["type"]) not in prev_keys]
    gone = [r for r in (prev or []) if (r["code"], r["type"]) not in cur_keys]

    # 保存本次
    snap = REPORT_DIR / f"{today}.json"
    snap.write_text(json.dumps({"label": label, "time": datetime.now().strftime("%H:%M"), "results": results},
                               ensure_ascii=False, indent=1))

    lines = [f"# 背离监控日报（{today} {datetime.now().strftime('%H:%M')}）",
             f"**范围**：{label}（{len(results)} 条背离）｜ 对比上次：{prev_file or '无'}",
             ""]
    if args.full:
        new, gone = results, []
    lines.append(f"## 🔴 底背离 {sum(1 for r in new if r['type']=='底背离')} / 🟢 顶背离 {sum(1 for r in new if r['type']=='顶背离')}")
    if new:
        for r in new:
            icon = "🔴底背离" if r["type"] == "底背离" else "🟢顶背离"
            lines.append(f"- {icon} **{r['name']}**({r['code']}) {r['p1_date']}({r['p1']},{r['p1_rsi']}) → {r['p2_date']}({r['p2']},{r['p2_rsi']})")
    else:
        lines.append("- （无新增背离）")
    if gone:
        lines.append("\n## ⚠️ 已消失")
        for r in gone:
            lines.append(f"- {r['type']} {r['name']}({r['code']})")
    report = "\n".join(lines) + "\n"

    out = Path(args.out) if args.out else REPORT_DIR / f"{today}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"✅ 报告: {out}")


if __name__ == "__main__":
    main()
