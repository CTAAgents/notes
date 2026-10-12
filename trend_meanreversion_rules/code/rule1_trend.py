# -*- coding: utf-8 -*-
"""规则一回测框架：期货时序趋势跟踪。

实现《趋势跟踪与均值回归交易规则》第 3 节的完整规则：
  信号 → 入场门槛 → 波动率目标化与杠杆上限 → 归一化
  → 恐慌状态过滤 → 拥挤监控 → 免交易带 → 执行（跳空/涨跌停过滤）
  → 回撤防线 → 单品种 ATR 止损

用法：
    python rule1_trend.py            # 跑默认三档窗口
    python rule1_trend.py --grid     # 跑完整 L 网格
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

import common as C


# ------------------------------------------------------------------ 配置
class Rule1Config:
    L = 10                    # 信号窗口（交易日）——第 12 节重标定后的首选档
    V_TARGET = 0.10           # 目标年化波动率
    CAP = 3.0                 # 单品种杠杆上限
    VOL_WIN = 60              # 波动率估计窗口
    REBAL = 5                 # 调仓间隔（交易日）
    ENTRY_K = 1.0             # 入场门槛：|s| / (sigma * sqrt(L)) > ENTRY_K
    BAND_K = 0.1              # 免交易带系数
    PANIC_RET = -0.05         # 恐慌状态：市场 60 日收益阈值
    PANIC_VOL_Q = 0.80        # 恐慌状态：波动率分位阈值
    PANIC_SCALE = 0.5         # 恐慌状态敞口缩放
    CROWD_Q = 0.90            # 拥挤度分位阈值
    CROWD_SCALE = 0.70        # 拥挤度敞口缩放
    DD_HALVE = 0.15           # 回撤腰斩线
    DD_FLAT = 0.25            # 回撤清仓线
    PAUSE_DAYS = 20           # 清仓后暂停交易日
    ATR_WIN = 20              # ATR 窗口
    ATR_STOP = 2.5            # 单品种止损：浮亏 > ATR_STOP * ATR（实测低敏感，见第 12.3 节）
    PCTL_WIN = 750            # 分位数滚动窗口（约 3 年）


# 依据四项验证重标定后的推荐档（实测见 code/param_recommend.py 与 outputs/param_recommend.json）
# 判据：① 成本占毛利 < 33%；② 参数曲面平滑（无孤立峰）；③ 自身 walk-forward 的选择过程稳定
RECOMMENDED = {
    "首选": {"L": 10, "ENTRY_K": 1.0},   # 夏普 0.44 / 年化 3.55% / 回撤 -19.8% / 成本占毛利 18.1%
    "备选": {"L": 20, "ENTRY_K": 1.0},   # 夏普 0.33 / 年化 2.58% / 回撤 -16.9% / 成本占毛利 17.8%
}
# 明确排除的窗口及原因（同一 L 的曲面形状诊断）
EXCLUDED = {
    5: "K>=1.0 时不通过成本门槛（成本占毛利 44.9%）",
    120: "全部 K 档夏普 <= 0.06",
    250: "参数曲面非单调：K=1.5 处为孤立峰（0.50），紧邻 K=1.0 为 -0.00",
}


# ------------------------------------------------------------------ 工具
def atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, n: int) -> pd.DataFrame:
    """Wilder ATR（简化：真实波幅的滚动均值）。"""
    pc = close.shift(1)
    tr = pd.concat([(high - low).stack(),
                    (high - pc).abs().stack(),
                    (low - pc).abs().stack()], axis=1).max(axis=1).unstack()
    tr = tr.reindex_like(close)
    return tr.rolling(n, min_periods=n // 2).mean()


def rolling_percentile(s: pd.Series, win: int) -> pd.Series:
    """滚动分位（0~1）：当前值在近 win 期中的排名位置。"""
    return s.rolling(win, min_periods=win // 3).apply(
        lambda a: (a[-1] > a[:-1]).mean() if len(a) > 1 else np.nan, raw=True)


def mean_pairwise_corr(ret: pd.DataFrame, win: int = 60) -> pd.Series:
    """滚动窗口内两两相关系数的均值（等权近似的拥挤度代理）。"""
    out = {}
    for i in range(win, len(ret) + 1):
        w = ret.iloc[i - win:i]
        cm = w.corr().to_numpy()
        n = cm.shape[0]
        if n < 3:
            out[ret.index[i - 1]] = np.nan
            continue
        iu = np.triu_indices(n, k=1)
        vals = cm[iu]
        vals = vals[~np.isnan(vals)]
        out[ret.index[i - 1]] = float(vals.mean()) if len(vals) else np.nan
    return pd.Series(out).reindex(ret.index)


# ------------------------------------------------------------------ 主回测
def rebalance_dates(index: pd.DatetimeIndex, step: int) -> list:
    warm = 260
    return [index[i] for i in range(warm, len(index), step)]


def target_weights(dates, ret, high, low, close, cfg: Rule1Config,
                   mkt_ret: pd.Series, crowd: pd.Series):
    """生成每个调仓日的目标权重（仅用当日及之前的信息）。"""
    logret = np.log1p(ret.fillna(0.0)).where(ret.notna())
    S = logret.rolling(cfg.L).sum()
    V = ret.rolling(cfg.VOL_WIN).std() * np.sqrt(252)
    sd_d = ret.rolling(cfg.VOL_WIN).std()
    mkt_r60 = mkt_ret.rolling(60).sum()
    mkt_v60 = mkt_ret.rolling(cfg.VOL_WIN).std() * np.sqrt(252)
    vol_q = rolling_percentile(mkt_v60, cfg.PCTL_WIN)
    crowd_q = rolling_percentile(crowd, cfg.PCTL_WIN)

    out = {}
    for d in dates:
        s = S.loc[d]; v = V.loc[d]; sdv = sd_d.loc[d]
        with np.errstate(invalid="ignore", divide="ignore"):
            strength = s.abs() / (sdv * np.sqrt(cfg.L))
        ok = s.notna() & v.notna() & (v > 0) & (strength > cfg.ENTRY_K)
        w = pd.Series(0.0, index=ret.columns)
        if ok.any():
            raw = np.sign(s[ok]) * np.minimum(cfg.V_TARGET / v[ok], cfg.CAP)
            w[ok] = raw
        tot = w.abs().sum()
        if tot > 0:
            w = w / tot
        # 恐慌状态过滤
        if np.isfinite(mkt_r60.loc[d]) and np.isfinite(vol_q.loc[d]):
            if (mkt_r60.loc[d] < cfg.PANIC_RET) and (vol_q.loc[d] > cfg.PANIC_VOL_Q):
                w = w * cfg.PANIC_SCALE
        # 拥挤监控
        if np.isfinite(crowd_q.loc[d]) and crowd_q.loc[d] > cfg.CROWD_Q:
            w = w * cfg.CROWD_SCALE
        out[d] = w
    return pd.DataFrame(out).T


def simulate(target: pd.DataFrame, ret: pd.DataFrame, high, low, close,
             cfg: Rule1Config, cost_bps: float, tradable: pd.DataFrame):
    """逐日结算：含免交易带、执行过滤、回撤防线与单品种 ATR 止损。"""
    dates = ret.index
    n = len(dates)
    rb = set(target.index)
    atr_panel = atr(high, low, close, cfg.ATR_WIN)

    net = np.zeros(n); gross = np.zeros(n); turn = np.zeros(n)
    paused_until = -1
    w = pd.Series(0.0, index=ret.columns)
    entry_px = pd.Series(np.nan, index=ret.columns)
    stopped = set()
    nav = 1.0
    peak = 1.0
    dd_scale = 1.0
    reentry = False
    flat_events = 0
    stop_events = 0
    n_rebal = 0

    for i in range(n):
        d = dates[i]
        r = ret.iloc[i].fillna(0.0)
        pg = float((w * r).sum())
        gross[i] = pg

        # ---- 暂停期结束：以当时净值为新基准重算回撤，恢复半仓 ----
        if dd_scale == 0.0 and i >= paused_until:
            peak = nav
            dd_scale = 0.5
            reentry = True

        # ---- 调仓 ----
        if d in rb and (i >= paused_until):
            n_rebal += 1
            wn = target.loc[d].copy()
            # 执行过滤：不可交易标的权重归零
            if d in tradable.index:
                bad = ~tradable.loc[d].reindex(wn.index).fillna(False)
                wn[bad] = 0.0
            # 免交易带
            band = cfg.BAND_K * cfg.V_TARGET / (ret.rolling(cfg.VOL_WIN).std().loc[d] * np.sqrt(252))
            band = band.reindex(wn.index).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            keep = (wn - w).abs() < band
            wn[keep] = w[keep]
            # 已止损标的在下次调仓前不恢复
            for sym in stopped:
                if sym in wn.index:
                    wn[sym] = 0.0
            stopped = set()
            # 回撤缩放
            wn = wn * dd_scale
            delta = float((wn - w).abs().sum())
            turn[i] = delta
            net[i] = pg - delta * cost_bps / 1e4
            changed = (wn - w).abs() > 1e-12
            entry_px[changed & (wn != 0)] = close.loc[d][changed & (wn != 0)]
            entry_px[wn == 0] = np.nan
            w = wn
        else:
            net[i] = pg

        # ---- 净值与回撤防线 ----
        port = net[i]
        nav *= (1.0 + port)
        peak = max(peak, nav)
        dd = nav / peak - 1.0
        if dd <= -cfg.DD_FLAT:
            if dd_scale != 0.0:
                flat_events += 1
                paused_until = i + cfg.PAUSE_DAYS     # 仅在进入清仓的那一天设定暂停期
            w = w * 0.0
            dd_scale = 0.0
        elif dd <= -cfg.DD_HALVE:
            dd_scale = 0.5
        else:
            dd_scale = 1.0
        if reentry and dd > -cfg.DD_HALVE:
            dd_scale = 1.0
            reentry = False

        # ---- 单品种 ATR 止损 ----
        if i > 0:
            a = atr_panel.iloc[i]
            px = close.iloc[i]
            loss = (px - entry_px) / entry_px
            hit = loss < -(cfg.ATR_STOP * a / px)
            hit = hit.reindex(w.index).fillna(False) & (w.abs() > 1e-12)
            for sym in w.index[hit]:
                stopped.add(sym)
            if hit.any():
                cut = float(w[hit].abs().sum())
                w[hit] = 0.0
                turn[i] += cut
                stop_events += int(hit.sum())

        # ---- 权重漂移 ----
        den = 1.0 + pg
        if abs(den) > 1e-9:
            w = w * (1.0 + r) / den

    diag = {"n_rebal": n_rebal, "n_flat": flat_events, "n_stop_events": stop_events}
    return (pd.Series(net, index=dates), pd.Series(gross, index=dates),
            pd.Series(turn, index=dates), diag)


def run(L=None, verbose=True, **overrides) -> dict:
    """L=None 时使用 Rule1Config.L（即第 12 节重标定后的首选档 L=10）。"""
    cfg = Rule1Config()
    cfg.L = Rule1Config.L if L is None else L
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise KeyError(f"Rule1Config 无此参数：{k}")
        setattr(cfg, k, v)
    ohlc = C.load_futures_ohlc()
    close, high, low = ohlc["close"], ohlc["high"], ohlc["low"]
    ret = close.pct_change()
    mkt_ret = ret.mean(axis=1)
    crowd = mean_pairwise_corr(ret, win=60)
    tradable = C.tradable_mask(close, ret, code_of=None).fillna(False)
    # 期货涨跌停按品种差异较大，这里用保守统一阈值（见文档局限说明）
    dates = rebalance_dates(ret.index, cfg.REBAL)
    tgt = target_weights(dates, ret, high, low, close, cfg, mkt_ret, crowd)
    net, gross, turn, diag = simulate(tgt, ret, high, low, close, cfg,
                                      C.COST_BPS["futures"], tradable)
    m = C.metrics(net, gross, turn)
    m["_gate_ok"] = C.cost_gate_ok(m, 3.0)
    m["_n_positions_mean"] = float((tgt != 0).sum(axis=1).mean())
    m["_n_rebal"] = diag["n_rebal"]
    m["_n_flat"] = diag["n_flat"]
    m["_n_stop_events"] = diag["n_stop_events"]
    if verbose:
        C.print_metrics(f"规则一 期货时序趋势 L={L}", m)
        print(f"      平均持仓 {m['_n_positions_mean']:.1f} 个品种；执行调仓 {diag['n_rebal']} 次"
              f"（计划 {len(dates)}）；清仓触发 {diag['n_flat']} 次；"
              f"单品种止损 {diag['n_stop_events']} 次；成本门槛"
              f"{'通过' if m['_gate_ok'] else '不通过'}")
    return {"L": cfg.L, "metrics": m, "net": net, "gross": gross, "turn": turn,
            "config": {k: getattr(cfg, k) for k in dir(cfg) if k.isupper()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true", help="跑完整 L 网格")
    ap.add_argument("--preset", default="首选", choices=list(RECOMMENDED),
                    help="跑第 12 节重标定后的推荐档（默认 首选）")
    args = ap.parse_args()

    print("=" * 96)
    print("规则一回测：期货时序趋势跟踪")
    print("=" * 96)
    rep = {}

    if not args.grid:
        p = RECOMMENDED[args.preset]
        print(f"\n[推荐档：{args.preset}] L={p['L']}, ENTRY_K={p['ENTRY_K']}")
        print("  排除的窗口：")
        for L, why in EXCLUDED.items():
            print(f"    L={L:3d} —— {why}")
        print()
        res = run(p["L"], ENTRY_K=p["ENTRY_K"])
        rep[f"preset_{args.preset}"] = {k: v for k, v in res["metrics"].items()}

    grid = [5, 10, 20, 60, 120, 250] if args.grid else []
    for L in grid:
        res = run(L)
        rep[f"L{L}"] = {k: v for k, v in res["metrics"].items()}
    outp = C.OUT / "rule1_results.json"
    outp.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=float),
                    encoding="utf-8")
    print(f"\n结果已写出 {outp}")


if __name__ == "__main__":
    main()