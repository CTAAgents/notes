# -*- coding: utf-8 -*-
"""上线前的多重检验校正流程。

实现四种方法并对 60 个参数组合实跑：
  1. White (2000) Reality Check      —— 自举检验「最优组合」的真实显著性
  2. Hansen (2005) SPA               —— studentized 版本，对劣质策略稳健
  3. Bailey & López de Prado (2014) 紧缩夏普比率（DSR）
  4. Bailey, Borwein, López de Prado & Zhu (2016) 回测过拟合概率（PBO / CSCV）

用法：
    python multipletest.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import stats

import common as C

N_BOOT = 2000
BLOCK = 20          # stationary bootstrap 平均块长
SEED = 20261008


# ---------------------------------------------------------------- 自举工具
def stationary_bootstrap_idx(T: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Politis--Romano 平稳自举的时间索引。"""
    p = 1.0 / block
    idx = np.empty(T, dtype=np.int64)
    idx[0] = rng.integers(T)
    for t in range(1, T):
        if rng.random() < p:
            idx[t] = rng.integers(T)
        else:
            idx[t] = (idx[t - 1] + 1) % T
    return idx


def nw_se(x: np.ndarray, lags: int = 5) -> float:
    x = x[~np.isnan(x)]
    n = len(x)
    e = x - x.mean()
    s = (e @ e) / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * ((e[k:] @ e[:-k]) / n)
    return float(np.sqrt(max(s, 1e-18) / n))


# ---------------------------------------------------------------- 1. Reality Check
def reality_check(R: pd.DataFrame, n_boot=N_BOOT, block=BLOCK, seed=SEED, studentized=False):
    """White (2000)。H0：所有策略的期望收益 ≤ 0。"""
    X = R.fillna(0.0).to_numpy()
    T = X.shape[0]
    mu = X.mean(axis=0)
    if studentized:
        se = np.array([nw_se(X[:, k]) for k in range(X.shape[1])])
        V = float((mu / se).max())
    else:
        se = None
        V = float(np.sqrt(T) * mu.max())
    rng = np.random.default_rng(seed)
    Vb = np.empty(n_boot)
    for b in range(n_boot):
        idx = stationary_bootstrap_idx(T, block, rng)
        Xb = X[idx]
        mb = Xb.mean(axis=0)
        if studentized:
            Vb[b] = ((mb - mu) / se).max()
        else:
            Vb[b] = np.sqrt(T) * (mb - mu).max()
    p = float((Vb >= V).mean())
    return {"统计量": V, "p值": p, "最优组合": R.columns[int(mu.argmax())],
            "n_boot": n_boot, "studentized": studentized}


# ---------------------------------------------------------------- 2. Hansen SPA
def hansen_spa(R: pd.DataFrame, n_boot=N_BOOT, block=BLOCK, seed=SEED):
    """Hansen (2005) SPA。对表现差的策略做 recentering 以降低其影响。"""
    X = R.fillna(0.0).to_numpy()
    T = X.shape[0]
    mu = X.mean(axis=0)
    se = np.array([nw_se(X[:, k]) for k in range(X.shape[1])])
    t = mu / se
    V = float(max(0.0, t.max()))
    # 「劣质策略」阈值：Hansen 建议 -sqrt(2 log log T)
    thr = -np.sqrt(2 * np.log(np.log(T))) if T > 3 else -1.0
    g = np.where(t >= thr, mu, 0.0)
    rng = np.random.default_rng(seed)
    Vb = np.empty(n_boot)
    for b in range(n_boot):
        idx = stationary_bootstrap_idx(T, block, rng)
        mb = X[idx].mean(axis=0)
        z = (mb - g) / se
        Vb[b] = max(0.0, z.max())
    p = float((Vb >= V).mean())
    return {"统计量": V, "p值": p, "最优组合": R.columns[int(t.argmax())],
            "劣质策略阈值": float(thr), "n_poor": int((t < thr).sum())}


