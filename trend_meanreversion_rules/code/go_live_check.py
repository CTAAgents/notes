# -*- coding: utf-8 -*-
"""上线检查单总入口：把第 10 节的六步流程跑成一次并给出总判决。

此前四道闸门分散在 multipletest.py、walkforward.py、rule_wf.py 中，
本脚本把它们串成唯一入口，输出逐项通过/未通过与最终结论。

七步（对应《交易规则》第 10.5 节）：
  1 登记搜索空间（N）
  2 构建网格日收益矩阵
  3 闸门一/二：White Reality Check、Hansen SPA、Romano--Wolf
  4 闸门三：紧缩夏普比率（DSR）
  5 闸门四：回测过拟合概率（PBO / CSCV）
  6 样本外 walk-forward（参数选择是否外推）
  7 可交易性核查（涨跌停/停牌的剔除是否真的接进回测引擎）

用法：
    python go_live_check.py                 # 完整检查（自举 2000 次）
    python go_live_check.py --fast          # 快速检查（自举 300 次）
    python go_live_check.py --with-rule-wf  # 额外跑规则自身参数的 walk-forward（约 5 分钟）
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import common as C
import multipletest as MT
import walkforward as WF

REPORT = C.OUT / "go_live_report.json"

# 步骤 7 的开关：只有当可交易性过滤真的接进回测引擎后才应置为 True。
# 当前网格由论文口径引擎生成，未做该过滤，因此保持 False。
TRADABILITY_APPLIED = False

# 各步骤的判据
CRIT = {
    "reality_check_p": 0.05,
    "hansen_spa_p": 0.05,
    "romano_wolf_alpha": 0.05,
    "dsr": 0.95,
    "pbo": 0.50,
    "wf_decay": 0.50,          # IS→OOS 相对衰减不得超过 50%
    "wf_oos_sharpe": 0.0,      # OOS 均值夏普须为正
    "limit_share": 0.01,       # 涨跌停样本次数占比上限
}


def _line(ch="─", n=96):
    print(ch * n)


def step1_search_space(R: pd.DataFrame) -> dict:
    print("\n【步骤 1】登记搜索空间")
    N = R.shape[1]
    print(f"  试验次数 N = {N}（网格列数）")
    print(f"  样本长度 T = {R.shape[0]} 个交易日")
    print("  说明：N 必须是「全部」试过的参数组合，含失败与废弃的；漏登记会使后续校正失效。")
    print("  退出码约定：0 = 全部通过；1 = 存在未通过项（供 CI 触发阻断）")
    if N < 2:
        print("  ✗ N < 2，无搜索空间可言，后续校正无意义")
        return {"pass": False, "N": N, "T": int(R.shape[0])}
    print("  ✓ 搜索空间已登记")
    return {"pass": True, "N": N, "T": int(R.shape[0])}


def step2_grid(R: pd.DataFrame) -> dict:
    print("\n【步骤 2】网格日收益矩阵")
    nan_share = float(R.isna().to_numpy().mean())
    print(f"  形状 {R.shape[0]} 日 × {R.shape[1]} 组合；缺失占比 {nan_share:.2%}")
    ok = R.shape[1] >= 5 and R.shape[0] >= 500
    print(f"  {'✓' if ok else '✗'} 规模检查({'通过' if ok else '样本或组合数过少'})")
    return {"pass": bool(ok), "shape": list(R.shape), "nan_share": nan_share}


def step3_gates(R, n_boot, block, seed) -> dict:
    print("\n【步骤 3】闸门一/二：自举类检验")
    rc = MT.reality_check(R, n_boot=n_boot, block=block, seed=seed)
    rcs = MT.reality_check(R, n_boot=n_boot, block=block, seed=seed, studentized=True)
    spa = MT.hansen_spa(R, n_boot=n_boot, block=block, seed=seed)
    rw = MT.romano_wolf(R, n_boot=n_boot, block=block, seed=seed,
                        alpha=CRIT["romano_wolf_alpha"])
    print(f"  White RC（非 studentized） p = {rc['p值']:.4f}"
          f"  {'拒绝' if rc['p值'] <= 0.05 else '不拒绝'}"
          f"   ← 跨资产类别时该统计量易被高波动组合支配，参考价值低")
    print(f"  White RC（studentized）    p = {rcs['p值']:.4f}"
          f"  {'拒绝' if rcs['p值'] <= 0.05 else '不拒绝'}")
    print(f"  Hansen SPA                 p = {spa['p值']:.4f}"
          f"  {'拒绝' if spa['p值'] <= 0.05 else '不拒绝'}"
          f"（劣质策略 {spa['n_poor']}/{R.shape[1]}）")
    print(f"  Romano--Wolf（FWER 5%）    拒绝 {rw['n_rejected']}/{R.shape[1]} 个假设")
    for s in rw["steps"][:3]:
        print(f"      第 {s['第几步']} 步 {s['假设']:<28s} t={s['t']:6.2f} "
              f"剩余 {s['剩余假设数']:2d} 逐步 p={s['逐步校正p']:.4f}")
    ok = (rcs["p值"] <= CRIT["reality_check_p"]) or (spa["p值"] <= CRIT["hansen_spa_p"])
    print(f"  {'✓' if ok else '✗'} 判据：studentized RC 或 SPA 至少一个拒绝"
          f"（{'满足' if ok else '均未拒绝，判定为数据窥探产物'}）")
    return {"pass": bool(ok), "reality_check": rc, "reality_check_studentized": rcs,
            "hansen_spa": spa, "romano_wolf": rw}


def step4_dsr(R) -> dict:
    print("\n【步骤 4】闸门三：紧缩夏普比率（DSR）")
    sr = R.mean() / R.std(ddof=1) * np.sqrt(252)
    best = sr.idxmax()
    x = R[best].dropna()
    sr_daily = R.mean() / R.std(ddof=1)
    out = MT.deflated_sharpe(float(sr_daily[best]), len(x), float(x.skew()),
                             float(x.kurtosis()) + 3.0, sr_daily.dropna().to_numpy())
    print(f"  最优组合 {best}：日夏普 {out['SR_hat(日)']:.4f}（年化 {sr[best]:.2f}）")
    print(f"  {R.shape[1]} 次试验下的期望最大日夏普 SR0 = {out['SR0(日,期望最大值)']:.4f}")
    print(f"  DSR = {out['DSR']:.4f}   （判据 ≥ {CRIT['dsr']}）")
    ok = out["DSR"] >= CRIT["dsr"]
    print(f"  {'✓' if ok else '✗'} {'通过' if ok else '未通过：最优夏普不高于搜索带来的期望膨胀'}")
    return {"pass": bool(ok), "best": best, "年化夏普": float(sr[best]), **out}


def step5_pbo(R, n_splits=10) -> dict:
    print("\n【步骤 5】闸门四：回测过拟合概率（PBO / CSCV）")
    out = MT.pbo_cscv(R, n_splits=n_splits)
    print(f"  PBO = {out['PBO']:.4f}（{out['n_combinations']} 种切分；"
          f"OOS 相对排名均值 {out['OOS相对排名均值']:.3f}）")
    ok = out["PBO"] <= CRIT["pbo"]
    print(f"  {'✓' if ok else '✗'} 判据 ≤ {CRIT['pbo']}："
          f"{'通过（样本内最优在样本外不易落到中位数以下）' if ok else '未通过：选择过程不比抛硬币更好'}")
    return {"pass": bool(ok), **out}


def step6_walkforward(R, is_win, oos_win, step, n_splits_check=True) -> dict:
    print("\n【步骤 6】样本外 walk-forward")
    folds = WF.walk_forward(R, is_win, oos_win, step)
    if not folds:
        print("  ✗ 样本长度不足以切分")
        return {"pass": False, "reason": "样本不足"}
    res, f = WF.summarize(folds, list(R.columns), is_win, oos_win)
    print(f"  折数 {res['n_folds']}；IS 夏普均值 {res['IS夏普均值']:.2f} → "
          f"OOS {res['OOS夏普均值']:.2f}（相对衰减 {res['衰减比例']*100:.1f}%）")
    print(f"  OOS 为正的折 {int(res['OOS为正的折占比']*res['n_folds'])}/{res['n_folds']}；"
          f"被选组合的 OOS 平均分位 {res['被选组合的OOS平均分位']:.2f}")
    print(f"  IS→OOS 秩相关 {res['IS_OOS秩相关']:.2f}；"
          f"OOS 中位数参数夏普 {res['逐折OOS_中位数夏普']:.2f}")
    reasons = []
    if res["衰减比例"] > CRIT["wf_decay"]:
        reasons.append(f"相对衰减 {res['衰减比例']*100:.0f}% > {CRIT['wf_decay']*100:.0f}%")
    if res["OOS夏普均值"] <= CRIT["wf_oos_sharpe"]:
        reasons.append(f"OOS 均值夏普 {res['OOS夏普均值']:.2f} 非正")
    ok = not reasons
    print(f"  {'✓' if ok else '✗'} {'通过' if ok else '未通过：' + '；'.join(reasons)}")
    return {"pass": bool(ok), "原因": reasons, **{k: v for k, v in res.items()
                                                  if k != "选中组合分布"}}


def step7_tradability(R) -> dict:
    print("\n【步骤 7】可交易性核查")
    # 证据：收益序列中触及涨跌停的样本次数占比
    lim = pd.Series({c: 0.10 for c in R.columns})     # 未知代码时按主板阈值保守估计
    hits = (R.abs() >= (lim - 0.003))
    share = float(hits.to_numpy().mean())
    print(f"  收益序列中 |r| ≥ 涨跌停阈值的样本占比：{share:.3%}")
    print(f"  回测引擎是否已剔除涨跌停/停牌成交：{'是' if TRADABILITY_APPLIED else '否'}")
    ok = TRADABILITY_APPLIED and share <= CRIT["limit_share"]
    if not TRADABILITY_APPLIED:
        print("  ✗ 未通过：涨跌停与停牌的可交易性过滤尚未接入回测引擎")
        print("      动作：把 C.tradable_mask 接进成交判定（涨跌停当日顺延、停牌不调仓），"
              "并把本文件顶部的 TRADABILITY_APPLIED 置为 True 后重跑")
    elif share > CRIT["limit_share"]:
        print(f"  ✗ 未通过：涨跌停样本占比 {share:.3%} 超过 {CRIT['limit_share']:.1%}")
    else:
        print("  ✓ 通过")
    return {"pass": bool(ok), "limit_share": share,
            "tradability_applied": TRADABILITY_APPLIED}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="自举 300 次（快速检查）")
    ap.add_argument("--n-boot", type=int, default=None)
    ap.add_argument("--block", type=int, default=MT.BLOCK)
    ap.add_argument("--seed", type=int, default=MT.SEED)
    ap.add_argument("--is", dest="is_win", type=int, default=WF.IS_DEF)
    ap.add_argument("--oos", dest="oos_win", type=int, default=WF.OOS_DEF)
    ap.add_argument("--step", type=int, default=WF.STEP_DEF)
    ap.add_argument("--with-rule-wf", action="store_true",
                    help="额外跑规则自身参数的 walk-forward（约 5 分钟）")
    args = ap.parse_args()

    n_boot = args.n_boot or (300 if args.fast else MT.N_BOOT)
    gp = C.OUT / "grid_returns.parquet"
    if not gp.exists():
        raise SystemExit("未找到 grid_returns.parquet，请先运行 run_grid.py")
    R = pd.read_parquet(gp)

    t0 = time.time()
    _line("═")
    print("上线检查单（go-live checklist）")
    print(f"网格 {R.shape[0]} 日 × {R.shape[1]} 组合；自举 {n_boot} 次；"
          f"随机种子 {args.seed}")
    _line("═")

    rep = {}
    rep["配置"] = {"N": int(R.shape[1]), "T": int(R.shape[0]), "n_boot": n_boot,
                   "block": args.block, "seed": args.seed,
                   "IS": args.is_win, "OOS": args.oos_win, "step": args.step,
                   "判据": CRIT}

    rep["步骤1_搜索空间"] = step1_search_space(R)
    rep["步骤2_网格"] = step2_grid(R)
    rep["步骤3_自举检验"] = step3_gates(R, n_boot, args.block, args.seed)
    rep["步骤4_DSR"] = step4_dsr(R)
    rep["步骤5_PBO"] = step5_pbo(R)
    rep["步骤6_样本外"] = step6_walkforward(R, args.is_win, args.oos_win, args.step)
    rep["步骤7_可交易性"] = step7_tradability(R)

    if args.with_rule_wf:
        print("\n【附加】规则自身参数的 walk-forward（分规则）")
        try:
            import rule_wf as RWF
            n1 = RWF.collect_rule1()
            _, s1 = RWF.walk(n1, "规则一")
            n2 = RWF.collect_rule2("sw")
            _, s2 = RWF.walk(n2, "规则二")
            rep["附加_规则WF"] = {"规则一": s1, "规则二": s2}
        except Exception as e:
            print(f"  跳过：{type(e).__name__}: {e}")
            rep["附加_规则WF"] = {"error": str(e)}

    # ---- 总判决 ----
    _line("═")
    print("总判决")
    _line("═")
    fails = []
    for k, v in rep.items():
        if isinstance(v, dict) and "pass" in v:
            label = k.split("_", 1)[-1]
            mark = "✓" if v["pass"] else "✗"
            print(f"  {mark} {label}")
            if not v["pass"]:
                fails.append(label)
    print()
    passed = len(fails) == 0
    if passed:
        print("  结论：七步全部通过，可进入实盘前的执行层对照（Phase 3）")
    else:
        print(f"  结论：{len(fails)} 项未通过，相关规则不得直接上线 ——")
        for f in fails:
            print(f"    · {f}")
    rep["总判决"] = {"通过": passed, "未通过项": fails,
                     "耗时秒": round(time.time() - t0, 1)}
    print(f"\n  耗时 {rep['总判决']['耗时秒']} 秒")

    REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2, default=float),
                      encoding="utf-8")
    print(f"报告已写出 {REPORT}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())