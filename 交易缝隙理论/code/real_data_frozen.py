# -*- coding: utf-8 -*-
"""独立文章的冻结数据层：与综述（781cadd68dfbd170 快照）严格对齐的真实数据加载。

本文件是综述项目 code/real_data.py 的冻结复算版本，逻辑保持一致，仅做两处修改
（改点均在下方以“冻结版修改”标注）：
  1. 窗口截断：数据源在快照冻结后被更新（本地库新增了更晚的交易bar），为避免
     universe 现场采样漂移，按固定截止日 end 截断（默认 20261008）；
  2. 支持从冻结清单读取 universe：默认读取综述 outputs/real_universe.json 的
     400 只代码（该清单随快照冻结，供复算对齐），跳过现场采样。

复权因子缓存、口径、字段定义与综述完全一致；digest 可与 781cadd68dfbd170 比对，
不一致即说明数据链发生了漂移。
"""
from __future__ import annotations

import hashlib
import json
import os
import warnings

import numpy as np

# 停牌/新上市造成的全空窗口会产生 nanmean/nanstd 的空切片告警，属预期，静音
for _m in ("Mean of empty slice", "Degrees of freedom <= 0 for slice",
           "invalid value encountered in scalar divide"):
    warnings.filterwarnings("ignore", message=_m)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="numpy")

DAY_DTYPE = np.dtype([
    ("date", "<u4"), ("open", "<u4"), ("high", "<u4"), ("low", "<u4"),
    ("close", "<u4"), ("amount", "<f4"), ("volume", "<u4"), ("res", "<u4"),
])

# 沪深北 A 股代码前缀（排除指数、基金、债券、B 股）
SH_PREFIX = ("600", "601", "603", "605", "688", "689")
SZ_PREFIX = ("000", "001", "002", "003", "300", "301")
BJ_PREFIX = ("920",)
LIMIT_BANDS = (0.05, 0.10, 0.20, 0.30)   # 封板判定尝试的涨跌幅档位
FEATURE_WIN = 60                          # 最长回看窗口
NEW_LISTING_DAYS = 20                     # 新股上市初期剔除天数
MIN_MEDIAN_AMOUNT = 2.0e7                 # 成交额中位数下限（元），流动性筛除
END_I = 20261008                          # 冻结版修改：固定截止日

_HERE = os.path.dirname(os.path.abspath(__file__))
_REVIEW = os.path.abspath(os.path.join(_HERE, "..", "..", "AI金融交易综述"))
FACTOR_CACHE = os.path.join(_REVIEW, "outputs", "hfq_factors.json")   # 冻结版修改：指向综述缓存
DEFAULT_UNIVERSE = os.path.join(_REVIEW, "outputs", "real_universe.json")


def discover_vipdoc() -> str:
    """自动发现含沪深日线的通达信 vipdoc 根目录。"""
    import glob
    cands = []
    for base in ("C:/", "D:/", "E:/"):
        if not os.path.isdir(base):
            continue
        for pat in ("*/vipdoc", "*/*/vipdoc", "*/*/*/vipdoc"):
            cands.extend(glob.glob(base + pat))
    best, best_n = None, 0
    for r in cands:
        d = os.path.join(r, "sh", "lday")
        if not os.path.isdir(d):
            continue
        n = len([f for f in os.listdir(d) if f.endswith(".day")])
        if n > best_n:
            best, best_n = r, n
    if best is None:
        raise FileNotFoundError("未找到通达信 vipdoc 日线目录")
    return best


def _list_stocks(vipdoc: str):
    out = []
    for mkt, pref in (("sh", SH_PREFIX), ("sz", SZ_PREFIX), ("bj", BJ_PREFIX)):
        d = os.path.join(vipdoc, mkt, "lday")
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".day") or not fn.startswith(mkt):
                continue
            code = fn[len(mkt):-4]          # 去掉 sh/sz/bj 前缀，得到 6 位代码
            if code.startswith(pref):
                out.append((mkt, code, os.path.join(d, fn)))
    return out


