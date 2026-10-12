# -*- coding: utf-8 -*-
"""P0 数据层：时点（point-in-time）面板的构造与快照接口。

真实研究中这里应接入时点数据库（成分股、按披露日对齐的财报、按首次可见时间对齐的文本）。
本文件给出一个确定性、可复现的合成面板，用于让 P0--P2 流程可端到端跑通；
合成数据仅用于验证评测流程，不代表任何市场结论。
"""
from __future__ import annotations

import hashlib

import numpy as np


def make_snapshot(n_dates: int = 1200, n_assets: int = 60, n_feat: int = 8,
                  seed: int = 20261009):
    """构造时点面板快照。

    返回 dict：
      X      : (T, N, K) 特征，t 期只用 t 及以前的信息生成（无前视）
      r      : (T, N)    下一期收益（标签），由 t 期特征经一个稀疏真实函数生成
      mask   : (T, N)    可交易掩码（时点成分）
      digest : str       数据快照校验和
    """
    rng = np.random.default_rng(seed)

    # 时点成分：随时间缓慢变化的宇宙（避免幸存者偏差式的固定名单）
    alive = rng.random((n_assets,)) < 0.9
    mask = np.zeros((n_dates, n_assets), dtype=bool)

    # 特征带持续性（AR(1)），使基于特征的信号换手不会被人为放大
    rho = 0.9
    X = np.zeros((n_dates, n_assets, n_feat))
    X[0] = rng.standard_normal((n_assets, n_feat))
    innov = np.sqrt(1.0 - rho ** 2)
    for t in range(1, n_dates):
        X[t] = rho * X[t - 1] + innov * rng.standard_normal((n_assets, n_feat))
    for t in range(n_dates):
        if t % 40 == 0 and t > 0:  # 每 40 期按“一对一”换手，保持宇宙规模稳定
            on = np.where(alive)[0]
            off = np.where(~alive)[0]
            if on.size > 2 and off.size > 0:
                alive[rng.choice(on)] = False
                alive[rng.choice(off)] = True
        mask[t] = alive

    # 稀疏且微弱的真实信号：只有 3 个特征贡献，外加一个弱交互项
    beta = np.zeros(n_feat)
    beta[[0, 2, 5]] = [0.00050, -0.00035, 0.00030]
    signal = X @ beta + 0.00030 * (X[:, :, 0] * X[:, :, 2])
    noise = rng.standard_normal((n_dates, n_assets)) * 0.06
    r = signal + noise

    # 交易制度约束：涨跌停（|上一期收益| 达阈值）、停牌、退市（mask 外）
    limit_hit = np.abs(r) >= 0.12
    suspend = rng.random((n_dates, n_assets)) < 0.005
    tradable = np.ones((n_dates, n_assets), dtype=bool)
    tradable[0] = mask[0]
    tradable[1:] = mask[1:] & (~limit_hit[:-1]) & (~suspend[1:])

    digest = hashlib.sha256(
        np.ascontiguousarray(X).tobytes() + np.ascontiguousarray(r).tobytes()
        + np.ascontiguousarray(tradable).tobytes()
    ).hexdigest()[:16]

    return {"X": X, "r": r, "mask": mask, "tradable": tradable, "digest": digest}


def snapshot_digest(snap) -> str:
    return snap["digest"]
