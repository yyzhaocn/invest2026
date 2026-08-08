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
DM = Path(__file__).resolve().parents[2] / "divergence-multi" / "scripts" / "divergence-multi.py"
REPORT_DIR = Path.cwd() / "generated" / "divergence_monitor"


def scan_target(args):
    """标准背离 + live 即时背离（divergence-multi 模块）。返回 (label, std, live)。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dm", str(DM))
    dm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dm)
    import pandas as pd
    if args.blocks:
        targets = []
        for bk in args.blocks.split(","):
            targets += dm.block_stocks(bk.strip())
        label = f"板块 {args.blocks}"
    elif args.account:
        targets = dm.account_stocks(args.account)
        label = f"组合 {args.account}"
    else:
        raise SystemExit("❌ 需 --account 或 --blocks")

    std, live = [], []
    for code, name in targets:
        try:
            nm, pts = fetch_kline(code, lmt=120)
            if not pts:
                continue
            df = pd.DataFrame(pts)
            for d in dm.detect_multi(df, 5, live=False):
                if d["score"] >= 2:
                    std.append({"code": code, "name": dm.fix_name(code, name or nm),
                                "type": d["type"], "score": d["score"],
                                "indicators": d["indicators"],
                                "p1_date": str(d["p1_date"])[:10], "p2_date": str(d["p2_date"])[:10]})
            for d in dm.detect_multi(df, 2, live=True):
                if d["score"] >= 2:
                    live.append({"code": code, "name": dm.fix_name(code, name or nm),
                                 "type": d["type"], "score": d["score"],
                                 "indicators": d["indicators"],
                                 "p1_date": str(d["p1_date"])[:10], "p2_date": str(d["p2_date"])[:10]})
        except Exception:
            pass
    return label, std, live


def main():
    ap = argparse.ArgumentParser(description="每日盘后背离监控（新增背离对比）")
    ap.add_argument("--account", default="", help="组合账户")
    ap.add_argument("--blocks", default="", help="板块代码逗号分隔")
    ap.add_argument("--out", default="", help="报告输出路径（默认 generated/divergence_monitor/<date>.md）")
    ap.add_argument("--full", action="store_true", help="报告全部背离（默认仅新增）")
    args = ap.parse_args()

    label, results, live_results = scan_target(args)
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
            lines.append(f"- {icon} **{r['name']}**({r['code']}) 共振{r['score']} {r['p1_date']}→{r['p2_date']} {'/'.join(r['indicators'])}")
    else:
        lines.append("- （无新增背离）")
    if gone:
        lines.append("\n## ⚠️ 已消失")
        for r in gone:
            lines.append(f"- {r['type']} {r['name']}({r['code']})")
    lines.append(f"\n## ⚡ 即时新信号（{len(live_results)} 条，待5天窗口确认）")
    if live_results:
        for r in sorted(live_results, key=lambda x: -x["score"])[:10]:
            icon = "🔴底" if r["type"] == "底背离" else "🟢顶"
            lines.append(f"- {icon} 共振{r['score']} {r['name']}({r['code']}) {r['p1_date']}→{r['p2_date']} {'/'.join(r['indicators'])}")
    else:
        lines.append("- （无）")
    report = "\n".join(lines) + "\n"

    out = Path(args.out) if args.out else REPORT_DIR / f"{today}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"✅ 报告: {out}")


if __name__ == "__main__":
    main()
