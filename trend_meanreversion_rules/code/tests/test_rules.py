# -*- coding: utf-8 -*-
"""规则框架的回归测试。

覆盖四类：
  1. 共享层（成本、涨跌停、指标）的数值正确性
  2. 策略对称性（G1 门禁：符号翻转后毛收益严格相反、换手相同）
  3. 统计工具的已知性质（EG 临界值、OU 半衰期回收、自举检验的功效）
  4. 多重检验的思想校验（噪声下不拒绝、强信号下拒绝）

运行：
    cd code && python -m pytest tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common as C            # noqa: E402
import multipletest as MT     # noqa: E402
import rule3_pairs as R3      # noqa: E402


# ---------------------------------------------------------------- 工具
def make_ret(T=400, K=6, seed=0, mu=0.0, sd=0.01) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=T)
    cols = [f"A{i}" for i in range(K)]
    return pd.DataFrame(rng.normal(mu, sd, size=(T, K)), index=idx, columns=cols)


# ---------------------------------------------------------------- 1. 共享层
def test_limit_pct_board_classification():
    assert C.limit_pct("600519") == 0.10      # 主板
    assert C.limit_pct("000001") == 0.10
    assert C.limit_pct("300750") == 0.20      # 创业板
    assert C.limit_pct("301001") == 0.20
    assert C.limit_pct("688981") == 0.20      # 科创板
    assert C.limit_pct("689009") == 0.20


def test_tradable_mask_detects_limits():
    px = pd.DataFrame({"x": [10.0, 11.0, 12.1]})
    ret = px.pct_change()
    m = C.tradable_mask(px, ret)
    assert bool(m.iloc[2]["x"]) is False      # +10% 触及主板涨停
    # 创业板同样 +10% 不应被判为涨停
    px2 = pd.DataFrame({"y": [10.0, 11.0]})
    res2 = C.tradable_mask(px2, px2.pct_change(), code_of=lambda c: "300001")
    assert bool(res2.iloc[1]["y"]) is True


def test_metrics_sharpe_and_mdd_match_hand_calc():
    # metrics() 依赖月频重采样计算月胜率，因此必须提供 DatetimeIndex
    r = pd.Series([0.01, -0.02, 0.03, 0.00, 0.01] * 60,
                  index=pd.bdate_range("2020-01-01", periods=300))
    m = C.metrics(r, r, pd.Series(0.0, index=r.index))
    expect_sharpe = r.mean() / r.std(ddof=1) * np.sqrt(252)
    assert m["Sharpe"] == pytest.approx(expect_sharpe, rel=1e-9)
    nav = (1 + r).cumprod()
    expect_mdd = ((nav / nav.cummax()) - 1).min()
    assert m["最大回撤"] == pytest.approx(expect_mdd, rel=1e-9)
    # 无成本时毛利 = 净收益
    assert m["成本拖累年化"] == pytest.approx(0.0, abs=1e-12)


def test_metrics_handles_constant_series():
    r = pd.Series(0.0, index=pd.bdate_range("2020-01-01", periods=100))
    m = C.metrics(r, r, pd.Series(0.0, index=r.index))
    assert np.isnan(m["Sharpe"]) or m["Sharpe"] == 0.0
    assert m["最大回撤"] == pytest.approx(0.0)


def test_cost_gate_boundary():
    assert C.cost_gate_ok({"成本占毛利比": 0.20}, 3.0) is True    # 毛利/成本 = 5
    assert C.cost_gate_ok({"成本占毛利比": 0.34}, 3.0) is False   # 2.94 < 3
    # 毛利非正时（比值 ≤ 0）不判失败，交由上游核查
    assert C.cost_gate_ok({"成本占毛利比": -0.5}, 3.0) is True


# ---------------------------------------------------------------- 2. 对称性（G1）
def test_sign_symmetry_exact_without_drift():
    """G1 门禁：符号翻转后毛收益应严格互为相反数、换手完全相同。"""
    ret = make_ret(T=300, K=5, seed=1)
    rb = ret.index[50::21]
    rng = np.random.default_rng(7)
    W = pd.DataFrame(rng.normal(0, 0.2, size=(len(rb), ret.shape[1])),
                     index=rb, columns=ret.columns)
    n1, g1, t1 = C.run_weights_backtest(ret, W, 2.0, hold_drift=False)
    n2, g2, t2 = C.run_weights_backtest(ret, -W, 2.0, hold_drift=False)
    assert np.allclose(g1.to_numpy(), -g2.to_numpy())
    assert np.allclose(t1.to_numpy(), t2.to_numpy())
    # 成本为不区分方向的常数扣项
    assert np.allclose((n1 - g1).to_numpy(), (n2 - g2).to_numpy())


def test_sign_symmetry_approx_with_drift():
    """含权重漂移时对称性只是近似——漂移分母 (1±r) 不同。"""
    ret = make_ret(T=300, K=5, seed=2)
    rb = ret.index[50::21]
    rng = np.random.default_rng(8)
    W = pd.DataFrame(rng.normal(0, 0.2, size=(len(rb), ret.shape[1])),
                     index=rb, columns=ret.columns)
    n1, g1, t1 = C.run_weights_backtest(ret, W, 2.0, hold_drift=True)
    n2, g2, t2 = C.run_weights_backtest(ret, -W, 2.0, hold_drift=True)
    assert np.corrcoef(g1.to_numpy(), g2.to_numpy())[0, 1] < -0.999
    assert (g1 + g2).abs().mean() < 0.1 * g1.abs().mean()


# ---------------------------------------------------------------- 3. 统计工具
def test_eg_crit_matches_mackinnon_at_T60():
    assert R3.eg_crit(60, 2, 0.05) == pytest.approx(-3.4396, abs=1e-4)


def test_eg_crit_stricter_than_standard_adf():
    # EG 专用临界值必须比标准 ADF 的 -2.86 更负，否则口径修正无意义
    for T in (30, 60, 120, 500):
        assert R3.eg_crit(T, 2, 0.05) < -2.86


def test_eg_crit_monotone_in_T():
    vals = [R3.eg_crit(T, 2, 0.05) for T in (30, 60, 120, 250, 1000)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))   # 样本越长越接近渐近值


def test_ou_params_recovers_halflife():
    rng = np.random.default_rng(3)
    phi_true, T = 0.9, 4000
    e = np.zeros(T)
    for t in range(1, T):
        e[t] = phi_true * e[t - 1] + rng.normal(0, 1)
    phi_hat, hl = R3.ou_params(e)
    assert phi_hat == pytest.approx(phi_true, abs=0.02)
    assert hl == pytest.approx(np.log(2) / (-np.log(phi_true)), rel=0.15)


def test_ou_params_rejects_explosive():
    e = np.cumsum(np.ones(200))            # 强趋势，phi >= 1
    _, hl = R3.ou_params(e)
    assert not np.isfinite(hl)


def test_kalman_beta_is_one_step_ahead():
    """关键性质：返回的 beta_t 不得吸收第 t 期观测（否则制造虚假均值回归）。"""
    rng = np.random.default_rng(5)
    xb = np.linspace(0, 1, 300)
    xa = 2.0 * xb
    b = R3.kalman_beta(xa, xb, beta0=1.0)
    # 首项必须等于初值（尚未使用任何观测）
    assert b[0] == pytest.approx(1.0)
    # 序列应收敛到真值附近
    assert b[-1] == pytest.approx(2.0, abs=0.5)


def test_stationary_bootstrap_preserves_length_and_range():
    rng = np.random.default_rng(9)
    idx = MT.stationary_bootstrap_idx(500, 20, rng)
    assert len(idx) == 500
    assert idx.min() >= 0 and idx.max() < 500


# ---------------------------------------------------------------- 4. 多重检验
def test_reality_check_does_not_reject_pure_noise():
    R = make_ret(T=400, K=25, seed=11, mu=0.0, sd=0.01)
    rc = MT.reality_check(R, n_boot=300, block=20, seed=1)
    assert rc["p值"] > 0.05


def test_reality_check_rejects_strong_signal():
    R = make_ret(T=400, K=25, seed=12, mu=0.0, sd=0.01)
    R.iloc[:, 0] = 0.004                    # 注入一条强正收益
    rc = MT.reality_check(R, n_boot=300, block=20, seed=1)
    assert rc["p值"] <= 0.05


def test_hansen_spa_poor_performers_do_not_create_signal():
    """SPA 的要点：劣质策略不应把自己"再中心化"成显著。"""
    R = make_ret(T=400, K=20, seed=13, mu=-0.01, sd=0.02)   # 全部为负
    spa = MT.hansen_spa(R, n_boot=300, block=20, seed=1)
    assert spa["统计量"] == pytest.approx(0.0, abs=1e-9)
    assert spa["p值"] > 0.05


def test_romano_wolf_no_rejection_on_noise():
    R = make_ret(T=400, K=20, seed=14, mu=0.0, sd=0.01)
    rw = MT.romano_wolf(R, n_boot=300, block=20, seed=1, alpha=0.05)
    assert rw["n_rejected"] == 0


def test_romano_wolf_detects_strong_signal():
    R = make_ret(T=400, K=20, seed=15, mu=0.0, sd=0.01)
    R.iloc[:, 3] = 0.005
    rw = MT.romano_wolf(R, n_boot=300, block=20, seed=1, alpha=0.05)
    assert R.columns[3] in rw["rejected"]


def test_deflated_sharpe_with_single_trial_has_zero_benchmark():
    """N=1 时 SR0 应为 0，DSR 退化为对 SR 的正态检验。"""
    sr, T, skew, kurt = 0.08, 500, 0.0, 3.0
    out = MT.deflated_sharpe(sr, T, skew, kurt, np.array([sr]))
    assert out["SR0(日,期望最大值)"] == pytest.approx(0.0, abs=1e-12)
    from scipy import stats
    expect = stats.norm.cdf(sr * np.sqrt(T - 1) / np.sqrt(1 - skew * sr
                                                        + (kurt - 1) / 4 * sr ** 2))
    assert out["DSR"] == pytest.approx(expect, rel=1e-9)


def test_deflated_sharpe_penalises_more_trials():
    sr = 0.08
    d1 = MT.deflated_sharpe(sr, 500, 0.0, 3.0, np.array([sr]))
    trials = np.random.default_rng(0).normal(0.03, 0.05, size=200)
    d2 = MT.deflated_sharpe(sr, 500, 0.0, 3.0, trials)
    assert d2["DSR"] < d1["DSR"]


def test_pbo_low_when_best_in_sample_also_best_out_of_sample():
    """构造一个"真信号"列：样本内外都最强 → 过拟合概率应偏低。"""
    R = make_ret(T=480, K=10, seed=16, mu=0.0, sd=0.01)
    R.iloc[:, 0] = R.iloc[:, 0] + 0.003      # 全样本一致的超额收益
    pbo = MT.pbo_cscv(R, n_splits=8)
    assert pbo["PBO"] < 0.5


def test_pbo_high_when_signal_is_only_in_sample():
    """构造一个"前半段强、后半段弱"的列：样本内最优在样本外易失效。"""
    R = make_ret(T=480, K=10, seed=17, mu=0.0, sd=0.01)
    R.iloc[:240, 0] = R.iloc[:240, 0] + 0.006
    R.iloc[240:, 0] = R.iloc[240:, 0] - 0.006
    pbo = MT.pbo_cscv(R, n_splits=8)
    assert pbo["PBO"] > 0.5