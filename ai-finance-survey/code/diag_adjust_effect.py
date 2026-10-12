# -*- coding: utf-8 -*-
"""复权口径对截面信号的影响：同一批特征在"后复权"与"不复权"两种标签下的 IC 对比。

做法：保持特征与权重完全不变，只把标签换成原始收盘价的相邻比，两列 IC 的
差异只可能来自除权跳空本身，用于回答"复权是否显著改变了信号结构"。

运行：python diag_adjust_effect.py
"""
from __future__ import annotations

import numpy as np

from diag_ls_lo import NAMES
from eval import ic_series
from real_data import make_snapshot


def main():
    snap = make_snapshot()
    X, r, mask, adj, raw = snap["X"], snap["r"], snap["mask"], snap["adj"], snap["raw"]
    T, N, K = X.shape

    # 不复权标签：直接用原始收盘价相邻比
    raw_ret = raw[1:] / raw[:-1] - 1.0
    raw_r = np.zeros_like(r)
    raw_r[:-1] = np.nan_to_num(raw_ret)
    raw_r[:-1] = np.where(np.isfinite(raw_ret), raw_r[:-1], 0.0)

    print(f"快照 digest={snap['digest']}  T={T} N={N}")
    print(f"{'特征':12s} {'后复权IC':>10s} {'不复权IC':>10s} {'差':>9s}")
    for k in range(K):
        a = ic_series(X[:, :, k], r, mask)["ic_mean"]
        b = ic_series(X[:, :, k], raw_r, mask)["ic_mean"]
        print(f"{NAMES[k]:12s} {a:10.4f} {b:10.4f} {a - b:+9.4f}")


if __name__ == "__main__":
    main()