# -*- coding: utf-8 -*-
"""规则三：期货协整配对筛选算法 + 阈值交易回测。

对应《趋势跟踪与均值回归交易规则》第 5 节。筛选流程分七步：
  S1 产业链分组          → 候选对生成
  S2 相关性初筛
  S3 Engle--Granger 协整检验（OLS + ADF）
  S4 OU 参数估计（AR(1) → theta、半衰期）
  S5 半衰期区间筛选 [5, 60] 交易日
  S6 滚动重估（形成期 60 日 / 交易期 21 日）
  S7 生成可交易对表（含对冲比率、均值、标准差）

交易规则：标准化价差 z 的阈值进出场（开仓 |z|>2.0、平仓 |z|<0.5、止损 |z|>3.5、
时间止损 3H），对冲比率用 Kalman 滤波在线更新（可选静态）。

用法：
    python rule3_pairs.py --screen        # 只跑筛选，输出可交易对表
    python rule3_pairs.py --backtest      # 筛选 + 阈值交易回测
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller

import common as C

# 产业链划分（同《交易规则》表 12）
CHAINS = {
    "黑色": ["RB", "HC", "I", "J", "JM", "SF", "SM"],
    "能化": ["MA", "PP", "L", "TA", "EG", "V", "BU", "SC", "FU"],
    "有色": ["CU", "AL", "ZN", "NI", "SN", "PB"],
    "农产品": ["M", "Y", "P", "C", "CS", "OI", "RM", "SR", "CF", "AP"],
    "油脂": ["A", "B", "M", "Y", "P", "OI"],
}


class Rule3Config:
    FORM = 60          # 形成期（交易日）
    TRADE = 21         # 交易期（交易日）
    MIN_CORR = 0.6     # S2 相关性下限
    ADF_P = 0.05       # S3 协整显著性
    HL_LO, HL_HI = 5.0, 60.0   # S5 半衰期区间（交易日）
    Z_OPEN = 2.0       # 开仓阈值
    Z_CLOSE = 0.5      # 平仓阈值
    Z_STOP = 3.5       # 止损阈值
    TIME_STOP_X = 3.0  # 时间止损：持仓超过 TIME_STOP_X × 半衰期
    MAX_PAIRS = 20     # 同时持仓上限
    TOTAL_RISK = 0.30  # 总风险预算（1 倍标准差价差变动对应的资金敞口）
    KALMAN = True
    USE_EG_CRIT = True # True：用 Engle--Granger 专用临界值；False：用标准 ADF p 值
    KALMAN_Q = 1e-5    # Kalman 状态噪声
    KALMAN_R = 1e-3    # Kalman 观测噪声


# ------------------------------------------------------------------ S1--S5 筛选
def eg_crit(T: int, n_vars: int = 2, level: float = 0.05) -> float:
    """Engle--Granger 协整检验的专用临界值（MacKinnon 响应面）。

    标准 ADF 临界值（约 -2.86/-2.89）适用于「已知无协整关系」的单序列单位根检验；
    协整检验的残差是估计出来的，其分布左移，必须用更负的临界值，否则会系统性高估通过率。

    MacKinnon (1991) 响应面：crit = b_inf + b1/T + b2/T^2，n_vars=2（含常数项）。

    返回负的临界值；ADF 统计量小于它才判定协整。
    """
    table = {
        0.01: (-3.9001, -10.534, -30.03),
        0.05: (-3.3377, -5.967, -8.98),
        0.10: (-3.0462, -4.069, -5.73),
    }
    b_inf, b1, b2 = table.get(level, table[0.05])
    return b_inf + b1 / T + b2 / (T * T)


def ou_params(resid: np.ndarray, dt: float = 1.0) -> tuple[float, float]:
    """对价差残差拟合 AR(1)：e_{t+1}=c+phi*e_t+u，返回 (phi, 半衰期)。"""
    x, y = resid[:-1], resid[1:]
    if len(x) < 20:
        return np.nan, np.nan
    A = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    phi = float(beta[1])
    if not np.isfinite(phi) or phi <= 0 or phi >= 1:
        return phi, np.nan
    hl = dt * np.log(2.0) / (-np.log(phi))
    return phi, float(hl)


def screen_pair(pa: pd.Series, pb: pd.Series, cfg: Rule3Config) -> dict | None:
    """对单个候选对做 S2--S5 全套检验。pa/pb 为形成期对数价格。"""
    df = pd.concat([pa, pb], axis=1).dropna()
    if len(df) < cfg.FORM * 0.6:
        return None
    xa, xb = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    # S2 相关性初筛
    corr = float(np.corrcoef(xa, xb)[0, 1])
    if not np.isfinite(corr) or corr < cfg.MIN_CORR:
        return {"_reject": "corr"}
    # S3 Engle--Granger：OLS ln A ~ ln B，残差 ADF
    A = np.column_stack([np.ones_like(xb), xb])
    coef, *_ = np.linalg.lstsq(A, xa, rcond=None)
    alpha, beta = float(coef[0]), float(coef[1])
    resid = xa - (alpha + beta * xb)
    try:
        adf_stat, adf_p, _usedlag, _nobs, crit_std, *_ = adfuller(
            resid, autolag="AIC", regression="c")
    except Exception:
        return {"_reject": "adf_err"}
    # 协整检验必须用 EG 专用临界值（比标准 ADF 更负）
    crit_eg = eg_crit(len(resid), 2, cfg.ADF_P)
    use_stat = cfg.USE_EG_CRIT
    passed = (float(adf_stat) < crit_eg) if use_stat else (adf_p <= cfg.ADF_P)
    if not passed:
        return {"_reject": "adf", "adf_p": adf_p, "corr": corr,
                "adf_stat": float(adf_stat), "crit_eg": float(crit_eg),
                "crit_std": float(crit_std["5%"]),
                "near_miss": bool(float(adf_stat) < float(crit_std["5%"]))}
    # S4 OU 参数
    phi, hl = ou_params(resid)
    if not np.isfinite(hl):
        return {"_reject": "ou", "corr": corr, "adf_p": adf_p}
    # S5 半衰期区间
    if not (cfg.HL_LO <= hl <= cfg.HL_HI):
        return {"_reject": "halflife", "corr": corr, "adf_p": adf_p, "hl": hl}
    return {"_ok": True, "corr": corr, "adf_p": float(adf_p), "adf_stat": float(adf_stat),
            "alpha": alpha, "beta": beta, "phi": phi, "halflife": hl,
            "mu": float(resid.mean()), "sd": float(resid.std(ddof=1)),
            "n": len(df)}


def screen_all(cfg: Rule3Config | None = None, verbose=True) -> pd.DataFrame:
    """S1--S6：对所有产业链内候选对做滚动筛选，返回每个形成期的通过对。"""
    cfg = cfg or Rule3Config()
    ohlc = C.load_futures_ohlc()
    close = ohlc["close"]
    logp = np.log(close.where(close > 0))

    pairs = []
    seen = set()
    for chain, syms in CHAINS.items():
        avail = [s for s in syms if s in logp.columns]
        for i in range(len(avail)):
            for j in range(i + 1, len(avail)):
                key = tuple(sorted((avail[i], avail[j])))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append((chain, key[0], key[1]))
    if verbose:
        print(f"S1 候选对生成：{len(pairs)} 对，覆盖 {len(CHAINS)} 条产业链")

    rows = []
    rejects = {}
    near_miss = 0
    starts = range(cfg.FORM, len(logp.index) - cfg.TRADE, cfg.TRADE)
    for s in starts:
        f0, f1 = s - cfg.FORM, s
        d_form = logp.index[f1 - 1]
        for chain, sa, sb in pairs:
            if sa not in logp.columns or sb not in logp.columns:
                continue
            r = screen_pair(logp[sa].iloc[f0:f1], logp[sb].iloc[f0:f1], cfg)
            if r is None:
                continue
            if "_reject" in r:
                rejects[r["_reject"]] = rejects.get(r["_reject"], 0) + 1
                if r.get("near_miss"):
                    near_miss += 1
                continue
            rows.append({"form_end": d_form, "chain": chain, "A": sa, "B": sb,
                         "corr": r["corr"], "adf_p": r["adf_p"], "adf_stat": r["adf_stat"],
                         "beta": r["beta"], "halflife": r["halflife"], "mu": r["mu"],
                         "sd": r["sd"], "alpha": r["alpha"]})
    res = pd.DataFrame(rows)
    if verbose:
        print(f"S2--S5 筛选完成（临界值口径："
              f"{'EG 专用' if cfg.USE_EG_CRIT else '标准 ADF'}）："
              f"通过 {len(res)} 条（候选 {len(pairs) * len(list(starts))} 次检验）")
        if rejects:
            print("      拒绝原因分布："
                  + "，".join(f"{k}={v}" for k, v in sorted(rejects.items())))
        if cfg.USE_EG_CRIT and near_miss:
            print(f"      [关键] 其中 {near_miss} 次通过标准 ADF 5% 但未通过 EG 专用临界值"
                  f"（{near_miss / max(1, sum(rejects.values())) * 100:.1f}% 的拒绝来自口径修正）")
        if len(res):
            print(f"      平均相关系数 {res['corr'].mean():.3f}；"
                  f"平均 ADF p {res['adf_p'].mean():.4f}；"
                  f"半衰期中位数 {res['halflife'].median():.1f} 交易日")
            print(f"      通过数最多的产业链：{res['chain'].value_counts().head(3).to_dict()}")
    return res


# ------------------------------------------------------------------ 交易回测
def kalman_beta(xa: np.ndarray, xb: np.ndarray, q=1e-5, r=1e-3,
                beta0=None) -> np.ndarray:
    """对 ln A = alpha + beta ln B 做随机游走系数的 Kalman 滤波。

    返回**一步前瞻**的 beta_t：即在观测到第 t 期之前对 beta 的预测值。
    这一点至关重要——若返回「吸收当期观测后」的 beta，则价差 e_t 会被当期价格拟合，
    残差呈现人为的均值回归，回测会产生虚高的夏普（本文首版即因此得到不可信的 3.51）。
    """
    n = len(xa)
    theta = np.array([0.0, beta0 if beta0 is not None else 1.0])   # [alpha, beta]
    P = np.eye(2) * 1.0
    Q = np.eye(2) * q
    out = np.empty(n)
    for t in range(n):
        F = np.array([1.0, xb[t]])
        out[t] = theta[1]                     # 先记录前瞻 beta（未使用第 t 期观测）
        yhat = F @ theta
        S = F @ P @ F.T + r
        K = (P @ F.T) / S
        theta = theta + K * (xa[t] - yhat)    # 再用第 t 期观测更新
        P = P - np.outer(K, F) @ P + Q
    return out


def backtest_pairs(cfg: Rule3Config | None = None, verbose=True, screened=None):
    """S7 + 阈值交易。

    两处关键口径（修正首版缺陷）：
      1. z 用「形成期 + 已过去交易期」的滚动 60 日均值与标准差计算，而非形成期常数
         （形成期 sd 不能代表交易期波动，会导致 |z| 虚高、开仓即平仓）；
      2. 每对按风险预算归一：1 倍标准差价差变动对应 risk_per_pair 的资金敞口，
         日损益 ≈ 方向 × Δz × risk_per_pair，避免多对敞口直接相加。
    """
    cfg = cfg or Rule3Config()
    if screened is None:
        screened = screen_all(cfg, verbose=verbose)
    if screened.empty:
        print("无通过筛选的配对，回测终止")
        return None
    ohlc = C.load_futures_ohlc()
    close = ohlc["close"]
    logp = np.log(close.where(close > 0))
    dates = logp.index
    by_form = {d: g for d, g in screened.groupby("form_end")}
    form_ends = sorted(by_form.keys())

    risk_per_pair = cfg.TOTAL_RISK / cfg.MAX_PAIRS
    pnl = np.zeros(len(dates))
    turn = np.zeros(len(dates))
    trades = []
    n_open = np.zeros(len(dates))

    for d0 in form_ends:
        i0 = dates.get_loc(d0)
        i1 = min(i0 + cfg.TRADE, len(dates))
        window = by_form[d0].sort_values("halflife").head(cfg.MAX_PAIRS)
        for _, row in window.iterrows():
            A, B = row["A"], row["B"]
            f0 = max(0, i0 - cfg.FORM)
            pa_f = logp[A].iloc[f0:i0].to_numpy()
            pb_f = logp[B].iloc[f0:i0].to_numpy()
            pa_t = logp[A].iloc[i0:i1].to_numpy()
            pb_t = logp[B].iloc[i0:i1].to_numpy()
            if (len(pa_f) < 30 or len(pa_t) < 3
                    or np.isnan(pa_f).any() or np.isnan(pb_f).any()
                    or np.isnan(pa_t).any() or np.isnan(pb_t).any()):
                continue
            # 价差序列：在「形成期 + 交易期」全程用同一条因果 Kalman 估计 beta，
            # 避免两段使用不同 beta 定义造成接缝处 z 失真
            pa_all = np.concatenate([pa_f, pa_t])
            pb_all = np.concatenate([pb_f, pb_t])
            if cfg.KALMAN:
                betas = kalman_beta(pa_all, pb_all, q=cfg.KALMAN_Q, r=cfg.KALMAN_R,
                                    beta0=row["beta"])
            else:
                betas = np.full(len(pa_all), row["beta"])
            e_all = pa_all - betas * pb_all
            s = pd.Series(e_all)
            mu = s.rolling(60, min_periods=40).mean().to_numpy()
            sd = s.rolling(60, min_periods=40).std(ddof=1).to_numpy()
            with np.errstate(invalid="ignore", divide="ignore"):
                z = (e_all - mu) / sd
            z = np.where(np.isfinite(z), z, 0.0)

            state, entry_i = 0, None
            hl = max(row["halflife"], 1.0)
            seg_start = cfg.FORM - 1
            for t in range(cfg.FORM, len(z)):
                zt = z[t]
                if state == 0:
                    if zt > cfg.Z_OPEN:
                        state, entry_i, seg_start = -1, t, t
                        turn[i0 + (t - cfg.FORM)] += risk_per_pair
                    elif zt < -cfg.Z_OPEN:
                        state, entry_i, seg_start = 1, t, t
                        turn[i0 + (t - cfg.FORM)] += risk_per_pair
                else:
                    dpnl = state * (z[t] - z[t - 1]) * risk_per_pair
                    pnl[i0 + (t - cfg.FORM)] += dpnl
                    exit_now = (abs(zt) < cfg.Z_CLOSE or abs(zt) > cfg.Z_STOP
                                or (t - entry_i) > cfg.TIME_STOP_X * hl)
                    if exit_now:
                        cost = 2 * C.COST_BPS["futures"] / 1e4 * risk_per_pair
                        pnl[i0 + (t - cfg.FORM)] -= cost
                        turn[i0 + (t - cfg.FORM)] += risk_per_pair
                        trades.append({"form_end": d0, "A": A, "B": B, "dir": state,
                                       "days": t - entry_i,
                                       "z_span": float(z[t] - z[entry_i])})
                        state, entry_i = 0, None
                n_open[i0 + (t - cfg.FORM)] += (state != 0)

    net = pd.Series(pnl, index=dates)
    gross = net.copy()
    turn_s = pd.Series(turn, index=dates)
    m = C.metrics(net, gross, turn_s)
    m["_n_trades"] = len(trades)
    m["_n_pairs_screened"] = int(len(screened))
    m["_avg_hold_days"] = float(np.mean([t["days"] for t in trades])) if trades else float("nan")
    m["_avg_open"] = float(n_open[n_open > 0].mean()) if (n_open > 0).any() else 0.0
    if verbose:
        print(f"\nS7 交易回测：成交 {len(trades)} 笔；平均持仓 "
              f"{m['_avg_hold_days']:.1f} 天；在有仓日的平均同时持仓对数 {m['_avg_open']:.1f}")
        C.print_metrics("规则三 期货协整配对 L=60", m)
        print("      注：成本与冲击已按每笔往返计；敞口按风险预算归一（总风险 30%）")
    return {"metrics": m, "screened": screened, "trades": pd.DataFrame(trades)}


def compare_critical_values(cfg: Rule3Config | None = None):
    """对照「标准 ADF p 值」与「Engle--Granger 专用临界值」两种口径的通过率。"""
    cfg = cfg or Rule3Config()
    print("=" * 96)
    print("S3 临界值口径对照：标准 ADF vs Engle--Granger 专用临界值")
    print("=" * 96)
    out = {}
    for use_eg in (False, True):
        c = Rule3Config()
        c.USE_EG_CRIT = use_eg
        res = screen_all(c, verbose=False)
        tag = "EG 专用临界值" if use_eg else "标准 ADF p 值"
        n_pass = len(res)
        hl_med = float(res["halflife"].median()) if n_pass else float("nan")
        adf_med = float(res["adf_stat"].median()) if n_pass else float("nan")
        out[tag] = {"通过条数": n_pass, "半衰期中位数": hl_med, "ADF统计量中位数": adf_med}
        print(f"  {tag:16s}：通过 {n_pass:4d} 条；"
              f"通过者 ADF 统计量中位数 {adf_med:6.2f}；半衰期中位数 {hl_med:5.1f} 日")
    T = cfg.FORM
    print(f"\n  EG 专用 5% 临界值（T={T}，MacKinnon 响应面）= {eg_crit(T, 2, 0.05):.4f}")
    print(f"  标准 ADF 5% 临界值（近似）                = -2.86")
    if len(out) == 2:
        a = list(out.values())
        if a[0]["通过条数"]:
            print(f"\n  口径修正使通过数由 {a[0]['通过条数']} 降至 {a[1]['通过条数']}，"
                  f"减少 {1 - a[1]['通过条数'] / a[0]['通过条数']:.1%}")
    return out


def kalman_sensitivity(cfg: Rule3Config | None = None):
    """Kalman q/r 参数敏感性：不同状态噪声与观测噪声下的交易表现。"""
    cfg = cfg or Rule3Config()
    print("=" * 96)
    print("Kalman q/r 参数敏感性")
    print("=" * 96)
    base = screen_all(cfg, verbose=False)      # 筛选只需做一次，与 q/r 无关
    if base.empty:
        print("无通过筛选的配对，跳过")
        return pd.DataFrame()
    rows = []
    for q in (1e-6, 1e-5, 1e-4):
        for r in (1e-4, 1e-3, 1e-2):
            c = Rule3Config()
            c.KALMAN_Q, c.KALMAN_R = q, r
            c.USE_EG_CRIT = cfg.USE_EG_CRIT
            out = backtest_pairs(c, verbose=False, screened=base)
            m = out["metrics"] if out else {}
            rows.append({"q": q, "r": r, "夏普": m.get("Sharpe", float("nan")),
                         "年化": m.get("年化收益", float("nan")),
                         "成交笔数": m.get("_n_trades", 0),
                         "平均持仓天数": m.get("_avg_hold_days", float("nan"))})
            print(f"  q={q:.0e} r={r:.0e}  夏普 {rows[-1]['夏普']:6.2f}  "
                  f"年化 {rows[-1]['年化']*100:7.2f}%  成交 {rows[-1]['成交笔数']:3d} 笔  "
                  f"平均持仓 {rows[-1]['平均持仓天数']:5.1f} 天")
    df = pd.DataFrame(rows)
    print(f"\n  夏普跨参数标准差 {df['夏普'].std():.2f}；"
          f"成交笔数范围 [{df['成交笔数'].min()}, {df['成交笔数'].max()}]")
    df.to_csv(C.OUT / "rule3_kalman_sensitivity.csv", index=False, encoding="utf-8-sig")
    print(f"  已写出 {C.OUT / 'rule3_kalman_sensitivity.csv'}")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--compare-crit", action="store_true",
                    help="对照标准 ADF 与 EG 专用临界值")
    ap.add_argument("--kalsens", action="store_true", help="Kalman q/r 敏感性")
    ap.add_argument("--no-eg-crit", action="store_true",
                    help="退回标准 ADF p 值口径")
    args = ap.parse_args()
    cfg = Rule3Config()
    if args.no_eg_crit:
        cfg.USE_EG_CRIT = False

    if args.compare_crit:
        compare_critical_values()
        return
    if args.kalsens:
        kalman_sensitivity(cfg)
        return

    print("=" * 96)
    print("规则三：期货协整配对筛选与阈值交易")
    print("=" * 96)
    if args.screen and not args.backtest:
        res = screen_all(cfg)
        outp = C.OUT / "rule3_screened_pairs.csv"
        res.to_csv(outp, index=False, encoding="utf-8-sig")
        print(f"\n可交易对表已写出 {outp}（{len(res)} 条）")
        return
    out = backtest_pairs(cfg)
    if out is None:
        return
    out["screened"].to_csv(C.OUT / "rule3_screened_pairs.csv", index=False,
                           encoding="utf-8-sig")
    out["trades"].to_csv(C.OUT / "rule3_trades.csv", index=False, encoding="utf-8-sig")
    (C.OUT / "rule3_results.json").write_text(
        json.dumps(out["metrics"], ensure_ascii=False, indent=2, default=float),
        encoding="utf-8")
    print(f"\n结果已写出 {C.OUT}")


if __name__ == "__main__":
    main()