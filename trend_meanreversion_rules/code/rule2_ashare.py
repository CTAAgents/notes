# -*- coding: utf-8 -*-
"""规则二回测框架：A 股截面反转（纯多头 + 指数对冲）。

实现《趋势跟踪与均值回归交易规则》第 4 节的完整规则：
  60 日累计收益 → 行业与市值中性化（残差排序）→ 取最输的 20%（收窄至 N 只）
  → 等权 ×(1-现金冗余) → 月频调仓 → 单票偏离止损 → 回撤防线 → beta 对冲

行业中性化数据来源（三选一，见 --industry）：
  cluster : 用收益的相关结构做主成分 + 聚类，得到数据驱动的行业代理（默认）
  file    : 读取外部行业表 CSV（列 code,industry），真实行业分类
  none    : 不做行业中性化（仅做市值代理中性化）

市值数据局限：本地 `.day` 无市值字段，本文用 20 日均成交额的对数作规模代理
（与流通市值高度相关但非市值本身），如实标注。

用法：
    python rule2_ashare.py
    python rule2_ashare.py --industry file --industry-file industry.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import common as C


class Rule2Config:
    L = 250                   # 信号窗口（交易日）——第 12 节重标定后的首选档
    REBAL = 21                # 调仓间隔（月频）
    BOTTOM_Q = 0.20           # 取残差最低的 20%
    MAX_NAMES = 50            # 实盘持仓上限
    MIN_NAMES = 15            # 低于此数不做该期调仓
    CASH_BUFFER = 0.30        # 现金冗余
    LIQ_WIN = 20              # 流动性窗口
    LIQ_FLOOR = 5e7           # 日均成交额门槛
    STOP_LOSS = 0.15          # 单票止损
    STOP_LOSS_HI = 0.10       # 高波动期收紧后
    VOL_HI_Q = 0.80           # 高波动分位阈值
    DD_HALVE = 0.20           # 回撤腰斩线
    DD_FLAT = 0.30            # 回撤清仓线
    PAUSE_DAYS = 40           # 清仓暂停
    BETA_WIN = 60             # beta 估计窗口
    N_CLUSTERS = 20           # 行业代理簇数
    PCTL_WIN = 750


# 依据四项验证重标定后的推荐档（实测见 code/param_recommend.py 与 outputs/param_recommend.json）
# 真实申万一级中性化口径下：L=250 与 L=60 夏普几乎相同，但 L=250 的回撤浅 16 个百分点、
# 换手低 32%、成本占毛利低 6.6 个百分点，因此以 L=250 为首选。
RECOMMENDED = {
    "首选": {"L": 250},   # 夏普 0.18 / 年化 1.57% / 回撤 -45.2% / 换手 7.10 / 成本占毛利 25.7%
    "备选": {"L": 60},    # 夏普 0.19 / 年化 1.69% / 回撤 -61.5% / 换手 10.39 / 成本占毛利 32.2%（贴门槛）
}
# 明确排除的窗口及原因
EXCLUDED = {
    20: "成本占毛利 53.9%，不通过成本门槛",
    120: "收益为负（夏普 -0.15）",
}


# ------------------------------------------------------------------ 行业代理
def industry_proxy_cluster(ret: pd.DataFrame, asof: pd.Timestamp, k=20,
                           win=250, seed=0) -> pd.Series:
    """数据驱动的行业代理：对近 win 日收益做 PCA + KMeans，得到簇标签。

    这是代理而非真实行业分类——它捕捉的是收益的共同波动结构，
    与申万/中信行业高度相关但不等价。真实行业表请用 --industry file。
    """
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    hist = ret.loc[:asof].tail(win)
    x = hist.fillna(0.0).T.to_numpy()
    x = x - x.mean(axis=1, keepdims=True)
    ncomp = min(20, x.shape[1] - 1, x.shape[0] - 1)
    z = PCA(n_components=ncomp, random_state=seed).fit_transform(x)
    kk = min(k, max(2, z.shape[0] // 20))
    lab = KMeans(n_clusters=kk, n_init=4, random_state=seed).fit_predict(z)
    return pd.Series(lab, index=hist.columns, name="industry")


def build_industry(ret, dates, mode="sw", path=None, k=20) -> dict:
    """返回 {调仓日: Series(code->industry)}。

    mode:
      sw      : 通达信本地文件解析的申万体系行业（真实分类，默认）
      tdx     : 通达信行业（真实分类）
      cluster : 用收益相关结构做主成分 + 聚类，得到数据驱动的行业代理
      file    : 读取外部行业表 CSV（列 code,industry）
      none    : 不做行业中性化
    注：真实行业分类来自 <TDX>/T0002/hq_cache/tdxhy.cfg 与 incon.dat，为**静态快照**，
    不含行业变更历史；这是相对真实历史分类的已知偏差。
    """
    if mode == "none":
        return {d: None for d in dates}
    if mode in ("sw", "tdx"):
        from industry_data import load_industry_map
        mp = load_industry_map(source=mode, level=1)
        return {d: pd.Series({c: mp.get(c, "NA") for c in ret.columns}) for d in dates}
    if mode == "file":
        tbl = pd.read_csv(path, dtype={"code": str})
        mp = dict(zip(tbl["code"], tbl["industry"]))
        return {d: pd.Series({c: mp.get(c, "NA") for c in ret.columns}) for d in dates}
    # cluster：每 250 个交易日重估一次，避免每日重算
    cache, out, step = {}, {}, 250
    for idx, d in enumerate(dates):
        if idx % step == 0:
            cache = industry_proxy_cluster(ret, d, k=k)
        out[d] = cache
    return out


# ------------------------------------------------------------------ 中性化
def neutralize(s: pd.Series, industry: pd.Series | None, size: pd.Series) -> pd.Series:
    """横截面回归取残差：s ~ 行业哑变量 + log(规模代理)。"""
    df = pd.DataFrame({"s": s, "size": size}).dropna()
    if len(df) < 30:
        return pd.Series(dtype="f8")
    X = pd.DataFrame(index=df.index)
    X["size"] = np.log(df["size"].clip(lower=1.0))
    if industry is not None:
        ind = industry.reindex(df.index).fillna("NA")
        dummies = pd.get_dummies(ind, prefix="ind", drop_first=True, dtype="f8")
        X = pd.concat([X, dummies], axis=1)
    X = X.loc[:, X.std() > 0]
    X.insert(0, "const", 1.0)
    A = X.to_numpy(dtype="f8")
    y = df["s"].to_numpy(dtype="f8")
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return pd.Series(y - A @ beta, index=df.index)


# ------------------------------------------------------------------ 主回测
def run(L=None, mode="sw", industry_file=None, verbose=True, **overrides):
    """L=None 时使用 Rule2Config.L（即第 12 节重标定后的首选档 L=250）。"""
    cfg = Rule2Config()
    cfg.L = Rule2Config.L if L is None else L
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise KeyError(f"Rule2Config 无此参数：{k}")
        setattr(cfg, k, v)
    ret, amt, px, nflag = C.load_ashare()
    ret = ret.reindex(columns=sorted(ret.columns))
    amt = amt.reindex(columns=ret.columns)
    px = px.reindex(columns=ret.columns)

    idx_panel = C.load_ashare_indices().reindex(ret.index).ffill()
    bench = idx_panel["沪深300"].pct_change()

    tradable = C.tradable_mask(px, ret).fillna(False)
    liquid = C.liquidity_filter(amt, cfg.LIQ_WIN, cfg.LIQ_FLOOR).fillna(False)
    eligible = tradable & liquid

    logret = np.log1p(ret.fillna(0.0)).where(ret.notna())
    S = logret.rolling(cfg.L).sum()
    amt20 = amt.rolling(cfg.LIQ_WIN, min_periods=cfg.LIQ_WIN // 2).mean()

    dates = [ret.index[i] for i in range(max(cfg.L, cfg.BETA_WIN) + 20,
                                        len(ret.index), cfg.REBAL)]
    ind_map = build_industry(ret, dates, mode=mode, path=industry_file,
                             k=cfg.N_CLUSTERS)

    holdings, targets = {}, {}
    for d in dates:
        ok = eligible.loc[d] & S.loc[d].notna() & amt20.loc[d].notna()
        pool = S.loc[d][ok]
        if len(pool) < 100:
            continue
        resid = neutralize(pool, ind_map.get(d), amt20.loc[d][ok])
        if len(resid) < 50:
            continue
        k = max(int(len(resid) * cfg.BOTTOM_Q), cfg.MIN_NAMES)
        bottom = resid.nsmallest(k)
        if cfg.MAX_NAMES and len(bottom) > cfg.MAX_NAMES:
            bottom = bottom.nsmallest(cfg.MAX_NAMES)
        if len(bottom) < cfg.MIN_NAMES:
            continue
        w = pd.Series(0.0, index=ret.columns)
        w[bottom.index] = (1.0 - cfg.CASH_BUFFER) / len(bottom)
        holdings[d] = list(bottom.index)
        targets[d] = w

    # ---- 因果 beta：用持仓成分股的滚动 beta 加权，只用当日及之前的信息 ----
    # 注：pandas 3.0 的 DataFrame.rolling().cov(Series) 在宽表上会错列，这里用显式矩公式
    w_win = cfg.BETA_WIN
    mp = max(w_win // 2, 5)
    b_ = bench.fillna(0.0)
    mb = b_.rolling(w_win, min_periods=mp).mean()
    vb = (b_ * b_).rolling(w_win, min_periods=mp).mean() - mb ** 2
    mr = ret.rolling(w_win, min_periods=mp).mean()
    mrb = ret.mul(b_, axis=0).rolling(w_win, min_periods=mp).mean()
    cov = mrb.sub(mr.mul(mb, axis=0))
    beta_panel = cov.div(vb.replace(0.0, np.nan), axis=0)
    beta_port = {}
    for d, w_ in targets.items():
        held = w_[w_ > 0].index
        b = beta_panel.loc[d].reindex(held).replace([np.inf, -np.inf], np.nan)
        if b.notna().any():
            ww = w_.reindex(held)
            ww = ww.where(b.notna(), 0.0)
            beta_port[d] = float((ww * b.fillna(0.0)).sum() / ww.sum()) if ww.sum() > 0 else 0.0
        else:
            beta_port[d] = 0.0

    # ---- 逐日结算 ----
    dates_all = ret.index
    n = len(dates_all)
    rb = set(targets.keys())
    net = np.zeros(n); gross = np.zeros(n); turn = np.zeros(n)
    hedge_pnl = np.zeros(n)
    w = pd.Series(0.0, index=ret.columns)
    entry = pd.Series(np.nan, index=ret.columns)
    stopped = set()

    # 回撤控制作用于「对冲后的 alpha 成分」而非绝对净值：
    # 纯多头组合的绝对回撤主要来自 beta（2015、2018 等），用绝对回撤会让规则反复锁定。
    bench_f = bench.reindex(dates_all).fillna(0.0).to_numpy()

    nav, peak = 1.0, 1.0
    nav_a, peak_a = 1.0, 1.0
    beta_cur = 0.0
    dd_scale = 1.0
    paused_until = -1
    reentry = False
    n_rebal = 0; n_flat = 0; n_stop = 0; n_hit = 0; n_blocked = 0

    for i in range(n):
        d = dates_all[i]
        r = ret.iloc[i].fillna(0.0)
        pg = float((w * r).sum())
        gross[i] = pg

        # 暂停期结束：以当时 alpha 净值为新基准重算回撤，恢复半仓
        if dd_scale == 0.0 and i >= paused_until:
            peak_a = nav_a
            dd_scale = 0.5
            reentry = True

        if d in rb:
            n_hit += 1
        if d in rb and i >= paused_until:
            n_rebal += 1
            wn = targets[d].copy()
            for sym in stopped:
                if sym in wn.index:
                    wn[sym] = 0.0
            stopped = set()
            wn = wn * dd_scale
            delta = float((wn - w).abs().sum())
            turn[i] = delta
            net[i] = pg - delta * C.COST_BPS["ashare_stock"] / 1e4
            newly = (wn - w).abs() > 1e-12
            entry[newly & (wn > 0)] = px.loc[d][newly & (wn > 0)]
            entry[wn == 0] = np.nan
            w = wn
            beta_cur = beta_port.get(d, 0.0) * dd_scale
        else:
            net[i] = pg

        # 对冲损益（用最近一次调仓时估出的因果 beta）
        hedge_pnl[i] = beta_cur * bench_f[i]

        nav *= (1.0 + net[i])
        peak = max(peak, nav)
        # alpha 成分净值（用于回撤控制）
        active = net[i] - hedge_pnl[i]
        nav_a *= (1.0 + active)
        peak_a = max(peak_a, nav_a)
        dd_a = nav_a / peak_a - 1.0
        if dd_a <= -cfg.DD_FLAT:
            if dd_scale != 0.0:
                n_flat += 1
                paused_until = i + cfg.PAUSE_DAYS      # 仅在进入清仓的那一天设定暂停期
            w = w * 0.0
            dd_scale = 0.0
            beta_cur = 0.0
        elif dd_a <= -cfg.DD_HALVE:
            dd_scale = 0.5
        else:
            dd_scale = 1.0
        if reentry and dd_a > -cfg.DD_HALVE:
            dd_scale = 1.0
            reentry = False

        # 单票止损
        stopped_now = (px.iloc[i] / entry - 1.0) < -cfg.STOP_LOSS
        stopped_now = stopped_now.reindex(w.index).fillna(False) & (w > 1e-12)
        if stopped_now.any():
            for sym in w.index[stopped_now]:
                stopped.add(sym)
            cut = float(w[stopped_now].sum())
            w[stopped_now] = 0.0
            turn[i] += cut
            n_stop += int(stopped_now.sum())

        den = 1.0 + pg
        if abs(den) > 1e-9:
            w = w * (1.0 + r) / den

    # ---- beta 对冲（因果口径：调仓时估出的组合 beta × 指数收益）----
    net_s = pd.Series(net, index=dates_all)
    gross_s = pd.Series(gross, index=dates_all)
    turn_s = pd.Series(turn, index=dates_all)
    hp = pd.Series(hedge_pnl, index=dates_all)
    hedged = net_s - hp
    beta_mean = float(np.mean(list(beta_port.values()))) if beta_port else float("nan")

    m_long = C.metrics(net_s, gross_s, turn_s)
    m_hedged = C.metrics(hedged, gross_s - hp, turn_s)
    m_long["_gate_ok"] = C.cost_gate_ok(m_long, 3.0)
    m_long["_hedge_beta_mean"] = beta_mean
    m_long["_n_holdings_mean"] = float(np.mean([len(v) for v in holdings.values()])) if holdings else float("nan")
    m_long["_exrights_flags"] = nflag
    m_long["_n_rebal"] = n_rebal
    m_long["_n_flat"] = n_flat
    m_long["_n_stop_events"] = n_stop
    m_long["_n_rb_hit"] = n_hit
    m_long["_n_rb_blocked"] = n_hit - n_rebal

    if verbose:
        print(f"  行业中性化模式：{mode}"
              + (f"（外部表 {Path(industry_file).name}）" if mode == "file" else ""))
        C.print_metrics(f"规则二 A股截面反转 多头 L={L}", m_long)
        C.print_metrics(f"规则二 同上（指数对冲后）", m_hedged)
        print(f"      平均持仓 {m_long['_n_holdings_mean']:.1f} 只；"
              f"平均对冲 beta {m_long['_hedge_beta_mean']:.2f}；"
              f"除权修复 {nflag} 处；成本门槛"
              f"{'通过' if m_long['_gate_ok'] else '不通过'}")
        print(f"      调仓日命中 {m_long['_n_rb_hit']} 次，其中执行 {n_rebal}、被暂停阻塞 {m_long['_n_rb_blocked']}；"
              f"清仓触发 {n_flat} 次；单票止损 {n_stop} 次")
    return {"L": L, "mode": mode, "long": m_long, "hedged": m_hedged,
            "net": net_s, "hedged_net": hedged, "gross": gross_s, "turn": turn_s}


def run_longshort_reference(L=60, q=0.20, verbose=True):
    """论文口径的多空参照（研究用，不可实盘）：20% 分位两端等权，不加止损/上限/现金冗余。

    作用是把「规则二的工程增强项」与「论文构造」分离，从而定位纯多头版跑输的原因。
    """
    ret, amt, px, nflag = C.load_ashare()
    ret = ret.reindex(columns=sorted(ret.columns))
    amt = amt.reindex(columns=ret.columns)
    px = px.reindex(columns=ret.columns)
    tradable = C.tradable_mask(px, ret).fillna(False)
    liquid = C.liquidity_filter(amt, 20, 5e7).fillna(False)
    elig = tradable & liquid
    logret = np.log1p(ret.fillna(0.0)).where(ret.notna())
    S = logret.rolling(L).sum()

    dates = [ret.index[i] for i in range(L + 20, len(ret.index), 21)]
    tgt = {}
    for d in dates:
        s = S.loc[d]
        ok = s.notna() & elig.loc[d]
        sv = s[ok].sort_values()
        k = max(int(len(sv) * q), 5)
        if len(sv) < 2 * k:
            continue
        w = pd.Series(0.0, index=ret.columns)
        w[sv.index[:k]] = 0.5 / k      # 多「输家」（过去跌最多）
        w[sv.index[-k:]] = -0.5 / k    # 空「赢家」（过去涨最多）
        tgt[d] = w
    W = pd.DataFrame(tgt).T
    net, gross, turn = C.run_weights_backtest(ret, W, C.COST_BPS["ashare_stock"])
    m = C.metrics(net, gross, turn)
    m["_gate_ok"] = C.cost_gate_ok(m, 3.0)
    if verbose:
        C.print_metrics(f"规则二 参照：论文口径多空 L={L}", m)
        print("      （研究用，A 股做空不可实现；用于隔离工程增强项的影响）")
    return {"L": L, "metrics": m, "net": net}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--industry", default="sw",
                    choices=["sw", "tdx", "cluster", "file", "none"])
    ap.add_argument("--industry-file", default=None)
    ap.add_argument("--preset", default="首选", choices=list(RECOMMENDED),
                    help="跑第 12 节重标定后的推荐档（默认 首选）")
    ap.add_argument("--compare", action="store_true",
                    help="在 sw 与 cluster 两种中性化口径下对照")
    ap.add_argument("--ls-ref", action="store_true",
                    help="额外跑论文口径多空参照（用于归因）")
    args = ap.parse_args()
    print("=" * 96)
    print("规则二回测：A 股截面反转")
    print("=" * 96)
    rep = {}

    p = RECOMMENDED[args.preset]
    print(f"\n[推荐档：{args.preset}] L={p['L']}，行业中性化口径 {args.industry}")
    print("  排除的窗口：")
    for L, why in EXCLUDED.items():
        print(f"    L={L:3d} —— {why}")
    print()

    if args.compare:
        print("[口径对照] 真实申万 vs 聚类代理")
        for mode in ("sw", "cluster"):
            res = run(p["L"], mode=mode, industry_file=args.industry_file)
            rep[f"preset_{args.preset}_{mode}"] = {"long": res["long"],
                                                   "hedged": res["hedged"]}
    else:
        res = run(p["L"], mode=args.industry, industry_file=args.industry_file)
        rep[f"preset_{args.preset}"] = {"long": res["long"], "hedged": res["hedged"]}

    if args.ls_ref:
        print("\n[参照] 论文口径多空（研究用，不可实盘；窗口取论文最优 L=60）")
        ref = run_longshort_reference(L=60)
        rep["reference_ls"] = ref["metrics"]

    outp = C.OUT / "rule2_results.json"
    outp.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=float),
                    encoding="utf-8")
    print(f"\n结果已写出 {outp}")


if __name__ == "__main__":
    main()