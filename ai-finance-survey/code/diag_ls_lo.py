# -*- coding: utf-8 -*-
"""单特征多空 vs 仅多头（可实施）对照：为论文第 21 章的表生成数字。

多空组合需个股做空，A 股不可行；仅多头为可实施口径。两者并列，用于量化
"信息层可预测"与"可交易"之间的落差。方向取样本内更优者（多空与多头同向）。

运行：python diag_ls_lo.py
"""
from __future__ import annotations

import numpy as np

from baseline import apply_tradability, rank_weights
from eval import ic_series, metrics, walk_forward
from real_data import make_snapshot

NAMES = ["1日反转", "5日动量", "20日动量", "60日动量",
         "波动率", "量比", "距均线偏离", "非流动性"]


def _ret(w: np.ndarray, r: np.ndarray) -> np.ndarray:
    return np.array([float(np.sum(w[t] * r[t])) for t in range(w.shape[0])])


def lo_weights(sig: np.ndarray, mask: np.ndarray, tradable: np.ndarray) -> np.ndarray:
    """仅多头权重：只买信号为正的一半，归一到净暴露 1（可实施口径）。"""
    w = np.clip(apply_tradability(rank_weights(sig, mask), tradable), 0, None)
    s = w.sum(axis=1, keepdims=True)
    return np.divide(w, np.where(s == 0, 1, s))


def run():
    snap = make_snapshot()
    X, r, mask, tradable = snap["X"], snap["r"], snap["mask"], snap["tradable"]
    T, N, K = X.shape
    folds = list(walk_forward(T, 500, 120))

    def oos(x):
        return np.concatenate([x[te] for _tr, te in folds])

    def ls(sig):
        return _ret(apply_tradability(rank_weights(sig, mask), tradable), r)

    def lo(sig):
        return _ret(lo_weights(sig, mask, tradable), r)

    print(f"{'特征':12s} {'多空IS':>8s} {'多空OOS':>8s} {'多头OOS':>8s} "
          f"{'IC均值':>8s} {'IC-IR':>8s} {'t值':>7s}")
    rows = []
    for k in range(K):
        a_ls, a_lo = ls(X[:, :, k]), lo(X[:, :, k])
        b_ls, b_lo = ls(-X[:, :, k]), lo(-X[:, :, k])
        if metrics(a_ls)["sharpe"] >= metrics(b_ls)["sharpe"]:
            d, s_ls, s_lo = "+", a_ls, a_lo
        else:
            d, s_ls, s_lo = "-", b_ls, b_lo
        ic = ic_series(X[:, :, k], r, mask)
        # IC 序列的 t 值：IR × √n（截面 IC 的时序均值是否显著异于 0）
        t = ic["ic_ir"] * np.sqrt(ic["ic_n"]) if ic["ic_n"] > 0 else 0.0
        print(f"{NAMES[k]:12s} {metrics(s_ls)['sharpe']:8.3f} "
              f"{metrics(oos(s_ls))['sharpe']:8.3f} {metrics(oos(s_lo))['sharpe']:8.3f} "
              f"{d}{ic['ic_mean']:7.4f} {ic['ic_ir']:8.3f} {t:7.2f}")
        rows.append((NAMES[k], metrics(oos(s_ls))["sharpe"],
                     metrics(oos(s_lo))["sharpe"], t))
    print(f"\n最优：多空 OOS {max(x[1] for x in rows):.3f}，"
          f"仅多头 OOS {max(x[2] for x in rows):.3f}")
    ts = np.array([abs(x[3]) for x in rows])
    print(f"|t| > 3（Harvey--Liu--Zhu 门槛）者："
          f"{sum(ts > 3)}/{len(ts)} → "
          f"{[r[0] for r in rows if abs(r[3]) > 3]}")
    return rows


if __name__ == "__main__":
    run()