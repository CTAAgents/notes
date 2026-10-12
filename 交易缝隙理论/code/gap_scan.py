# -*- coding: utf-8 -*-
"""尺度扫描：持有时长（观测网格）下的净收益曲线——观测缝隙理论之尺度窗口的实证。

对 8 个价量特征 × 两种构建（多空 / 仅多头）× 调仓网格 Δ ∈ {1,2,3,5,10,20}：
  * 信号每日计算，但决策与调仓仅发生在 Δ 的整数倍网格点上（观测装置的时间分辨率）；
  * 持有期内权重冻结，网格之间的新信息不改变仓位（这正是"在尺度 Δ 上观测"的含义）；
  * 成本仅在调仓日按换手收取：逐股 ADV、佣金＋过户费、分段卖出印花税、
    平方根冲击、参与率上限 10%（与综述第 21 章口径一致）。

Δ=1 退化为每日调仓，应与 audit_cost_by_candidate.py 的数字对齐（口径自检：
非流动性多空年化换手 14 倍、零成本 1.221、含冲击 1.014；其余特征因方向取优
可能为 audit 值的符号翻转，绝对值应一致）。

方向取样本内更优者（与 diag_ls_lo.py 同口径，在 Δ=1 上判定后固定），
因此各特征的零成本夏普为正，曲线展示的是成本摊薄与信息衰减在尺度上的交互。

运行：python gap_scan.py
输出：outputs/gap_scan.txt 与 outputs/gap_scan.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "AI金融交易综述", "code"))
sys.path.insert(0, CODE_DIR)

from baseline import apply_tradability, rank_weights  # noqa: E402
from costs import CostModel, ashare_fee_bps, stamp_duty_schedule  # noqa: E402
from diag_ls_lo import NAMES, lo_weights  # noqa: E402
from eval import metrics  # noqa: E402

# 冻结版数据层：截断至 20261008 并读取综述冻结的 400 只清单，
# 与快照 781cadd68dfbd170 严格对齐（本地库在快照后新增了更晚的 bar）
from real_data_frozen import make_snapshot  # noqa: E402

CAPITAL = 1e8
DELTAS = (1, 2, 3, 5, 10, 20)
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "outputs"))


def daily_returns(weights: np.ndarray, r: np.ndarray) -> np.ndarray:
    return np.array([float(np.sum(weights[t] * r[t])) for t in range(weights.shape[0])])


def grid_weights(w_raw: np.ndarray, tradable: np.ndarray, delta: int) -> np.ndarray:
    """网格化：仅每 delta 日调仓，其余日权重冻结；调仓日不可成交者保持旧仓。"""
    T, N = w_raw.shape
    W = np.zeros((T, N))
    last = np.zeros(N)
    for t in range(T):
        if t % delta == 0:
            tgt = w_raw[t].copy()
            if t > 0:                       # t=0 为首期建仓，不做制度过滤（与综述口径一致）
                hold = ~tradable[t]
                tgt[hold] = last[hold]
            W[t] = tgt
            last = tgt
        else:
            W[t] = last
    return W


def scan_one(w_raw: np.ndarray, r: np.ndarray, tradable: np.ndarray,
             cm, extra: np.ndarray, delta: int) -> dict:
    W = grid_weights(w_raw, tradable, delta)
    T, N = r.shape
    out = np.zeros(T)
    prev = np.zeros(N)
    for t in range(T):
        c = 0.0
        if t % delta == 0:
            c = cm.cost(prev, W[t], CAPITAL, extra_fee_sell=float(extra[t]))
            prev = W[t]
        out[t] = float(np.sum(W[t] * r[t])) - c
    turnover = float(np.abs(np.diff(W, axis=0)).sum(axis=1).mean() * 252)
    return {"ret": out, "turnover": turnover}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    snap = make_snapshot()
    X, r, mask, tradable, amt = (snap["X"], snap["r"], snap["mask"],
                                 snap["tradable"], snap["amt"])
    adv = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
    adv = np.where(np.isfinite(adv) & (adv > 0), adv, 1e7)
    fee = ashare_fee_bps()
    extra = stamp_duty_schedule(snap["dates"])
    cm_zero = CostModel(mode="zero")
    cm_imp = CostModel(mode="impact", fee_bps=fee, adv=adv)

    lines = []
    lines.append(f"快照 digest={snap['digest']}  窗口 {snap['window'][0]}–{snap['window'][1]}"
                 f"  T={snap['T']} N={snap['N']}")
    lines.append(f"网格 Δ ∈ {list(DELTAS)}；方向取样本内更优（Δ=1 判定后固定）")
    results = {}
    for k, nm in enumerate(NAMES):
        results[nm] = {}
        for tag in ("多空", "仅多头"):
            if tag == "多空":
                w_pos = apply_tradability(rank_weights(X[:, :, k], mask), tradable)
                w_neg = apply_tradability(rank_weights(-X[:, :, k], mask), tradable)
            else:
                w_pos = lo_weights(X[:, :, k], mask, tradable)
                w_neg = lo_weights(-X[:, :, k], mask, tradable)
            s_pos = metrics(daily_returns(w_pos, r))["sharpe"]
            s_neg = metrics(daily_returns(w_neg, r))["sharpe"]
            w_raw = w_pos if s_pos >= s_neg else w_neg
            direction = "+" if s_pos >= s_neg else "-"
            rows = []
            for d in DELTAS:
                g = scan_one(w_raw, r, tradable, cm_zero, np.zeros(r.shape[0]), d)
                c = scan_one(w_raw, r, tradable, cm_imp, extra, d)
                row = {"delta": d, "turnover": g["turnover"],
                       "sharpe_zero": metrics(g["ret"])["sharpe"],
                       "sharpe_impact": metrics(c["ret"])["sharpe"]}
                rows.append(row)
            results[nm][tag] = {"direction": direction, "rows": rows}
            lines.append(f"\n{nm}（{tag}，方向 {direction}）")
            lines.append(f"  {'Δ(日)':>6s} {'年化换手':>9s} {'零成本夏普':>10s} {'含冲击夏普':>10s}")
            for row in rows:
                lines.append(f"  {row['delta']:6d} {row['turnover']:9.0f} "
                             f"{row['sharpe_zero']:10.3f} {row['sharpe_impact']:10.3f}")

    meta = {"digest": snap["digest"], "window": [int(snap["window"][0]), int(snap["window"][1])],
            "T": int(snap["T"]), "N": int(snap["N"]), "deltas": list(DELTAS),
            "capital": CAPITAL}
    with open(os.path.join(OUT_DIR, "gap_scan.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, ensure_ascii=False, indent=1)
    text = "\n".join(lines)
    with open(os.path.join(OUT_DIR, "gap_scan.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()