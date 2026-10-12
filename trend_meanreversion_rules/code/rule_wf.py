# -*- coding: utf-8 -*-
"""规则自身的样本外 walk-forward 参数选择检验。

与 walkforward.py 的区别：那里检验的是「60 个论文口径组合」的选择，
这里检验的是\emph{规则自身参数}（规则一的 L、规则二的 L）的选择——
后者才是参数推荐的直接依据。

做法（无需额外回测）：对每个候选参数跑一次全样本回测，拿到逐日净收益序列；
再按滚动折在序列上切片：用样本内窗口的夏普选出参数，报告该参数在
紧随其后的样本外窗口的夏普。

口径说明：净收益序列来自全样本连续运行（含回撤暂停、止损等路径依赖状态），
因此样本外夏普读作「若持续运行该参数的策略，在该窗口的实际表现」，
这正是实盘场景的口径。

用法：
    python rule_wf.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import common as C
import rule1_trend as R1
import rule2_ashare as R2

IS_WIN, OOS_WIN, STEP = 756, 252, 252
L1 = [5, 10, 20, 60, 120, 250]
L2 = [20, 60, 120, 250]


def sharpe(x) -> float:
    x = np.asarray(x, dtype="f8")
    x = x[~np.isnan(x)]
    if len(x) < 20 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


def collect_rule1():
    print("规则一：为每个窗口跑一次全样本回测 ...")
    nets = {}
    for L in L1:
        res = R1.run(L, verbose=False)
        nets[L] = res["net"]
        print(f"  L={L:3d} 全样本夏普 {sharpe(res['net'].to_numpy()):6.2f}")
    return nets


def collect_rule2(mode="sw"):
    print(f"规则二：为每个窗口跑一次全样本回测（口径 {mode}）...")
    nets = {}
    for L in L2:
        res = R2.run(L, mode=mode, verbose=False)
        nets[L] = res["net"]                      # run() 返回的 net 为逐日净收益 Series
        print(f"  L={L:3d} 全样本多头夏普 {sharpe(res['net'].to_numpy()):6.2f}")
    return nets


def walk(nets: dict, label: str):
    idx = None
    for s in nets.values():
        idx = s.index
        break
    T = len(idx)
    folds, start = [], 0
    while start + IS_WIN + OOS_WIN <= T:
        is_i = slice(start, start + IS_WIN)
        oos_i = slice(start + IS_WIN, start + IS_WIN + OOS_WIN)
        sr_is = {L: sharpe(s.iloc[is_i].to_numpy()) for L, s in nets.items()}
        sr_oos = {L: sharpe(s.iloc[oos_i].to_numpy()) for L, s in nets.items()}
        best = max(sr_is, key=lambda k: (sr_is[k] if np.isfinite(sr_is[k]) else -9e9))
        folds.append({"is_start": idx[start].date(), "is_end": idx[start + IS_WIN - 1].date(),
                      "oos_start": idx[start + IS_WIN].date(),
                      "oos_end": idx[start + IS_WIN + OOS_WIN - 1].date(),
                      "selected": best, "sr_is": sr_is[best], "sr_oos": sr_oos[best],
                      "sr_oos_med": float(np.nanmedian(list(sr_oos.values()))),
                      "sr_is_all": sr_is, "sr_oos_all": sr_oos})
        start += STEP

    print(f"\n{label} 样本外 walk-forward（IS={IS_WIN} / OOS={OOS_WIN} / 步长={STEP}）")
    print(f"  {'IS 区间':<24s} {'OOS 区间':<24s} {'选中':>6s} {'IS夏普':>7s} {'OOS夏普':>8s} {'OOS中位':>8s}")
    for f in folds:
        print(f"  {str(f['is_start'])}~{str(f['is_end'])}  {str(f['oos_start'])}~{str(f['oos_end'])}  "
              f"{f['selected']:>6} {f['sr_is']:7.2f} {f['sr_oos']:8.2f} {f['sr_oos_med']:8.2f}")
    df = pd.DataFrame([{k: v for k, v in f.items()
                        if k not in ("sr_is_all", "sr_oos_all")} for f in folds])
    is_m = float(df["sr_is"].mean()); oos_m = float(df["sr_oos"].mean())
    med_m = float(df["sr_oos_med"].mean())
    print(f"  汇总：IS 夏普均值 {is_m:.2f} → OOS {oos_m:.2f}"
          f"（衰减 {is_m-oos_m:.2f}，相对 {(is_m-oos_m)/abs(is_m)*100 if is_m else float('nan'):.1f}%）")
    print(f"        OOS 为正的折 {int((df['sr_oos']>0).sum())}/{len(df)}；"
          f"OOS 中位数参数夏普均值 {med_m:.2f}；选择增益 {oos_m-med_m:+.2f}")
    print(f"        窗口选择分布：{df['selected'].value_counts().to_dict()}")
    return df, {"IS均值": is_m, "OOS均值": oos_m, "衰减": is_m - oos_m,
                "相对衰减": (is_m - oos_m) / abs(is_m) if is_m else float("nan"),
                "OOS为正折数": int((df["sr_oos"] > 0).sum()), "折数": len(df),
                "OOS中位数参数均值": med_m, "选择增益": oos_m - med_m,
                "窗口选择分布": {str(k): int(v) for k, v in df["selected"].value_counts().items()}}


def main():
    out = {}
    n1 = collect_rule1()
    df1, s1 = walk(n1, "规则一（期货时序趋势）")
    out["rule1"] = s1
    df1.to_csv(C.OUT / "rule_wf_rule1.csv", index=False, encoding="utf-8-sig")

    n2 = collect_rule2("sw")
    df2, s2 = walk(n2, "规则二（A股截面反转，纯多头）")
    out["rule2"] = s2
    df2.to_csv(C.OUT / "rule_wf_rule2.csv", index=False, encoding="utf-8-sig")

    (C.OUT / "rule_wf_results.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n结果已写出 {C.OUT / 'rule_wf_results.json'}")


if __name__ == "__main__":
    main()