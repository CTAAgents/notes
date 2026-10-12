# -*- coding: utf-8 -*-
"""上线前的样本外 walk-forward 检验。

这是《交易规则》第 10 节所列流程中「步骤 6」的落地实现——该步骤此前只写在流程里，
未实跑。本模块把它补齐。

设计：
  把样本切成滚动折：样本内（IS）窗口 756 日（约 3 年）用于「选出最优组合」，
  紧随其后的样本外（OOS）窗口 252 日（约 1 年）用于「检验该选择的实际表现」，
  每次向前滚动 252 日。IS 与 OOS 严格不重叠。

输出四类量：
  1. 每折选中的组合、IS 夏普、OOS 夏普 —— 看衰减
  2. IS 夏普与 OOS 夏普的关系（回归斜率、秩相关）—— 看样本内排名是否有预测力
  3. OOS 组合夏普 vs 全样本「事后最优」夏普 —— 看选择损失
  4. 与「不做选择、固定用某一组合」的对照 —— 看选择本身是否创造价值

用法：
    python walkforward.py
    python walkforward.py --is 504 --oos 126 --step 126
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from scipy import stats

import common as C

IS_DEF, OOS_DEF, STEP_DEF = 756, 252, 252


def sharpe(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    if len(x) < 20 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


def walk_forward(R: pd.DataFrame, is_win=IS_DEF, oos_win=OOS_DEF, step=STEP_DEF):
    """滚动切分并逐折记录「IS 选优 → OOS 检验」的结果。"""
    T = len(R)
    X = R.fillna(0.0).to_numpy()
    cols = list(R.columns)
    folds = []
    start = 0
    while start + is_win + oos_win <= T:
        is_sl = slice(start, start + is_win)
        oos_sl = slice(start + is_win, start + is_win + oos_win)
        sr_is = np.array([sharpe(X[is_sl, k]) for k in range(X.shape[1])])
        sr_oos = np.array([sharpe(X[oos_sl, k]) for k in range(X.shape[1])])
        if np.all(np.isnan(sr_is)):
            start += step
            continue
        n_star = int(np.nanargmax(sr_is))
        folds.append({
            "is_start": R.index[start], "is_end": R.index[start + is_win - 1],
            "oos_start": R.index[start + is_win], "oos_end": R.index[start + is_win + oos_win - 1],
            "chosen": cols[n_star],
            "sr_is_chosen": float(sr_is[n_star]),
            "sr_oos_chosen": float(sr_oos[n_star]),
            "sr_is_med": float(np.nanmedian(sr_is)),
            "sr_oos_med": float(np.nanmedian(sr_oos)),
            "sr_is_oracle": float(np.nanmax(sr_is)),
            "sr_oos_oracle": float(np.nanmax(sr_oos)),
            "rank_oos_of_chosen": float(
                (np.nansum(sr_oos < sr_oos[n_star]) + 1) / (np.sum(~np.isnan(sr_oos)) + 1)),
            "_sr_is": sr_is, "_sr_oos": sr_oos,
        })
        start += step
    return folds


def summarize(folds, cols, is_win=IS_DEF, oos_win=OOS_DEF) -> dict:
    f = pd.DataFrame([{k: v for k, v in d.items() if not k.startswith("_")} for d in folds])
    if f.empty:
        return {}
    # IS 与 OOS 夏普的横截面关系（逐折池化）
    all_is = np.concatenate([d["_sr_is"] for d in folds])
    all_oos = np.concatenate([d["_sr_oos"] for d in folds])
    m = ~np.isnan(all_is) & ~np.isnan(all_oos)
    slope, intercept, r_val, p_val, se = stats.linregress(all_is[m], all_oos[m])
    rho, rho_p = stats.spearmanr(all_is[m], all_oos[m])
    out = {
        "n_folds": int(len(f)),
        "IS窗口": int(is_win), "OOS窗口": int(oos_win),
        "IS夏普均值": float(f["sr_is_chosen"].mean()),
        "OOS夏普均值": float(f["sr_oos_chosen"].mean()),
        "衰减_IS减OOS": float((f["sr_is_chosen"] - f["sr_oos_chosen"]).mean()),
        "衰减比例": float((f["sr_is_chosen"] - f["sr_oos_chosen"]).mean()
                        / abs(f["sr_is_chosen"].mean())) if f["sr_is_chosen"].mean() != 0 else float("nan"),
        "OOS为正的折占比": float((f["sr_oos_chosen"] > 0).mean()),
        "IS_OOS横截面回归斜率": float(slope),
        "IS_OOS秩相关": float(rho), "秩相关p值": float(rho_p),
        "逐折OOS_中位数夏普": float(f["sr_oos_med"].mean()),
        "逐折OOS事后最优夏普": float(f["sr_oos_oracle"].mean()),
        "被选组合的OOS平均分位": float(f["rank_oos_of_chosen"].mean()),
        "选中组合分布": f["chosen"].value_counts().to_dict(),
    }
    return out, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--is", dest="is_win", type=int, default=IS_DEF)
    ap.add_argument("--oos", dest="oos_win", type=int, default=OOS_DEF)
    ap.add_argument("--step", type=int, default=STEP_DEF)
    args = ap.parse_args()

    gp = C.OUT / "grid_returns.parquet"
    if not gp.exists():
        raise SystemExit("请先运行 run_grid.py 生成网格收益矩阵")
    R = pd.read_parquet(gp)
    print("=" * 96)
    print(f"样本外 walk-forward 检验：{R.shape[1]} 个组合，{R.shape[0]} 个交易日")
    print(f"IS={args.is_win} 日 / OOS={args.oos_win} 日 / 步长={args.step} 日")
    print("=" * 96)

    folds = walk_forward(R, args.is_win, args.oos_win, args.step)
    if not folds:
        raise SystemExit("样本长度不足以切分，请缩小 IS 或 OOS 窗口")
    res, f = summarize(folds, list(R.columns), args.is_win, args.oos_win)

    print(f"\n折数：{res['n_folds']}")
    print("\n逐折明细：")
    print(f"  {'IS 区间':<26s} {'OOS 区间':<26s} {'选中组合':<26s} {'IS夏普':>7s} {'OOS夏普':>8s} {'OOS分位':>7s}")
    for _, r in f.iterrows():
        print(f"  {str(r['is_start'].date())}~{str(r['is_end'].date()):<12s} "
              f"{str(r['oos_start'].date())}~{str(r['oos_end'].date()):<12s} "
              f"{r['chosen']:<26s} {r['sr_is_chosen']:7.2f} {r['sr_oos_chosen']:8.2f} "
              f"{r['rank_oos_of_chosen']:7.2f}")

    print("\n汇总：")
    print(f"  IS 夏普均值 {res['IS夏普均值']:.2f}  →  OOS 夏普均值 {res['OOS夏普均值']:.2f}  "
          f"（衰减 {res['衰减_IS减OOS']:.2f}，相对衰减 {res['衰减比例']*100:.1f}%）")
    print(f"  OOS 为正的折占比 {res['OOS为正的折占比']*100:.1f}%")
    print(f"  被选组合在 OOS 的平均分位 {res['被选组合的OOS平均分位']:.2f}"
          f"（0.5 = 与随机挑选无异）")
    print(f"  IS→OOS 横截面回归斜率 {res['IS_OOS横截面回归斜率']:.2f}；"
          f"秩相关 {res['IS_OOS秩相关']:.2f}（p={res['秩相关p值']:.3f}）")
    print(f"  逐折 OOS 中位数夏普 {res['逐折OOS_中位数夏普']:.2f}；"
          f"OOS 事后最优夏普 {res['逐折OOS事后最优夏普']:.2f}")
    print(f"  选中组合分布：{res['选中组合分布']}")

    print("\n" + "-" * 96)
    verdict = []
    if res["衰减比例"] > 0.5:
        verdict.append(f"IS→OOS 夏普相对衰减 {res['衰减比例']*100:.0f}%，超过 50%："
                       f"样本内表现不能外推")
    if res["被选组合的OOS平均分位"] < 0.6:
        verdict.append(f"被选组合在 OOS 的平均分位仅 {res['被选组合的OOS平均分位']:.2f}，"
                       f"接近随机挑选：样本内排名对样本外缺乏预测力")
    if res["IS_OOS秩相关"] < 0.3:
        verdict.append(f"IS→OOS 秩相关 {res['IS_OOS秩相关']:.2f} 低于 0.3："
                       f"参数选择过程不稳定")
    if res["OOS为正的折占比"] < 0.6:
        verdict.append(f"仅 {res['OOS为正的折占比']*100:.0f}% 的折在样本外为正")
    if not verdict:
        print("结论：walk-forward 检验通过，可进入执行层对照（Phase 3）")
    else:
        print("结论：walk-forward 检验未通过——")
        for v in verdict:
            print(f"  · {v}")
    res["verdict"] = verdict

    (C.OUT / "walkforward_results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    f.to_csv(C.OUT / "walkforward_folds.csv", index=False, encoding="utf-8-sig")
    print(f"\n结果已写出 {C.OUT / 'walkforward_results.json'}")


if __name__ == "__main__":
    main()