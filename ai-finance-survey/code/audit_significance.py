# -*- coding: utf-8 -*-
"""第三轮评审用诊断：检验第 21 章新增显著性结论的稳健性。

(1) IC 序列的时序自相关与 Newey--West 调整后的 t 值。论文用 t = IC-IR*sqrt(n)，
    该式假设逐期 IC 序列独立；动量类信号的 IC 有持续性，若自相关为正，
    该 t 会被高估。这里给出 AR(1) 系数与 NW 调整 t。
(2) 候选池的平均两两相关与有效试验数 N_eff，用于检验 DSR 的 E[max_N] 项。

运行：python audit_significance.py
"""
from __future__ import annotations

import numpy as np

from baseline import apply_tradability, rank_weights
from diag_ls_lo import NAMES
from eval import metrics, walk_forward
from real_data import make_snapshot


def ic_series_raw(signal, r, mask):
    out = []
    for t in range(signal.shape[0]):
        m = mask[t]
        if m.sum() < 3:
            continue
        a, b = signal[t][m], r[t][m]
        if a.std() == 0 or b.std() == 0:
            continue
        out.append(float(np.corrcoef(a, b)[0, 1]))
    return np.asarray(out)


def nw_t(x: np.ndarray, lags: int = 5) -> tuple:
    """Newey--West 调整的均值 t 值：返回 (t_naive, t_nw, ar1)。"""
    n = x.size
    mu = x.mean()
    d = x - mu
    g0 = float(np.dot(d, d) / n)
    var = g0
    for k in range(1, lags + 1):
        gk = float(np.dot(d[k:], d[:-k]) / n)
        var += 2.0 * (1.0 - k / (lags + 1.0)) * gk
    var = max(var, 1e-18)
    se_nw = np.sqrt(var / n)
    se_naive = np.sqrt(g0 / n)
    ar1 = float(np.corrcoef(d[1:], d[:-1])[0, 1]) if n > 2 else 0.0
    return mu / se_naive, mu / se_nw, ar1


def main():
    snap = make_snapshot()
    X, r, mask, tradable = snap["X"], snap["r"], snap["mask"], snap["tradable"]
    T, N, K = X.shape

    print("=== (1) IC 序列自相关与 Newey--West 调整 ===")
    print(f"{'特征':12s} {'IC均值':>9s} {'t(论文口径)':>11s} {'AR(1)':>8s} "
          f"{'t(NW)':>8s} {'是否仍过|t|>3':>13s}")
    for k, nm in enumerate(NAMES):
        s = ic_series_raw(X[:, :, k], r, mask)
        t_naive, t_nw, ar1 = nw_t(s)
        print(f"{nm:12s} {s.mean():9.4f} {t_naive:11.2f} {ar1:8.3f} "
              f"{t_nw:8.2f} {'是' if abs(t_nw) > 3 else '否':>13s}")

    print("\n=== (2) 候选池相关结构与有效试验数 ===")
    # 只取单特征与随机组合（岭回归候选在 1881×400 面板上构造极耗内存，
    # 且其相关结构与随机组合同类，故此处从略）
    cands = {}
    for k in range(K):
        cands[f"feat{k}"] = X[:, :, k]
    rng = np.random.default_rng(7)
    for j in range(50):
        w = rng.standard_normal(K)
        cands[f"rand{j}"] = X @ w
    cols = []
    for name, sig in cands.items():
        w = apply_tradability(rank_weights(sig, mask), tradable)
        cols.append(np.array([float(np.sum(w[t] * r[t])) for t in range(T)]))
    M = np.column_stack(cols)
    C = np.corrcoef(M, rowvar=False)
    off = C[np.triu_indices_from(C, 1)]
    rho = float(np.nanmean(off))
    n_c = C.shape[0]
    n_eff = n_c / (1.0 + (n_c - 1.0) * rho)
    print(f"候选数 = {n_c}；平均两两相关 = {rho:.3f}")
    print(f"有效试验数 N_eff = N/(1+(N-1)*rho) = {n_eff:.1f}")
    print(f"最大两两相关 = {np.nanmax(off):.3f}；相关系数矩阵的条件数 = "
          f"{np.linalg.cond(C):.1e}")

    # 用 N_eff 重算 DSR 的 sr0（标准误口径），看结论是否稳固
    folds = list(walk_forward(T, 500, 120))
    oos = {n: np.concatenate([M[te, j] for _tr, te in folds])
           for j, n in enumerate(cands)}
    best = "rand10"
    om = metrics(oos[best])
    sr = om["sharpe"] / np.sqrt(252)

    def sr0_for(n_trials):
        var = max(1 - om["skew"] * sr + (om["kurt"] - 1) / 4 * sr ** 2, 1e-9) / max(om["n"] - 1, 1)
        from math import e, sqrt
        from statistics import NormalDist
        nd = NormalDist()
        z1 = nd.inv_cdf(1 - 1 / n_trials)
        z2 = nd.inv_cdf(1 - 1 / (n_trials * e))
        g = 0.5772156649015329
        return sqrt(var) * ((1 - g) * z1 + g * z2)

    print(f"\nDSR 基准项 sr0：N=61 时 {sr0_for(61):.4f}；"
          f"N_eff={n_eff:.1f} 时 {sr0_for(max(n_eff, 2.0)):.4f}")
    print(f"观测 sr（非年化）= {sr:.4f}")


if __name__ == "__main__":
    main()