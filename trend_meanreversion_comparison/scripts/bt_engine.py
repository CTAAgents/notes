# -*- coding: utf-8 -*-
"""统一口径对照回测：趋势跟踪 vs 均值回归（期货 + A 股）。

核心设计：两策略唯一区别是信号的符号。
  信号统一为「过去 L 日累计对数收益」s_i(t)；趋势取 +s，反转取 -s。
  同一资产池 / 同一调仓频率 / 同一成本模型 / 同一评估指标。
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

SKILL = r"C:\Users\yangd\.trae-cn\skills\tdx-local-data\scripts"
sys.path.insert(0, SKILL)
sys.path.insert(0, str(Path(__file__).parent))
from tdx_local import load_daily, read_day  # noqa: E402
from fast_data import load_ashare_returns  # noqa: E402

TDX_ROOT = Path(r"D:\Programs\new_tdx_mock\vipdoc")
OUT = Path(r"d:\Finance\趋势跟踪与均值回归对比综述\outputs")
START, END = "2014-01-01", "2026-09-30"
L_GRID = [5, 10, 20, 60, 120, 250]
REBAL, VOL_WIN = 5, 60


# ------------------------------------------------------------------ 数据加载
def load_futures(symbols):
    fc = OUT / "futures_close.parquet"
    if fc.exists():
        return pd.read_parquet(fc), {"n_ok": int(pd.read_parquet(fc).shape[1]),
                                     "n_miss": 0, "cached": True}
    res = load_daily(symbols, source="continuous", min_bars=250, guard=True)
    close = {}
    for sym, df in res["data"].items():
        s = df["close"].loc[START:END]
        if len(s) >= 250:
            close[sym] = s
    panel = pd.DataFrame(close).sort_index()
    OUT.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(fc)
    return panel, res["meta"]


def load_ashare_indices():
    codes = {"sh000001": "上证综指", "sz399001": "深证成指", "sh000300": "沪深300",
             "sh000905": "中证500", "sh000852": "中证1000", "sz399006": "创业板指",
             "sh000016": "上证50"}
    close = {}
    for code, name in codes.items():
        df = read_day(str(TDX_ROOT / code[:2] / "lday" / f"{code}.day"))
        if df is not None:
            close[name] = df["close"].loc[START:END]
    return pd.DataFrame(close).sort_index()


# ------------------------------------------------------------------ 指标
def _mdd(nav):
    return float(((nav / nav.cummax()) - 1).min())


def _nw_tstat(x, lags=5):
    x = np.asarray(x)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 30:
        return float("nan")
    e = x - x.mean()
    g0 = (e @ e) / n
    var = g0
    for k in range(1, lags + 1):
        var += 2 * (1 - k / (lags + 1)) * ((e[k:] @ e[:-k]) / n)
    return float(x.mean() / np.sqrt(max(var, 1e-18) / n))


def metrics(net, gross, turn):
    nav, gnav = (1 + net).cumprod(), (1 + gross).cumprod()
    yrs = len(net) / 252.0
    cagr = float(nav.iloc[-1] ** (1 / yrs) - 1)
    gcagr = float(gnav.iloc[-1] ** (1 / yrs) - 1)
    mdd = _mdd(nav)
    monthly = (1 + net).resample("ME").prod() - 1
    gsum = float(gross.sum())
    return {
        "年化收益": cagr, "年化波动": float(net.std() * np.sqrt(252)),
        "Sharpe": float(net.mean() / net.std() * np.sqrt(252)) if net.std() > 0 else float("nan"),
        "毛利Sharpe": float(gross.mean() / gross.std() * np.sqrt(252)) if gross.std() > 0 else float("nan"),
        "最大回撤": mdd, "Calmar": float(cagr / abs(mdd)) if mdd < 0 else float("nan"),
        "偏度": float(net.skew()), "超额峰度": float(net.kurtosis()),
        "年化换手": float(turn.sum() / yrs), "毛利年化": gcagr,
        "成本拖累年化": float(gcagr - cagr), "月胜率": float((monthly > 0).mean()),
        "NW_t统计量": _nw_tstat(net.to_numpy()),
        "成本占毛利比": float((gross - net).sum() / gsum) if abs(gsum) > 1e-9 else float("nan"),
    }


# ------------------------------------------------------------------ 信号与回测
def precompute(ret, L):
    logret = np.log1p(ret).where(ret.notna())
    return logret.rolling(L).sum(), ret.rolling(VOL_WIN).std() * np.sqrt(252)


def signal_at(S, vol, i, kind, mode, q=0.2, target_vol=0.10, cap=3.0):
    s, v = S.iloc[i], vol.iloc[i]
    valid = s.notna() & v.notna() & (v > 0)
    sign = 1.0 if kind == "trend" else -1.0
    w = pd.Series(0.0, index=s.index)
    if valid.sum() < 6:
        return w
    if mode == "TS":
        raw = sign * np.sign(s[valid]) * np.minimum(target_vol / v[valid], cap)
        if raw.abs().sum() > 0:
            w[valid] = raw / raw.abs().sum()
    else:
        sv = s[valid].sort_values()
        k = max(int(len(sv) * q), 3)
        if len(sv) >= 2 * k:
            w[sv.index[:k]] = -0.5 / k
            w[sv.index[-k:]] = 0.5 / k
            if kind == "reversion":
                w = -w
    return w


def run_backtest(ret, kind, mode, L, cost_bps):
    S, vol = precompute(ret, L)
    dates = ret.index
    n = len(dates)
    warm = max(L, VOL_WIN) + 1
    net = np.zeros(n); gross = np.zeros(n); turn = np.zeros(n)
    w = pd.Series(0.0, index=ret.columns)
    nxt = warm
    for i in range(warm, n):
        r = ret.iloc[i].fillna(0.0)
        pg = float((w * r).sum())
        gross[i] = pg
        if i >= nxt:
            wn = signal_at(S, vol, i, kind, mode)
            d = float((wn - w).abs().sum())
            turn[i] = d
            net[i] = pg - d * cost_bps / 1e4
            w = wn
            nxt = i + REBAL
        else:
            net[i] = pg
        den = 1.0 + pg
        if abs(den) > 1e-9:
            w = w * (1.0 + r) / den
    idx = dates[warm:]
    return (pd.Series(net[warm:], index=idx),
            pd.Series(gross[warm:], index=idx),
            pd.Series(turn[warm:], index=idx))


FUT = ("A AG AL AP AU B BU C CF CS CU CY FG FU HC I IC IF IH J JD JM L M MA NI "
       "OI P PB PP RB RM RS RU SC SF SM SN SR T TA TF V Y ZN").split()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"config": {"futures_universe": len(FUT), "L_grid": L_GRID,
                      "rebal_days": REBAL, "vol_win": VOL_WIN, "period": f"{START}..{END}",
                      "cost_bps": {"futures_single_side": 2.0, "ashare_single_side": 15.0}},
           "results": {}}

    def record(tag, kind, L, net, gross, turn):
        k = f"{tag}_{kind}_L{L}"
        rep["results"][k] = metrics(net, gross, turn)
        m = rep["results"][k]
        print(f"    {tag:22s} {kind:9s} L={L:3d}  Sharpe={m['Sharpe']:6.2f}  "
              f"毛Sharpe={m['毛利Sharpe']:6.2f}  CAGR={m['年化收益']*100:7.2f}%  "
              f"MDD={m['最大回撤']*100:7.2f}%  换手={m['年化换手']:6.2f}")

    print("[1/3] 期货主力连续 ...")
    fpanel, fmeta = load_futures(FUT)
    fret = fpanel.pct_change()
    rep["config"]["futures_ok"] = int(fret.shape[1])
    rep["config"]["futures_missing"] = [s for s in FUT if s not in fpanel.columns]
    print(f"    面板 {fret.shape[0]} 日 × {fret.shape[1]} 品种 {fret.index.min().date()}~{fret.index.max().date()}")
    for mode in ("TS", "XS"):
        for kind in ("trend", "reversion"):
            for L in L_GRID:
                record(f"fut_{mode}", kind, L, *run_backtest(fret, kind, mode, L, 2.0))

    print("[2/3] A 股宽基指数 ...")
    ipanel = load_ashare_indices()
    iret = ipanel.pct_change()
    print(f"    面板 {iret.shape[0]} 日 × {iret.shape[1]} 指数（成本按 ETF/股指期货口径 5bp）")
    for kind in ("trend", "reversion"):
        for L in L_GRID:
            record("ashare_idx_TS", kind, L, *run_backtest(iret, kind, "TS", L, 5.0))

    print("[3/3] A 股个股截面 ...")
    apanel, nflag = load_ashare_returns()
    print(f"    面板 {apanel.shape[0]} 日 × {apanel.shape[1]} 只；除权修复 {nflag} 处")
    rep["config"]["ashare_stocks"] = int(apanel.shape[1])
    rep["config"]["ashare_exrights_flags"] = int(nflag)
    for kind in ("trend", "reversion"):
        for L in L_GRID:
            record("ashare_stk_XS", kind, L, *run_backtest(apanel, kind, "XS", L, 15.0))

    with open(OUT / "backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"\n写出 {OUT/'backtest_results.json'}")


if __name__ == "__main__":
    main()
