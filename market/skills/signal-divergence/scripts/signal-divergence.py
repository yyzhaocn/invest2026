#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
signal-divergence: 底背离 + 确认条件共振选股（恒生电子 7-24 模式）。

条件（底背离.md 原则 + 恒生案例复盘）：
  ① 底背离（MACD/RSI/KDJ/量价 ≥2 重共振），摆动2 在最近 N 天
  ② MACD 金叉（DIF > DEA）
  ③ MACD 柱翻红（DIF - DEA > 0）
  ④ 均线多头（SMA5 > SMA20）
  ⑤ 低位（现价在近 60 日 30% 分位以下）

评分 = 满足条件数（0-5）。全满足 = 恒生 7-24 同款完整信号。

用法:
  python3 signal-divergence.py                       # 扫全部缓存股票
  python3 signal-divergence.py --recent 3            # 背离摆动2在最近3天
  python3 signal-divergence.py --account 7维选股
  python3 signal-divergence.py --block BK0448
  python3 signal-divergence.py --min-score 2 --json
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from kline import kline_cache_dir, fetch_kline, resolve_name  # noqa: E402

DM_PATH = Path(__file__).resolve().parents[2] / "divergence-multi" / "scripts" / "divergence-multi.py"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
PORTFOLIO = "/Users/yyz/.agents/skills/stock/portfolio/scripts/portfolio.py"

_name_cache = {}


def dm():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dm", str(DM_PATH))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fix_name(code, name):
    if name and name != code:
        return name
    if code not in _name_cache:
        try:
            _name_cache[code] = resolve_name(code)
        except Exception:
            _name_cache[code] = code
    return _name_cache[code]


def cached_stocks():
    out = []
    for f in kline_cache_dir().glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("points"):
                out.append((f.stem, d.get("name") or f.stem))
        except Exception:
            pass
    return out


def block_stocks(bk):
    out, pn = [], 1
    while True:
        p = subprocess.run(["curl", "-sS", "--max-time", "12", "-H", f"User-Agent: {UA}",
                            "-H", "Referer: https://quote.eastmoney.com/",
                            f"https://push2delay.eastmoney.com/api/qt/clist/get?pn={pn}&pz=100&po=1&np=1&fltt=2&invt=2&fid=f20&fs=b:{bk}&fields=f12,f14"],
                           capture_output=True, text=True)
        if p.returncode != 0 or not p.stdout.strip():
            break
        d = json.loads(p.stdout)
        diff = (d.get("data") or {}).get("diff") or []
        out += [(r["f12"], r["f14"]) for r in diff]
        if len(out) >= ((d.get("data") or {}).get("total") or 0):
            break
        pn += 1
    return out


def account_stocks(account):
    p = subprocess.run(["python3", PORTFOLIO, "--account", account, "show", "--json"],
                       capture_output=True, text=True, timeout=30)
    pf = json.loads(p.stdout)
    pos = pf["positions"]
    if isinstance(pos, dict):
        return [(k, v.get("name", k)) for k, v in pos.items()]
    return [(x["code"], x["name"]) for x in pos]


def load_cached(code):
    p = kline_cache_dir() / f"{code}.json"
    if not p.exists():
        return None, None
    d = json.loads(p.read_text(encoding="utf-8"))
    return d.get("name"), d.get("points")


