# -*- coding: utf-8 -*-
"""P0--P2 评测层：walk-forward 切分、六类指标、缩水夏普（DSR）与回测过拟合概率（PBO）。
实现遵循 Bailey & Lopez de Prado (2014) 的 DSR 与 Bailey et al. (2016) 的 CSCV 思路。
"""
from __future__ import annotations

from itertools import combinations
from math import e, sqrt
from statistics import NormalDist

import numpy as np

_ND = NormalDist()
_EULER = 0.5772156649015329  # 欧拉-马歇罗尼常数


# ---------- 切分 ----------
def walk_forward(T: int, train_len: int, test_len: int, step: int | None = None):
    """滚动前向切分，产出 (train_idx, test_idx)。禁止测试段信息进入训练。"""
    step = step or test_len
    i = 0
    while i + train_len + test_len <= T:
        yield (np.arange(i, i + train_len),
               np.arange(i + train_len, i + train_len + test_len))
        i += step


# ---------- 指标 ----------
def metrics(r: np.ndarray, ppy: int = 252) -> dict:
    r = np.asarray(r, dtype=float)
    if r.size == 0:
        return {}
    mu = r.mean() * ppy
    vol = r.std(ddof=1) * sqrt(ppy) if r.size > 1 else 0.0
    sharpe = mu / vol if vol > 0 else 0.0
    eq = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(eq)
    mdd = float(np.min(eq / peak - 1.0))
    var95 = float(np.quantile(r, 0.05))
    cvar = float(r[r <= var95].mean()) if np.any(r <= var95) else var95
    sk = float(((r - r.mean()) ** 3).mean() / (r.std() ** 3 + 1e-12))
    ku = float(((r - r.mean()) ** 4).mean() / (r.std() ** 4 + 1e-12))
    return {"ann_return": float(mu), "ann_vol": float(vol), "sharpe": float(sharpe),
            "max_drawdown": mdd, "var95": var95, "cvar95": cvar,
            "skew": sk, "kurt": ku, "n": int(r.size)}


def _sharpe_cols(x: np.ndarray) -> np.ndarray:
    """按列计算年化夏普（x 为 T×M）。"""
    x = np.asarray(x, dtype=float)
    mu = x.mean(axis=0)
    sd = x.std(axis=0, ddof=1)
    sd[sd == 0] = 1e-12
    return mu / sd


# ---------- 信号类指标：逐期截面 IC 与 IR ----------
def ic_series(signal: np.ndarray, fwd_ret: np.ndarray, mask: np.ndarray) -> dict:
    """逐期计算截面 IC（信号与下期收益的 Pearson 相关），并给出 IR 等汇总。

    signal、fwd_ret、mask 均为 T×N；IC 仅在同一期可交易集合内计算。
    """
    T = signal.shape[0]
    ics = []
    for t in range(T):
        m = mask[t]
        if m.sum() < 3:
            continue
        s = signal[t][m]
        r = fwd_ret[t][m]
        if s.std() == 0 or r.std() == 0:
            continue
        ics.append(float(np.corrcoef(s, r)[0, 1]))
    ics = np.asarray(ics, dtype=float)
    if ics.size == 0:
        return {"ic_mean": 0.0, "ic_std": 0.0, "ic_ir": 0.0,
                "ic_positive_ratio": 0.0, "ic_n": 0}
    sd = ics.std(ddof=1) if ics.size > 1 else 0.0
    return {"ic_mean": float(ics.mean()), "ic_std": float(sd),
            "ic_ir": float(ics.mean() / sd) if sd > 0 else 0.0,
            "ic_positive_ratio": float((ics > 0).mean()), "ic_n": int(ics.size)}


# ---------- 缩水夏普 DSR ----------
def deflated_sharpe(sr: float, T: int, n_trials: int, var_sr: float,
                    skew: float = 0.0, kurt: float = 3.0) -> dict:
    """sr 为观测到的（非年化）夏普；var_sr 为多次试验夏普估计的截面方差。

    注意 var_sr 的取法决定结果的量级：它应当估计"试验夏普估计量的方差
    V(SR_hat)"。若把候选池样本外夏普的**截面离散度**直接代入，只有在候选
    彼此独立、且池中不存在真实质量差异时才成立；候选高度相关、或池内含真实
    强弱之分时，该离散度会混入质量差异并高估 V(SR_hat)。本实现按原式保留该
    口径，配对的解析口径见 deflated_sharpe_se，两者应并列报告并说明取舍。
    """
    if n_trials < 2:
        n_trials = 2
    z1 = _ND.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _ND.inv_cdf(1.0 - 1.0 / (n_trials * e))
    sr0 = sqrt(max(var_sr, 1e-12)) * ((1.0 - _EULER) * z1 + _EULER * z2)
    denom = sqrt(max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2, 1e-9))
    dsr = _ND.cdf((sr - sr0) * sqrt(max(T - 1, 1)) / denom)
    return {"sr": sr, "sr0_expected_max": sr0, "dsr": dsr,
            "n_trials": n_trials, "T": T}


