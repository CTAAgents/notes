# -*- coding: utf-8 -*-
"""P1 基线层：候选策略集合与经典基线。

候选集刻意混合“弱信号”与“纯噪声”，用于演示多重检验与 PBO 如何区分真信号与挑选偏差。
所有信号只使用 t 期可得特征（预测 t+1 期收益），学习型基线用扩展窗，禁止前视。
"""
from __future__ import annotations

import numpy as np


def rank_weights(signal: np.ndarray, mask: np.ndarray, gross: float = 1.0) -> np.ndarray:
    """截面去均值 + 单位毛暴露，构建多空权重；不可交易处置零。"""
    s = np.where(mask, signal, np.nan)
    s = s - np.nanmean(s, axis=1, keepdims=True)
    s = np.nan_to_num(s)
    g = np.abs(s).sum(axis=1, keepdims=True)
    g[g == 0] = 1.0
    return gross * s / g


def ridge_expanding(X: np.ndarray, r: np.ndarray, mask: np.ndarray,
                    lam: float = 1.0, min_train: int = 200) -> np.ndarray:
    """扩展窗岭回归：每期只用 t 期之前的数据拟合，再对 t 期出信号。"""
    T, N, K = X.shape
    Xf = X.reshape(T * N, K)
    rf = r.reshape(T * N)
    mf = mask.reshape(T * N)
    out = np.zeros((T, N))
    eye = np.eye(K)
    for t in range(T):
        hi = t * N
        Xtr = Xf[:hi][mf[:hi]]
        rtr = rf[:hi][mf[:hi]]
        if rtr.size < min_train:
            continue
        A = Xtr.T @ Xtr + lam * eye
        b = Xtr.T @ rtr
        w = np.linalg.solve(A, b)
        out[t] = X[t] @ w
    return out


def apply_tradability(weights: np.ndarray, tradable: np.ndarray) -> np.ndarray:
    """不可交易（涨跌停/停牌/退市）的资产沿用上一期权重，禁止假设仍可调仓。"""
    T, N = weights.shape
    out = weights.copy()
    for t in range(1, T):
        hold = ~tradable[t]
        if hold.any():
            out[t, hold] = out[t - 1, hold]
    return out


LAMBDA_GRID = (0.1, 1.0, 10.0)


def build_candidates(snap, n_random: int = 50, seed: int = 7) -> dict:
    """构造候选策略池：单特征 + 随机线性组合 + 岭回归（含岭参数网格）。

    随机线性组合中绝大多数是纯噪声，正是它们让多重检验与 PBO 有意义。
    岭参数网格属于超参数搜索，须一并计入试验账本。
    """
    X, r, mask = snap["X"], snap["r"], snap["mask"]
    T, N, K = X.shape
    cands = {}
    for k in range(K):
        cands[f"feat{k}"] = X[:, :, k]
    rng = np.random.default_rng(seed)
    for j in range(n_random):
        w = rng.standard_normal(K)
        cands[f"rand{j}"] = X @ w
    for lam in LAMBDA_GRID:
        cands[f"ridge_lam{lam}"] = ridge_expanding(X, r, mask, lam=lam)
    return cands
