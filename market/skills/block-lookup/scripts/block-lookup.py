#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
block-lookup: 查任意 A 股所属东财行业板块（一级/二级/三级）+ 地域板块 + 概念标签。

输入支持股票代码（6 位）或股票名称。数据源：
  - 个股行业归属: push2delay /api/qt/stock/get (f127 二级行业, f128 地域, f129 概念)
  - 板块分级列表: _shared/boards.py load_boards("行业")（一/二/三级，1 小时缓存）

用法:
  python3 block-lookup.py <股票代码或名称> [--json]
  python3 block-lookup.py 300684
  python3 block-lookup.py 中石科技 --json
"""
import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from boards import load_boards  # noqa: E402
from httpget import httpget  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Referer": "https://quote.eastmoney.com/"}

SUFFIX_RE = re.compile(r"[ⅠⅡⅢⅣⅤ一二三四五六七八九十]+$")

# 无后缀二级行业 → 一级行业映射（东财命名不统一，如 小金属→有色金属）
IND_MAP = {
    "小金属": ["有色金属"], "工业金属": ["有色金属"], "贵金属": ["有色金属"],
    "能源金属": ["有色金属"], "化学制药": ["医药生物"], "生物制品": ["医药生物"],
    "医疗器械": ["医药生物"], "医疗服务": ["医药生物"], "中药": ["医药生物"],
    "软件开发": ["计算机"], "IT服务": ["计算机"], "游戏": ["传媒"],
    "白酒": ["食品饮料"], "半导体": ["电子"], "专用设备": ["机械设备"],
    "通用设备": ["机械设备"], "光学光电子": ["电子"], "元件": ["电子"],
    "电池": ["电力设备"], "光伏设备": ["电力设备"], "风电设备": ["电力设备"],
}


def resolve_code(q: str) -> str:
    """股票代码或名称 → 6 位代码（名称走东财 suggest 接口）。"""
    q = q.strip()
    if re.fullmatch(r"\d{6}", q):
        return q
    url = "https://searchapi.eastmoney.com/api/suggest/get?" + urllib.parse.urlencode(
        {"input": q, "type": "14", "token": "D43BF722C8E33BDC906FB84D85E326E8", "count": 5})
    try:
        r = httpget(url, headers=UA, timeout=10)
        d = r.json()
        for item in (d.get("QuotationCodeTable", {}).get("Data") or []):
            if item.get("Name") == q and item.get("SecurityTypeName") in ("深A", "沪A", "京A", "深A(退市)", "沪A(退市)"):
                return item["Code"]
    except Exception as e:
        raise SystemExit(f"❌ 名称解析失败: {e}")
    raise SystemExit(f"❌ 未找到股票: {q}")


def stock_industry(code: str) -> dict:
    """拉个股 f127/f128/f129。f127=二级行业名, f128=地域, f129=概念。"""
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    r = httpget("https://push2delay.eastmoney.com/api/qt/stock/get",
                params={"secid": secid, "fields": "f57,f58,f127,f128,f129"},
                headers=UA, timeout=10)
    d = (r.json() or {}).get("data") or {}
    if not d or not d.get("f58"):
        raise SystemExit(f"❌ 未查询到 {code} 的行业信息（接口返回空，稍后重试）")
    return d


def match_industry(ind_name: str, boards: list) -> dict:
    """在行业分级列表中定位 ind_name（f127 二级行业名）对应的一/二/三级板块。"""
    base = SUFFIX_RE.sub("", ind_name or "")  # 电子化学品Ⅱ -> 电子化学品
    l1 = l2 = l3 = None
    for b in boards:
        nm = b.get("name", "")
        if nm == ind_name:                      # 精确命中（通常为二级）
            l2 = b
        elif b.get("level") == "三级":
            core = nm[2:] if nm.startswith("其他") else nm  # 其他小金属 -> 小金属
            cand = core == base + "Ⅲ" or core == base or core == "其他" + base
            if not cand and l3 is None and core.startswith(base) and len(core) > len(base):
                cand = True  # 兜底：半导体设备(三级) 匹配 base=半导体
            if cand:
                l3 = b
        elif b.get("level") == "一级" and base.startswith(nm):
            l1 = b
    if l3 and l2 and l2.get("level") == "三级":  # f127 若返回三级名
        l2, l3 = l3, None
    if not l1:                                    # 映射表兜底
        for lv_name in IND_MAP.get(base, []):
            l1 = next((b for b in boards if b.get("level") == "一级" and b.get("name") == lv_name), None)
            if l1:
                break
    return {"一级": l1, "二级": l2, "三级": l3}


def match_region(region_name: str, boards: list) -> dict:
    """地域板块匹配（load_boards 无地域，用一级行业接口拿不到则跳过）。"""
    return {}


def main():
    ap = argparse.ArgumentParser(description="查任意 A 股的东财行业板块（一/二/三级）+ 概念")
    ap.add_argument("query", help="股票代码（6位）或名称")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--refresh", action="store_true", help="强制刷新板块缓存")
    args = ap.parse_args()

    code = resolve_code(args.query)
    info = stock_industry(code)
    name, ind, region, concepts = info.get("f58"), info.get("f127"), info.get("f128"), info.get("f129")

    boards = load_boards("行业", refresh=args.refresh)
    matched = match_industry(ind, boards)

    out = {
        "code": code, "name": name,
        "industry_2nd": ind,
        "industry": {lv: ({"code": b.get("code"), "name": b.get("name")} if b else None)
                     for lv, b in matched.items()},
        "region": region,
        "concepts": [c for c in (concepts or "").split(",") if c],
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"{name} ({code}) 东财行业归属：")
    for lv in ("一级", "二级", "三级"):
        b = matched[lv]
        if b:
            print(f"  {lv}: {b.get('name')} ({b.get('code')})")
        else:
            print(f"  {lv}: —")
    print(f"  地域: {region or '—'}")
    if concepts:
        print(f"  概念: {concepts}")


if __name__ == "__main__":
    main()
