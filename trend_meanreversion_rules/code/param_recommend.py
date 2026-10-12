# -*- coding: utf-8 -*-
"""依据四项验证结论，对规则一与规则二做参数重标定。

三项扫描：
  A. 规则一：窗口 L × 入场门槛 ENTRY_K 二维扫描
     —— 验证 3 显示工程增强改变了窗口排序，而入场门槛是 L=250 失效的主因之一，
        因此必须与 L 联合扫描，不能单独定 L。
  B. 规则一：ATR 止损倍数敏感性（L=10/20 两档）
     —— 止损是另一处"工程判断"，需要确认推荐档位对它的依赖程度。
  C. 规则二：窗口 L 扫描（真实申万一级口径）
     —— 此前只有 L=60 一个点，无法给出参数推荐。

输出 outputs/param_recommend.json，并打印推荐表。

用法：
    python param_recommend.py            # 全部扫描
    python param_recommend.py --quick    # 只跑 A 与 C
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd

import common as C
import rule1_trend as R1
import rule2_ashare as R2

L_GRID = [5, 10, 20, 60, 120, 250]


def _row(tag, m, extra=None):
    d = {"标签": tag, "夏普": m.get("Sharpe", float("nan")),
         "年化": m.get("年化收益", float("nan")),
         "最大回撤": m.get("最大回撤", float("nan")),
         "换手": m.get("年化换手", float("nan")),
         "成本占毛利": m.get("成本占毛利比", float("nan")),
         "NW_t": m.get("NW_t统计量", float("nan")),
         "门槛": "通过" if m.get("_gate_ok", True) else "不通过"}
    if extra:
        d.update(extra)
    return d


def sweep_rule1_L_entry(quick=False):
    print("\n" + "=" * 100)
    print("扫描 A：规则一 —— 窗口 L × 入场门槛 ENTRY_K")
    print("=" * 100)
    ks = [0.0, 1.0] if quick else [0.0, 0.5, 1.0, 1.5]
    rows = []
    for L in L_GRID:
        for k in ks:
            t0 = time.time()
            res = R1.run(L, verbose=False, ENTRY_K=k)
            m = res["metrics"]
            rows.append(_row(f"L={L}, K={k}", m,
                             {"L": L, "ENTRY_K": k,
                              "持仓数": m.get("_n_positions_mean", float("nan")),
                              "止损次数": m.get("_n_stop_events", 0)}))
            print(f"  L={L:3d} K={k:4.1f}  夏普 {rows[-1]['夏普']:6.2f}  "
                  f"年化 {rows[-1]['年化']*100:7.2f}%  回撤 {rows[-1]['最大回撤']*100:7.2f}%  "
                  f"换手 {rows[-1]['换手']:6.2f}  成本/毛利 {rows[-1]['成本占毛利']*100:7.2f}%  "
                  f"{rows[-1]['门槛']}  [{time.time()-t0:.0f}s]")
    return pd.DataFrame(rows)


def sweep_rule1_atr():
    print("\n" + "=" * 100)
    print("扫描 B：规则一 —— ATR 止损倍数（L=10 与 L=20）")
    print("=" * 100)
    rows = []
    for L in (10, 20):
        for a in (1.5, 2.5, 4.0, 99.0):      # 99 等价于关闭止损
            res = R1.run(L, verbose=False, ATR_STOP=a)
            m = res["metrics"]
            tag = "关闭" if a > 10 else f"{a}"
            rows.append(_row(f"L={L}, ATR={tag}", m,
                             {"L": L, "ATR_STOP": a,
                              "止损次数": m.get("_n_stop_events", 0)}))
            print(f"  L={L:3d} ATR倍={tag:>4s}  夏普 {rows[-1]['夏普']:6.2f}  "
                  f"年化 {rows[-1]['年化']*100:7.2f}%  回撤 {rows[-1]['最大回撤']*100:7.2f}%  "
                  f"止损 {rows[-1]['止损次数']:4d} 次  {rows[-1]['门槛']}")
    return pd.DataFrame(rows)


def sweep_rule2_L(mode="sw"):
    print("\n" + "=" * 100)
    print(f"扫描 C：规则二 —— 窗口 L（行业中性化口径 = {mode}）")
    print("=" * 100)
    rows = []
    for L in (20, 60, 120, 250):
        t0 = time.time()
        res = R2.run(L, mode=mode, verbose=False)
        m = res["long"]
        h = res["hedged"]
        rows.append(_row(f"L={L}", m, {"L": L, "口径": mode,
                                       "对冲后夏普": h.get("Sharpe", float("nan")),
                                       "对冲后年化": h.get("年化收益", float("nan")),
                                       "止损次数": m.get("_n_stop_events", 0)}))
        print(f"  L={L:3d}  多头夏普 {rows[-1]['夏普']:6.2f}  "
              f"年化 {rows[-1]['年化']*100:7.2f}%  回撤 {rows[-1]['最大回撤']*100:7.2f}%  "
              f"换手 {rows[-1]['换手']:6.2f}  成本/毛利 {rows[-1]['成本占毛利']*100:7.2f}%  "
              f"| 对冲后 {(h.get('Sharpe', float('nan'))):5.2f}  {rows[-1]['门槛']}  "
              f"[{time.time()-t0:.0f}s]")
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    out = {}
    dfA = sweep_rule1_L_entry(args.quick)
    out["A_rule1_L_entry"] = dfA.to_dict("records")
    if not args.quick:
        dfB = sweep_rule1_atr()
        out["B_rule1_atr"] = dfB.to_dict("records")
    dfC = sweep_rule2_L("sw")
    out["C_rule2_L"] = dfC.to_dict("records")

    # ---- 推荐 ----
    print("\n" + "=" * 100)
    print("推荐（仅取成本门槛通过者，按夏普排序）")
    print("=" * 100)
    okA = dfA[dfA["门槛"] == "通过"].sort_values("夏普", ascending=False)
    print("\n规则一（L, ENTRY_K）：")
    if len(okA):
        print(f"  最优 {okA.iloc[0]['标签']}：夏普 {okA.iloc[0]['夏普']:.2f}、"
              f"年化 {okA.iloc[0]['年化']*100:.2f}%、回撤 {okA.iloc[0]['最大回撤']*100:.2f}%")
        print("  通过门槛的全部组合（前 8）：")
        for _, r in okA.head(8).iterrows():
            print(f"    {r['标签']:<16s} 夏普 {r['夏普']:6.2f} 年化 {r['年化']*100:7.2f}% "
                  f"成本/毛利 {r['成本占毛利']*100:7.2f}%")
    else:
        print("  无组合通过成本门槛")

    okC = dfC[dfC["门槛"] == "通过"].sort_values("夏普", ascending=False)
    print("\n规则二（L）：")
    if len(okC):
        print(f"  最优 {okC.iloc[0]['标签']}：多头夏普 {okC.iloc[0]['夏普']:.2f}、"
              f"年化 {okC.iloc[0]['年化']*100:.2f}%、成本/毛利 "
              f"{okC.iloc[0]['成本占毛利']*100:.2f}%")
    else:
        print("  无组合通过成本门槛")

    (C.OUT / "param_recommend.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n结果已写出 {C.OUT / 'param_recommend.json'}")


if __name__ == "__main__":
    main()