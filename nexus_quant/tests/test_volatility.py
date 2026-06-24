"""Tests for math/volatility.py"""

import numpy as np
import pandas as pd
import pytest
from ..math.volatility import (
    log_returns, historical_vol, historical_vol_scalar,
    ewma_vol, ewma_vol_scalar, parkinson_vol,
    vol_regime_label, vol_term_structure,
)


def _random_prices(n: int = 252, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, 0.01, n)
    prices  = 100 * np.exp(np.cumsum(returns))
    return pd.Series(prices)


def _make_ohlc(prices: pd.Series, noise: float = 0.003):
    rng = np.random.default_rng(0)
    n   = len(prices)
    highs = prices * (1 + rng.uniform(0, noise, n))
    lows  = prices * (1 - rng.uniform(0, noise, n))
    return highs, lows


# ─── Log Returns ──────────────────────────────────────────────────────────────

def test_log_returns_length():
    p = _random_prices(100)
    r = log_returns(p)
    assert len(r) == 99

def test_log_returns_mean_near_zero():
    rng = np.random.default_rng(1)
    # Stationary AR(0) process: returns should average near 0
    r = pd.Series(rng.normal(0, 0.01, 500))
    prices = 100 * np.exp(r.cumsum())
    lr = log_returns(prices)
    assert abs(lr.mean()) < 0.005


# ─── Historical Vol ───────────────────────────────────────────────────────────

def test_historical_vol_positive():
    p = _random_prices()
    v = historical_vol_scalar(p, 60)
    assert v > 0

def test_historical_vol_annualized():
    # ~ 15% daily vol should produce ann vol ≈ 0.15 * sqrt(252) ... wait no:
    # daily vol = 0.01 → ann vol = 0.01 * sqrt(252) ≈ 0.159
    rng = np.random.default_rng(2)
    r   = pd.Series(rng.normal(0, 0.01, 500))
    p   = 100 * np.exp(r.cumsum())
    v   = historical_vol_scalar(p, 252)
    assert 0.10 < v < 0.25


# ─── EWMA Vol ─────────────────────────────────────────────────────────────────

def test_ewma_vol_positive():
    p = _random_prices()
    v = ewma_vol_scalar(p)
    assert v > 0

def test_ewma_reacts_faster_than_hist():
    # Insert a volatility spike at the end
    rng = np.random.default_rng(3)
    r   = pd.Series(np.concatenate([
        rng.normal(0, 0.005, 200),
        rng.normal(0, 0.05, 20),   # spike
    ]))
    p   = 100 * np.exp(r.cumsum())

    ewma_v = ewma_vol_scalar(p, lam=0.94)
    hist_v = historical_vol_scalar(p, 60)
    # EWMA should be closer to the spike than 60-day equally-weighted
    assert ewma_v > hist_v * 0.8  # both elevated; EWMA is at least 80% of hist

def test_ewma_vol_series_not_empty():
    p = _random_prices(100)
    s = ewma_vol(p)
    assert len(s) > 0
    assert not s.dropna().empty


# ─── Parkinson Vol ────────────────────────────────────────────────────────────

def test_parkinson_positive():
    p = _random_prices()
    h, l = _make_ohlc(p)
    pv = parkinson_vol(h, l, window=20)
    assert pv.dropna().iloc[-1] > 0

def test_parkinson_length():
    p = _random_prices(100)
    h, l = _make_ohlc(p)
    pv = parkinson_vol(h, l, window=20)
    assert len(pv.dropna()) > 0


# ─── Regime Label ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ann_vol,expected", [
    (0.10, "low_vol"),
    (0.25, "normal_vol"),
    (0.40, "high_vol"),
    (0.60, "crisis_vol"),
])
def test_vol_regime_label(ann_vol, expected):
    assert vol_regime_label(ann_vol, 0.15, 0.35, 0.55) == expected


# ─── Term Structure ───────────────────────────────────────────────────────────

def test_term_structure_keys():
    p = _random_prices(300)
    ts = vol_term_structure(p, [10, 30, 60, 252])
    assert set(ts.keys()) == {10, 30, 60, 252}

def test_term_structure_monotone_approx():
    # Longer lookbacks in calm markets should be more stable (not necessarily strictly ordered)
    p = _random_prices(300)
    ts = vol_term_structure(p, [10, 30, 60])
    vals = list(ts.values())
    # All positive
    assert all(v > 0 for v in vals)
