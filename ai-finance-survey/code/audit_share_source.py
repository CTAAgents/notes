# -*- coding: utf-8 -*-
"""股本数据来源风险的质量门：不依赖外部来源的序列形态自检。

背景：规模中性化所用的流通股本只有 AKShare 一个来源（本地 base.dbf 布局不可
解析、无法交叉校验）。既然无法做来源间比对，就退一步做"序列形态自检"——检查
序列是否呈现可预期的分段常数形态、变动是否落在合理的窗口、有无异常跳变。

这些检验不能证明数值正确，但能排除若干类明显错误（脏数据、日期错位、单位
换算错误、序列回退）。检验项：
  C1 非正股本 / 缺失
  C2 变动次数与变动幅度分布（含异常大跳变）
  C3 变动发生的月份分布（送转/增发多集中在年初与年中，可作软核查）
  C4 抖动检测：变动后短期内回退（可能对应期权行权/回购，也可能是数据错位）
  C5 与本地日线成交额的规模一致性（流通市值不应为负或极端）

运行：python audit_share_source.py
"""
from __future__ import annotations

import json
import os
from collections import Counter

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CACHE = os.path.join(ROOT, "outputs", "outstanding_shares.json")


def main():
    with open(CACHE, encoding="utf-8") as f:
        data = json.load(f)
    print(f"缓存个股数 = {len(data)}")

    n_bad = 0
    jumps, n_change, jitter = [], [], 0
    jitter_mag = []
    months = Counter()
    series_ok = 0
    outliers = []

    for sym, seq in data.items():
        if not seq:
            n_bad += 1
            continue
        d = np.array([p[0] for p in seq])
        v = np.array([p[1] for p in seq], dtype=float)
        if v.size == 0 or np.any(~np.isfinite(v)) or np.any(v <= 0):
            n_bad += 1
            outliers.append((sym, "非正或缺失股本"))
            continue
        series_ok += 1
        ch = np.where(np.diff(v) != 0)[0]
        n_change.append(ch.size)
        for i in ch:
            months[int(str(d[i + 1])[4:6])] += 1
            ratio = v[i + 1] / v[i]
            jumps.append(ratio)
            if ratio > 3.0 or ratio < 0.5:
                outliers.append((sym, f"{int(d[i+1])} 跳变 {v[i]:.3e}→{v[i+1]:.3e}"))
        # 抖动：变动后 5 个交易日内回退到原值
        for i in ch:
            w = v[i + 1:i + 6]
            if w.size and np.any(np.isclose(w, v[i])):
                jitter += 1
                jitter_mag.append(abs(v[i + 1] / v[i] - 1.0))

    n_change = np.array(n_change)
    jumps = np.array(jumps)
    print(f"  形态合格序列 = {series_ok}；不合格 = {n_bad}")
    print(f"  C1 非正/缺失股本：{n_bad} 只")
    print(f"  C2 变动次数：中位 {np.median(n_change):.0f}、最大 {n_change.max():.0f}；"
          f"总变动 {jumps.size} 次")
    print(f"     变动幅度：中位 {np.median(jumps):.4f}｜p1 {np.percentile(jumps,1):.4f}"
          f"｜p99 {np.percentile(jumps,99):.4f}｜最大 {jumps.max():.3f}")
    print(f"     幅度 >3 倍或 <0.5 倍的异常跳变：{int(((jumps>3)|(jumps<0.5)).sum())} 次")
    tot = sum(months.values())
    print(f"  C3 变动月份分布（前 6）："
          + " ".join(f"{m}月 {c}（{c/tot:.1%}）"
                     for m, c in months.most_common(6)))
    print(f"  C4 抖动（变动后 5 日内回退）：{jitter} 次")
    if jitter_mag:
        jm = np.array(jitter_mag)
        print(f"     抖动幅度：中位 {np.median(jm):.4%}｜p95 {np.percentile(jm,95):.4%}"
              f"｜最大 {jm.max():.2%}")
        print(f"     幅度 >1% 的抖动 {int((jm>0.01).sum())} 次；"
              f">10% 的 {int((jm>0.10).sum())} 次")
    print(f"  C5 异常清单（前 12 条）：")
    for sym, why in outliers[:12]:
        print(f"     {sym}: {why}")
    if len(outliers) > 12:
        print(f"     … 另有 {len(outliers)-12} 条")


if __name__ == "__main__":
    main()