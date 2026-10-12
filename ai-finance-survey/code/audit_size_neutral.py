# -*- coding: utf-8 -*-
"""规模中性化：检验非流动性的收益是否由规模解释（方案见 docs/size_control_plan.tex）。

数据：流通股本取 AKShare 的逐日 outstanding_share（时点值，缓存到
outputs/outstanding_shares.json）；规模代理为 流通市值 = 原始收盘价 × 流通股本。
不用本地 base.dbf 快照——它只有 2139 只且是当前值，回填 2019 年会造成严重前视
（实测 sz300750 流通股本在样本期内放大 19.6 倍）。

三种中性化方法：
  M1 双重排序 5×5（附 2×5 粗网格）
  M2 截面回归取残差（主判据）
  M3 规模层内多空等权合成（下界对照）

判据（方案第 1.2 节）：中性化后含冲击夏普 ≥0.7 判定存在超出规模的流动性维度；
≤0.3 判定由规模驱动；中间则如实报告“无法分离”。

运行：python audit_size_neutral.py
"""
from __future__ import annotations

import json
import os

import numpy as np

from baseline import apply_tradability, rank_weights
from costs import CostModel, ashare_fee_bps, stamp_duty_schedule
from eval import metrics
from real_data import make_snapshot

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
UNIVERSE = os.path.join(ROOT, "outputs", "real_universe.json")
SHARE_CACHE = os.path.join(ROOT, "outputs", "outstanding_shares.json")
CAPITAL = 1e8
K_ILLIQ = 7          # 非流动性在第 8 列
MIN_NAMES = 40


