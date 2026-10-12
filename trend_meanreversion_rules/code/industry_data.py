# -*- coding: utf-8 -*-
"""从通达信本地文件解析真实行业分类。

数据来源（均为通达信客户端自带，无需联网）：
  <TDX>/incon.dat                    行业码 → 行业名（含 #TDXNHY 通达信行业、#SWHY 申万行业）
  <TDX>/T0002/hq_cache/tdxhy.cfg     证券代码 → (通达信行业码, 申万行业码)

tdxhy.cfg 行格式：market|code|TDX行业码|||SW行业码
  例：0|000001|T1001|||X500102

对外接口：
  load_industry_map(level=1, source="sw") → {6位代码: 行业名}
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

TDX_DIRS = [
    Path(r"D:\Programs\new_tdx_mock"),
    Path(r"D:\Programs\new_tdxqh"),
    Path(r"D:\Programs\goldsun"),
    Path(r"D:\Programs\zd_huatai_qyb"),
]
CACHE = Path(__file__).resolve().parent.parent / "outputs"


def _read_gbk(p: Path) -> str:
    return p.read_text(encoding="gbk", errors="replace")


def parse_incon(tdx_dir: Path) -> dict[str, dict[str, str]]:
    """解析 incon.dat 的各行业段：{段名: {码: 名称}}。"""
    p = tdx_dir / "incon.dat"
    if not p.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    cur = None
    for raw in _read_gbk(p).splitlines():
        line = raw.strip()
        if not line or line.startswith("######"):
            continue
        if line.startswith("#"):
            cur = line[1:]
            out.setdefault(cur, {})
            continue
        if cur and "|" in line:
            parts = line.split("|", 1)
            out[cur][parts[0].strip()] = parts[1].strip()
    return out


def parse_tdxhy(tdx_dir: Path) -> dict[str, dict[str, str]]:
    """解析 tdxhy.cfg → {code: {"tdx": 通达信行业码, "sw": 申万行业码}}。"""
    p = tdx_dir / "T0002" / "hq_cache" / "tdxhy.cfg"
    if not p.exists():
        return {}
    out = {}
    for raw in _read_gbk(p).splitlines():
        parts = raw.strip().split("|")
        if len(parts) < 6:
            continue
        code = parts[1].strip()
        if not code:
            continue
        out[code] = {"tdx": parts[2].strip(), "sw": parts[5].strip()}
    return out


def _level_prefix(code: str, level: int) -> str:
    """从行业码取指定层级的键。

    通达信行业码形如 T10 / T1001 / T100101（数字串，每 2 位一级）；
    申万行业码形如 X50 / X5001 / X500102。
    本函数返回「前 1 + 2*level 位」作为层级键。
    """
    if not code or len(code) < 3:
        return code
    n = 1 + 2 * level
    return code[:n]


# tdxhy.cfg 第 3 列为通达信行业码（T 前缀），第 6 列为申万体系行业码（X 前缀）；
# 两者的「码 → 名称」分别位于 incon.dat 的 TDXNHY 与 TDXRSHY 段
SEGMENT = {"tdx": "TDXNHY", "sw": "TDXRSHY"}


def load_industry_map(tdx_dir: Path | None = None, source: str = "sw",
                      level: int = 1, use_cache: bool = True) -> pd.Series:
    """返回 {6 位证券代码: 行业名}。

    source: "sw" 申万体系行业 | "tdx" 通达信行业
    level : 1 / 2 / 3 级
    """
    fc = CACHE / f"industry_{source}_L{level}.parquet"
    if use_cache and fc.exists():
        s = pd.read_parquet(fc).iloc[:, 0]
        s.name = "industry"
        return s

    dirs = [tdx_dir] if tdx_dir else TDX_DIRS
    for d in dirs:
        if not d.exists():
            continue
        incon = parse_incon(d)
        hy = parse_tdxhy(d)
        if not hy:
            continue
        names = incon.get(SEGMENT.get(source, "TDXNHY"), {})
        if not names:
            continue
        rows = {}
        for code, v in hy.items():
            raw = v.get(source, "")
            if not raw:
                continue
            key = _level_prefix(raw, level)
            nm = names.get(key) or names.get(raw)
            if nm:
                rows[code] = nm
        if rows:
            s = pd.Series(rows, name="industry")
            s.index.name = "code"
            CACHE.mkdir(parents=True, exist_ok=True)
            s.to_frame().to_parquet(fc)
            return s
    return pd.Series(dtype="object", name="industry")


if __name__ == "__main__":
    for src in ("sw", "tdx"):
        for lv in (1, 2):
            try:
                s = load_industry_map(source=src, level=lv, use_cache=False)
            except Exception as e:
                print(f"{src} L{lv}: 解析失败 {type(e).__name__}: {e}")
                continue
            print(f"{src} L{lv}: 覆盖 {len(s)} 只证券，{s.nunique()} 个行业")
            if len(s):
                top = s.value_counts().head(8)
                print("   " + "；".join(f"{k}({v})" for k, v in top.items()))