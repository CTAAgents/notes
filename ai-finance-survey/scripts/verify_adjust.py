# -*- coding: utf-8 -*-
"""复权因子核验：用 AKShare 独立取原始价与后复权价，检查
"通达信原始价 × 本地缓存的复权因子" 是否与独立后复权价一致。

核验范围默认取第 21 章冻结的 universe（outputs/real_universe.json）全量个股，
报告相对偏差的中位数、95 分位与最大值，而不是只抽几只作示意。
参考价结果缓存到 outputs/adjust_check.json，重跑不再联网。

运行：python scripts/verify_adjust.py            # 全量（首次需联网）
      python scripts/verify_adjust.py --sample   # 仅抽样 8 只（快速自检）
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "code"))
import real_data as rd  # noqa: E402

SAMPLE = ["sh600519", "sh600000", "sz000001", "sz300750",
          "sz002594", "sh601318", "bj920002", "bj920000"]
START = "20190102"
UNIVERSE = os.path.join(ROOT, "outputs", "real_universe.json")
CACHE = os.path.join(ROOT, "outputs", "adjust_check.json")


def _load_codes(use_sample: bool):
    if use_sample or not os.path.exists(UNIVERSE):
        return SAMPLE
    with open(UNIVERSE, encoding="utf-8") as f:
        return json.load(f)["codes"]


def _fetch_ref(sym: str, d0: int, d1: int):
    import akshare as ak
    ref = ak.stock_zh_a_daily(symbol=sym, start_date=str(d0), end_date=str(d1), adjust="hfq")
    ref = ref.set_index(ref["date"].astype(str).str.replace("-", "").astype(int))["close"]
    return {int(k): float(v) for k, v in ref.items()}


def main():
    use_sample = "--sample" in sys.argv
    codes = _load_codes(use_sample)
    vip = rd.discover_vipdoc()
    cache_fac = rd.load_hfq_factors(codes)
    ref_cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            ref_cache = json.load(f)

    print(f"核验范围：{len(codes)} 只（{'抽样' if use_sample else '冻结 universe 全量'}）")
    print(f"{'代码':10s} {'对照日数':>7s} {'最大相对偏差':>12s} {'因子末值':>10s}")
    worst = []
    skipped = 0
    for sym in codes:
        seq = cache_fac.get(sym)
        if not seq:
            skipped += 1
            continue
        path = os.path.join(vip, sym[:2], "lday", sym + ".day")
        arr = rd._read_day(path)
        d = arr["date"].astype(np.int64)
        sel = (d >= int(START))
        d, close = d[sel], arr["close"][sel] / 100.0
        if d.size == 0:
            skipped += 1
            continue
        sd = np.array([p[0] for p in seq])
        sv = np.array([p[1] for p in seq])
        k = np.searchsorted(sd, d, side="right") - 1
        fac = np.where(k >= 0, sv[np.clip(k, 0, None)], 1.0)
        ours = close * fac
        if sym not in ref_cache:
            try:
                ref_cache[sym] = {str(a): b for a, b in _fetch_ref(sym, int(d[0]), int(d[-1])).items()}
                if len(ref_cache) % 50 == 0:
                    with open(CACHE, "w", encoding="utf-8") as f:
                        json.dump(ref_cache, f)
                    print(f"  参考价抓取 {len(ref_cache)} 只", flush=True)
            except Exception:
                ref_cache[sym] = None
        ref = ref_cache.get(sym)
        if not ref:
            skipped += 1
            continue
        rk = np.array([int(x) for x in ref.keys()])
        rv = np.array([ref[str(int(x))] for x in rk])
        common, ia, ib = np.intersect1d(d, rk, return_indices=True)
        if common.size == 0:
            skipped += 1
            continue
        rel = np.abs(ours[ia] / rv[ib] - 1.0)
        mx = float(np.nanmax(rel))
        worst.append(mx)
        if use_sample:
            print(f"{sym:10s} {common.size:7d} {mx:12.3e} {fac[-1]:10.4f}")

    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(ref_cache, f)

    if worst:
        w = np.array(worst)
        print(f"\n核验个股数 = {len(w)}（跳过 {skipped} 只）")
        print(f"相对偏差：中位数 {np.median(w):.3e}｜95 分位 {np.percentile(w, 95):.3e}"
              f"｜最大 {w.max():.3e}")
        print(f"超过 1e-3 的个股数 = {int((w > 1e-3).sum())}；"
              f"超过 1e-2 的 = {int((w > 1e-2).sum())}")
        print("来源：通达信原始价 × AKShare 复权因子 vs AKShare 后复权价")


if __name__ == "__main__":
    main()