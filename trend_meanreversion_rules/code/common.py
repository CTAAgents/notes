# -*- coding: utf-8 -*-
"""共享层：数据加载、成本与可交易性过滤、13 项评估指标。

规则一、规则二、规则三与多重检验流程共用本模块，保证三套规则的回测口径
与综述《趋势跟踪与均值回归：同一自相关结构的两侧剪影》完全一致。
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

SKILL = r"C:\Users\yangd\.trae-cn\skills\tdx-local-data\scripts"
if SKILL not in sys.path:
    sys.path.insert(0, SKILL)

TDX_ROOT = Path(r"D:\Programs\new_tdx_mock\vipdoc")
OUT = Path(__file__).resolve().parent.parent / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

START, END = "2014-01-01", "2026-09-30"

# 成本参数（单边，基点），与综述一致
COST_BPS = {"futures": 2.0, "ashare_stock": 15.0, "ashare_index": 5.0}

FUTURES_UNIVERSE = (
    "A AG AL AP AU B BU C CF CS CU CY FG FU HC I IC IF IH J JD JM L M MA NI "
    "OI P PB PP RB RM RS RU SC SF SM SN SR T TA TF V Y ZN"
).split()

_DT = np.dtype([
    ("date", "<u4"), ("open", "<f4"), ("high", "<f4"), ("low", "<f4"),
    ("close", "<f4"), ("amount", "<u4"), ("vol", "<u4"), ("oi", "<u4"),
])


# ---------------------------------------------------------------- 基础解析
def read_day_fast(path) -> pd.DataFrame | None:
    """向量化解析 32 字节/行 .day 文件。"""
    try:
        b = Path(path).read_bytes()
        n = len(b) // 32
        if n < 10:
            return None
        a = np.frombuffer(b[: n * 32], dtype=_DT)
        idx = pd.to_datetime(a["date"].astype("int64").astype(str), format="%Y%m%d")
        df = pd.DataFrame({
            "open": a["open"].astype("f8"), "high": a["high"].astype("f8"),
            "low": a["low"].astype("f8"), "close": a["close"].astype("f8"),
            "amount": a["amount"].astype("f8"), "vol": a["vol"].astype("f8"),
            "oi": a["oi"].astype("f8"),
        }, index=pd.DatetimeIndex(idx, name="date"))
        df = df[(df["close"] > 0) & (df["close"] < 1e9) & (df["high"] >= df["low"])]
        return df.sort_index()
    except Exception:
        return None


# ---------------------------------------------------------------- 数据加载
def load_futures_ohlc(symbols=None, start=START, end=END, use_cache=True):
    """期货主力连续 OHLC（守门前复权）→ {field: DataFrame}，field ∈ close/high/low/amount/oi。"""
    symbols = symbols or FUTURES_UNIVERSE
    fc = OUT / "futures_ohlc.parquet"
    if use_cache and fc.exists():
        wide = pd.read_parquet(fc)
        return {f: wide[f] for f in wide.columns.levels[0]}
    from tdx_local import load_daily
    res = load_daily(symbols, source="continuous", min_bars=250, guard=True)
    frames = {"close": {}, "high": {}, "low": {}, "amount": {}, "oi": {}}
    for sym, df in res["data"].items():
        d = df.loc[start:end]
        if len(d) < 250:
            continue
        for f in frames:
            frames[f][sym] = d[f]
    wide = pd.concat({f: pd.DataFrame(v).sort_index() for f, v in frames.items()}, axis=1)
    wide.to_parquet(fc)
    return {f: wide[f] for f in wide.columns.levels[0]}


def load_futures(symbols=None, start=START, end=END, use_cache=True):
    """期货主力连续收盘价面板（薄封装）。"""
    return load_futures_ohlc(symbols, start, end, use_cache)["close"]


def _is_stock(mk, code):
    if mk == "sh":
        return code[:3] in {"600", "601", "603", "605", "688", "689"}
    return code[:3] in {"000", "001", "002", "003", "300", "301"}


def limit_pct(code: str) -> float:
    """涨跌停幅度：创业板 300/301、科创 688/689 为 20%，其余 10%。"""
    return 0.20 if code[:3] in {"300", "301", "688", "689"} else 0.10


def load_ashare(start=START, end=END, min_bars=400, last_after="2026-08-01",
                use_cache=True):
    """A 股个股：返回 (收益面板, 均价面板, 成交额面板, 除权修复计数)。

    除权近似修复（与综述一致）：主板日收益 < -10.5%、创业板/科创板 < -20.5% 判为
    除权，将该日收益置零。残余污染（小额分红型除权）无法识别，需外部复权因子补齐。
    """
    fr = OUT / f"ashare_ret_{start}_{end}.parquet"
    fa = OUT / f"ashare_amt_{start}_{end}.parquet"
    fp = OUT / f"ashare_px_{start}_{end}.parquet"
    ff = OUT / f"ashare_flags_{start}_{end}.txt"
    if use_cache and fr.exists() and fa.exists() and fp.exists():
        return (pd.read_parquet(fr), pd.read_parquet(fa), pd.read_parquet(fp),
                int(ff.read_text()) if ff.exists() else 0)

    rets, amts, px, nflag = {}, {}, {}, 0
    for mk in ("sh", "sz"):
        for p in sorted((TDX_ROOT / mk / "lday").glob(f"{mk}*.day")):
            code = p.stem[2:]
            if not _is_stock(mk, code):
                continue
            df = read_day_fast(p)
            if df is None or df.index.max() < pd.Timestamp(last_after):
                continue
            c = df["close"].loc[start:end]
            if len(c) < min_bars:
                continue
            r = c.pct_change()
            flag = r < -(limit_pct(code) + 0.005)
            nflag += int(flag.sum())
            rets[code] = r.mask(flag, 0.0).astype("f4")
            amts[code] = df["amount"].loc[start:end].astype("f4")
            px[code] = c.astype("f4")
    R = pd.DataFrame(rets).sort_index()
    A = pd.DataFrame(amts).reindex_like(R)
    P = pd.DataFrame(px).reindex_like(R)
    for obj, path in ((R, fr), (A, fa), (P, fp)):
        obj.to_parquet(path)
    ff.write_text(str(nflag))
    return R, A, P, nflag


def load_ashare_indices(start=START, end=END):
    """A 股宽基指数收盘价面板（用于 beta 估计与基准）。"""
    codes = {"sh000300": "沪深300", "sh000905": "中证500", "sh000852": "中证1000",
             "sh000001": "上证综指", "sz399001": "深证成指", "sz399006": "创业板指",
             "sh000016": "上证50"}
    close = {}
    for code, name in codes.items():
        df = read_day_fast(TDX_ROOT / code[:2] / "lday" / f"{code}.day")
        if df is not None:
            close[name] = df["close"].loc[start:end]
    return pd.DataFrame(close).sort_index()


# ---------------------------------------------------------------- 可交易性过滤
def tradable_mask(px: pd.DataFrame, ret: pd.DataFrame, code_of=None) -> pd.DataFrame:
    """返回 True 表示当日可正常成交。

    判据：非停牌（价格非缺失）、非涨跌停（|收益| 未触及涨跌停幅度 - 0.3% 容差）。
    停牌判定只能靠价格缺失近似，`.day` 无停牌标记，属已知局限。
    """
    ok = px.notna() & px.shift(1).notna()
    if code_of is None:
        lim = pd.Series(0.10, index=ret.columns)
    else:
        lim = pd.Series({c: limit_pct(code_of(c)) for c in ret.columns})
    at_limit = ret.abs() >= (lim - 0.003)
    return ok & ~at_limit


def liquidity_filter(amount: pd.DataFrame, window=20, floor=5e7) -> pd.DataFrame:
    """近 window 日日均成交额不低于 floor（默认 5000 万元）→ True 表示可选池。"""
    return amount.rolling(window, min_periods=window // 2).mean() >= floor


# ---------------------------------------------------------------- 评估指标
def max_drawdown(nav: pd.Series) -> float:
    return float(((nav / nav.cummax()) - 1).min())


def nw_tstat(x, lags=5) -> float:
    """Newey--West 稳健 t 统计量（Bartlett 核，滞后阶数 lags）。"""
    x = np.asarray(x, dtype="f8")
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 30:
        return float("nan")
    e = x - x.mean()
    s = (e @ e) / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * ((e[k:] @ e[:-k]) / n)
    return float(x.mean() / np.sqrt(max(s, 1e-18) / n))


METRIC_KEYS = ["年化收益", "年化波动", "Sharpe", "最大回撤", "Calmar", "偏度",
               "超额峰度", "年化换手", "毛利年化", "成本拖累年化", "月胜率",
               "NW_t统计量", "成本占毛利比"]


def metrics(net: pd.Series, gross: pd.Series, turnover: pd.Series) -> dict:
    """13 项强制指标（口径与综述一致）。"""
    net = net.dropna()
    gross = gross.dropna()
    if len(net) < 30:
        return {k: float("nan") for k in METRIC_KEYS}
    nav, gnav = (1 + net).cumprod(), (1 + gross).cumprod()
    yrs = len(net) / 252.0
    cagr = float(nav.iloc[-1] ** (1 / yrs) - 1)
    gcagr = float(gnav.iloc[-1] ** (1 / yrs) - 1)
    mdd = max_drawdown(nav)
    monthly = (1 + net).resample("ME").prod() - 1
    gsum = float(gross.sum())
    sd = net.std()
    return {
        "年化收益": cagr,
        "年化波动": float(sd * np.sqrt(252)),
        "Sharpe": float(net.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan"),
        "最大回撤": mdd,
        "Calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
        "偏度": float(net.skew()),
        "超额峰度": float(net.kurtosis()),
        "年化换手": float(turnover.sum() / yrs),
        "毛利年化": gcagr,
        "成本拖累年化": float(gcagr - cagr),
        "月胜率": float((monthly > 0).mean()),
        "NW_t统计量": nw_tstat(net.to_numpy()),
        "成本占毛利比": float((gross - net).sum() / gsum) if abs(gsum) > 1e-12 else float("nan"),
    }


def print_metrics(tag: str, m: dict) -> None:
    def f(k, pct=False):
        v = m.get(k, float("nan"))
        if not np.isfinite(v):
            return "   nan"
        return f"{v*100:7.2f}" if pct else f"{v:7.2f}"
    print(f"  {tag:34s} 夏普 {f('Sharpe')}  年化 {f('年化收益', True)}%  "
          f"回撤 {f('最大回撤', True)}%  换手 {f('年化换手')}  "
          f"成本/毛利 {f('成本占毛利比', True)}%  NW_t {f('NW_t统计量')}")


def cost_gate_ok(m: dict, multiple: float = 3.0) -> bool:
    """铁律二：毛利/成本 > multiple。返回 False 表示应废弃该参数组合。"""
    r = m.get("成本占毛利比", float("nan"))
    if not np.isfinite(r) or r <= 0:
        return True
    return (1.0 / r) > multiple


# ---------------------------------------------------------------- 组合回测骨架
def run_weights_backtest(ret: pd.DataFrame, weights: pd.Series | pd.DataFrame,
                         cost_bps: float, hold_drift=True):
    """给定「目标权重序列」，逐日结算净收益、毛收益与换手。

    weights：DataFrame(index=调仓日, columns=标的) 的目标权重；未列出的日期沿用上次权重。
    持有期内权重随收益漂移；换手按目标权重与实际权重之差计算；仅对变动部分收费。
    """
    dates = ret.index
    n = len(dates)
    cols = ret.columns
    if isinstance(weights, pd.Series):
        weights = weights.to_frame().T
    w_target = weights.reindex(columns=cols).fillna(0.0)
    rb = set(w_target.index)

    net = np.zeros(n); gross = np.zeros(n); turn = np.zeros(n)
    w = pd.Series(0.0, index=cols)
    for i in range(n):
        r = ret.iloc[i].fillna(0.0)
        pg = float((w * r).sum())
        gross[i] = pg
        d = dates[i]
        if d in rb:
            wn = w_target.loc[d]
            delta = float((wn - w).abs().sum())
            turn[i] = delta
            net[i] = pg - delta * cost_bps / 1e4
            w = wn
        else:
            net[i] = pg
        den = 1.0 + pg
        if hold_drift and abs(den) > 1e-9:
            w = w * (1.0 + r) / den
    idx = dates
    return (pd.Series(net, index=idx), pd.Series(gross, index=idx),
            pd.Series(turn, index=idx))