# -*- coding: utf-8 -*-
"""可实施性与归因诊断（对应第二轮评审 R8、R9）。

R8：给出同期等权全市场基准，并把仅多头组合的收益分解为 beta 与 alpha，
    使"仅多头含多少市场暴露"可量化。
R9：说明样本内最优候选 rand10 与最强单特征（量比）的关系——两者的截面
    信号相关度，以及各自的表现，判断随机混合是否只是量比的近似替身。

运行：python diag_alpha_beta.py
"""
from __future__ import annotations

import numpy as np

from baseline import apply_tradability, build_candidates, rank_weights
from diag_ls_lo import NAMES, _ret, lo_weights
from eval import metrics, walk_forward
from real_data import make_snapshot

SELECTED = "rand10"


def market_benchmark(r, mask):
    """等权全市场基准：每期对当期有效个股等权持有。"""
    out = np.zeros(r.shape[0])
    for t in range(r.shape[0]):
        m = mask[t]
        out[t] = float(r[t][m].mean()) if m.sum() else 0.0
    return out


def ols(y, x):
    """一元回归 y = a + b x，返回 (alpha 年化, beta)。"""
    xm, ym = x.mean(), y.mean()
    b = float(np.sum((x - xm) * (y - ym)) / max(np.sum((x - xm) ** 2), 1e-18))
    a = ym - b * xm
    return a * 252, b


def cross_section_corr(s1, s2, mask):
    """逐期截面相关的均值。"""
    cs = []
    for t in range(s1.shape[0]):
        m = mask[t]
        if m.sum() < 3:
            continue
        a, b = s1[t][m], s2[t][m]
        if a.std() == 0 or b.std() == 0:
            continue
        cs.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(cs)) if cs else float("nan")


def main():
    snap = make_snapshot()
    X, r, mask, tradable = snap["X"], snap["r"], snap["mask"], snap["tradable"]
    T = r.shape[0]
    folds = list(walk_forward(T, 500, 120))

    def oos(x):
        return np.concatenate([x[te] for _tr, te in folds])

    mkt = market_benchmark(r, mask)
    mm = metrics(mkt)
    print(f"等权全市场基准（同期）：年化 {mm['ann_return']:.3f} "
          f"夏普 {mm['sharpe']:.3f} 最大回撤 {mm['max_drawdown']:.3f} "
          f"OOS 夏普 {metrics(oos(mkt))['sharpe']:.3f}")

    cands = build_candidates(snap, n_random=50)
    k_illiq = NAMES.index("非流动性")

    def decompose(label, sig):
        s_lo = _ret(lo_weights(sig, mask, tradable), r)
        s_ls = _ret(apply_tradability(rank_weights(sig, mask), tradable), r)
        for tag, s in (("多空", s_ls), ("仅多头", s_lo)):
            a, b = ols(s, mkt)
            resid = s - b * mkt
            print(f"{label} {tag}：beta={b:.3f} 年化alpha={a:.3f} "
                  f"全样本夏普={metrics(s)['sharpe']:.3f} "
                  f"OOS夏普={metrics(oos(s))['sharpe']:.3f} "
                  f"剥beta后夏普={metrics(resid)['sharpe']:.3f} "
                  f"残差年化={metrics(resid)['ann_return']:.3f}")

    print()
    decompose(f"候选 {SELECTED}", cands[SELECTED])
    print()
    decompose("非流动性（成本后仍为正的候选）", X[:, :, k_illiq])

    # R9：rand10 与最强单特征（量比，k=5）的截面相关
    k_vratio = NAMES.index("量比")
    for nm, k in (("量比", k_vratio), ("1日反转", 0), ("非流动性", 7)):
        c = cross_section_corr(cands[SELECTED], X[:, :, k], mask)
        print(f"rand10 与 {nm} 的逐期截面相关均值 = {c:.3f}")


if __name__ == "__main__":
    main()