def _read_day(path: str) -> np.ndarray:
    with open(path, "rb") as f:
        buf = f.read()
    return np.frombuffer(buf, dtype=DAY_DTYPE, count=len(buf) // DAY_DTYPE.itemsize)


def _first_last_date(path: str):
    """只读首末日期，避免为筛选而整文件解析。"""
    sz = os.path.getsize(path)
    if sz < DAY_DTYPE.itemsize:
        return None, None
    with open(path, "rb") as f:
        d0 = int(np.frombuffer(f.read(4), dtype="<u4")[0])
        f.seek(sz - DAY_DTYPE.itemsize)
        d1 = int(np.frombuffer(f.read(4), dtype="<u4")[0])
    return d0, d1


def load_hfq_factors(codes, cache_path: str = FACTOR_CACHE, refresh: bool = False) -> dict:
    """读取/抓取后复权因子（AKShare）。结果缓存到综述 outputs，重跑不再联网。

    返回 {symbol: [[date_int, factor_float], ...]}（按日期升序）。抓取失败者置 None。
    """
    cache = {}
    if not refresh and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    need = [c for c in codes if c not in cache]
    if need:
        import akshare as ak
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        def _dump():
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)

        for i, sym in enumerate(need):
            try:
                df = ak.stock_zh_a_daily(symbol=sym, adjust="hfq-factor")
                d = df["date"].astype(str).str.replace("-", "").astype(int).tolist()
                v = [float(x) for x in df["hfq_factor"]]
                seq = sorted(zip(d, v))
                cache[sym] = [[int(a), float(b)] for a, b in seq]
            except Exception:
                cache[sym] = None
            if (i + 1) % 50 == 0:
                print(f"  复权因子抓取 {i + 1}/{len(need)}", flush=True)
                _dump()
        _dump()
    return cache


def _rolling_nanstd(a: np.ndarray, w: int) -> np.ndarray:
    T, N = a.shape
    out = np.full((T, N), np.nan)
    for t in range(w - 1, T):
        out[t] = np.nanstd(a[t - w + 1:t + 1], axis=0)
    return out


def _rolling_nanmean_ratio(num: np.ndarray, den: np.ndarray, w: int) -> np.ndarray:
    T, N = num.shape
    out = np.full((T, N), np.nan)
    for t in range(w - 1, T):
        out[t] = num[t] / np.nanmean(den[t - w + 1:t + 1], axis=0)
    return out


def _rolling_nanmean(a: np.ndarray, w: int) -> np.ndarray:
    T, N = a.shape
    out = np.full((T, N), np.nan)
    for t in range(w - 1, T):
        out[t] = np.nanmean(a[t - w + 1:t + 1], axis=0)
    return out


