# -*- coding: utf-8 -*-
"""打印 L × ENTRY_K 扫描表（含被截断的组合）。"""
import json

d = json.load(open(r"d:\Finance\趋势跟踪与均值回归交易规则\outputs\param_recommend.json",
                   encoding="utf-8"))
A = d["A_rule1_L_entry"]
byL = {}
for r in A:
    byL.setdefault(r["L"], {})[r["ENTRY_K"]] = r

print("规则一 L × ENTRY_K —— 格式：夏普 | 年化% | 成本占毛利% | 门槛")
print("  L  |        K=0.0        |        K=0.5        |        K=1.0        |        K=1.5")
for L in sorted(byL):
    cells = []
    for k in (0.0, 0.5, 1.0, 1.5):
        r = byL[L].get(k)
        if r is None:
            cells.append(" " * 20)
        else:
            cells.append(f"{r['夏普']:5.2f}|{r['年化']*100:6.2f}|{r['成本占毛利']*100:7.2f}|{r['门槛']}")
    print(f"{L:>4} | " + " | ".join(cells))

print()
print("规则二 L 扫描 —— 多头 / 对冲后")
for r in d["C_rule2_L"]:
    print(f"  L={r['L']:>3}  多头夏普 {r['夏普']:6.2f}  年化 {r['年化']*100:6.2f}%  "
          f"回撤 {r['最大回撤']*100:7.2f}%  换手 {r['换手']:6.2f}  "
          f"成本/毛利 {r['成本占毛利']*100:7.2f}%  对冲后 {r['对冲后夏普']:6.2f}  {r['门槛']}")

print()
print("规则一 ATR 敏感性")
for r in d.get("B_rule1_atr", []):
    print(f"  {r['标签']:<14s} 夏普 {r['夏普']:5.2f}  年化 {r['年化']*100:6.2f}%  "
          f"回撤 {r['最大回撤']*100:7.2f}%  止损 {r['止损次数']:4d} 次")