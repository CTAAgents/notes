# -*- coding: utf-8 -*-
"""把回测 JSON 打印成 Markdown 表格，便于抄入 LaTeX。"""
import json
from pathlib import Path

p = Path(r"d:\Finance\趋势跟踪与均值回归对比综述\outputs\backtest_results.json")
d = json.loads(p.read_text(encoding="utf-8"))
r = d["results"]
print("CONFIG:", json.dumps(d["config"], ensure_ascii=False))

KEYS = ["Sharpe", "毛利Sharpe", "年化收益", "年化波动", "最大回撤", "Calmar",
        "偏度", "超额峰度", "年化换手", "月胜率", "NW_t统计量", "成本拖累年化", "成本占毛利比"]


def fmt(m):
    return " | ".join(
        f"{m[k]*100:.2f}" if k in ("年化收益", "年化波动", "最大回撤", "成本拖累年化", "月胜率", "成本占毛利比")
        else f"{m[k]:.2f}" for k in KEYS)


print("\n| 口径 | 方向 | L | " + " | ".join(KEYS) + " |")
print("|" + "---|" * (3 + len(KEYS)))
for tag in ["fut_TS", "fut_XS", "ashare_idx_TS", "ashare_stk_XS"]:
    for kind in ["trend", "reversion"]:
        for L in [5, 10, 20, 60, 120, 250]:
            m = r[f"{tag}_{kind}_L{L}"]
            print(f"| {tag} | {kind} | {L} | {fmt(m)} |")