# ---------------------------------------------------------------- 2b. Romano--Wolf
def romano_wolf(R: pd.DataFrame, n_boot=N_BOOT, block=BLOCK, seed=SEED,
                alpha: float = 0.05) -> dict:
    """Romano--Wolf (2005) 逐步多重检验。

    与单步的 Reality Check 的差别：RC 只回答"最强的那个是否显著"，
    RW 给出\emph{每一个}假设的逐步校正 p 值，在控制族错误率（FWER）的同时
    保留更多功效（逐步法逐步缩小比较集，越靠后的假设面对的临界值越松）。

    算法：把 t 统计量由大到小排序；第 j 步只在剩余假设集合 {j, j+1, ...} 上
    取自举最大值作为临界分布；一旦某步不拒绝即停止，其后假设一律不拒绝。

    依赖同一次自举抽样（所有步共用），这是该方法与"逐条单独检验再加校正"的本质区别。
    """
    X = R.fillna(0.0).to_numpy()
    T, N = X.shape
    mu = X.mean(axis=0)
    se = np.array([nw_se(X[:, k]) for k in range(N)])
    se = np.where(se > 0, se, np.inf)
    t = mu / se
    order = np.argsort(-t)                      # t 由大到小

    rng = np.random.default_rng(seed)
    tb = np.empty((n_boot, N))
    for b in range(n_boot):
        idx = stationary_bootstrap_idx(T, block, rng)
        tb[b] = (X[idx].mean(axis=0) - mu) / se   # 再中心化（studentized）

    p_adj = np.ones(N)
    rejected = np.zeros(N, dtype=bool)
    steps, stopped = [], False
    for j in range(N):
        k = order[j]
        if stopped:
            p_adj[k] = 1.0
            continue
        rest = order[j:]
        stat = float(t[rest].max())
        boot = tb[:, rest].max(axis=1)
        p = float((boot >= stat).mean())
        p_adj[k] = p
        steps.append({"第几步": j + 1, "假设": R.columns[k],
                      "t": float(t[k]), "剩余假设数": int(len(rest)),
                      "逐步校正p": p})
        if p <= alpha:
            rejected[k] = True
        else:
            stopped = True
    return {"n_rejected": int(rejected.sum()), "alpha": alpha,
            "rejected": [R.columns[k] for k in np.where(rejected)[0]],
            "p_adj": {R.columns[k]: float(p_adj[k]) for k in range(N)},
            "steps": steps, "n_boot": n_boot}


# ---------------------------------------------------------------- 3. 紧缩夏普
def deflated_sharpe(sr_hat: float, T: int, skew: float, kurt: float,
                    sr_trials: np.ndarray) -> dict:
    """Bailey & López de Prado (2014) 紧缩夏普比率。

    sr_hat 为日频夏普；sr_trials 为全部试验的日频夏普（用于估计 SR 的横截面方差）。
    """
    N = len(sr_trials)
    gamma = 0.5772156649
    if N <= 1:
        sr0 = 0.0
    else:
        var_sr = float(np.var(sr_trials, ddof=1))
        if var_sr <= 0 or not np.isfinite(var_sr):
            sr0 = 0.0
        else:
            z1 = stats.norm.ppf(1 - 1.0 / N)
            z2 = stats.norm.ppf(1 - 1.0 / (N * np.e))
            sr0 = np.sqrt(var_sr) * ((1 - gamma) * z1 + gamma * z2)
    denom = np.sqrt(max(1e-12, 1 - skew * sr_hat + (kurt - 1) / 4.0 * sr_hat ** 2))
    dsr = float(stats.norm.cdf((sr_hat - sr0) * np.sqrt(T - 1) / denom))
    return {"SR_hat(日)": float(sr_hat), "SR0(日,期望最大值)": float(sr0),
            "DSR": dsr, "N_trials": N}


# ---------------------------------------------------------------- 4. PBO / CSCV
def pbo_cscv(R: pd.DataFrame, n_splits: int = 10) -> dict:
    """Bailey 等 (2016) 的 CSCV 过拟合概率。"""
    from itertools import combinations
    X = R.fillna(0.0).to_numpy()
    T, N = X.shape
    if N < 2:
        return {"PBO": float("nan")}
    b = T // n_splits
    blocks = [X[i * b:(i + 1) * b] for i in range(n_splits)]
    half = n_splits // 2
    logits, oos_ranks = [], []
    for combo in combinations(range(n_splits), half):
        is_idx = set(combo)
        IS = np.vstack([blocks[i] for i in is_idx])
        OOS = np.vstack([blocks[i] for i in range(n_splits) if i not in is_idx])
        sr_is = IS.mean(axis=0) / (IS.std(axis=0, ddof=1) + 1e-12)
        n_star = int(sr_is.argmax())
        sr_oos = OOS.mean(axis=0) / (OOS.std(axis=0, ddof=1) + 1e-12)
        # 相对排名 ω ∈ (0,1)
        r = stats.rankdata(sr_oos)[n_star] / (N + 1)
        oos_ranks.append(r)
        logits.append(np.log(r / (1 - r)))
    logits = np.array(logits)
    return {"PBO": float((logits < 0).mean()),
            "n_combinations": int(len(logits)),
            "OOS相对排名均值": float(np.mean(oos_ranks))}


