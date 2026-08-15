#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""larson-coc — Change of Character + MACD 标注分析（Larson 技能实现）。

对单只（或股票池随机 N 只）A 股：
  1. 拉日K（东财，本地缓存）
  2. 算 MACD(DIF/DEA/柱)，定位 空→多翻红日 / 柱状态 / 柱是否见顶回落
  3. 算 PRC(21/15日) 与量能比(1.5× 触发线) 做 CoC 确认
  4. 生成标注 K 线图：主图(均线+CoC标注) + MACD副图 + 量能，含 Change of Character 判断
  5. 输出端口文分析（每只一段）

用法:
  python3 larson_coc.py 600519                  # 单只
  python3 larson_coc.py --random 6              # 从本地股票池(缓存)kline 随机 6 只并按 CoC 类型归类
  python3 larson_coc.py 002916 002185 --json    # 多只 json
  python3 larson_coc.py --random 6 --out_dir generated/coc
"""
import argparse, glob, json, os, random, sys
import pandas as pd

sys.path.insert(0, "/Users/yyz/.agents/skills/stock/_shared")
from kline import fetch_kline

REPO = "/Users/yyz/pydev/invest2026"
CACHE_POOL = f"{REPO}/generated/cache/kline"
FONT = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS"]

_NAME = {}
for _snap in (f"{REPO}/generated/em/scan_20260808.csv", f"{REPO}/generated/em/scan_20260807.csv"):
    try:
        for _ln in open(_snap):
            _p = _ln.strip().split(",")
            if len(_p) >= 2 and _p[0].isdigit():
                _NAME.setdefault(_p[0], _p[1])
    except Exception:
        pass

def resolve(code):
    return _NAME.get(code, code)


def macd(c: pd.Series):
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = (dif - dea).values
    return dif, dea, hist


def analyze(code, lmt=120, w=70):
    """返回 dict: 各指标 + CoC 判断 + 关键点。"""
    name, pts = fetch_kline(code, lmt=lmt)
    if not pts:
        return {"code": code, "name": resolve(code) or code, "ok": False}
    if not name or name == code:
        name = resolve(code) or code
    df = pd.DataFrame(pts)
    df["x"] = range(len(df))
    c = df["close"].astype(float)
    v = df["volume"].astype(float)
    dif, dea, hv = macd(c)
    dates = df["date"].astype(str).tolist()
    N = len(df); ws = max(N - w, 0)

    # 翻红日(最近一次由负转正，在窗口内)
    flip = None
    for i in range(ws, N):
        if hv[i] > 0 and hv[i - 1] <= 0:
            flip = dates[i]
    # 窗口内柱顶 & 是否为回落
    seg = hv[ws:]
    top_i = ws + int(seg.argmax()) if len(seg) else 0
    top_d, top_v = dates[top_i], round(float(hv[top_i]), 3)
    latest_v, prev_v = round(float(hv[-1]), 3), round(float(hv[-2]), 3)
    rising = latest_v >= prev_v
    peaking = (not rising) and top_i >= N - 8  # 窗口近期刚见顶回落

    # PRC
    def prc(n):
        return (c.iloc[-1] / c.iloc[-1 - n] - 1) * 100 if len(c) > n else float("nan")
    prc21, prc15 = prc(21), prc(15)
    v20 = v.rolling(20).mean().iloc[-2] if len(v) > 21 else float("nan")
    vr = (v.iloc[-1] / v20) if v20 == v20 and v20 > 0 else float("nan")

    # 均线
    def sma(nn):
        return float(c.rolling(nn).mean().iloc[-1]) if len(c) >= nn else float("nan")
    ma = {n: round(sma(n), 2) for n in (5, 20, 30, 50, 200) if len(c) >= n}
    cur = float(c.iloc[-1])

    # —— CoC 判定（数据太短时降级）——
    too_short = len(df) < 40
    red_count = sum(1 for x in hv[ws:] if x > 0)
    if too_short:
        coc = "数据不足(次新/新上市，仅近似)"
        coc_type = "short"
    elif flip and not peaking and latest_v >= 0 and (prc21 is not None and prc21 >= 0):
        coc = "空→多CoC(已确立：翻红+PRC正)"
        coc_type = "bull-coc"
    elif flip and latest_v >= 0 and (prc21 is None or prc21 < 0):
        coc = "空→多CoC(萌芽：仅MACD翻红，PRC仍负待确认)"
        coc_type = "bull-early"
    elif flip and peaking:
        coc = "多→空逆变预警(翻红后柱见顶回落)"
        coc_type = "bear-warn"
    elif not flip and red_count == 0:
        coc = "弱势空头区(MACD全绿，无CoC)"
        coc_type = "bear"
    else:
        coc = "多头区但柱走弱/待变"
        coc_type = "bull-weak"
    return {
        "ok": True, "code": code, "name": name, "date": dates[-1], "close": round(cur, 2),
        "n_pts": len(df), "too_short": too_short,
        "prc21": round(prc21, 1) if prc21 == prc21 else None,
        "prc15": round(prc15, 1) if prc15 == prc15 else None,
        "vr": round(vr, 2) if vr == vr else None,
        "dif": round(float(dif.iloc[-1]), 3), "dea": round(float(dea.iloc[-1]), 3),
        "hist": latest_v, "prev_hist": prev_v, "hist_rising": rising,
        "flip": flip, "top_date": top_d, "top_val": top_v, "peaking": peaking,
        "ma": ma, "coc": coc, "coc_type": coc_type,
    }


def plot(code, res, out_path):
    """生成标注 K 线图：主图 + MACD + 量能。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    plt.rcParams["font.sans-serif"] = FONT
    plt.rcParams["axes.unicode_minus"] = False

    name, pts = fetch_kline(code, lmt=120)
    if not pts or len(pts) < 40:
        return False  # 数据太少不画图（次新股）
    df = pd.DataFrame(pts)
    df["x"] = range(len(df))
    c = df["close"].astype(float); o = df["open"].astype(float)
    h = df["high"].astype(float); l = df["low"].astype(float); v = df["volume"].astype(float)
    dates = df["date"].astype(str).tolist()
    dif, dea, hv = macd(c)
    N = len(df); w = 70; ws = N - w
    sub = df.tail(w).copy()
    dts = pd.to_datetime(df["date"])

    fig, (ax, axm, axv) = plt.subplots(3, 1, figsize=(13, 10.5), sharex=True,
                                       gridspec_kw={"height_ratios": [3.2, 1.0, 0.9], "hspace": 0.10})
    # candlestick
    for _, r in sub.iterrows():
        up = r["close"] >= r["open"]; col = "#e03131" if up else "#2f9e44"
        ax.vlines(r["x"], r["low"], r["high"], color=col, lw=1)
        ax.add_patch(Rectangle((r["x"] - 0.3, min(r["open"], r["close"])), 0.6,
                               max(abs(r["close"] - r["open"]), 0.02), facecolor=col, alpha=0.9, edgecolor=col))
    for nn, col, lab in [(5, "#f59f00", "5MA"), (20, "#1971c2", "20MA"), (30, "#e8590c", "30MA"), (200, "#8f44ad", "200MA")]:
        if len(c) < nn: continue
        m = c.rolling(nn).mean(); ax.plot(sub["x"], m.loc[sub.index], color=col, lw=1.3, label=lab)

    def mark(ds, txt, dy, color):
        i = df.index[df["date"] == ds][0]; y = c.iloc[i]
        ax.scatter(i, y, color=color, zorder=6, s=42)
        ax.annotate(txt, xy=(i, y), xytext=(i + 1.2, y + dy), color=color, fontsize=9.5,
                    fontweight="bold", arrowprops=dict(arrowstyle="->", color=color, lw=1.2))

    mark(dates[-1], f"现价 {c.iloc[-1]:.2f}", -25, "#212529")
    if res.get("flip") and res["flip"] >= dates[ws]:
        mark(res["flip"], f"MACD翻红\n{res['flip'][5:]} 空→多CoC", 9, "#e03131")
    if res.get("top_date") and res["top_date"] >= dates[ws] and res.get("peaking"):
        mark(res["top_date"], f"柱顶 {res['top_val']}", 12, "#f59f00")
    ax.text(0.01, 0.97, f"PRC 21日{res['prc21']:+.1f}%/15日{res['prc15']:+.1f}% · 量比{res['vr']:.2f}x",
            transform=ax.transAxes, fontsize=9, va="top", color="#495057", fontweight="bold")
    ax.legend(loc="upper left", fontsize=8, ncol=4); ax.grid(alpha=0.25)
    ax.set_title(f"{res['name']} ({code})  Larson Change of Character + MACD  ({res['date']} 收{res['close']})",
                 fontsize=13, fontweight="bold")

    hb = hv[ws:]
    axm.bar(sub["x"], hb, color=["#f03e3e" if x >= 0 else "#37b24d" for x in hb], width=0.7, alpha=0.6)
    axm.plot(sub["x"], dif.loc[sub.index], color="#f59f00", lw=1.3, label="DIF")
    axm.plot(sub["x"], dea.loc[sub.index], color="#1971c2", lw=1.3, label="DEA")
    axm.axhline(0, color="#868e96", lw=0.8); axm.legend(loc="upper left", fontsize=8); axm.grid(alpha=0.25)
    axm.set_ylabel("MACD")

    for _, r in sub.iterrows():
        axv.bar(r["x"], r["volume"] / 1e6, color="#e03131" if r["close"] >= r["open"] else "#2f9e44", alpha=0.6, width=0.6)
    axv.set_ylabel("量(百万股)"); axv.grid(alpha=0.25)
    axv.set_xticks(sub["x"][::5])
    axv.set_xticklabels([d.strftime("%m-%d") for d in dts.loc[sub.index][::5]])

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight"); plt.close(fig)
    return True


