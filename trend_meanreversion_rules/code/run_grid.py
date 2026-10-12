# -*- coding: utf-8 -*-
"""生成「参数网格」的日收益矩阵，供多重检验校正使用。

网格与综述一致：4 组口径（期货 TS / 期货 XS / A股指数 TS / A股个股 XS）
× 2 个方向（趋势 / 反转）× 6 个窗口 L ∈ {5,10,20,60,120,250} = 48 个组合。

为避免重复实现，直接复用综述项目的回测引擎（bt_engine.run_backtest）。

用法：
    python run_grid.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import common as C

PAPER_BT = Path(r"d:\Finance\趋势跟踪与均值回归对比综述\scripts\bt_engine.py")
L_GRID = [5, 10, 20, 60, 120, 250]


def _load_engine():
    spec = importlib.util.spec_from_file_location("paper_bt", PAPER_BT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["paper_bt"] = m
    spec.loader.exec_module(m)
    return m


def build_grid_returns(save=True) -> tuple[pd.DataFrame, list[str]]:
    bt = _load_engine()

    panels = {}
    # 期货（时序与截面均在同一 close 面板上跑）
    fclose = C.load_futures()
    panels["fut"] = (fclose.pct_change(), 2.0)
    # A 股指数时序
    idx = C.load_ashare_indices()
    panels["aidx"] = (idx.pct_change(), 5.0)
    # A 股个股截面
    aret, _amt, _px, _nf = C.load_ashare()
    panels["astk"] = (aret.reindex(columns=sorted(aret.columns)), 15.0)

    cols = {}
    for tag, (ret, cost) in panels.items():
        modes = ["TS", "XS"] if tag in ("fut", "astk") else ["TS"]
        for mode in modes:
            for kind in ("trend", "reversion"):
                for L in L_GRID:
                    key = f"{tag}_{mode}_{kind}_L{L}"
                    try:
                        net, _g, _t = bt.run_backtest(ret, kind, mode, L, cost)
                        cols[key] = net
                    except Exception as e:      # 失败如实记录
                        print(f"  [跳过] {key}: {type(e).__name__}: {e}")
    grid = pd.DataFrame(cols).sort_index()
    print(f"网格收益矩阵：{grid.shape[0]} 日 × {grid.shape[1]} 个组合")
    if save:
        grid.to_parquet(C.OUT / "grid_returns.parquet")
        print(f"已写出 {C.OUT / 'grid_returns.parquet'}")
    return grid, list(grid.columns)


if __name__ == "__main__":
    build_grid_returns()