# ---------------------------------------------------------------- 主流程
def main():
    gp = C.OUT / "grid_returns.parquet"
    if not gp.exists():
        raise SystemExit("请先运行 run_grid.py 生成网格收益矩阵")
    R = pd.read_parquet(gp)
    print("=" * 96)
    print(f"多重检验校正：{R.shape[1]} 个参数组合，{R.shape[0]} 个交易日")
    print("=" * 96)

    sr = R.mean() / R.std(ddof=1) * np.sqrt(252)
    top = sr.sort_values(ascending=False).head(5)
    print("\n【校正前】夏普最高的 5 个组合：")
    for k, v in top.items():
        print(f"    {k:34s} 年化夏普 {v:6.2f}")

    res = {}
    print("\n[1/4] White Reality Check（自举 {n} 次，平均块长 {b}）".format(n=N_BOOT, b=BLOCK))
    rc = reality_check(R, studentized=False)
    rcs = reality_check(R, studentized=True)
    print(f"    非 studentized：统计量 {rc['统计量']:.2f}，p = {rc['p值']:.4f}")
    print(f"    studentized  ：统计量 {rcs['统计量']:.2f}，p = {rcs['p值']:.4f}")
    res["reality_check"] = rc
    res["reality_check_studentized"] = rcs

    print("\n[2/4] Hansen SPA 检验")
    spa = hansen_spa(R)
    print(f"    统计量 {spa['统计量']:.2f}，p = {spa['p值']:.4f}；"
          f"劣质策略阈值 {spa['劣质策略阈值']:.2f}，劣质数 {spa['n_poor']}/{R.shape[1]}")
    res["hansen_spa"] = spa

    print("\n[2b/4] Romano--Wolf 逐步多重检验")
    rw = romano_wolf(R)
    print(f"    在 FWER 5% 下拒绝 {rw['n_rejected']}/{R.shape[1]} 个假设")
    if rw["steps"]:
        print("    逐步检验轨迹（前 5 步）：")
        for s in rw["steps"][:5]:
            print(f"      第 {s['第几步']} 步  {s['假设']:<28s} "
                  f"t={s['t']:6.2f}  剩余 {s['剩余假设数']:2d} 个  "
                  f"逐步校正 p={s['逐步校正p']:.4f}")
    if rw["rejected"]:
        print(f"    被拒绝：{rw['rejected']}")
    res["romano_wolf"] = rw

    print("\n[3/4] 紧缩夏普比率（DSR）")
    best = sr.idxmax()
    x = R[best].dropna()
    # 注意口径一致：DSR 公式中的 SR 与试验分布必须同为日频（不做年化）
    sr_daily = R.mean() / R.std(ddof=1)
    sr_hat_d = float(sr_daily[best])
    dsr = deflated_sharpe(sr_hat=sr_hat_d, T=len(x),
                          skew=float(x.skew()), kurt=float(x.kurtosis()) + 3.0,
                          sr_trials=sr_daily.dropna().to_numpy())
    print(f"    最优组合 {best}：日夏普 {dsr['SR_hat(日)']:.4f}（年化 {sr[best]:.2f}），"
          f"60 次试验下的期望最大值 SR0(日) {dsr['SR0(日,期望最大值)']:.4f}，"
          f"DSR = {dsr['DSR']:.4f}")
    res["deflated_sharpe"] = dsr | {"best": best, "年化夏普": float(sr[best])}

    print("\n[4/4] 回测过拟合概率（PBO / CSCV，S=10）")
    pbo = pbo_cscv(R, n_splits=10)
    print(f"    PBO = {pbo['PBO']:.4f}（{pbo['n_combinations']} 个组合切分；"
          f"OOS 相对排名均值 {pbo['OOS相对排名均值']:.3f}）")
    res["pbo"] = pbo

    print("\n" + "-" * 96)
    verdict = []
    if rc["p值"] > 0.05:
        verdict.append("Reality Check 不拒绝：最优组合的超额收益在数据窥探下不显著")
    if spa["p值"] > 0.05:
        verdict.append("Hansen SPA 不拒绝：无法认定存在真实的超额收益")
    if rw["n_rejected"] == 0:
        verdict.append("Romano--Wolf 在 FWER 5% 下未拒绝任何假设：无组合能通过族错误率控制")
    if res["deflated_sharpe"]["DSR"] < 0.95:
        verdict.append(f"DSR = {res['deflated_sharpe']['DSR']:.3f} < 0.95：最优夏普不高于"
                       f"「{R.shape[1]} 次试验下的期望最大值」")
    if pbo["PBO"] > 0.5:
        verdict.append(f"PBO = {pbo['PBO']:.2f} > 0.5：样本内最优在样本外低于中位数的概率过半")
    if not verdict:
        print("结论：四项校正均通过，最优组合可进入下一步（Phase 3 执行层对照）")
    else:
        print("结论：以下校正未通过，相关规则不得直接上线——")
        for v in verdict:
            print(f"  · {v}")
    res["verdict"] = verdict

    (C.OUT / "multipletest_results.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\n结果已写出 {C.OUT / 'multipletest_results.json'}")


if __name__ == "__main__":
    main()