def _xs_zscore(x: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """逐期截面 z 标准化；截面不足 3 只置 0。"""
    T, N = x.shape
    out = np.zeros((T, N))
    for t in range(T):
        m = valid[t]
        if m.sum() < 3:
            continue
        v = x[t][m]
        sd = v.std()
        if sd > 0:
            out[t][m] = (v - v.mean()) / sd
    return np.clip(out, -4.0, 4.0)


def make_snapshot(start: str = "20190102", end: int = END_I, n_max: int = 400,
                  min_cover: float = 0.90, seed: int = 20261009,
                  vipdoc: str | None = None, refresh_factors: bool = False,
                  codes_file: str | None = DEFAULT_UNIVERSE) -> dict:
    """构造真实数据快照（冻结版），返回与综述 data.make_snapshot 相同的键。

    冻结版修改：end 截断到固定日期；codes_file 非 None 时从其 "codes" 字段
    读取 universe（sh600000 形式），跳过现场采样。
    """
    vipdoc = vipdoc or discover_vipdoc()
    start_i = int(start)
    end_i_cap = int(end)

    # 交易日历取自上证指数日线
    idx = _read_day(os.path.join(vipdoc, "sh", "lday", "sh000001.day"))
    cal = idx["date"].astype(np.int64)
    cal = cal[(cal >= start_i) & (cal <= end_i_cap)]   # 冻结版修改：窗口截断
    end_i = int(cal[-1])
    T = len(cal)

    if codes_file:
        # 冻结版修改：直接从冻结清单构造 keep，跳过采样与筛选
        with open(codes_file, encoding="utf-8") as f:
            uni = json.load(f)
        keep = []
        for sym in uni["codes"]:
            mkt, code = sym[:2], sym[2:]
            path = os.path.join(vipdoc, mkt, "lday", f"{sym}.day")
            if not os.path.isfile(path):
                continue
            d0, _ = _first_last_date(path)
            arr = _read_day(path)
            d = arr["date"].astype(np.int64)
            sel = (d >= start_i) & (d <= end_i)
            keep.append((mkt, code, arr[sel], int(d0)))
    else:
        stocks = _list_stocks(vipdoc)
        keep = _sample_universe(vipdoc, stocks, cal, start_i, end_i, T, n_max, min_cover)

    syms = [mkt + code for mkt, code, _, _ in keep]
    factors = load_hfq_factors(syms, refresh=refresh_factors)
    n_missing = sum(1 for s in syms if not factors.get(s))
    keep = [(m, c, a, d0) for (m, c, a, d0), s in zip(keep, syms) if factors.get(s)]
    N = len(keep)

    close = np.full((T, N), np.nan)
    vol = np.full((T, N), np.nan)
    amt = np.full((T, N), np.nan)
    # 原始价另存为整数"分"，供涨跌停封板做精确判定
    oC = np.full((T, N), -1, dtype=np.int64)
    hC = np.full((T, N), -1, dtype=np.int64)
    lC = np.full((T, N), -1, dtype=np.int64)
    cC = np.full((T, N), -1, dtype=np.int64)
    fac = np.ones((T, N))
    newdays = [0] * N                        # 窗口内上市者需剔除的起始位置；<0 表示窗口前已上市
    codes = []
    for j, (mkt, code, arr, d0) in enumerate(keep):
        codes.append(mkt + code)
        d = arr["date"].astype(np.int64)
        pos = np.searchsorted(cal, d)
        newdays[j] = int(np.searchsorted(cal, d0)) if d0 >= int(cal[0]) else -1
        close[pos, j] = arr["close"] / 100.0
        vol[pos, j] = arr["volume"]
        amt[pos, j] = arr["amount"]
        oC[pos, j] = arr["open"]; hC[pos, j] = arr["high"]
        lC[pos, j] = arr["low"]; cC[pos, j] = arr["close"]
        seq = factors[codes[-1]]
        sd = np.array([p[0] for p in seq]); sv = np.array([p[1] for p in seq])
        k = np.searchsorted(sd, cal, side="right") - 1
        fac[:, j] = np.where(k >= 0, sv[np.clip(k, 0, None)], 1.0)

    # 后复权价：消除分红/送转跳空
    adj = close * fac
    logret = np.full((T, N), np.nan)
    logret[1:] = adj[1:] / adj[:-1] - 1.0
    have_bar = ~np.isnan(close)

    # 特征（K=8），全部只用 t 期及以前的信息
    ret1 = logret
    ret5 = np.full((T, N), np.nan)
    ret20 = np.full((T, N), np.nan)
    ret60 = np.full((T, N), np.nan)
    for k, arr in ((5, ret5), (20, ret20), (60, ret60)):
        arr[k:] = adj[k:] / adj[:-k] - 1.0
    vol20 = _rolling_nanstd(logret, 20)                      # 波动率（低波因子）
    vratio = _rolling_nanmean_ratio(vol, vol, 60)            # 量比（流动性/关注度）
    magap = _rolling_nanmean_ratio(adj, adj, 20) - 1.0       # 距 20 日均线
    illiq_num = np.abs(logret) / np.where(amt > 0, amt, np.nan)
    illiq = _rolling_nanmean(illiq_num, 20)                  # Amihud 非流动性

    feats = [ret1, ret5, ret20, ret60, vol20, vratio, magap, illiq]
    valid = np.zeros((T, N), dtype=bool)
    valid[FEATURE_WIN:] = have_bar[FEATURE_WIN:] & ~np.isnan(ret60[FEATURE_WIN:])
    for f in feats:
        valid &= np.isfinite(f)

    X = np.zeros((T, N, len(feats)))
    for k, f in enumerate(feats):
        X[:, :, k] = _xs_zscore(np.nan_to_num(f), valid)

    # 标签：t -> t+1 后复权收益；末期无标签
    r = np.zeros((T, N))
    r[:-1] = np.nan_to_num(logret[1:])

    # 涨跌停封板（整数"分"口径，交易所四舍五入到 0.01 元）：对四档幅度逐日识别
    pC = np.full((T, N), -1, dtype=np.int64)
    pC[1:] = cC[:-1]
    for t in range(1, T):                    # 停牌期间沿用上一有效收盘价
        bad = pC[t] == -1
        pC[t, bad] = pC[t - 1, bad]
    ex_date = np.zeros((T, N), dtype=bool)
    ex_date[1:] = fac[1:] != fac[:-1]        # 除权日涨跌停基准被调整，不做封板判定
    sealed_up = np.zeros((T, N), dtype=bool)
    sealed_dn = np.zeros((T, N), dtype=bool)
    for lim in LIMIT_BANDS:
        up = np.floor(pC * (1.0 + lim) + 0.5).astype(np.int64)
        dn = np.floor(pC * (1.0 - lim) + 0.5).astype(np.int64)
        sealed_up |= (cC == up) & (hC == cC)
        sealed_dn |= (cC == dn) & (lC == cC)
    ok = have_bar & (pC > 0) & ~ex_date
    sealed_up &= ok
    sealed_dn &= ok
    one_word = (sealed_up | sealed_dn) & (oC == cC) & (hC == lC)

    mask = valid.copy()
    mask[-1] = False
    # 新股上市初期剔除（仅对窗口内上市者；窗口前已上市者不剔除）
    for j in range(N):
        i0 = newdays[j]
        if i0 >= 0:
            mask[i0:i0 + NEW_LISTING_DAYS, j] = False

    tradable = mask & ~sealed_up & ~sealed_dn
    tradable[-1] = False

    digest = hashlib.sha256(
        np.ascontiguousarray(np.nan_to_num(close)).tobytes()
        + np.ascontiguousarray(fac).tobytes()
        + np.ascontiguousarray(X).tobytes()
        + np.ascontiguousarray(tradable).tobytes()
    ).hexdigest()[:16]

    stats = {
        "n_universe": N, "n_dropped_no_factor": n_missing,
        "n_new_listing_in_window": sum(1 for x in newdays if x >= 0),
        "n_bj": sum(1 for c in codes if c.startswith("bj")),
        "valid_ratio": float(mask.mean()),
        # 以下占比一律以“有效单元格”（mask 为真）为分母，便于同口径比较
        "sealed_up_ratio": float(sealed_up.sum() / max(mask.sum(), 1)),
        "sealed_dn_ratio": float(sealed_dn.sum() / max(mask.sum(), 1)),
        "sealed_total_ratio": float((sealed_up | sealed_dn).sum() / max(mask.sum(), 1)),
        "one_word_ratio": float(one_word.sum() / max(mask.sum(), 1)),
        "ex_date_cells": int(ex_date.sum()),
        "median_amount_cny": float(np.nanmedian(amt)),
    }
    return {"X": X, "r": r, "mask": mask, "tradable": tradable,
            "digest": digest, "dates": cal, "codes": codes, "fac": fac,
            "adj": adj, "raw": close, "amt": amt,
            "source": f"TDX vipdoc .day + AKShare 后复权因子（冻结版 @ {vipdoc}）",
            "window": (int(cal[0]), int(cal[-1])), "T": T, "N": N, "stats": stats}


def _sample_universe(vipdoc, stocks, cal, start_i, end_i, T, n_max, min_cover):
    """综述版现场采样逻辑（默认路径不触发；供需要时对照）。"""
    cand1 = []
    for mkt, code, path in stocks:
        try:
            d0, d1 = _first_last_date(path)
        except Exception:
            continue
        if d0 is None or d1 < end_i - 5:
            continue
        cand1.append((mkt, code, path, d0))
    if len(cand1) > n_max * 2:
        step = len(cand1) / (n_max * 2)
        cand1 = [cand1[int(i * step)] for i in range(n_max * 2)]
    keep = []
    for mkt, code, path, d0 in cand1:
        try:
            arr = _read_day(path)
        except Exception:
            continue
        if arr.size == 0:
            continue
        d = arr["date"].astype(np.int64)
        sel = (d >= start_i) & (d <= end_i)
        active_start = max(start_i, int(d0))
        active_len = T - int(np.searchsorted(cal, active_start))
        if active_len <= 0 or sel.sum() < min_cover * active_len:
            continue
        amt = arr["amount"][sel].astype(np.float64)
        if np.median(amt) < MIN_MEDIAN_AMOUNT:
            continue
        keep.append((mkt, code, arr[sel], int(d0)))
    if len(keep) > n_max:
        step = len(keep) / n_max
        keep = [keep[int(i * step)] for i in range(n_max)]
    return keep


if __name__ == "__main__":
    snap = make_snapshot()
    print(f"来源: {snap['source']}")
    print(f"窗口: {snap['window'][0]}–{snap['window'][1]}  T={snap['T']} N={snap['N']}")
    print(f"digest={snap['digest']}  不可成交占比={1 - snap['tradable'].mean():.4f}")
    print(f"预期与综述一致：digest=781cadd68dfbd170  T=1881  N=400")
    for k, v in snap["stats"].items():
        print(f"  {k} = {v}")