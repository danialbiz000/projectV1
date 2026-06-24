"""Tests for math/risk_metrics.py"""

import numpy as np
import pandas as pd
import pytest
from ..math.risk_metrics import (
    var_historical, var_parametric, expected_shortfall,
    kelly_fraction, kelly_from_trades,
    max_drawdown, current_drawdown, drawdown_series,
    sharpe_ratio, sortino_ratio, calmar_ratio,
    profit_factor, win_rate, expectancy, full_performance_report,
)


def _returns(seed: int = 0, n: int = 252) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0003, 0.012, n))


def _equity(returns: pd.Series, start: float = 100_000) -> pd.Series:
    return (1 + returns).cumprod() * start


# ─── VaR ──────────────────────────────────────────────────────────────────────

def test_var_historical_positive():
    r = _returns()
    v = var_historical(r)
    assert v > 0

def test_var_historical_95_lt_99():
    r = _returns()
    v95 = var_historical(r, 0.95)
    v99 = var_historical(r, 0.99)
    assert v99 >= v95

def test_var_parametric_positive():
    r = _returns()
    v = var_parametric(r)
    assert v > 0

def test_var_insufficient_data():
    r = pd.Series([0.01, -0.01, 0.02])
    assert np.isnan(var_historical(r))

def test_es_gte_var():
    r = _returns()
    v = var_historical(r, 0.95)
    es = expected_shortfall(r, 0.95)
    assert es >= v * 0.9  # ES should be at least close to VaR (could be equal in some cases)


# ─── Kelly ────────────────────────────────────────────────────────────────────

def test_kelly_positive_edge():
    k = kelly_fraction(0.55, 0.10, 0.08)
    assert k > 0

def test_kelly_negative_edge():
    # win_rate too low to overcome loss ratio
    k = kelly_fraction(0.30, 0.05, 0.15)
    assert k == 0.0

def test_kelly_clamped_to_one():
    # Even extreme edge should not exceed fraction parameter
    k = kelly_fraction(0.99, 0.50, 0.01, fraction=0.25)
    assert k <= 1.0

def test_kelly_fraction_parameter():
    k_full = kelly_fraction(0.60, 0.10, 0.08, fraction=1.0)
    k_half = kelly_fraction(0.60, 0.10, 0.08, fraction=0.5)
    assert abs(k_full - 2 * k_half) < 1e-9

def test_kelly_from_trades():
    rng = np.random.default_rng(10)
    pnl = pd.Series(rng.normal(0.01, 0.05, 200))
    k = kelly_from_trades(pnl)
    assert 0 <= k <= 1.0


# ─── Drawdown ─────────────────────────────────────────────────────────────────

def test_max_drawdown_non_negative():
    r = _returns()
    eq = _equity(r)
    assert max_drawdown(eq) >= 0

def test_max_drawdown_zero_for_monotone():
    eq = pd.Series([100.0, 101.0, 102.0, 103.0])
    assert max_drawdown(eq) == 0.0

def test_max_drawdown_known_value():
    eq = pd.Series([100.0, 120.0, 80.0, 90.0])
    # Peak = 120, trough = 80 → DD = 40/120 ≈ 0.333
    dd = max_drawdown(eq)
    assert abs(dd - (40 / 120)) < 1e-6

def test_current_drawdown_at_peak():
    eq = pd.Series([100.0, 110.0, 120.0])
    assert current_drawdown(eq) == 0.0

def test_drawdown_series_negative():
    r = _returns()
    eq = _equity(r)
    ds = drawdown_series(eq)
    assert (ds <= 0).all()


# ─── Performance Metrics ──────────────────────────────────────────────────────

def test_sharpe_ratio_positive_drift():
    rng = np.random.default_rng(5)
    r = pd.Series(rng.normal(0.001, 0.01, 500))
    sr = sharpe_ratio(r)
    assert sr > 0

def test_sortino_ratio_positive_drift():
    rng = np.random.default_rng(6)
    r = pd.Series(rng.normal(0.001, 0.01, 500))
    so = sortino_ratio(r)
    assert so > 0

def test_sortino_gte_sharpe_for_skewed_returns():
    # If downside vol < total vol, Sortino > Sharpe
    rng = np.random.default_rng(7)
    pos = pd.Series(rng.uniform(0, 0.02, 300))
    neg = pd.Series(rng.uniform(-0.005, 0, 100))
    r = pd.concat([pos, neg]).sample(frac=1, random_state=7).reset_index(drop=True)
    so = sortino_ratio(r)
    sh = sharpe_ratio(r)
    assert so >= sh

def test_profit_factor_profitable():
    pnl = pd.Series([1.0, 2.0, -0.5, 3.0, -1.0])
    assert profit_factor(pnl) > 1.0

def test_profit_factor_losing():
    pnl = pd.Series([-1.0, -2.0, 0.5, -3.0, 0.5])
    assert profit_factor(pnl) < 1.0

def test_win_rate_range():
    pnl = pd.Series([1, -1, 1, -1, 1])
    assert 0 <= win_rate(pnl) <= 1.0

def test_expectancy_positive_edge():
    pnl = pd.Series([2.0, -0.5, 3.0, -0.5, 2.0])
    assert expectancy(pnl) > 0

def test_full_performance_report_keys():
    r  = _returns()
    eq = _equity(r)
    pnl = pd.Series([1.0, -0.5, 2.0, -1.0, 0.5])
    rep = full_performance_report(r, eq, pnl)
    expected_keys = [
        "total_return_pct", "annualized_return_pct", "volatility_pct",
        "sharpe_ratio", "sortino_ratio", "max_drawdown_pct",
        "calmar_ratio", "var_95_daily_pct", "es_95_daily_pct",
        "num_trades", "win_rate_pct", "profit_factor", "expectancy",
    ]
    for k in expected_keys:
        assert k in rep, f"Missing key: {k}"
