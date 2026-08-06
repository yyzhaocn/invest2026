#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金数据与指标助手 (fund-compare / fund-score 共用)。

- fetch_fund: pingzhongdata 解析（净值序列、区间涨幅、规模、经理）
- 指标: 区间收益 / 最大回撤 / 年化波动率 / 前十大集中度（需持仓）
"""
import json
import math
import re

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"}
PERIOD_DAYS = {"1月": 22, "3月": 66, "6月": 132, "1年": 250}


def _extract_balanced(text, start, open_c, close_c):
    """从 start 处开始提取括号平衡的 JSON 片段（正确处理字符串内的括号）。"""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == open_c:
                depth += 1
            elif ch == close_c:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def fetch_fund(code: str):
    """解析 pingzhongdata。返回 dict 或 None。"""
    from httpget import httpget
    try:
        resp = httpget(f"https://fund.eastmoney.com/pingzhongdata/{code}.js",
                            timeout=15, headers=UA)
        resp.raise_for_status()
        text = resp.text

        def _var(name):
            m = re.search(rf'var {name}\s*=\s*"?([^";]+)"?;', text)
            return m.group(1) if m else None

        def _json(name):
            m = re.search(rf'var {name}\s*=\s*([\[\{{])', text)
            if not m:
                return None
            start = m.end() - 1
            frag = _extract_balanced(text, start, m.group(1), "]" if m.group(1) == "[" else "}")
            if frag is None:
                return None
            try:
                return json.loads(frag)
            except json.JSONDecodeError:
                return None

        trend = _json("Data_netWorthTrend") or []
        points = []
        for item in trend:
            if not isinstance(item, dict) or "x" not in item or "y" not in item:
                continue
            try:
                nav = float(item["y"])
            except (TypeError, ValueError):
                continue
            er = item.get("equityReturn")
            try:
                er = float(er) if er not in (None, "") else None
            except (TypeError, ValueError):
                er = None
            points.append({"date": __import__("datetime").datetime.fromtimestamp(int(item["x"]) / 1000).strftime("%Y-%m-%d"),
                           "nav": nav, "pct": er})
        if not points:
            return None

        # 规模（亿）
        scale = None
        fluct = _json("Data_fluctuationScale") or {}
        series = fluct.get("series") or []
        for item in reversed(series):
            y = item.get("y") if isinstance(item, dict) else None
            if y not in (None, ""):
                try:
                    scale = float(y)
                except (TypeError, ValueError):
                    pass
                break

        manager = ""
        mgr = _json("Data_currentFundManager") or []
        if mgr and isinstance(mgr, list):
            m0 = mgr[0]
            if isinstance(m0, dict):
                manager = str(m0.get("name") or "")

        return {
            "code": str(code).zfill(6),
            "name": _var("fS_name") or code,
            "points": points,
            "syl": {k: _var(k) for k in ("syl_1y", "syl_3y", "syl_6y", "syl_1n")},
            "scale": scale,
            "manager": manager,
        }
    except Exception:
        return None


def period_returns(points, year_len=250):
    """从净值序列算区间收益（%）。返回 {1月,3月,6月,1年}。"""
    out = {}
    for label, n in PERIOD_DAYS.items():
        if len(points) >= n + 1:
            out[label] = (points[-1]["nav"] / points[-1 - n]["nav"] - 1) * 100
    return out


def max_drawdown(points, window=None):
    """区间最大回撤（%）。window 为交易日数，None=全部。"""
    pts = points[-window:] if window else points
    if len(pts) < 2:
        return 0.0
    peak, mdd = pts[0]["nav"], 0.0
    for p in pts:
        peak = max(peak, p["nav"])
        dd = (p["nav"] / peak - 1) * 100
        if dd < mdd:
            mdd = dd
    return mdd


def annualized_vol(points, window=250):
    """年化波动率（%）：日收益标准差 × sqrt(250)。"""
    pts = points[-window:] if window else points
    rets = []
    for i in range(1, len(pts)):
        r = math.log(pts[i]["nav"] / pts[i - 1]["nav"])
        rets.append(r)
    if len(rets) < 20:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(250) * 100


def top10_ratio(points_holdings):
    """前十大持仓占净值比例（%）。holdings: [{netasset_ratio}]。"""
    ratios = sorted((float(h.get("netasset_ratio") or 0) for h in points_holdings), reverse=True)
    return sum(ratios[:10])


def fetch_holdings(code: str, report_date: str = None):
    """最新季度持仓（东方财富，写入 fundHoldings.csv 缓存）。返回列表或 []。"""
    import contextlib
    import sys
    from datetime import datetime
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "fund"))
    from fund_analyzer import FundAnalyzer
    if report_date is None:
        today = datetime.now()
        q = (today.month - 1) // 3
        month, day = ("12", "31") if q == 0 else (("03", "31") if q == 1 else (("06", "30") if q == 2 else ("09", "30")))
        report_date = f"{today.year - 1 if q == 0 else today.year}-{month}-{day}"
    try:
        with contextlib.redirect_stdout(sys.stderr):
            result = FundAnalyzer().stockHolding(code, report_date=report_date, page_num=1, page_size=200)
        return (result or {}).get("stocks", []) or []
    except Exception:
        return []


from pathlib import Path  # noqa: E402


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "161631"
    f = fetch_fund(code)
    if not f:
        print("fetch failed")
        sys.exit(1)
    pr = period_returns(f["points"])
    print(f"{f['name']} ({code}) nav={f['points'][-1]['nav']:.4f} scale={f['scale']} mgr={f['manager']}")
    print("periods:", {k: round(v, 2) for k, v in pr.items()})
    print(f"maxdd 1y: {max_drawdown(f['points'], 250):.2f}% vol: {annualized_vol(f['points']):.1f}%")