def txt_line(res):
    m = res["ma"]
    ma_s = " ".join(f"{n}d:{m.get(n)}" for n in (5, 20, 30) if n in m)
    stat = "↑柱升" if res["hist_rising"] else "↓柱缩"
    prc_s = "/".join(f"{p:+.1f}" if p == p else "n/a" for p in [res["prc21"], res["prc15"]])
    vr = res["vr"]
    vr_s = f"{vr:.2f}x" if vr == vr else "n/a"
    return (f"[{res['coc_type']}] {res['code']} {res['name']:<8} {res['date']} 收{res['close']}  "
            f"MACD柱{res['hist']:+.3f}({stat}): DIF {res['dif']}/DEA {res['dea']} | "
            f"PRC(21/15) {prc_s}% | 量比{vr_s} | {ma_s}\n"
            f"    → {res['coc']}")


def main():
    ap = argparse.ArgumentParser(description="larson-coc CoC+MACD 标注分析")
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--random", type=int, default=0, help="从本地股票池(缓存)kline 随机 N 只")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out_dir", default="generated/coc", help="图输出目录")
    args = ap.parse_args()

    if args.random:
        codes = sorted(p.split("/")[-1][: -5] for p in glob.glob(f"{CACHE_POOL}/*.json"))
        codes = random.sample(codes, min(args.random, len(codes)))
        label = f"股票池随机 {len(codes)} 只"
    else:
        codes = args.codes
        label = f"指定 {len(codes)} 只"
    if not codes:
        sys.exit("需指定代码，或 --random N")

    outs = []
    for code in codes:
        res = analyze(code)
        if not res.get("ok"):
            print(f"{code}: 拉取失败"); continue
        png = os.path.join(args.out_dir, f"coc_{code}.png")
        try:
            if not plot(code, res, png):
                png = "(数据不足/未绘图)"
        except Exception as e:
            png = f"(图失败 {e})"
        res["png"] = png
        outs.append(res)

    # 按 CoC 类型归类
    order = {"bull-coc": 0, "bull-early": 1, "bull-weak": 2, "bear-warn": 3, "bear": 4, "short": 5}
    outs.sort(key=lambda r: (order.get(r["coc_type"], 9), -r["close"]))
    if args.json:
        print(json.dumps(outs, ensure_ascii=False, indent=1))
        return
    print(f"\n=== Larson Change of Character — {label} ===")
    head = {"bull-coc": "🔴 空→多CoC（已确立）", "bull-early": "🟠 空→多CoC（萌芽待确认）",
            "bull-weak": "🟡 多头区但柱走弱", "bear-warn": "🟢 多→空逆变预警", "bear": "🔵 弱势空头区", "short": "⚪ 数据不足(次新)"}
    cur = None
    for r in outs:
        if r["coc_type"] != cur:
            cur = r["coc_type"]; print(f"\n## {head.get(cur, cur)}")
        print(txt_line(r))
        print(f"    图: {r['png']}")
    print("\n(技术面仅供参考，不构成投资建议)")


if __name__ == "__main__":
    main()
