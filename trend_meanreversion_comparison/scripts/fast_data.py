# -*- coding: utf-8 -*-
"""快速 .day 解析（numpy 向量化）与 A 股面板构建（带 parquet 缓存）。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TDX_ROOT = Path(r"D:\Programs\new_tdx_mock\vipdoc")
CACHE = Path(r"d:\Finance\趋势跟踪与均值回归对比综述\outputs")

_DT = np.dtype([
    ("date", "<u4"), ("open", "<f4"), ("high", "<f4"), ("low", "<f4"),
    ("close", "<f4"), ("amount", "<u4"), ("vol", "<u4"), ("oi", "<u4"),
])


def read_day_fast(path) -> pd.DataFrame | None:
    try:
        b = Path(path).read_bytes()
        n = len(b) // 32
        if n < 10:
            return None
        a = np.frombuffer(b[: n * 32], dtype=_DT)
        dates = pd.to_datetime(a["date"].astype("int64").astype(str), format="%Y%m%d")
        df = pd.DataFrame({
            "open": a["open"].astype("f8"), "high": a["high"].astype("f8"),
            "low": a["low"].astype("f8"), "close": a["close"].astype("f8"),
            "amount": a["amount"].astype("f8"), "vol": a["vol"].astype("f8"),
            "oi": a["oi"].astype("f8"),
        }, index=pd.DatetimeIndex(dates, name="date"))
        df = df[(df["close"] > 0) & (df["close"] < 1e9) & (df["high"] >= df["low"])]
        return df.sort_index()
    except Exception:
        return None


def _is_stock(mk, code):
    if mk == "sh":
        return code[:3] in {"600", "601", "603", "605", "688", "689"}
    return code[:3] in {"000", "001", "002", "003", "300", "301"}


def _limit(code):
    return 0.20 if code[:3] in {"300", "301", "688", "689"} else 0.10


def load_ashare_returns(start="2014-01-01", end="2026-09-30", min_bars=400,
                        last_after="2026-08-01", use_cache=True):
    """A 股个股日收益面板（除权跳空近似修复）。"""
    fc = CACHE / f"ashare_returns_{start}_{end}.parquet"
    fs = CACHE / f"ashare_returns_{start}_{end}.flags"
    if use_cache and fc.exists():
        return pd.read_parquet(fc), int(fs.read_text()) if fs.exists() else 0

    rets, nflag = {}, 0
    for mk in ("sh", "sz"):
        for p in sorted((TDX_ROOT / mk / "lday").glob(f"{mk}*.day")):
            code = p.stem[2:]
            if not _is_stock(mk, code):
                continue
            df = read_day_fast(p)
            if df is None or df.index.max() < pd.Timestamp(last_after):
                continue
            c = df["close"].loc[start:end]
            if len(c) < min_bars:
                continue
            r = c.pct_change()
            flag = r < -(_limit(code) + 0.005)
            nflag += int(flag.sum())
            rets[code] = r.mask(flag, 0.0).astype("f4")
    panel = pd.DataFrame(rets).sort_index()
    CACHE.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(fc)
    fs.write_text(str(nflag))
    return panel, nflag


if __name__ == "__main__":
    import time
    t0 = time.time()
    p, nf = load_ashare_returns(use_cache=False)
    print("panel", p.shape, p.index.min().date(), p.index.max().date(),
          "flags", nf, f"{time.time()-t0:.1f}s",
          "mem_MB", round(p.memory_usage(deep=True).sum() / 1e6, 1))
