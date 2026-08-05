#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund-score: 基金评分排序（收益30 + 回撤20 + 波动20 + 规模15 + 集中度15 = 100）。

用法:
  python3 fund-score.py <代码...> [--json]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from fund import annualized_vol, fetch_fund, fetch_holdings, max_drawdown, period_returns, top10_ratio  # noqa: E402

W = {"ret": 30.0, "dd": 20.0, "vol": 20.0, "scale": 15.0, "conc": 15.0}


def display_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text or ""))


def pad(text, width, align="left"):
    text = str(text or "")
    pad_len = max(0, width - display_width(text))
    if align == "right":
        return " " * pad_len + text
    return text + " " * pad_len


def _lin(v, v0, s0, v1, s1):
    """线性插值并截断：v0→s0, v1→s1。"""
    if v is None:
        return None
    if v1 == v0:
        return s0
    s = s0 + (v - v0) * (s1 - s0) / (v1 - v0)
    return max(min(s, max(s0, s1)), min(s0, s1))


def score_ret(pr):
    """收益分（30）：复合 = 1年×0.5 + 6月×0.3 + 3月×0.2。"""
    r1y, r6m, r3m = pr.get("1年"), pr.get("6月"), pr.get("3月")
    vals = [v for v in (r1y, r6m, r3m) if v is not None]
    if not vals:
        return W["ret"] / 2, None
    composite = sum(v * w for v, w in zip([r1y, r6m, r3m], [0.5, 0.3, 0.2]) if v is not None)
    s = _lin(composite, -50, 0, 100, W["ret"]) or W["ret"] / 2
    return s, round(composite, 2)


def score_dd(dd):
    s = _lin(dd, 0, W["dd"], -40, 0)
    return (s if s is not None else W["dd"] / 2), dd


def score_vol(vol):
    s = _lin(vol, 10, W["vol"], 60, 0)
    return (s if s is not None else W["vol"] / 2), vol


def score_scale(scale):
    if scale is None:
        return W["scale"] / 2, None
    if scale <= 100:
        s = W["scale"] * (scale / 100)
    else:
        s = W["scale"] * max(0, 1 - (scale - 100) / 900)
    return s, scale


def score_conc(ratio):
    if ratio is None:
        return W["conc"] / 2, None
    s = W["conc"] * (1 - abs(ratio - 50) / 50)
    return max(0, s), ratio


def main():
    ap = argparse.ArgumentParser(description="基金评分")
    ap.add_argument("codes", nargs="+", help="基金代码（1 个或多个）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []
    for code in args.codes:
        f = fetch_fund(str(code).zfill(6))
        if not f:
            print(f"⚠️  无法获取基金 {code}，跳过", file=sys.stderr)
            continue
        pr = period_returns(f["points"])
        dd = max_drawdown(f["points"], 250)
        vol = annualized_vol(f["points"], 250)
        holdings = fetch_holdings(f["code"])
        conc = top10_ratio(holdings) if holdings else None

        s_ret, ret_v = score_ret(pr)
        s_dd, dd_v = score_dd(dd)
        s_vol, vol_v = score_vol(vol)
        s_scale, scale_v = score_scale(f["scale"])
        s_conc, conc_v = score_conc(conc)
        total = round(s_ret + s_dd + s_vol + s_scale + s_conc, 1)
        results.append({
            "code": f["code"], "name": f["name"], "nav": f["points"][-1]["nav"],
            "total": total, "scores": {
                "ret": round(s_ret, 1), "dd": round(s_dd, 1), "vol": round(s_vol, 1),
                "scale": round(s_scale, 1), "conc": round(s_conc, 1)},
            "detail": {"ret_composite": ret_v, "maxdd": round(dd, 2),
                       "vol": round(vol, 2) if vol else None, "scale": scale_v,
                       "top10_ratio": round(conc, 2) if conc else None},
        })

    if not results:
        sys.exit("❌ 全部基金数据获取失败")
    results.sort(key=lambda r: -r["total"])

    if args.json:
        print(json.dumps({"asof": datetime.now().strftime("%Y-%m-%d %H:%M"),
                          "model": W, "results": results}, ensure_ascii=False, indent=2))
        return

    print(f"基金评分（{datetime.now().strftime('%Y-%m-%d %H:%M')}）: "
          f"收益{W['ret']:.0f} + 回撤{W['dd']:.0f} + 波动{W['vol']:.0f} + 规模{W['scale']:.0f} + 集中度{W['conc']:.0f} = 100")
    header = " ".join([pad("代码", 8), pad("名称", 22), pad("总分", 6, "right"),
                    pad("收益分", 7, "right"), pad("回撤分", 7, "right"), pad("波动分", 7, "right"),
                    pad("规模分", 7, "right"), pad("集中度分", 8, "right")])
    print(header)
    print("-" * display_width(header))
    for r in results:
        nm = r["name"]
        if display_width(nm) > 22:
            nm = nm[:10] + ".."
        s = r["scores"]
        print(" ".join([pad(r["code"], 8), pad(nm, 22), pad(f"{r['total']:.1f}", 6, "right"),
                      pad(f"{s['ret']:.1f}", 7, "right"), pad(f"{s['dd']:.1f}", 7, "right"),
                      pad(f"{s['vol']:.1f}", 7, "right"), pad(f"{s['scale']:.1f}", 7, "right"),
                      pad(f"{s['conc']:.1f}", 8, "right")]))
    print("\n明细:")
    for r in results:
        d = r["detail"]
        parts = []
        if d["ret_composite"] is not None:
            parts.append(f"收益复合 {d['ret_composite']:+.1f}%")
        parts.append(f"回撤 {d['maxdd']:.1f}%")
        if d["vol"] is not None:
            parts.append(f"波动 {d['vol']:.1f}%")
        if d["scale"] is not None:
            parts.append(f"规模 {d['scale']:.1f}亿")
        if d["top10_ratio"] is not None:
            parts.append(f"前十集中 {d['top10_ratio']:.1f}%")
        print(f"  {r['code']} {r['name']}: " + " ｜ ".join(parts))


if __name__ == "__main__":
    main()
