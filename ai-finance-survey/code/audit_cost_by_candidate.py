# -*- coding: utf-8 -*-
"""候选级成本敏感性审计（第三轮评审 Q1 的证据脚本）。

论文第 21 章以样本内最优候选为例演示成本吞噬收益；该候选的换手偏高，
不足以代表整个候选池。本脚本对 8 个单特征的两种构建方式（多空 / 仅多头）
各自计算年化换手与两档夏普（零成本 / 含冲击），用于回答一个问题：
"成本后为负" 是普遍现象，还是与换手绑定的条件现象。

口径与第 21 章一致：逐股 ADV（窗口内成交额中位数）、佣金＋过户费＋分段
卖出印花税、平方根冲击、参与率上限 10%。符号按原特征方向，未取样本内
更优方向，因此若某特征的 IC 为负，其零成本夏普也为负。

运行：python audit_cost_by_candidate.py
"""
from __future__ import annotations

import numpy as np

from baseline import apply_tradability, rank_weights
from costs import CostModel, ashare_fee_bps, stamp_duty_schedule
from diag_ls_lo import NAMES, lo_weights
from eval import metrics
from real_data import make_snapshot

CAPITAL = 1e8


def portfolio_returns(weights, r, cm, extra) -> np.ndarray:
    T = r.shape[0]
    out = np.zeros(T)
    prev = np.zeros(r.shape[1])
    for t in range(T):
        out[t] = (float(np.sum(weights[t] * r[t]))
                  - cm.cost(prev, weights[t], CAPITAL,
                            extra_fee_sell=float(extra[t])))
        prev = weights[t]
    return out


def annualized_turnover(weights) -> float:
    return float(np.abs(np.diff(weights, axis=0)).sum(axis=1).mean() * 252)


def main():
    snap = make_snapshot()
    X, r, mask, tradable, amt = (snap["X"], snap["r"], snap["mask"],
                                 snap["tradable"], snap["amt"])
    adv = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
    adv = np.where(np.isfinite(adv) & (adv > 0), adv, 1e7)
    fee = ashare_fee_bps()
    extra = stamp_duty_schedule(snap["dates"])
    cm_zero = CostModel(mode="zero")
    cm_imp = CostModel(mode="impact", fee_bps=fee, adv=adv)

    print(f"{'特征':12s} {'口径':7s} {'年化换手':>9s} {'零成本夏普':>10s} "
          f"{'含冲击夏普':>10s} {'成本耗损':>9s}")
    rows = []
    for k, nm in enumerate(NAMES):
        for tag, w in (("多空", apply_tradability(rank_weights(X[:, :, k], mask), tradable)),
                       ("仅多头", lo_weights(X[:, :, k], mask, tradable))):
            g = metrics(portfolio_returns(w, r, cm_zero, np.zeros(r.shape[0])))
            c = metrics(portfolio_returns(w, r, cm_imp, extra))
            to = annualized_turnover(w)
            rows.append((nm, tag, to, g["sharpe"], c["sharpe"]))
            print(f"{nm:12s} {tag:7s} {to:9.0f} {g['sharpe']:10.3f} "
                  f"{c['sharpe']:10.3f} {g['sharpe'] - c['sharpe']:9.2f}")

    live = [(f"{a}({b})", t, gs, cs) for a, b, t, gs, cs in rows if cs > 0]
    print(f"\n含冲击后夏普仍为正的构建方式：{len(live)} / {len(rows)}")
    for nm, t, gs, cs in live:
        print(f"  {nm:16s} 年化换手 {t:.0f}，零成本 {gs:.3f} → 含冲击 {cs:.3f}")
    tos = np.array([x[2] for x in rows])
    print(f"\n换手分布：最小 {tos.min():.0f} 倍、中位 {np.median(tos):.0f} 倍、"
          f"最大 {tos.max():.0f} 倍，跨度 {tos.max() / tos.min():.0f} 倍")


if __name__ == "__main__":
    main()