# ---------- 数据 ----------
def load_shares(codes, cache_path=SHARE_CACHE):
    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    need = [c for c in codes if c not in cache]
    if need:
        import akshare as ak
        for i, sym in enumerate(need):
            try:
                df = ak.stock_zh_a_daily(symbol=sym, start_date="20190101",
                                         end_date="20261008", adjust="")
                d = df["date"].astype(str).str.replace("-", "").astype(int)
                v = df["outstanding_share"].astype(float)
                cache[sym] = [[int(a), float(b)] for a, b in zip(d, v)]
            except Exception:
                cache[sym] = None
            if (i + 1) % 50 == 0:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f)
                print(f"  流通股本抓取 {i + 1}/{len(need)}", flush=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    return cache


def build_size(snap, shares) -> np.ndarray:
    """流通市值矩阵 (T,N)：原始收盘价 × 当日流通股本，逐日对齐。"""
    cal = snap["dates"]
    raw = snap["raw"]
    T, N = raw.shape
    size = np.full((T, N), np.nan)
    miss = 0
    for j, sym in enumerate(snap["codes"]):
        seq = shares.get(sym)
        if not seq:
            miss += 1
            continue
        sd = np.array([p[0] for p in seq])
        sv = np.array([p[1] for p in seq])
        k = np.searchsorted(sd, cal, side="right") - 1
        v = np.where(k >= 0, sv[np.clip(k, 0, None)], np.nan)
        size[:, j] = raw[:, j] * v
    if miss:
        print(f"  缺少流通股本的个股数 = {miss}（其规模置 NaN，不参与分层）")
    return size


# ---------- 组合工具 ----------
def _ret(w, r):
    return np.array([float(np.sum(w[t] * r[t])) for t in range(w.shape[0])])


def _net(w, r, cm, extra):
    T = r.shape[0]
    out = np.zeros(T)
    prev = np.zeros(r.shape[1])
    for t in range(T):
        out[t] = (float(np.sum(w[t] * r[t]))
                  - cm.cost(prev, w[t], CAPITAL, extra_fee_sell=float(extra[t])))
        prev = w[t]
    return out


def _valid(mask, size):
    return mask & np.isfinite(size) & (size > 0)


def _rank01(x, ok):
    """逐期截面分位（0~1）。"""
    T, N = x.shape
    out = np.full((T, N), np.nan)
    for t in range(T):
        m = ok[t]
        if m.sum() < MIN_NAMES:
            continue
        v = x[t][m]
        out[t][m] = v.argsort().argsort() / max(m.sum() - 1, 1)
    return out


# ---------- M1 双重排序 ----------
def m1_double_sort(sig, size, r, ok, n_size=5, n_illiq=5):
    T = sig.shape[0]
    grid = np.zeros((n_size, n_illiq))
    cnt = np.zeros((n_size, n_illiq))
    spreads = []
    for t in range(T - 1):
        m = ok[t]
        if m.sum() < MIN_NAMES:
            continue
        idx = np.where(m)[0]
        sz = size[t][idx]
        sg = np.array_split(np.argsort(sz), n_size)          # 规模层（小→大）
        row = np.full(n_illiq, np.nan)
        for si, sub in enumerate(sg):
            if len(sub) < n_illiq:
                continue
            sub_idx = idx[sub]
            iv = sig[t][sub_idx]
            ig = np.array_split(np.argsort(iv), n_illiq)     # 层内按非流动性分层
            for gi, sel in enumerate(ig):
                rr = float(r[t][sub_idx[sel]].mean())
                grid[si, gi] += rr
                cnt[si, gi] += 1
                if gi == n_illiq - 1:
                    row[si] = rr
                if gi == 0:
                    row[si] -= rr
        if np.isfinite(row).all():
            spreads.append(float(np.nanmean(row)))
    g = grid / np.maximum(cnt, 1) * 1e4
    print(f"  {n_size}×{n_illiq} 网格（行=规模层由小到大，列=非流动性层由低到高，单位 bp/日）：")
    for si in range(n_size):
        print("   ", " ".join(f"{x:7.1f}" for x in g[si]))
    inrow = g[:, -1] - g[:, 0]
    print(f"  各规模层内（最不流动 − 最流动）: "
          + " ".join(f"{x:6.1f}" for x in inrow))
    print(f"  层内价差均值 = {np.nanmean(inrow):.1f} bp")
    return float(np.nanmean(inrow)), g


# ---------- M2 截面回归取残差 ----------
def m2_residual(sig, size, ok):
    T, N = sig.shape
    res = np.zeros((T, N))
    betas = []
    for t in range(T):
        m = ok[t]
        if m.sum() < MIN_NAMES:
            continue
        idx = np.where(m)[0]
        y = sig[t][idx]
        x = np.log(size[t][idx])
        A = np.column_stack([np.ones_like(x), x])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        betas.append(coef[1])
        res[t][idx] = y - A @ coef
    print(f"  ln(规模) 的回归系数：均值 {np.mean(betas):+.4f}"
          f"（负值表示规模越大非流动性越低，符合预期）")
    return res


# ---------- M3 层内多空等权合成 ----------
def m3_within_layer(sig, size, mask, tradable, ok, n_size=5):
    T, N = mask.shape
    layer_w = [None] * T
    for t in range(T):
        m = ok[t]
        if m.sum() < MIN_NAMES:
            continue
        idx = np.where(m)[0]
        sg = np.array_split(np.argsort(size[t][idx]), n_size)
        ws = []
        for sub in sg:
            if len(sub) < 5:
                continue
            sub_idx = idx[sub]
            one = np.zeros(N)
            one[sub_idx] = sig[t][sub_idx]
            one = one - one[sub_idx].mean()
            g = np.abs(one).sum()
            if g > 0:
                ws.append(one / g)
        if ws:
            layer_w[t] = ws
    w_out = np.zeros((T, N))
    for t in range(T):
        if layer_w[t]:
            w_out[t] = np.mean(layer_w[t], axis=0)
    return apply_tradability(w_out, tradable)


def _turnover(w):
    return float(np.abs(np.diff(w, axis=0)).sum(axis=1).mean() * 252)


def main():
    snap = make_snapshot()
    X, r, mask, tradable, amt = (snap["X"], snap["r"], snap["mask"],
                                 snap["tradable"], snap["amt"])
    dates = snap["dates"]
    sig = X[:, :, K_ILLIQ]

    print("=== 数据准备 ===")
    shares = load_shares(list(snap["codes"]))
    size = build_size(snap, shares)
    ok = _valid(mask, size)
    print(f"  有效单元格占比（同时有特征与规模）：{ok.mean():.4f}")

    fee = ashare_fee_bps()
    extra = stamp_duty_schedule(dates)
    adv = np.nanmedian(np.where(tradable, amt, np.nan), axis=0)
    adv = np.where(np.isfinite(adv) & (adv > 0), adv, 1e7)
    cm_imp = CostModel(mode="impact", fee_bps=fee, adv=adv)

    print("\n=== 基准：未中性化的非流动性（复核第 21 章口径）===")
    w_base = apply_tradability(rank_weights(sig, mask), tradable)
    g0 = metrics(_ret(w_base, r))
    n0 = metrics(_net(w_base, r, cm_imp, extra))
    print(f"  零成本夏普 {g0['sharpe']:.3f}；含冲击夏普 {n0['sharpe']:.3f}；"
          f"年化换手 {_turnover(w_base):.0f} 倍")

    print("\n=== M1 双重排序 ===")
    m1_5, _ = m1_double_sort(sig, size, r, ok, 5, 5)
    print()
    m1_2, _ = m1_double_sort(sig, size, r, ok, 2, 5)

    print("\n=== M2 截面回归取残差（主判据）===")
    res = m2_residual(sig, size, ok)
    w_m2 = apply_tradability(rank_weights(res, ok), tradable)
    g2 = metrics(_ret(w_m2, r))
    n2 = metrics(_net(w_m2, r, cm_imp, extra))
    print(f"  规模中性化后：零成本夏普 {g2['sharpe']:.3f}；含冲击夏普 {n2['sharpe']:.3f}；"
          f"年化换手 {_turnover(w_m2):.0f} 倍")
    years = np.array([d // 10000 for d in dates])
    sp = _net(w_m2, r, cm_imp, extra)
    print("  逐年含冲击夏普："
          + " ".join(f"{y}:{metrics(sp[years == y])['sharpe']:.2f}"
                     for y in sorted(set(years)) if (years == y).sum() > 60))

    print("\n=== M3 规模层内多空等权合成（下界对照）===")
    w_m3 = m3_within_layer(sig, size, mask, tradable, ok)
    g3 = metrics(_ret(w_m3, r))
    n3 = metrics(_net(w_m3, r, cm_imp, extra))
    print(f"  规模中性组合：零成本夏普 {g3['sharpe']:.3f}；含冲击夏普 {n3['sharpe']:.3f}；"
          f"年化换手 {_turnover(w_m3):.0f} 倍")

    print("\n=== 判据汇总（方案第 1.2 节）===")
    vals = {"M1 层内价差(bp)": m1_5, "M2 含冲击夏普": n2["sharpe"],
            "M3 含冲击夏普": n3["sharpe"]}
    for k, v in vals.items():
        print(f"  {k} = {v:+.3f}")
    verdict = ("存在超出规模的流动性维度" if n2["sharpe"] >= 0.7 else
               "由规模驱动" if n2["sharpe"] <= 0.3 else "无法分离")
    print(f"  → M2 主判据判定：{verdict}")


if __name__ == "__main__":
    main()