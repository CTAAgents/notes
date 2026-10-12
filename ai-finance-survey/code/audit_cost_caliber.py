# -*- coding: utf-8 -*-
"""成本口径审计：冲击模型的 ADV 假设与样本真实成交额是否匹配。

论文第 21 章报告的"含冲击"夏普用的是 CostModel 默认 ADV=10 亿元，且对全部
个股取同一常数。本脚本用快照里逐个股的日成交额（穿越窗口的中位数）替代该常数，
重算同一候选的含冲击表现，量化 ADV 假设对结论的影响。

运行：python audit_cost_caliber.py
"""
from __future__ import annotations

import numpy as np

from baseline import apply_tradability, build_candidates, rank_weights
from costs import CostModel
from eval import metrics
from real_data import make_snapshot

CAPITAL = 1e8
SELECTED = "rand10"          # 论文第 21 章选中的候选


def portfolio_return(weights, r, cm: CostModel):
    T = r.shape[0]
    out = np.zeros(T)
    prev = np.zeros(r.shape[1])
    for t in range(T):
        out[t] = float(np.sum(weights[t] * r[t])) - cm.cost(prev, weights[t], CAPITAL)
        prev = weights[t]
    return out


class PerNameCost(CostModel):
    """按个股各自的 ADV 计算参与率；其余口径与 CostModel 保持一致。"""

    def __init__(self, adv_vec, **kw):
        super().__init__(mode="impact", **kw)
        self.adv_vec = adv_vec

    def cost(self, weights, next_weights, capital=CAPITAL):
        turn = np.abs(next_weights - weights)
        notional = turn * capital
        part = notional / np.where(self.adv_vec > 0, self.adv_vec, np.inf)
        over = part > self.max_part
        self.violations += int(np.sum(over))
        part = np.clip(part, 0.0, self.max_part)
        return float(np.sum(turn * (self.fee + self.k * np.sqrt(part))))


def main():
    snap = make_snapshot()
    X, r, mask, tradable = snap["X"], snap["r"], snap["mask"], snap["tradable"]
    amt = snap["amt"] if "amt" in snap else None
    if amt is None:                       # 快照未返回成交额时，从原始价量重取
        raise SystemExit("快照未包含 amt，需在 real_data 返回值中补上")

    # 每只个股在窗口内的日成交额中位数（元），作为其 ADV 代理
    adv_med = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
    adv_med = np.where(np.isfinite(adv_med) & (adv_med > 0), adv_med, 1e7)

    cands = build_candidates(snap, n_random=50)
    w = apply_tradability(rank_weights(cands[SELECTED], mask), tradable)

    print(f"候选={SELECTED}  资本={CAPITAL:.0e} 元")
    print(f"样本 ADV 代理（个股成交额中位数）：中位 {np.median(adv_med):.3e} 元 "
          f"| 25 分位 {np.percentile(adv_med, 25):.3e} | 75 分位 {np.percentile(adv_med, 75):.3e}")
    print(f"论文所用常数 ADV = 1.000e+09 元，相当于样本中位数的 "
          f"{1e9 / np.median(adv_med):.1f} 倍\n")

    cases = [("论文口径 ADV=1e9（常数）", CostModel(mode="impact")),
             ("逐股 ADV=成交额中位数", PerNameCost(adv_med)),
             ("逐股 ADV=中位数 / 2", PerNameCost(adv_med / 2))]
    print(f"{'口径':26s} {'年化':>8s} {'夏普':>8s} {'最大回撤':>10s} {'参与率超限':>10s}")
    for name, cm in cases:
        m = metrics(portfolio_return(w, r, cm))
        print(f"{name:26s} {m['ann_return']:8.3f} {m['sharpe']:8.3f} "
              f"{m['max_drawdown']:10.3f} {cm.violations:10d}")

    # 零成本基准，供对照
    m0 = metrics(portfolio_return(w, r, CostModel(mode="zero")))
    print(f"{'零成本（对照）':26s} {m0['ann_return']:8.3f} {m0['sharpe']:8.3f} "
          f"{m0['max_drawdown']:10.3f} {0:10d}")


if __name__ == "__main__":
    main()