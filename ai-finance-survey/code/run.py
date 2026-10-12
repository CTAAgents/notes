# -*- coding: utf-8 -*-
"""P0--P2 端到端参考实现：数据快照 -> 候选池 -> 交易制度过滤 -> 成本 -> 评测 -> 试验账本。

本版按同行评审意见修订：
  M5  补信号类指标 IC / IR
  M6  样本外改用滚动前向（walk-forward），并保留单次切分作对照
  M7  DSR 同时给出标准误口径与截面离散度口径，并对 PBO 做切分敏感性分析
  M8  纳入涨跌停 / 停牌 / 退市的不可成交过滤
  M10 试验账本覆盖超参数搜索（随机组合数、岭参数网格）

运行：python run.py            合成面板（默认）
      python run.py --real     本地通达信 vipdoc 真实日线最小实证
说明：合成面板仅用于验证评测流程，不代表任何真实市场结论；--real 的真实数据
      口径与边界（不复权、幸存者偏差等）见 real_data.py 与论文第 21 章。
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

from baseline import LAMBDA_GRID, apply_tradability, build_candidates, rank_weights
from costs import (COMMISSION_BPS, STAMP_BPS_HIGH, STAMP_BPS_LOW, TRANSFER_BPS,
                   CostModel, ashare_fee_bps, stamp_duty_schedule)
from data import make_snapshot
from eval import (deflated_sharpe, deflated_sharpe_se, ic_series, metrics,
                  pbo_cscv, pbo_sensitivity, walk_forward)

CAPITAL = 1e8
N_RANDOM = 50
TRAIN_LEN = 600
TEST_LEN = 120


def portfolio_returns(weights, r, cost_model: CostModel, extra_sell=None):
    """extra_sell 为逐期卖出附加费率（如印花税）；None 表示不加。"""
    T, N = r.shape
    out = np.zeros(T)
    prev = np.zeros(N)
    for t in range(T):
        ex = 0.0 if extra_sell is None else float(extra_sell[t])
        gross = float(np.sum(weights[t] * r[t]))
        out[t] = gross - cost_model.cost(prev, weights[t], CAPITAL, extra_fee_sell=ex)
        prev = weights[t]
    return out


def turnover_stats(weights) -> dict:
    """换手统计：日均合计换手 sum|Δw| 与年化倍数。"""
    d = np.abs(np.diff(weights, axis=0)).sum(axis=1)
    return {"daily_mean": float(d.mean()), "annualized": float(d.mean() * 252)}


def make_cost_models(snap, source: str):
    """构造三档成本模型与卖出附加费序列。

    真实数据用逐股 ADV（窗口内日成交额中位数）与 A 股费率构成；
    合成面板没有成交额字段，沿用常数 ADV 与单一费率。
    """
    if source == "real" and snap.get("amt") is not None:
        amt, tradable = snap["amt"], snap["tradable"]
        adv = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
        adv = np.where(np.isfinite(adv) & (adv > 0), adv, 1e7)
        fee = ashare_fee_bps()
        extra = stamp_duty_schedule(snap["dates"])
        note = (f"逐股 ADV（中位 {np.median(adv):.3e} 元）；费率 {fee}bp 双边"
                f"（佣金 {COMMISSION_BPS} + 过户费 {TRANSFER_BPS}）"
                f"＋卖出印花税分段 {STAMP_BPS_HIGH}/{STAMP_BPS_LOW}bp")
    else:
        adv = 1e9
        fee = 5.0
        extra = None
        note = f"常数 ADV=1e9 元；单一费率 {fee}bp 双边（合成面板无成交额字段）"
    models = {m: CostModel(mode=m, fee_bps=fee, adv=adv) for m in ("zero", "fixed", "impact")}
    return models, extra, note, adv


def main(source: str = "synth"):
    if source == "real":
        from real_data import make_snapshot as real_snapshot
        snap = real_snapshot()
        train_len, test_len = 500, 120
        true_sigs = set()
        out_path = "trial_ledger_real.json"
        print(f"数据源：{snap['source']}（窗口 {snap['window'][0]}–{snap['window'][1]}）")
        for k, v in snap.get("stats", {}).items():
            print(f"  {k} = {v}")
    else:
        snap = make_snapshot()
        train_len, test_len = TRAIN_LEN, TEST_LEN
        true_sigs = {"feat0", "feat2", "feat5"}
        out_path = "trial_ledger.json"
    X, r, mask, tradable = snap["X"], snap["r"], snap["mask"], snap["tradable"]
    T, N, K = X.shape
    print(f"数据快照 digest={snap['digest']}  T={T} N={N} K={K}")
    print(f"不可成交单元占比={1 - tradable.mean():.4f}"
          f"（含封板 / 停牌 / 上市前与历史不足）")
    cost_models, extra_sell, cost_note, adv_used = make_cost_models(snap, source)
    print(f"成本口径：{cost_note}")

    cands = build_candidates(snap, n_random=N_RANDOM)
    # 试验账本：候选池大小 = 单特征 K + 随机组合 n_random + 岭参数网格 |grid|
    n_trials = len(cands)
    print(f"\n试验账本：候选数 N={n_trials} "
          f"（单特征 {K} + 随机组合 {N_RANDOM} + 岭参数网格 {len(LAMBDA_GRID)}）")

    # 权重（含可交易性过滤）与零成本收益
    perf, ics = {}, {}
    for name, sig in cands.items():
        w = apply_tradability(rank_weights(sig, mask), tradable)
        perf[name] = portfolio_returns(w, r, CostModel(mode="zero"))
        ics[name] = ic_series(sig, r, mask)
    mat = np.column_stack([perf[n] for n in cands])

    # 轮动前向：样本外为各折测试段的拼接
    folds = list(walk_forward(T, train_len, test_len))
    def assemble(series):
        return np.concatenate([series[te] for _tr, te in folds])
    oos_wf = {n: assemble(perf[n]) for n in cands}
    cut = int(T * 0.75)
    oos_single = {n: perf[n][cut:] for n in cands}

    # 研究者按“样本内（前 train_len 期）夏普”挑策略
    is_sharpe = {n: metrics(perf[n][:train_len])["sharpe"] for n in cands}
    order = sorted(cands, key=lambda n: -is_sharpe[n])
    best = order[0]
    best_oos = metrics(oos_wf[best])["sharpe"]
    beat = [n for n in cands
            if n not in true_sigs and metrics(oos_wf[n])["sharpe"] > best_oos]

    print("\n按样本内夏普排序前 5（零成本）：")
    for n in order[:5]:
        print(f"  {n:14s} is={is_sharpe[n]:.3f} "
              f"wf_oos={metrics(oos_wf[n])['sharpe']:.3f} "
              f"single_oos={metrics(oos_single[n])['sharpe']:.3f}")
    tag = "真实信号" if best in true_sigs else ("纯噪声" if true_sigs else "按样本内夏普选出")
    print(f"\n样本内最优：{best}（{tag}）")
    print(f"  滚动前向 OOS 夏普={best_oos:.3f}；"
          f"样本外夏普高于它的候选数={len(beat)}")

    # 信号类指标（IC / IR）
    b = ics[best]
    print(f"\n信号类指标（{best}）：IC均值={b['ic_mean']:.4f} "
          f"IC标准差={b['ic_std']:.4f} IR={b['ic_ir']:.3f} "
          f"IC>0占比={b['ic_positive_ratio']:.3f}（n={b['ic_n']}）")

    # 成本三档（含换手率与成本占比，按协议第 16 章强制项）
    w_best = apply_tradability(rank_weights(cands[best], mask), tradable)
    turn = turnover_stats(w_best)
    zero_ret = portfolio_returns(w_best, r, cost_models["zero"])
    zero_ann = metrics(zero_ret)["ann_return"]
    cost_rows = []
    print("\n成本三档（该候选，全样本）：")
    for mode in ("zero", "fixed", "impact"):
        cm = cost_models[mode]
        s = portfolio_returns(w_best, r, cm, extra_sell=extra_sell)
        m = metrics(s)
        drag = float((zero_ret - s).mean() * 252)
        share = drag / zero_ann if zero_ann else float("nan")
        cost_rows.append({"mode": mode, "ann_return": m["ann_return"],
                          "sharpe": m["sharpe"], "max_drawdown": m["max_drawdown"],
                          "cost_drag_ann": drag, "cost_share_of_gross": share,
                          "violations": cm.violations})
        print(f"  {mode:7s} ann={m['ann_return']:.3f} sharpe={m['sharpe']:.3f} "
              f"mdd={m['max_drawdown']:.3f} 年化成本={drag:.3f} "
              f"占毛收益={share:.2f} 参与率超限={cm.violations}")
    print(f"  换手：日均合计 {turn['daily_mean']:.3f}，年化约 {turn['annualized']:.0f} 倍")

    # 多重检验：DSR 两种口径
    oos_m = metrics(oos_wf[best])
    sr_n = oos_m["sharpe"] / np.sqrt(252)
    srs = np.array([metrics(oos_wf[n])["sharpe"] for n in cands]) / np.sqrt(252)
    var_disp = float(np.var(srs, ddof=1))
    dsr_disp = deflated_sharpe(sr_n, oos_m["n"], n_trials, var_disp,
                               oos_m["skew"], oos_m["kurt"])
    dsr_se = deflated_sharpe_se(sr_n, oos_m["n"], n_trials,
                                oos_m["skew"], oos_m["kurt"])
    print(f"\n缩水夏普 DSR（N={n_trials}）：")
    print(f"  标准误口径  sr0={dsr_se['sr0_expected_max']:.4f} DSR={dsr_se['dsr']:.4f}")
    print(f"  截面离散口径 sr0={dsr_disp['sr0_expected_max']:.4f} DSR={dsr_disp['dsr']:.4f}")

    # 回测过拟合概率：PBO 及其切分敏感性
    pbo = pbo_cscv(mat, n_splits=12)
    sens = pbo_sensitivity(mat, splits=(8, 12, 16, 20))
    print(f"回测过拟合概率 PBO={pbo['pbo']:.3f}（组合数 {pbo['n_combos']}）")
    print(f"  切分敏感性：{sens['by_splits']} → 区间 [{sens['min']:.3f}, {sens['max']:.3f}]")

    ledger = {
        "source": source,
        "snapshot_digest": snap["digest"],
        "window": list(snap.get("window", [])),
        "data_stats": snap.get("stats", {}),
        "search_space": {
            "n_feature_signals": K,
            "n_random_combinations": N_RANDOM,
            "ridge_lambda_grid": list(LAMBDA_GRID),
            "total_trials_N": n_trials,
        },
        "splits": {"walk_forward": {"train": train_len, "test": test_len,
                                    "n_folds": len(folds)},
                   "single_split_cut": cut},
        "selected": best,
        "selected_is_true_signal": (best in true_sigs) if true_sigs else None,
        "oos_sharpe_walkforward": best_oos,
        "oos_sharpe_single_split": metrics(oos_single[best])["sharpe"],
        "n_candidates_beating_selected_oos": len(beat),
        "ic_ir": ics[best],
        "cost_caliber": cost_note,
        "cost_tiers": cost_rows,
        "turnover": turn,
        "dsr_standard_error": dsr_se,
        "dsr_dispersion": dsr_disp,
        "dsr_preferred": "standard_error",
        "dsr_preferred_reason": (
            "候选池为同 8 个特征的线性组合、彼此高度相关，其样本外夏普的截面离散度"
            "主要反映策略质量差异而非估计误差，用作 V(SR_hat) 会高估；"
            "标准误口径的 V(SR_hat) 取自单个夏普估计的解析方差，更贴合原式含义。"
            "残留余地：E[max_N] 项假设试验独立，候选相关会使该项偏大，故标准误口径略偏保守。"
        ),
        "pbo": pbo["pbo"],
        "pbo_sensitivity": sens,
        "tradability_untradeable_ratio": float(1 - tradable.mean()),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n试验账本已写入 {out_path}")

    # 冻结 universe，使实证可被他人复算（评审意见 R4）
    if source == "real" and snap.get("codes"):
        adv_ser = (adv_used if np.ndim(adv_used) else np.full(len(snap["codes"]), adv_used))
        uni = {
            "snapshot_digest": snap["digest"],
            "window": list(snap.get("window", [])),
            "note": "本清单为第 21 章真实数据实证的固定样本；抽样框依赖本地 vipdoc 清单，"
                    "故随快照冻结，供他人复算时对齐。",
            "n": len(snap["codes"]),
            "codes": list(snap["codes"]),
            "adv_median_amount_cny": [float(x) for x in adv_ser],
        }
        uni_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "real_universe.json"))
        with open(uni_path, "w", encoding="utf-8") as f:
            json.dump(uni, f, ensure_ascii=False, indent=2)
        print(f"universe 清单已冻结：{uni_path}（{uni['n']} 只）")


if __name__ == "__main__":
    main("real" if "--real" in sys.argv else "synth")
