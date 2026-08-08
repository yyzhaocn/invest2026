#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data-zjlx: 拉取东财全市场资金流向（zjlx）快照，供 scan 等技能 join 主力净流入。

数据源: push2delay /api/qt/clist/get (fid=f62 主力净流入排序, fs=全市场7段)
输出:   generated/em/YYMMDD/zjlx_zlb_YYYYMMDDHHMM.csv（表头与 scan.py 兼容）

⚠️ 分页坑（实测）: push2delay 深分页每页最多 100 条——统一 pz=100 从 pn=1 拉到底
   （约 53 页/5292 只），切勿 pz=200 混用（offset 错位导致重复/缺失）。

用法:
  python3 data-zjlx.py [--out 目录] [--json]
  python3 data-zjlx.py --dir  ~/pydev/atime/generated   # 指定存档目录
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
FS = "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2"
FIELDS = ("f12,f14,f2,f3,f8,f9,f10,f15,f16,f17,f18,f20,f21,f23,f62,f66,f69,f72,f75,f78,f81,f84,f87,"
          "f100,f102,f124,f184")
HEADERS = ["序号", "最新价", "今日涨跌幅", "换手率", "市盈率", "市净率", "代码", "-", "名称", "最高价", "最低价",
           "开盘价", "昨收价", "总市值", "流通市值", "振幅", "主力净流入", "超大单净流入", "超大单净占比",
           "大单净流入", "大单净占比", "中单净流入", "中单净占比", "小单净流入", "小单净占比", "所属行业",
           "所属概念", "未知字段_f146", "未知字段_f147", "所属地域", "所属板块", "所属指数", "相关",
           "主力净占比", "-", "-", "-"]


def fetch_page(pn: int, pz: int = 100, retries: int = 6) -> list:
    """拉一页成分，失败重试。返回 diff 列表。"""
    url = (f"https://push2delay.eastmoney.com/api/qt/clist/get?fid=f62&po=1&pz={pz}&pn={pn}&np=1&fltt=2&invt=2"
           f"&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs={FS}&fields={FIELDS}")
    for _ in range(retries):
        p = subprocess.run(["curl", "-sS", "--max-time", "20", "-H", f"User-Agent: {UA}",
                            "-H", "Referer: https://data.eastmoney.com/zjlx/detail.html", url],
                           capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            try:
                diff = (json.loads(p.stdout).get("data") or {}).get("diff") or []
                if diff:
                    return diff
            except Exception:
                pass
        time.sleep(3)
    return []


def fetch_all() -> tuple:
    """分页拉全量。返回 (rows, total)。pz=100 从 pn=1 拉到底（深分页限制）。"""
    seen, rows, total, pn = set(), [], None, 1
    while pn <= 60:
        diff = fetch_page(pn)
        if not diff:
            break
        if total is None:
            pass
        for r in diff:
            code = str(r.get("f12", "")).zfill(6)
            if code in seen:
                continue
            seen.add(code)
            rows.append([str(len(seen)), r.get("f2"), r.get("f3"), r.get("f8"), r.get("f9"), r.get("f10"),
                         r.get("f12"), 0, r.get("f14"), r.get("f15"), r.get("f16"), r.get("f17"), r.get("f18"),
                         r.get("f20"), r.get("f21"), r.get("f23"), r.get("f62"), r.get("f66"), r.get("f69"),
                         r.get("f72"), r.get("f75"), r.get("f78"), r.get("f81"), r.get("f84"), r.get("f87"),
                         r.get("f100"), r.get("f102"), None, None, r.get("f124"), None, None, None,
                         r.get("f184"), None, None, None])
        if len(seen) >= 5000 or (diff and len(diff) < 100):
            # 已近全量或末页
            if len(diff) < 100 and len(seen) > 4000:
                break
        pn += 1
        if pn % 10 == 0:
            print(f"  pn={pn} 累计 {len(seen)}", flush=True)
        time.sleep(1.0)
    return rows, len(seen)


def main():
    ap = argparse.ArgumentParser(description="东财全市场资金流向快照")
    ap.add_argument("--out", default=None, help="输出目录（默认 cwd/generated/em/YYMMDD/）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    args = ap.parse_args()

    rows, total = fetch_all()
    if not rows:
        print("❌ 拉取失败（接口限流？稍后重试）", file=sys.stderr)
        sys.exit(1)

    now = datetime.now()
    outdir = Path(args.out) if args.out else Path.cwd() / "generated" / "em" / now.strftime("%y%m%d")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"zjlx_zlb_{now.strftime('%y%m%d%H%M')}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)

    if args.json:
        print(json.dumps({"path": str(path), "count": len(rows), "asof": now.strftime("%y%m%d%H%M")}))
    else:
        print(f"✅ zjlx 快照: {path} ({len(rows)} 只, {path.stat().st_size/1024:.0f} KB)")
        print("scan 将自动 join 该文件的主力净流入")


if __name__ == "__main__":
    main()
