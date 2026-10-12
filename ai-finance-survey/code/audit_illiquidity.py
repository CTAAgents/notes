# -*- coding: utf-8 -*-
"""非流动性线索的深入检验（第三轮评审后的跟进分析）。

背景：第 21 章的候选级成本对照显示，8 个价量特征中只有 Amihud 非流动性在
含冲击后夏普仍为正（多空 1.014、仅多头 0.892），换手仅 14--18 倍。但它到底是
"可提取的 alpha"，还是"持有非流动性资产的补偿"，需要单独检验——本文一贯的
口径是：可预测不等于可交易，那么可交易也不等于可提取。

本脚本做六项检验：
  T1 分层与尾部依赖：按非流动性分十层，溢价是全面单调还是尾部驱动
  T2 子期稳定性：逐年拆解，看是否依赖少数时段
  T3 可投资子集：提高 ADV 门槛后溢价是否存活
  T4 竞品归因：与其余七个因子的相关，排除被已知异象解释
  T5 流动性风险解释：溢价是否集中于市场流动性恶化期
  T6 成本稳健性：ADV 折半/四分之一下的存活

运行：python audit_illiquidity.py
"""
from __future__ import annotations

import numpy as np

from baseline import apply_tradability, rank_weights
from costs import CostModel, ashare_fee_bps, stamp_duty_schedule
from diag_ls_lo import NAMES, lo_weights
from eval import metrics
from real_data import make_snapshot

CAPITAL = 1e8
K_ILLIQ = NAMES.index("非流动性")
MIN_NAMES = 30          # 每期参与排序的最少个股数


def _ret(w, r):
    return np.array([float(np.sum(w[t] * r[t])) for t in range(w.shape[0])])


def _turnover(w):
    return float(np.abs(np.diff(w, axis=0)).sum(axis=1).mean() * 252)


def _net_returns(w, r, cm, extra):
    T = r.shape[0]
    out = np.zeros(T)
    prev = np.zeros(r.shape[1])
    for t in range(T):
        out[t] = (float(np.sum(w[t] * r[t]))
                  - cm.cost(prev, w[t], CAPITAL, extra_fee_sell=float(extra[t])))
        prev = w[t]
    return out


def _rolling_percentile_rank(x, mask, win=60):
    """逐期截面分位（0~1），供构造"仅可投资子集"的权重。"""
    T, N = x.shape
    out = np.full((T, N), np.nan)
    for t in range(T):
        m = mask[t]
        if m.sum() < MIN_NAMES:
            continue
        v = x[t][m]
        order = v.argsort().argsort().astype(float)
        out[t][m] = order / max(len(v) - 1, 1)
    return out


def t1_decile(sig, r, mask):
    """按非流动性分十层，报告各层平均下期收益（基点）与单调性。"""
    T = sig.shape[0]
    buckets = [[] for _ in range(10)]
    spreads = []
    for t in range(T - 1):
        m = mask[t]
        if m.sum() < MIN_NAMES:
            continue
        idx = np.where(m)[0]
        v = sig[t][idx]
        order = np.argsort(v)
        groups = np.array_split(order, 10)
        for g, sel in enumerate(groups):
            buckets[g].append(float(r[t][idx[sel]].mean()))
        spreads.append(float(r[t][idx[groups[-1]]].mean() - r[t][idx[groups[0]]].mean()))
    means = np.array([np.mean(b) * 1e4 for b in buckets])
    print("  十层平均下期收益（基点，第 1 层=最流动、第 10 层=最不流动）：")
    print("   ", " ".join(f"{x:6.1f}" for x in means))
    rho = np.corrcoef(np.arange(10), means)[0, 1]
    print(f"    层序与收益的相关系数 = {rho:.3f}（越接近 1 越单调）")
    sp = np.array(spreads)
    print(f"    首末层价差：日均 {sp.mean()*1e4:.1f} bp，胜率 {(sp > 0).mean():.3f}")
    return means, rho