def evaluate(code, m, recent_days, end_date=""):
    """底背离 + 确认条件评估（直接读缓存 K 线，避免实时拉取）。返回 dict 或 None。"""
    nm, pts = load_cached(code)
    if not pts or len(pts) < 40:
        return None
    import pandas as pd
    df = pd.DataFrame(pts)
    if end_date:
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["date"] <= pd.Timestamp(end_date)]
    closes = df["close"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()

    # 底背离（live 即时检测 window=2：捕捉最近形成的新背离，右窗口截断）
    divs = m.detect_multi(df, 2, live=True)
    bottom = [d for d in divs if d["type"] == "底背离" and d["score"] >= 2]
    if not bottom:
        return None
    d = bottom[0]
    p2 = str(d["p2_date"])[:10]
    if end_date:
        cutoff = (pd.Timestamp(end_date) - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    else:
        cutoff = (datetime.now() - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    if p2 < cutoff or (end_date and p2 > end_date):
        return None

    # 确认条件
    close = closes[-1]
    sma5 = sum(closes[-5:]) / 5
    sma20 = sum(closes[-20:]) / 20
    rsi_s = m.rsi_series(closes)
    dif_s = m.macd_dif_series(closes)
    deas = m.ema_series(dif_s, 9)
    dif, dea = dif_s[-1], deas[-1]
    hi60, lo60 = max(highs[-60:]), min(lows[-60:])
    pos_pct = (close - lo60) / (hi60 - lo60) * 100 if hi60 > lo60 else 100

    conds = {
        "MACD金叉": dif > dea,
        "MACD柱翻红": (dif - dea) > 0,
        "均线多头": sma5 > sma20,
        "低位(30%分位下)": pos_pct < 30,
    }
    score = sum(1 for v in conds.values() if v)
    return {"code": code, "name": fix_name(code, nm),
            "div_score": d["score"], "indicators": d["indicators"],
            "p1_date": str(d["p1_date"])[:10], "p2_date": p2,
            "price": round(close, 2), "pos_pct": round(pos_pct, 0),
            "confirm": conds, "score": score}


def plot_annotated(code, r, m, out=None):
    """标注 K 线图：底背离连线 + MACD金叉 + 近60日支撑/压力 + 摆动点。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    import pandas as pd
    nm, pts = load_cached(code)
    if not pts:
        return None
    df = pd.DataFrame(pts)
    df["date"] = pd.to_datetime(df["date"])
    closes = df["close"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    dif_s = m.macd_dif_series(closes)
    deas = m.ema_series(dif_s, 9)
    xn = mdates.date2num(df["date"])

    rsi_s = m.rsi_series(closes)
    k_s = m.kdj_k_series(highs, lows, closes)
    d_s = m.ema_series(k_s, 3)
    j_s = [3*a-2*b if a is not None and b is not None else None for a, b in zip(k_s, d_s)]
    d1, d2 = pd.Timestamp(r["p1_date"]), pd.Timestamp(r["p2_date"])
    i1 = (df["date"] == d1).idxmax(); i2 = (df["date"] == d2).idxmax()

    fig, axes = plt.subplots(4, 1, figsize=(13, 13), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1, 1, 1]})
    ax, axr, axm, axk = axes
    fig.suptitle(f"{r['name']} ({code}) 底背离+确认信号 ｜ {r['p1_date']}→{r['p2_date']} ｜ 确认{r['score']}/5",
                 fontsize=13, fontweight="bold", color="#222")

    # K线
    for i, row in df.iterrows():
        up = row["close"] >= row["open"]
        c = "#d63031" if up else "#2ecc71"
        ax.vlines(xn[i], row["low"], row["high"], color=c, lw=0.7)
        ax.add_patch(plt.Rectangle((xn[i]-0.3, min(row["open"], row["close"])), 0.6,
                                   abs(row["close"]-row["open"]) or 0.01, color=c, alpha=0.9))
    # 摆动低点连线
    ax.plot([xn[i1], xn[i2]], [lows[i1], lows[i2]], color="#f03e3e", lw=1.8, ls="--")
    ax.scatter([xn[i1], xn[i2]], [lows[i1], lows[i2]], color="#f03e3e", s=45, zorder=5)
    ax.annotate(f"底背离 {r['p1_date'][5:]}→{r['p2_date'][5:]}", xy=(xn[i2], lows[i2]),
                xytext=(xn[i2]-6, lows[i2]-3), color="#f03e3e", fontsize=10, fontweight="bold")
    # 近60日支撑/压力
    hi60, lo60 = max(highs[-60:]), min(lows[-60:])
    ax.axhline(hi60, color="#3b82f6", lw=0.8, ls=":", alpha=0.8)
    ax.axhline(lo60, color="#2ecc71", lw=0.8, ls=":", alpha=0.8)
    ax.text(xn[0], hi60*1.002, f"60日压力 {hi60:.2f}", color="#3b82f6", fontsize=9)
    ax.text(xn[0], lo60*0.995, f"60日支撑 {lo60:.2f}", color="#2ecc71", fontsize=9)
    # MACD 金叉标注
    cross_i = None
    for i in range(1, len(dif_s)):
        if dif_s[i] is not None and deas[i] is not None and dif_s[i-1] is not None and deas[i-1] is not None:
            if dif_s[i-1] <= deas[i-1] and dif_s[i] > deas[i]:
                cross_i = i
    if cross_i is not None:
        ax.scatter([xn[cross_i]], [highs[cross_i]*1.02], marker="^", s=140, color="#ffd700", zorder=6, edgecolors="#222")
        ax.annotate(f"MACD金叉 {df['date'].iloc[cross_i].strftime('%m-%d')}", xy=(xn[cross_i], highs[cross_i]*1.02),
                    xytext=(xn[cross_i]+3, highs[cross_i]*1.04), color="#b8860b", fontsize=10, fontweight="bold")
    ax.set_ylabel("价格"); ax.grid(alpha=0.2)

    # RSI 子图（始终标注摆动点+RSI值；背离时画红线）
    axr.plot(xn, rsi_s, color="#7048e8", lw=1.1)
    axr.axhline(30, color="#888", lw=0.6, ls="--"); axr.axhline(70, color="#888", lw=0.6, ls="--")
    rsi_div = "RSI" in r["indicators"]
    axr.plot([xn[i1], xn[i2]], [rsi_s[i1], rsi_s[i2]], color="#f03e3e" if rsi_div else "#888", lw=1.5, ls="--", alpha=0.9)
    axr.scatter([xn[i1], xn[i2]], [rsi_s[i1], rsi_s[i2]], s=30, zorder=5,
                color="#f03e3e" if rsi_div else "#9aa0a6")
    axr.annotate(f"RSI {rsi_s[i1]:.0f}→{rsi_s[i2]:.0f}" + (" 背离" if rsi_div else " 未背离"),
                 xy=(xn[i2], rsi_s[i2]), xytext=(xn[i2]+2, rsi_s[i2]+4), fontsize=9,
                 color="#f03e3e" if rsi_div else "#888")
    axr.set_ylabel("RSI"); axr.grid(alpha=0.2)

    # MACD 子图
    for i in range(len(dif_s)):
        if dif_s[i] is None: continue
        hist = (dif_s[i] - deas[i]) if deas[i] is not None else 0
        axm.bar(xn[i], hist, width=0.6, color="#d63031" if hist >= 0 else "#2ecc71", alpha=0.7)
    axm.plot(xn, dif_s, color="#f59e0b", lw=1, label="DIF")
    axm.plot(xn, deas, color="#3b82f6", lw=1, label="DEA")
    axm.axhline(0, color="#888", lw=0.5)
    if "MACD" in r["indicators"]:
        axm.plot([xn[i1], xn[i2]], [dif_s[i1], dif_s[i2]], color="#f03e3e", lw=1.5, ls="--")
    if cross_i is not None:
        axm.scatter([xn[cross_i]], [dif_s[cross_i]], marker="^", s=110, color="#ffd700", zorder=6, edgecolors="#222")
    axm.set_ylabel("MACD"); axm.legend(fontsize=8, loc="upper left"); axm.grid(alpha=0.2)

    # KDJ 子图（始终标注摆动点；背离时画红线）
    axk.plot(xn, k_s, color="#2ecc71", lw=1.1, label="K")
    axk.plot(xn, d_s, color="#f0b45a", lw=1.1, label="D")
    axk.plot(xn, j_s, color="#9aa0a6", lw=0.8, label="J")
    axk.axhline(20, color="#888", lw=0.6, ls="--"); axk.axhline(80, color="#888", lw=0.6, ls="--")
    kdj_div = "KDJ" in r["indicators"]
    axk.plot([xn[i1], xn[i2]], [k_s[i1], k_s[i2]], color="#f03e3e" if kdj_div else "#888", lw=1.5, ls="--", alpha=0.9)
    axk.scatter([xn[i1], xn[i2]], [k_s[i1], k_s[i2]], s=30, zorder=5,
                color="#f03e3e" if kdj_div else "#9aa0a6")
    axk.annotate(f"K {k_s[i1]:.0f}→{k_s[i2]:.0f}" + (" 背离" if kdj_div else " 未背离"),
                 xy=(xn[i2], k_s[i2]), xytext=(xn[i2]+2, k_s[i2]+4), fontsize=9,
                 color="#f03e3e" if kdj_div else "#888")
    axk.set_ylabel("KDJ"); axk.legend(fontsize=8, loc="upper left"); axk.grid(alpha=0.2)
    axk.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    fig.tight_layout()
    outp = Path(out) if out else Path.cwd() / "generated" / f"signal_div_{code}.png"
    outp.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outp, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return str(outp)


def verify_results(results, end_date):
    """事后验证：end_date 收盘买入 → 最新收盘，计算收益与胜率。"""
    import pandas as pd
    rows = []
    for r in results:
        nm, pts = load_cached(r["code"])
        if not pts:
            continue
        df = pd.DataFrame(pts)
        df["date"] = pd.to_datetime(df["date"])
        buy_df = df[df["date"] <= pd.Timestamp(end_date)]
        if buy_df.empty:
            continue
        buy = buy_df["close"].astype(float).iloc[-1]
        sell = df["close"].astype(float).iloc[-1]
        last_d = df["date"].iloc[-1].strftime("%m-%d")
        rows.append({"code": r["code"], "name": r["name"], "buy": buy, "sell": sell,
                     "ret": (sell / buy - 1) * 100, "last": last_d})
    rows.sort(key=lambda x: -x["ret"])
    print(f"\n=== 事后验证（{end_date} 收盘买入 → 最新）===")
    print(f"{'代码':8s}{'名称':10s}{'买入':>9s}{'最新':>8s}{'收益':>8s}  至")
    for x in rows:
        print(f"{x['code']:8s}{x['name']:10s}{x['buy']:>9.2f}{x['sell']:>8.2f}{x['ret']:>+7.1f}%  {x['last']}")
    if rows:
        pos = sum(1 for x in rows if x["ret"] > 0)
        avg = sum(x["ret"] for x in rows) / len(rows)
        print(f"\n胜率: {pos}/{len(rows)} ｜ 平均收益: {avg:+.1f}%")
    return rows


def main():
    ap = argparse.ArgumentParser(description="底背离+确认条件共振选股")
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--block")
    ap.add_argument("--account")
    ap.add_argument("--recent", type=int, default=3, help="背离摆动2在最近 N 天（默认 3）")
    ap.add_argument("--min-score", type=int, default=2, help="背离最低共振分")
    ap.add_argument("--min-confirm", type=int, default=3, help="确认条件最低满足数（默认 3）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--view", action="store_true", help="生成看板 HTML")
    ap.add_argument("--plot", action="store_true", help="对命中股票画标注K线图（PNG）")
    ap.add_argument("--end-date", default="", help="数据截断日（YYYY-MM-DD）——找该日收盘后可确认的背离")
    ap.add_argument("--verify", action="store_true", help="事后验证：end_date 收盘买入 → 最新，输出收益+胜率")
    args = ap.parse_args()

    m = dm()
    if args.block:
        targets = block_stocks(args.block); label = f"板块 {args.block}"
    elif args.account:
        targets = account_stocks(args.account); label = f"组合 {args.account}"
    elif args.codes:
        targets = [(c, "") for c in args.codes]; label = "代码列表"
    else:
        targets = cached_stocks(); label = f"缓存股票池"

    results = []
    for i, (code, name) in enumerate(targets):
        r = evaluate(code, m, args.recent, args.end_date)
        if r and r["div_score"] >= args.min_score and r["score"] >= args.min_confirm:
            results.append(r)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(targets)}", file=sys.stderr, flush=True)

    results.sort(key=lambda r: (-r["score"], -r["div_score"]))
    if args.verify:
        verify_results(results, args.end_date or datetime.now().strftime("%Y-%m-%d"))
        return
    if args.plot:
        for r in results:
            p = plot_annotated(r["code"], r, m)
            print(f"  {r['name']}: {p}" if p else f"  {r['code']} 无数据")
        return
    if args.json:
        print(json.dumps({"scanned": len(targets), "recent_days": args.recent, "results": results},
                         ensure_ascii=False, indent=1))
        return

    print(f"\n=== {label} 底背离+确认共振 {len(results)} 条（最近{args.recent}天，确认≥{args.min_confirm}/5）===")
    for r in results:
        ck = " ".join(k for k, v in r["confirm"].items() if v)
        print(f"{'⭐' if r['score'] >= 4 else '✅' if r['score'] == 3 else '·'} 确认{r['score']}/5 背离{r['div_score']}重 "
              f"{r['name']}({r['code']}) {r['p1_date']}→{r['p2_date']} 现价{r['price']} 分位{r['pos_pct']:.0f}% | {ck}")


if __name__ == "__main__":
    main()
