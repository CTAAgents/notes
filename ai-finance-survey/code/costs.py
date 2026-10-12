# -*- coding: utf-8 -*-
"""P0 成本层：零成本 / 固定费率 / 含平方根冲击三档成本。

冲击成本采用绝对参与率模型 impact = K * sqrt(participation)，
参与率 = |成交额| / ADV，并设上限；超限标记（真实系统中应拒绝或拆单）。

ADV 可为标量（对全部资产取同一常数）或逐资产向量；真实数据实证应用后者，
以个股自身的成交额为准。另提供卖出侧附加费 extra_fee_sell，用于按日期分段
计入 A 股卖出印花税（2023-08-28 起由 0.1% 降至 0.05%）。
"""
from __future__ import annotations

import numpy as np


class CostModel:
    def __init__(self, mode: str = "impact", fee_bps: float = 5.0,
                 impact_k: float = 0.02, adv=1e9,
                 max_participation: float = 0.10):
        assert mode in {"zero", "fixed", "impact"}
        self.mode = mode
        self.fee = fee_bps / 1e4
        self.k = impact_k
        self.adv = adv                    # 标量或形状 (N,) 的逐资产 ADV
        self.max_part = max_participation
        self.violations = 0

    def cost(self, weights: np.ndarray, next_weights: np.ndarray,
             capital: float = 1e8, extra_fee_sell: float = 0.0) -> float:
        """返回调仓成本，以组合净值的比例计（与权重口径一致）。

        extra_fee_sell 仅作用于卖出部分（如印花税），按当期费率传入。
        """
        if self.mode == "zero":
            return 0.0
        d = next_weights - weights
        turn = np.abs(d)
        sell = np.sum(np.maximum(-d, 0.0))          # 卖出侧换手
        if self.mode == "fixed":
            return float(np.sum(turn) * self.fee + sell * extra_fee_sell)
        # impact: 参与率由成交名义额与该资产的 ADV 决定
        notional = turn * capital
        part = notional / self.adv                  # adv 为向量时逐资产相除
        over = part > self.max_part
        self.violations += int(np.sum(over))
        part = np.clip(part, 0.0, self.max_part)
        impact = self.k * np.sqrt(part)
        return float(np.sum(turn * (self.fee + impact)) + sell * extra_fee_sell)


# ---- A 股费率构成（真实数据实证用；合成面板仍用单一费率）----
COMMISSION_BPS = 2.5          # 券商佣金，双边
TRANSFER_BPS = 0.1            # 过户费，双边
STAMP_BPS_HIGH = 10.0         # 卖出印花税：2023-08-28 之前 0.1%
STAMP_BPS_LOW = 5.0           # 卖出印花税：2023-08-28 起 0.05%
STAMP_CUT_DATE = 20230828


def ashare_fee_bps() -> float:
    """双边基础费率（佣金 + 过户费），不含卖出印花税。"""
    return COMMISSION_BPS + TRANSFER_BPS


def stamp_duty_schedule(dates: np.ndarray) -> np.ndarray:
    """按交易日给出卖出印花税费率序列。"""
    d = np.asarray(dates)
    return np.where(d >= STAMP_CUT_DATE, STAMP_BPS_LOW, STAMP_BPS_HIGH) / 1e4