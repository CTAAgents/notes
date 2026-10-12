# -*- coding: utf-8 -*-
"""参照系分解链：候选的 α 在参照工具扩张下的路径（第 5 章分解公式的演示）。

链：无参照 → 等权全市场 → 加非流动性多空工具 → 加 1 日反转多空工具。
对每个代表候选（仅多头，可实施口径；方向取样本内更优），报告每一步嵌套回归
的截距 α（年化）与各暴露 β；同时对每件新工具报告它相对已有参照的截距
（α_ℱ(g)），验证分解公式 α_ℱ′ = α_ℱ − γ·α_ℱ(g) 的两个乘数都能看见。

口径：全样本、冻结快照（781cadd68dfbd170）；收益为零成本毛收益（分解针对
毛收益，对冲与交易成本另计）。参照工具按理论口径为零成本多空组合；做空侧
在 A 股受限，详见正文边界讨论。

运行：python ref_decomp.py
输出：outputs/ref_decomp.txt 与 outputs/ref_decomp.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "AI金融交易综述", "code"))
sys.path.insert(0, CODE_DIR)

from baseline import apply_tradability, build_candidates, rank_weights  # noqa: E402
from diag_ls_lo import NAMES, _ret, lo_weights  # noqa: E402
from eval import metrics  # noqa: E402

# 冻结版数据层：与快照 781cadd68dfbd170 严格对齐
from real_data_frozen import make_snapshot  # noqa: E402

OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "outputs"))


def market_benchmark(r, mask):
    out = np.zeros(r.shape[0])
    for t in range(r.shape[0]):
        m = mask[t]
        out[t] = float(r[t][m].mean()) if m.sum() else 0.0
    return out


def nested_alpha(y, xs, names):
    """嵌套 OLS：逐步加入回归元，报告每一步的截距（年化）与暴露。"""
    Xd = np.ones((len(y), 1))
    rows = []
    for nm, x in zip(names, xs):
        Xd = np.hstack([Xd, np.asarray(x)[:, None]])
        coef, *_ = np.linalg.lstsq(Xd, y, rcond=None)
        rows.append({"step": nm, "alpha_ann": float(coef[0] * 252),
                     "betas": [float(b) for b in coef[1:]]})
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    snap = make_snapshot()
    X, r, mask, tradable = snap["X"], snap["r"], snap["mask"], snap["tradable"]
    cands = build_candidates(snap, n_random=50)

    def lo(sig):
        return _ret(lo_weights(sig, mask, tradable), r)

    def ls(sig):
        return _ret(apply_tradability(rank_weights(sig, mask), tradable), r)

    k = {nm: i for i, nm in enumerate(NAMES)}
    mkt = market_benchmark(r, mask)
    g_illiq = ls(X[:, :, k["非流动性"]])
    g_rev1 = ls(X[:, :, k["1日反转"]])
    tools = [("等权全市场", mkt), ("非流动性工具", g_illiq), ("1日反转工具", g_rev1)]
    tool_names = [t[0] for t in tools]

    def best_dir(sig):
        """方向取样本内更优者（与 gap_scan 同口径）。"""
        a, b = lo(sig), lo(-sig)
        if metrics(a)["sharpe"] >= metrics(b)["sharpe"]:
            return a, "+"
        return b, "-"

    targets = {
        "非流动性(仅多头)": best_dir(X[:, :, k["非流动性"]]),
        "量比(仅多头)": best_dir(X[:, :, k["量比"]]),
        "1日反转(仅多头)": best_dir(X[:, :, k["1日反转"]]),
        "rand10(仅多头)": best_dir(cands["rand10"]),
    }

    lines = [f"快照 digest={snap['digest']}  T={snap['T']} N={snap['N']}"]
    out = {"meta": {"digest": snap["digest"], "T": int(snap["T"]), "N": int(snap["N"])},
           "tools_alpha": {}, "targets": {}}

    # 每件新工具相对已有参照的截距 α_ℱ(g)：验证分解公式的第二个乘数
    lines.append("\n—— 工具自身的截距路径（对现金 / 对已有参照）——")
    for j in range(3):
        xs = [t[1] for t in tools[:j]]
        nm_list = tool_names[:j]
        y = tools[j][1]
        rows = nested_alpha(y, xs, nm_list)
        base = float(y.mean() * 252)
        lines.append(f"{tool_names[j]}：对现金 α={base:+.3f}"
                     + "".join(f"，{row['step']}后 α={row['alpha_ann']:+.3f}" for row in rows))
        out["tools_alpha"][tool_names[j]] = {"to_cash": base,
                                             "chain": rows}

    # 候选的 α 路径
    lines.append("\n—— 候选的 α 路径（年化，零成本毛收益；方向取样本内更优）——")
    header = f"{'候选':22s} {'向':>2s} {'对现金':>8s} {'+等权':>8s} {'+非流动性':>9s} {'+1日反转':>10s}"
    lines.append(header)
    xs_all = [t[1] for t in tools]
    for nm, (y, dr) in targets.items():
        rows = nested_alpha(y, xs_all, tool_names)
        a0 = float(y.mean() * 252)
        lines.append(f"{nm:22s} {dr:>2s} {a0:8.3f} {rows[0]['alpha_ann']:8.3f} "
                     f"{rows[1]['alpha_ann']:9.3f} {rows[2]['alpha_ann']:10.3f}")
        out["targets"][nm] = {"to_cash": a0, "dir": dr, "chain": rows,
                              "sharpe": metrics(y)["sharpe"]}

    text = "\n".join(lines)
    with open(os.path.join(OUT_DIR, "ref_decomp.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT_DIR, "ref_decomp.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()