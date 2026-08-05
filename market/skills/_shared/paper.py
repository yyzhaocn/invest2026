#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纸面交易共享数据层 (portfolio / trade-journal / performance 共用)。

持久化 (git 忽略，位于 shared/paper/):
  portfolio.json  - 现金与持仓
  trades.csv      - 全部买卖流水 (含已实现盈亏)
  snapshots.csv   - 每日组合净值快照

行情:
  - 股票: push2delay ulist 实时行情
  - 基金: fund.eastmoney.com/pingzhongdata 最新净值 (日更)
"""
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PAPER_DIR = REPO_ROOT / "shared" / "paper"
PORTFOLIO_FILE = PAPER_DIR / "portfolio.json"
TRADES_FILE = PAPER_DIR / "trades.csv"
SNAPSHOTS_FILE = PAPER_DIR / "snapshots.csv"
FUNDCODE_FILE = REPO_ROOT / "fund" / "fundcode.csv"

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}

_fund_codes = None


# ---------- 数据存取 ----------

def load_portfolio() -> dict:
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"base_capital": 100000.0, "cash": 100000.0, "positions": {}, "created": ""}


def save_portfolio(pf: dict):
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    if not pf.get("created"):
        pf["created"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    PORTFOLIO_FILE.write_text(json.dumps(pf, ensure_ascii=False, indent=2), encoding="utf-8")


def init_portfolio(cash: float, force: bool = False) -> dict:
    pf = load_portfolio()
    if (pf.get("positions") or pf.get("cash")) and not force:
        raise ValueError(f"组合已存在 (现金 {pf['cash']:.2f}, {len(pf.get('positions', {}))} 个持仓)；如需重置用 --force")
    pf = {"base_capital": float(cash), "cash": float(cash), "positions": {},
          "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    save_portfolio(pf)
    return pf


def load_trades() -> list:
    if not TRADES_FILE.exists():
        return []
    with open(TRADES_FILE, encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def append_trade(trade: dict):
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ts", "date", "side", "code", "name", "kind", "qty", "price", "amount", "note", "realized_pnl"]
    new = not TRADES_FILE.exists()
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new:
            w.writeheader()
        w.writerow({k: trade.get(k, "") for k in fieldnames})


def load_snapshots() -> list:
    if not SNAPSHOTS_FILE.exists():
        return []
    with open(SNAPSHOTS_FILE, encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def record_snapshot(total_value: float, cash: float, market_value: float,
                    total_pnl: float, day_pnl: float = None):
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    rows = load_snapshots()
    prev = None
    for r in rows:
        if r["date"] == date:
            prev = r
            break
    if prev:
        # 当日已有快照：更新（幂等）
        rows = [r for r in rows if r["date"] != date]
    base = float(prev["total_value"]) if prev else (total_value - (day_pnl or 0))
    if day_pnl is None:
        day_pnl = total_value - base
    day_pct = (day_pnl / base * 100) if base else 0.0
    total_pct = (total_pnl / float(load_portfolio()["base_capital"]) * 100) if prev is None else total_pnl / float(prev["total_value"]) * 100
    # 用 base_capital 算总收益率
    pf = load_portfolio()
    total_pct = total_pnl / float(pf.get("base_capital", 100000)) * 100
    row = {"date": date, "total_value": round(total_value, 2), "cash": round(cash, 2),
           "market_value": round(market_value, 2), "day_pnl": round(day_pnl, 2),
           "day_pct": round(day_pct, 4), "total_pnl": round(total_pnl, 2),
           "total_pct": round(total_pct, 4)}
    rows.append(row)
    rows.sort(key=lambda r: r["date"])
    with open(SNAPSHOTS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerows(rows)
    return row


# ---------- 行情 ----------

def is_fund(code: str) -> bool:
    global _fund_codes
    if _fund_codes is None:
        _fund_codes = set()
        if FUNDCODE_FILE.exists():
            for line in FUNDCODE_FILE.read_text(encoding="utf-8-sig").splitlines()[1:]:
                parts = line.split(",")
                if parts and parts[0].strip().isdigit():
                    _fund_codes.add(parts[0].strip())
    return code in _fund_codes


def batch_quotes(codes) -> dict:
    """批量取股票实时行情，返回 {code: {name, price, pct}}。"""
    import requests
    result = {}
    unique = list(dict.fromkeys(c for c in codes if c))
    for i in range(0, len(unique), 80):
        chunk = unique[i:i + 80]
        secids = ",".join(f"{'1' if c.startswith('6') else '0'}.{c}" for c in chunk)
        try:
            resp = requests.get("https://push2delay.eastmoney.com/api/qt/ulist.np/get",
                                params={"fltt": 2, "secids": secids, "fields": "f12,f14,f2,f3",
                                        "ut": "fa5fd1943c7b386f172d6893dbfba10b"},
                                timeout=15, headers=UA)
            resp.raise_for_status()
            for item in (resp.json().get("data") or {}).get("diff") or []:
                code = str(item.get("f12", "")).zfill(6)
                if item.get("f2") in (None, "-"):
                    continue
                result[code] = {"name": str(item.get("f14", code)),
                                "price": float(item.get("f2")),
                                "pct": float(item.get("f3", 0) or 0)}
        except Exception:
            continue
    return result


def get_fund_nav(code: str):
    """取基金最新单位净值。返回 (nav, name, date) 或 (None, None, None)。"""
    import requests
    try:
        resp = requests.get(f"https://fund.eastmoney.com/pingzhongdata/{code}.js",
                            timeout=15, headers=UA)
        resp.raise_for_status()
        text = resp.text
        m = re.search(r"var Data_netWorthTrend = (\[.*?\]);", text, re.DOTALL)
        if not m:
            return None, None, None
        trend = json.loads(m.group(1))
        if not trend:
            return None, None, None
        last = trend[-1]
        nav = float(last.get("y", 0))
        date = datetime.fromtimestamp(int(last["x"]) / 1000).strftime("%Y-%m-%d")
        nm = re.search(r'var fS_name = "([^"]+)";', text)
        name = nm.group(1) if nm else code
        return nav, name, date
    except Exception:
        return None, None, None


def get_price(code: str):
    """获取标的价格。返回 (price, name, kind, extra)。kind: stock/fund。"""
    code = str(code).zfill(6)
    if is_fund(code):
        nav, name, date = get_fund_nav(code)
        if nav is None:
            return None, None, "fund", {"error": "未取到基金净值"}
        return nav, (name or code), "fund", {"nav_date": date}
    quotes = batch_quotes([code])
    q = quotes.get(code)
    if not q:
        return None, None, "stock", {"error": "无行情（代码可能不存在/停牌）"}
    return q["price"], q["name"], "stock", {"pct": q["pct"]}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        print("paper dir:", PAPER_DIR)
        print("portfolio exists:", PORTFOLIO_FILE.exists())
        code = sys.argv[2] if len(sys.argv) > 2 else "600600"
        print("is_fund(600600):", is_fund("600600"), "| is_fund(161631):", is_fund("161631"))
        price, name, kind, extra = get_price(code)
        print(f"get_price({code}): {price} {name} ({kind}) {extra}")