def t2_subperiod(w_ls, w_lo, r, dates, cm_zero, cm_imp, extra):
    print("  逐年（按日历年份切分）：")
    years = np.array([d // 10000 for d in dates])
    g_ls = _ret(w_ls, r)
    n_ls = _net_returns(w_ls, r, cm_imp, extra)
    g_lo = _ret(w_lo, r)
    n_lo = _net_returns(w_lo, r, cm_imp, extra)
    print(f"  {'年份':6s} {'交易日':>6s} {'多空零成本':>10s} {'多空含冲击':>10s} "
          f"{'仅多头零成本':>12s} {'仅多头含冲击':>12s}")
    for y in sorted(set(years)):
        s = years == y
        if s.sum() < 60:
            continue
        print(f"  {y:6d} {int(s.sum()):6d} "
              f"{metrics(g_ls[s])['sharpe']:10.2f} {metrics(n_ls[s])['sharpe']:10.2f} "
              f"{metrics(g_lo[s])['sharpe']:12.2f} {metrics(n_lo[s])['sharpe']:12.2f}")


def _trailing_adv(amt, tradable, win=250, stride=21):
    """时点安全的 ADV：滚动 250 日中位数，每 21 日重算一次并前向填充。

    避免用全样本中位数筛选子集带来的前视问题。
    """
    T, N = amt.shape
    out = np.full((T, N), np.nan)
    last = None
    for t in range(T):
        if t >= win and (t - win) % stride == 0:
            w = np.where(tradable[t - win:t], amt[t - win:t], np.nan)
            last = np.nanmedian(w, axis=0)
        out[t] = last if last is not None else np.nan
    fill = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
    fill = np.where(np.isfinite(fill) & (fill > 0), fill, 1e7)
    for t in range(T):
        bad = ~np.isfinite(out[t])
        out[t, bad] = fill[bad]
    return out


def t3_investable(sig, r, mask, tradable, adv_t, min_pct):
    """只在流动性较好的子集内构造多空（按当期 ADV 分位筛选，时点安全）。"""
    keep = np.zeros_like(mask)
    for t in range(mask.shape[0]):
        a = adv_t[t]
        thr = np.quantile(a, min_pct)
        keep[t] = mask[t] & (a >= thr)
    w = apply_tradability(rank_weights(sig, keep), tradable)
    return w


def _ttest(a, b):
    """两样本均值差的 t 值（异方差）。"""
    na, nb = a.size, b.size
    va, vb = a.var(ddof=1) / na, b.var(ddof=1) / nb
    return float((a.mean() - b.mean()) / np.sqrt(va + vb))


def main():
    snap = make_snapshot()
    X, r, mask, tradable, amt = (snap["X"], snap["r"], snap["mask"],
                                 snap["tradable"], snap["amt"])
    dates = snap["dates"]
    T = r.shape[0]
    adv = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
    adv = np.where(np.isfinite(adv) & (adv > 0), adv, 1e7)
    fee = ashare_fee_bps()
    extra = stamp_duty_schedule(dates)
    cm_zero = CostModel(mode="zero")

    sig = X[:, :, K_ILLIQ]
    w_ls = apply_tradability(rank_weights(sig, mask), tradable)
    w_lo = lo_weights(sig, mask, tradable)

    print("=== T1 分层与尾部依赖 ===")
    t1_decile(sig, r, mask)

    print("\n=== T2 子期稳定性 ===")
    t2_subperiod(w_ls, w_lo, r, dates, cm_zero,
                 CostModel(mode="impact", fee_bps=fee, adv=adv), extra)

    print("\n=== T3 可投资子集（按当期 ADV 分位筛选后重建多空，时点安全）===")
    adv_t = _trailing_adv(amt, tradable)
    for pct in (0.0, 0.3, 0.5, 0.7):
        w = t3_investable(sig, r, mask, tradable, adv_t, pct)
        g = metrics(_ret(w, r))["sharpe"]
        cm = CostModel(mode="impact", fee_bps=fee, adv=adv_t.mean(axis=0))
        n = metrics(_net_returns(w, r, cm, extra))["sharpe"]
        print(f"  保留 ADV 后 {(1-pct)*100:4.0f}% 的个股 → 零成本夏普 {g:6.3f}，"
              f"含冲击夏普 {n:6.3f}，年化换手 {_turnover(w):5.0f} 倍")

    print("\n=== T4 与其余因子的相关（多空收益序列）===")
    base = _ret(w_ls, r)
    for k, nm in enumerate(NAMES):
        if k == K_ILLIQ:
            continue
        wk = apply_tradability(rank_weights(X[:, :, k], mask), tradable)
        c = float(np.corrcoef(base, _ret(wk, r))[0, 1])
        print(f"  与 {nm:10s} 的相关 = {c:+.3f}")

    print("\n=== T5 流动性风险解释：溢价是否集中于市场流动性恶化期 ===")
    illiq_xs = np.array([np.nanmean(illiq_t[mask[t]]) if mask[t].sum() > 0 else np.nan
                         for t, illiq_t in enumerate(X[:, :, K_ILLIQ])])
    dLiq = np.full(T, np.nan)
    dLiq[1:] = illiq_xs[1:] - illiq_xs[:-1]      # 截面平均非流动性上升 = 流动性恶化
    ok = np.isfinite(dLiq) & np.isfinite(base)
    high = ok & (dLiq > np.nanquantile(dLiq[ok], 0.75))
    low = ok & (dLiq < np.nanquantile(dLiq[ok], 0.25))
    print(f"  流动性恶化期（截面平均非流动性升幅前 25%）：日均 {base[high].mean()*1e4:6.1f} bp"
          f"（{int(high.sum())} 天）")
    print(f"  流动性改善期（后 25%）：                日均 {base[low].mean()*1e4:6.1f} bp"
          f"（{int(low.sum())} 天）")
    print(f"  两期之差 = {(base[high].mean() - base[low].mean())*1e4:.1f} bp；"
          f"均值差 t 值 = {_ttest(base[high], base[low]):+.2f}；"
          f"因子收益与 dLiq 的相关 = {np.corrcoef(base[ok], dLiq[ok])[0, 1]:+.3f}")

    print("\n=== T6 成本稳健性（ADV 打折后重算含冲击夏普）===")
    for mult in (1.0, 0.5, 0.25):
        cm = CostModel(mode="impact", fee_bps=fee, adv=adv * mult)
        n_ls = _net_returns(w_ls, r, cm, extra)
        n_lo = _net_returns(w_lo, r, CostModel(mode="impact", fee_bps=fee, adv=adv * mult), extra)
        print(f"  ADV ×{mult:4.2f} → 多空含冲击夏普 {metrics(n_ls)['sharpe']:6.3f}"
              f"；仅多头 {metrics(n_lo)['sharpe']:6.3f}")


if __name__ == "__main__":
    main()