def deflated_sharpe_se(sr: float, T: int, n_trials: int,
                       skew: float = 0.0, kurt: float = 3.0) -> dict:
    """DSR 的解析（标准误）口径：以单个夏普估计的标准误充当 sqrt(V(SR_hat))。

    SE(SR) = sqrt((1 - g3*SR + (g4-1)/4*SR^2)/(T-1))，其中 g3/g4 为收益的
    偏度与峰度。两个口径的标准化方式完全相同（都以该解析标准误除 (sr - sr0)），
    差别只在 sr0 里 V(SR_hat) 的取法：本口径用解析方差，deflated_sharpe 用
    候选池样本外夏普的截面方差。

    就本研究的候选池而言（同 8 个特征的线性组合、彼此高度相关），截面离散度
    主要度量的是策略质量差异而非估计误差，代入会高估 V(SR_hat)，故本口径更适用。
    仍需说明两点边界：(1) 原文 DSR 的 V(SR_hat) 取自试验集夏普的方差，本口径的
    解析方差是在试验集不可用时的替代，二者不等价；(2) E[max_N] 项假设试验相互
    独立，候选相关会使其偏大，故本口径在该意义上略偏保守。
    """
    if n_trials < 2:
        n_trials = 2
    var_sr = max(1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2, 1e-9) / max(T - 1, 1)
    z1 = _ND.inv_cdf(1.0 - 1.0 / n_trials)
    z2 = _ND.inv_cdf(1.0 - 1.0 / (n_trials * e))
    sr0 = sqrt(var_sr) * ((1.0 - _EULER) * z1 + _EULER * z2)
    dsr = _ND.cdf((sr - sr0) / sqrt(var_sr))
    return {"sr": sr, "sr0_expected_max": sr0, "dsr": dsr,
            "se_sr": sqrt(var_sr), "n_trials": n_trials, "T": T,
            "method": "standard_error"}


# ---------- 回测过拟合概率 PBO（CSCV） ----------
def pbo_cscv(perf: np.ndarray, n_splits: int = 12) -> dict:
    """perf 为 T×M 的策略收益矩阵。返回 PBO 与对数几率分布。"""
    perf = np.asarray(perf, dtype=float)
    T, M = perf.shape
    if n_splits % 2:
        n_splits += 1
    if M < 2 or T < n_splits * 2:
        return {"pbo": float("nan"), "n_combos": 0, "logits": []}
    parts = np.array_split(np.arange(T), n_splits)
    logits, over = [], 0
    combos = list(combinations(range(n_splits), n_splits // 2))
    for c in combos:
        is_idx = np.concatenate([parts[i] for i in c])
        oos_idx = np.concatenate([parts[i] for i in range(n_splits) if i not in c])
        is_sr = _sharpe_cols(perf[is_idx])
        oos_sr = _sharpe_cols(perf[oos_idx])
        n_star = int(np.argmax(is_sr))
        # 相对排名 omega = rank/(M+1)，越靠下越像过拟合
        rank = int((oos_sr < oos_sr[n_star]).sum()) + 1
        w = rank / (M + 1)
        w = min(max(w, 1e-6), 1 - 1e-6)
        logits.append(float(np.log(w / (1 - w))))
        if w < 0.5:
            over += 1
    return {"pbo": over / len(combos), "n_combos": len(combos), "logits": logits}


def pbo_sensitivity(perf: np.ndarray, splits=(8, 12, 16, 20)) -> dict:
    """对 CSCV 切分段数做敏感性分析，报告 PBO 的区间与逐项取值。"""
    out = {}
    for s in splits:
        out[s] = pbo_cscv(perf, n_splits=s)["pbo"]
    vals = [v for v in out.values() if v == v]  # 去 NaN
    return {"by_splits": out,
            "min": float(min(vals)) if vals else float("nan"),
            "max": float(max(vals)) if vals else float("nan")}
