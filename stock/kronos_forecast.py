#!/usr/bin/env python3
"""Use Kronos foundation model to forecast A-share K-line (daily)."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle
import requests

plt.rcParams["font.sans-serif"] = [
    "PingFang SC",
    "Hiragino Sans GB",
    "STHeiti",
    "Arial Unicode MS",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False

STOCK_DIR = Path(__file__).resolve().parent
REPO_ROOT = STOCK_DIR.parent
KRONOS_ROOT = Path(os.environ.get("KRONOS_ROOT", "/Users/yyz/pydev/Kronos"))
OUTPUT_DIR = STOCK_DIR / "generated" / "kronos"
KLINE_CACHE_DIR = OUTPUT_DIR / "cache"
KLINE_CACHE_EXPIRE_TRADING_SECONDS = 10 * 60  # 交易时段 10 分钟 TTL

DEFAULT_LOOKBACK = 30
LONG_LOOKBACK = 400
SHORT_LOOKBACK = 30  # same as default; --short is a no-op alias
MIN_LOOKBACK = 30
WALK_FORWARD_N = 5
DEFAULT_PRED_LEN = 5

MORNING_START = time(9, 30)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
AFTERNOON_END = time(15, 0)

sys.path.insert(0, str(STOCK_DIR))
sys.path.insert(0, str(KRONOS_ROOT))

from trading_calendar import is_trading_day  # noqa: E402
from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    return s


def _normalize_stock_code(stock_code: str) -> str:
    return str(stock_code).strip()


def _kline_cache_path(stock_code: str) -> Path:
    return KLINE_CACHE_DIR / f"kline_{_normalize_stock_code(stock_code)}.csv"


def _is_trading_session(now: datetime | None = None) -> bool:
    """A 股连续竞价时段（9:30–11:30 / 13:00–15:00）。"""
    now = now or datetime.now()
    if not is_trading_day(now):
        return False
    t = now.time()
    return (MORNING_START <= t <= MORNING_END) or (AFTERNOON_START <= t <= AFTERNOON_END)


def _should_use_kline_cache(cache_path: Path, now: datetime | None = None) -> tuple[bool, str]:
    """Return (use_cache, reason). Non-trading session: cache never expires."""
    now = now or datetime.now()
    if not cache_path.is_file():
        return False, "cache_miss"
    if cache_path.stat().st_size <= 0:
        return False, "cache_empty"

    if _is_trading_session(now):
        age = now.timestamp() - cache_path.stat().st_mtime
        if age < KLINE_CACHE_EXPIRE_TRADING_SECONDS:
            return True, f"trading_fresh({int(age)}s)"
        return False, f"trading_expired({int(age)}s)"

    return True, "non_trading_session"


def _load_kline_cache(cache_path: Path) -> pd.DataFrame:
    df = pd.read_csv(cache_path)
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    return df.sort_values("timestamps").reset_index(drop=True)


def _save_kline_cache(df: pd.DataFrame, cache_path: Path) -> None:
    KLINE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(".csv.tmp")
    df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
    tmp_path.replace(cache_path)


def _fetch_daily_kline_remote(stock_code: str) -> pd.DataFrame:
    """Fetch daily OHLCV from API; prefer Eastmoney, fallback to Sina."""
    try:
        return _fetch_eastmoney_kline(stock_code)
    except Exception as exc:
        print(f"Eastmoney K线失败 ({exc})，改用新浪数据源")
        return _fetch_sina_kline(stock_code)


def fetch_daily_kline(stock_code: str) -> pd.DataFrame:
    """Fetch daily OHLCV with cross-run cache under generated/kronos/cache/."""
    stock_code = _normalize_stock_code(stock_code)
    cache_path = _kline_cache_path(stock_code)
    now = datetime.now()
    in_session = _is_trading_session(now)
    use_cache, reason = _should_use_kline_cache(cache_path, now)
    print(
        f"[K线缓存] code={stock_code} path={cache_path} "
        f"exists={cache_path.is_file()} trading_session={in_session} -> {reason}"
    )
    if use_cache:
        try:
            df = _load_kline_cache(cache_path)
            print(f"从本地缓存读取K线数据: {cache_path} ({reason}, {len(df)} 行)")
            return df
        except Exception as exc:
            print(f"读取K线缓存失败 ({exc})，将重新下载")
            reason = "cache_read_error"

    print(f"从API下载K线数据: {stock_code} ({reason})")
    df = _fetch_daily_kline_remote(stock_code)
    _save_kline_cache(df, cache_path)
    print(f"K线数据已缓存: {cache_path} ({len(df)} 行)")
    return df


def _fetch_sina_kline(stock_code: str) -> pd.DataFrame:
    if stock_code.startswith(("0", "3")):
        symbol = f"sz{stock_code}"
    elif stock_code.startswith("6"):
        symbol = f"sh{stock_code}"
    else:
        raise ValueError(f"不支持的股票代码: {stock_code}")

    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
        f"?symbol={symbol}&scale=240&ma=no&datalen=1200"
    )
    resp = _session().get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    text = resp.text.strip()
    start = text.find("([")
    end = text.rfind("])")
    if start < 0 or end < 0:
        raise RuntimeError("新浪K线返回格式异常")
    payload = json.loads(text[start + 1 : end + 1])
    rows = []
    for item in payload:
        close = float(item["close"])
        volume = float(item.get("volume") or 0)
        rows.append(
            {
                "timestamps": item["day"],
                "open": float(item["open"]),
                "close": close,
                "high": float(item["high"]),
                "low": float(item["low"]),
                "volume": volume,
                "amount": volume * close,
            }
        )
    df = pd.DataFrame(rows)
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    return df.sort_values("timestamps").reset_index(drop=True)


def _fetch_eastmoney_kline(stock_code: str) -> pd.DataFrame:
    if stock_code.startswith(("0", "3")):
        secid = f"0.{stock_code}"
    elif stock_code.startswith("6"):
        secid = f"1.{stock_code}"
    else:
        raise ValueError(f"不支持的股票代码: {stock_code}")

    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": "1000000",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://quote.eastmoney.com/sz{stock_code}.html",
    }
    resp = _session().get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params=params,
        headers=headers,
        timeout=30,
    )
    match = re.search(r"\((\{.*\})\);?$", resp.text, re.DOTALL)
    if not match:
        raise RuntimeError("K线接口返回格式异常")
    payload = json.loads(match.group(1))
    klines = payload.get("data", {}).get("klines") or []
    if not klines:
        raise RuntimeError(f"未获取到 {stock_code} 的K线数据")

    rows = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 11:
            continue
        rows.append(
            {
                "timestamps": parts[0],
                "open": float(parts[1] or 0),
                "close": float(parts[2] or 0),
                "high": float(parts[3] or 0),
                "low": float(parts[4] or 0),
                "volume": float(parts[5] or 0),
                "amount": float(parts[6] or 0),
            }
        )
    df = pd.DataFrame(rows)
    df["timestamps"] = pd.to_datetime(df["timestamps"])
    return df.sort_values("timestamps").reset_index(drop=True)


def next_trading_days(start: datetime, n: int) -> list[datetime]:
    days: list[datetime] = []
    cur = start
    while len(days) < n:
        cur += timedelta(days=1)
        if is_trading_day(cur):
            days.append(cur)
    return days


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _add_day_separators(
    axes,
    context_df: pd.DataFrame,
    pred_dates: pd.Series | pd.Index,
) -> None:
    day_marks = pd.to_datetime(pd.Series(pred_dates).drop_duplicates().sort_values())
    today = None
    boundary = None
    if not context_df.empty:
        today = pd.to_datetime(context_df["timestamps"].iloc[-1])
        if len(day_marks):
            first_pred = day_marks.iloc[0]
            if first_pred > today:
                boundary = today + (first_pred - today) / 2

    today_norm = today.normalize() if today is not None else None

    for ax in axes:
        for day in day_marks:
            if today_norm is not None and pd.to_datetime(day).normalize() == today_norm:
                continue
            ax.axvline(day, color="#94a3b8", linewidth=1.0, alpha=0.55, zorder=0)
        if today is not None:
            ax.axvline(
                today,
                color="#334155",
                linewidth=2.2,
                alpha=0.85,
                zorder=1,
            )
        if boundary is not None:
            ax.axvline(
                boundary,
                color="#475569",
                linewidth=1.6,
                linestyle=":",
                alpha=0.95,
                zorder=0,
            )
        ax.grid(True, which="minor", axis="x", alpha=0.12, linestyle="-", linewidth=0.6)


def _candle_width(xnums: list[float]) -> float:
    if len(xnums) < 2:
        return 0.6
    deltas = [xnums[i + 1] - xnums[i] for i in range(len(xnums) - 1)]
    return min(0.8, sorted(deltas)[len(deltas) // 2] * 0.65)


def _draw_candlesticks(
    ax,
    dates: pd.Series | pd.Index,
    opens,
    highs,
    lows,
    closes,
    *,
    variant: str = "hist",
) -> None:
    """Draw OHLC candles. variant: hist | backtest_pred | future_pred."""
    dates = pd.to_datetime(dates)
    xnums = [float(v) for v in mdates.date2num(dates)]
    width = _candle_width(xnums)

    if variant == "hist":
        bull_face, bear_face = "#ef4444", "#22c55e"
        bull_edge, bear_edge = "#b91c1c", "#15803d"
        wick_color = "#374151"
        alpha = 0.85
    elif variant == "backtest_pred":
        bull_face, bear_face = "#bbf7d0", "#dcfce7"
        bull_edge = bear_edge = wick_color = "#16a34a"
        alpha = 0.92
    else:
        bull_face, bear_face = "#fecaca", "#fee2e2"
        bull_edge = bear_edge = wick_color = "#dc2626"
        alpha = 0.92

    for x, o, h, low, c in zip(xnums, opens, highs, lows, closes):
        o, h, low, c = float(o), float(h), float(low), float(c)
        bullish = c >= o
        face = bull_face if bullish else bear_face
        edge = bull_edge if bullish else bear_edge
        ax.plot([x, x], [low, h], color=wick_color, linewidth=0.9, zorder=2, alpha=alpha)
        body_bottom = min(o, c)
        body_height = abs(c - o)
        if body_height < 1e-9:
            ax.plot(
                [x - width / 2, x + width / 2],
                [o, o],
                color=edge,
                linewidth=1.2,
                zorder=3,
                alpha=alpha,
            )
        else:
            ax.add_patch(
                Rectangle(
                    (x - width / 2, body_bottom),
                    width,
                    body_height,
                    facecolor=face,
                    edgecolor=edge,
                    linewidth=0.8,
                    alpha=alpha,
                    zorder=3,
                )
            )


def _annotate_below_axis(
    ax,
    dates: pd.Series | pd.Index,
    labels: list[str],
    *,
    color: str = "#334155",
    rotation: float = 0,
) -> None:
    """Place small labels just below the x-axis at given trading days."""
    dates = pd.to_datetime(dates)
    for day, label in zip(dates, labels):
        ax.annotate(
            label,
            xy=(mdates.date2num(day), 0),
            xycoords=("data", "axes fraction"),
            xytext=(0, -4),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=8,
            color=color,
            rotation=rotation,
            clip_on=False,
        )


def plot_forecast(
    context_df: pd.DataFrame,
    real_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    stock_code: str,
    out_path: Path,
    mode: str | None = None,
    walk_forward_df: pd.DataFrame | None = None,
) -> None:
    fig, (ax_k, ax1, ax2) = plt.subplots(
        3,
        1,
        figsize=(12, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 1.5]},
    )
    backtest = mode == "backtest" if mode is not None else not real_df.empty
    pred_close_color = "#16a34a" if backtest else "#dc2626"
    pred_volume_color = "#86efac" if backtest else "#fca5a5"
    pred_candle_variant = "backtest_pred" if backtest else "future_pred"

    for ax in (ax_k, ax1, ax2):
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")

    _add_day_separators((ax_k, ax1, ax2), context_df, pred_df.index)

    _draw_candlesticks(
        ax_k,
        context_df["timestamps"],
        context_df["open"],
        context_df["high"],
        context_df["low"],
        context_df["close"],
        variant="hist",
    )
    if backtest:
        _draw_candlesticks(
            ax_k,
            real_df["timestamps"],
            real_df["open"],
            real_df["high"],
            real_df["low"],
            real_df["close"],
            variant="hist",
        )
    _draw_candlesticks(
        ax_k,
        pred_df.index,
        pred_df["open"],
        pred_df["high"],
        pred_df["low"],
        pred_df["close"],
        variant=pred_candle_variant,
    )
    ax_k.set_ylabel("K线")
    ax_k.grid(True, alpha=0.3)

    ax1.plot(
        context_df["timestamps"],
        context_df["close"],
        label="历史收盘",
        color="#2563eb",
        linewidth=1.5,
    )
    if backtest:
        ax1.plot(
            real_df["timestamps"],
            real_df["close"],
            label="真实收盘",
            color="#2563eb",
            linewidth=1.5,
        )
    ax1.plot(
        pred_df.index,
        pred_df["close"],
        label="预测收盘",
        color=pred_close_color,
        linewidth=1.8,
        linestyle="--",
    )
    if walk_forward_df is not None and not walk_forward_df.empty:
        wf_ts = pd.to_datetime(walk_forward_df["timestamps"])
        wf_close = walk_forward_df["pred_close"]
        if backtest:
            ax1.plot(
                wf_ts,
                wf_close,
                label="Walk-forward预测",
                color="#15803d",
                linewidth=2.0,
                linestyle="-",
                marker="o",
                markersize=7,
                zorder=5,
            )
        else:
            ax1.scatter(
                wf_ts,
                wf_close,
                color="#16a34a",
                s=55,
                zorder=6,
                label="回溯预测",
                edgecolors="#14532d",
                linewidths=0.8,
            )
            div_labels = [
                f"{row['error_pct']:+.1f}%" if pd.notna(row["error_pct"]) else "—"
                for _, row in walk_forward_df.iterrows()
            ]
            _annotate_below_axis(ax1, wf_ts, div_labels, color="#15803d", rotation=35)
    if not backtest and not pred_df.empty:
        fp_ts = pd.to_datetime(pred_df.index)
        fp_close = pred_df["close"]
        ax1.scatter(
            fp_ts,
            fp_close,
            color="#dc2626",
            s=65,
            zorder=7,
            label=f"前瞻 {len(pred_df)} 日",
            edgecolors="#7f1d1d",
            linewidths=0.8,
        )
        for day, price in zip(fp_ts, fp_close):
            ax1.annotate(
                f"{price:.2f}",
                xy=(mdates.date2num(day), float(price)),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#b91c1c",
                fontweight="bold",
            )
        price_labels = [f"{v:.2f}" for v in fp_close]
        _annotate_below_axis(ax1, fp_ts, price_labels, color="#dc2626", rotation=35)
    ax1.set_ylabel("收盘价")
    title = f"Kronos 回测 — {stock_code} 阳光电源" if backtest else f"Kronos 预测 — {stock_code} 阳光电源"
    ax1.set_title(title)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.bar(
        context_df["timestamps"],
        context_df["volume"],
        color="#93c5fd",
        alpha=0.7,
        label="历史成交量",
        width=0.8,
    )
    if backtest:
        ax2.bar(
            real_df["timestamps"],
            real_df["volume"],
            color="#93c5fd",
            alpha=0.7,
            label="真实成交量",
            width=0.8,
        )
    ax2.bar(
        pred_df.index,
        pred_df["volume"],
        color=pred_volume_color,
        alpha=0.85,
        label="预测成交量",
        width=0.8,
    )
    ax2.set_ylabel("成交量")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    if not backtest and (
        (walk_forward_df is not None and not walk_forward_df.empty)
        or not pred_df.empty
    ):
        fig.subplots_adjust(bottom=0.14)
    else:
        plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_combined(
    context_df: pd.DataFrame,
    future_pred_df: pd.DataFrame,
    stock_code: str,
    out_path: Path,
    walk_forward_df: pd.DataFrame | None = None,
) -> None:
    """Single chart: history (blue) + walk-forward backtrack (green) + future forecast (red)."""
    today = pd.to_datetime(context_df["timestamps"].iloc[-1])

    fig, (ax_k, ax1, ax2) = plt.subplots(
        3,
        1,
        figsize=(12, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 1.5]},
    )

    for ax in (ax_k, ax1, ax2):
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")

    _add_day_separators((ax_k, ax1, ax2), context_df, future_pred_df.index)

    # K-line: historical only + future predicted candles (no walk-forward overlay)
    _draw_candlesticks(
        ax_k,
        context_df["timestamps"],
        context_df["open"],
        context_df["high"],
        context_df["low"],
        context_df["close"],
        variant="hist",
    )
    _draw_candlesticks(
        ax_k,
        future_pred_df.index,
        future_pred_df["open"],
        future_pred_df["high"],
        future_pred_df["low"],
        future_pred_df["close"],
        variant="future_pred",
    )
    ax_k.set_ylabel("K线")
    ax_k.grid(True, alpha=0.3)

    # Close: blue history, green backtrack dots, red forward dots
    ax1.plot(
        context_df["timestamps"],
        context_df["close"],
        label="历史收盘",
        color="#2563eb",
        linewidth=1.5,
    )
    if walk_forward_df is not None and not walk_forward_df.empty:
        wf_ts = pd.to_datetime(walk_forward_df["timestamps"])
        wf_close = walk_forward_df["pred_close"]
        ax1.scatter(
            wf_ts,
            wf_close,
            color="#16a34a",
            s=55,
            zorder=6,
            label=f"回溯 {len(walk_forward_df)} 日",
            edgecolors="#14532d",
            linewidths=0.8,
        )
        div_labels = [
            f"{row['error_pct']:+.1f}%" if pd.notna(row["error_pct"]) else "—"
            for _, row in walk_forward_df.iterrows()
        ]
        _annotate_below_axis(ax1, wf_ts, div_labels, color="#15803d", rotation=35)

    if not future_pred_df.empty:
        fp_ts = pd.to_datetime(future_pred_df.index)
        fp_close = future_pred_df["close"]
        ax1.scatter(
            fp_ts,
            fp_close,
            color="#dc2626",
            s=65,
            zorder=7,
            label=f"前瞻 {len(future_pred_df)} 日",
            edgecolors="#7f1d1d",
            linewidths=0.8,
        )
        price_labels = [f"{v:.2f}" for v in fp_close]
        _annotate_below_axis(ax1, fp_ts, price_labels, color="#dc2626", rotation=35)

    # Dotted vertical at today separating backtrack from future
    for ax in (ax_k, ax1, ax2):
        ax.axvline(
            today,
            color="#475569",
            linewidth=1.8,
            linestyle=":",
            alpha=0.95,
            zorder=4,
        )

    ax1.set_ylabel("收盘价")
    ax1.set_title(f"Kronos 综合 — {stock_code} 阳光电源")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.bar(
        context_df["timestamps"],
        context_df["volume"],
        color="#93c5fd",
        alpha=0.7,
        label="历史成交量",
        width=0.8,
    )
    ax2.bar(
        future_pred_df.index,
        future_pred_df["volume"],
        color="#fca5a5",
        alpha=0.85,
        label="预测成交量",
        width=0.8,
    )
    ax2.set_ylabel("成交量")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.subplots_adjust(bottom=0.14)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def load_predictor(model_name: str = "NeoQuasar/Kronos-small"):
    device = pick_device()
    print(f"加载模型 {model_name}，设备: {device}")
    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained(model_name)
    predictor = KronosPredictor(model, tokenizer, device=device, max_context=512)
    return predictor


def _prepare_windows(
    raw: pd.DataFrame,
    lookback: int,
    pred_len: int,
    mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, int]:
    if mode == "backtest":
        need = lookback + pred_len
        if len(raw) < need + 5:
            lookback = min(lookback, len(raw) - pred_len - 1)
        if lookback < MIN_LOOKBACK:
            raise RuntimeError(f"历史数据不足: 仅 {len(raw)} 条，需要至少 {MIN_LOOKBACK} 日输入窗口")

        window = raw.iloc[-(lookback + pred_len) :].copy().reset_index(drop=True)
        context = window.iloc[:lookback].copy()
        real = window.iloc[lookback : lookback + pred_len].copy()
        y_timestamp = real["timestamps"]
    else:
        if len(raw) < lookback + 5:
            lookback = min(lookback, len(raw) - pred_len - 1)
        if lookback < MIN_LOOKBACK:
            raise RuntimeError(f"历史数据不足: 仅 {len(raw)} 条，需要至少 {MIN_LOOKBACK} 日输入窗口")

        context = raw.iloc[-lookback:].copy().reset_index(drop=True)
        real = pd.DataFrame()
        last_date = context["timestamps"].iloc[-1]
        y_timestamp = pd.Series(next_trading_days(last_date.to_pydatetime(), pred_len))

    return context, real, y_timestamp, lookback


def run_forecast(
    stock_code: str,
    lookback: int = DEFAULT_LOOKBACK,
    pred_len: int = DEFAULT_PRED_LEN,
    model_name: str = "NeoQuasar/Kronos-small",
    mode: str = "backtest",
    *,
    raw: pd.DataFrame | None = None,
    predictor=None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = raw if raw is not None else fetch_daily_kline(stock_code)
    context, real, y_timestamp, lookback = _prepare_windows(raw, lookback, pred_len, mode)

    if predictor is None:
        predictor = load_predictor(model_name)

    label = "回测" if mode == "backtest" else "前瞻"
    print(f"[{label}] 输入窗口 {lookback} 日，预测 {pred_len} 个交易日")
    x_df = context[["open", "high", "low", "close", "volume", "amount"]]
    pred_df = predictor.predict(
        df=x_df,
        x_timestamp=context["timestamps"],
        y_timestamp=y_timestamp,
        pred_len=pred_len,
        T=1.0,
        top_p=0.9,
        sample_count=1,
        verbose=True,
    )
    pred_df.index = y_timestamp.values
    return context, real, pred_df


def run_walk_forward(
    raw: pd.DataFrame,
    lookback: int,
    walk_n: int,
    predictor,
) -> pd.DataFrame:
    """1-step walk-forward: for each of the last walk_n days, predict D_k using data through D_k-1."""
    if walk_n <= 0:
        return pd.DataFrame()

    n = len(raw)
    if n < walk_n + MIN_LOOKBACK:
        raise RuntimeError(
            f"历史数据不足，无法进行 {walk_n} 日 walk-forward: 仅 {n} 条，"
            f"需要至少 {walk_n + MIN_LOOKBACK} 条"
        )

    rows: list[dict] = []
    for k in range(walk_n):
        target_idx = n - walk_n + k
        available = target_idx  # rows with indices 0 .. target_idx-1
        eff_lookback = min(lookback, available)
        if eff_lookback < MIN_LOOKBACK:
            raise RuntimeError(
                f"walk-forward 目标日 {raw.iloc[target_idx]['timestamps'].date()} "
                f"可用历史仅 {available} 日，不足 {MIN_LOOKBACK}"
            )

        # Strictly no data from target_idx onward (ends at target_idx - 1).
        context = raw.iloc[target_idx - eff_lookback : target_idx].copy().reset_index(drop=True)
        target = raw.iloc[target_idx]
        y_timestamp = pd.Series([target["timestamps"]])

        pred_df = predictor.predict(
            df=context[["open", "high", "low", "close", "volume", "amount"]],
            x_timestamp=context["timestamps"],
            y_timestamp=y_timestamp,
            pred_len=1,
            T=1.0,
            top_p=0.9,
            sample_count=1,
            verbose=False,
        )

        pred_close = float(pred_df["close"].iloc[0])
        real_close = float(target["close"])
        rows.append(
            {
                "timestamps": target["timestamps"],
                "context_end": context["timestamps"].iloc[-1],
                "context_len": eff_lookback,
                "pred_open": float(pred_df["open"].iloc[0]),
                "pred_high": float(pred_df["high"].iloc[0]),
                "pred_low": float(pred_df["low"].iloc[0]),
                "pred_close": pred_close,
                "pred_volume": float(pred_df["volume"].iloc[0]),
                "real_open": float(target["open"]),
                "real_high": float(target["high"]),
                "real_low": float(target["low"]),
                "real_close": real_close,
                "real_volume": float(target["volume"]),
                "error": pred_close - real_close,
                "error_pct": (pred_close / real_close - 1) * 100 if real_close else float("nan"),
            }
        )

    return pd.DataFrame(rows)


def save_result(
    mode: str,
    stock_code: str,
    context: pd.DataFrame,
    real: pd.DataFrame,
    pred: pd.DataFrame,
    ts: str,
    walk_forward_df: pd.DataFrame | None = None,
    *,
    plot: bool = True,
) -> tuple[Path, Path, Path | None]:
    tag = "backtest" if mode == "backtest" else "future"
    csv_path = OUTPUT_DIR / f"kronos_{stock_code}_{ts}_{tag}.csv"
    png_path = OUTPUT_DIR / f"kronos_{stock_code}_{ts}_{tag}.png"

    out = pred.copy()
    out.index.name = "timestamps"
    if not real.empty:
        out["real_close"] = real["close"].values
        out["real_volume"] = real["volume"].values
    out.to_csv(csv_path, encoding="utf-8-sig")

    wf_path: Path | None = None
    if walk_forward_df is not None and not walk_forward_df.empty:
        wf_path = OUTPUT_DIR / f"kronos_{stock_code}_{ts}_walk_forward.csv"
        walk_forward_df.to_csv(wf_path, index=False, encoding="utf-8-sig")
        with csv_path.open("a", encoding="utf-8-sig") as f:
            f.write("\n# walk_forward\n")
        walk_forward_df.to_csv(csv_path, mode="a", index=False, encoding="utf-8-sig")

    if plot:
        plot_forecast(
            context,
            real,
            pred,
            stock_code,
            png_path,
            mode=mode,
            walk_forward_df=walk_forward_df,
        )
    return csv_path, png_path, wf_path


def save_combined_chart(
    stock_code: str,
    context: pd.DataFrame,
    future_pred: pd.DataFrame,
    ts: str,
    walk_forward_df: pd.DataFrame | None = None,
) -> Path:
    png_path = OUTPUT_DIR / f"kronos_{stock_code}_{ts}_combined.png"
    plot_combined(context, future_pred, stock_code, png_path, walk_forward_df=walk_forward_df)
    return png_path


def print_summary(mode: str, stock_code: str, context: pd.DataFrame, real: pd.DataFrame, pred: pd.DataFrame, pred_len: int) -> None:
    title = "回测摘要" if mode == "backtest" else "前瞻摘要"
    print(f"\n=== {title} ===")
    print(f"股票: {stock_code} 阳光电源")
    if mode == "backtest" and not real.empty:
        real_close = real["close"].iloc[-1]
        pred_close = pred["close"].iloc[-1]
        err_pct = (pred_close / real_close - 1) * 100
        print(f"最后一日真实收盘: {real_close:.2f} ({real['timestamps'].iloc[-1].date()})")
        print(f"最后一日预测收盘: {pred_close:.2f} ({pred.index[-1].date()})")
        print(f"末日误差: {err_pct:+.2f}%")
        mae = pred["close"].values - real["close"].values
        print(f"区间收盘 MAE: {abs(mae).mean():.2f}")
    else:
        last_close = context["close"].iloc[-1]
        pred_close = pred["close"].iloc[-1]
        change_pct = (pred_close / last_close - 1) * 100
        print(f"最近收盘: {last_close:.2f} ({context['timestamps'].iloc[-1].date()})")
        print(f"预测 {pred_len} 日后收盘: {pred_close:.2f} ({pred.index[-1].date()})")
        print(f"累计变动: {change_pct:+.2f}%")
    show = pred.copy()
    show["timestamps"] = show.index
    print(show[["timestamps", "open", "high", "low", "close", "volume"]].to_string(index=False, float_format="%.2f"))


def print_walk_forward_summary(walk_forward_df: pd.DataFrame, walk_n: int) -> None:
    if walk_forward_df.empty:
        return
    print(f"\n=== Walk-forward 回溯摘要 (最近 {walk_n} 日 1-step，严格无前瞻) ===")
    for _, row in walk_forward_df.iterrows():
        day = pd.to_datetime(row["timestamps"]).date()
        ctx_end = pd.to_datetime(row["context_end"]).date()
        print(
            f"  {day}: 真实 {row['real_close']:.2f} | 回溯预测 {row['pred_close']:.2f} | "
            f"偏离 {row['error']:+.2f} ({row['error_pct']:+.2f}%) "
            f"[上下文至 {ctx_end}, {int(row['context_len'])} 日]"
        )
    mae = walk_forward_df["error"].abs().mean()
    mape = walk_forward_df["error_pct"].abs().mean()
    print(f"回溯偏离 MAE: {mae:.2f} 元")
    print(f"回溯偏离 MAPE: {mape:.2f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kronos A-share forecast")
    parser.add_argument("stock_code", nargs="?", default="300274")
    parser.add_argument(
        "--lookback",
        type=int,
        default=None,
        help=f"显式指定输入窗口交易日数（默认 {DEFAULT_LOOKBACK}；--long 为 {LONG_LOOKBACK}，优先于 --long）",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help=f"短周期（默认行为，{SHORT_LOOKBACK} 日；可忽略，保留兼容）",
    )
    parser.add_argument(
        "--long",
        action="store_true",
        help=f"长周期：输入窗口 {LONG_LOOKBACK} 个交易日（可被 --lookback 覆盖）",
    )
    parser.add_argument(
        "--pred-len",
        type=int,
        default=DEFAULT_PRED_LEN,
        help=f"预测未来交易日数（默认 {DEFAULT_PRED_LEN}；backtest/future 共用）",
    )
    parser.add_argument("--model", default="NeoQuasar/Kronos-small")
    parser.add_argument(
        "--mode",
        choices=("backtest", "future", "both", "combined"),
        default="both",
        help="backtest=绿线对比真实; future=预测未来; both/combined=CSV 分开 + 一张综合图",
    )
    parser.add_argument(
        "--walk-n",
        type=int,
        default=WALK_FORWARD_N,
        help=f"最近 N 个交易日 walk-forward 1-step 预测（默认 {WALK_FORWARD_N}，0=关闭）",
    )
    args = parser.parse_args()
    if args.lookback is not None:
        lookback = args.lookback
    elif args.long:
        lookback = LONG_LOOKBACK
    else:
        lookback = DEFAULT_LOOKBACK  # --short is no-op (same as default)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_mode = args.mode in ("both", "combined")
    modes = ["backtest", "future"] if combined_mode else [args.mode]

    raw = fetch_daily_kline(args.stock_code)
    predictor = load_predictor(args.model)
    outputs: list[tuple[str, Path, Path, Path | None]] = []
    future_context: pd.DataFrame | None = None
    future_pred: pd.DataFrame | None = None

    walk_forward_df = pd.DataFrame()
    if args.walk_n > 0:
        print(f"\n运行 walk-forward 1-step 预测 (n={args.walk_n}) …")
        walk_forward_df = run_walk_forward(raw, lookback, args.walk_n, predictor)
        print_walk_forward_summary(walk_forward_df, args.walk_n)

    for mode in modes:
        context, real, pred = run_forecast(
            args.stock_code,
            lookback,
            args.pred_len,
            args.model,
            mode,
            raw=raw,
            predictor=predictor,
        )
        if mode == "future":
            future_context, future_pred = context, pred
        csv_path, png_path, wf_path = save_result(
            mode,
            args.stock_code,
            context,
            real,
            pred,
            ts,
            walk_forward_df=walk_forward_df if mode == "future" else None,
            plot=not combined_mode,
        )
        print_summary(mode, args.stock_code, context, real, pred, args.pred_len)
        outputs.append((mode, csv_path, png_path, wf_path))

    combined_png: Path | None = None
    if combined_mode and future_context is not None and future_pred is not None:
        combined_png = save_combined_chart(
            args.stock_code,
            future_context,
            future_pred,
            ts,
            walk_forward_df=walk_forward_df,
        )

    print("\n=== 输出文件 ===")
    for mode, csv_path, png_path, wf_path in outputs:
        label = "回测" if mode == "backtest" else "前瞻"
        print(f"[{label}] CSV: {csv_path}")
        if not combined_mode:
            print(f"[{label}] 图表: {png_path}")
    if combined_png is not None:
        print(f"[综合] 图表: {combined_png}")
    if not walk_forward_df.empty and outputs:
        wf_path = outputs[-1][3] or (outputs[0][3] if len(outputs) > 1 else None)
        if wf_path is not None:
            print(f"[Walk-forward] CSV: {wf_path}")


if __name__ == "__main__":
    main()
