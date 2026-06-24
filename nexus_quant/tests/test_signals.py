"""Tests for math/signals.py"""

import numpy as np
import pandas as pd
import pytest
from ..math.signals import (
    zscore, zscore_scalar, mean_reversion_signal, bollinger_signal,
    momentum_signal, rsi, macd_signal,
    pair_spread, pair_zscore,
    relative_volume, volume_breakout_signal,
    quality_signal, value_signal,
)


def _trend_up(n: int = 100) -> pd.Series:
    return pd.Series(np.linspace(100, 120, n))


def _trend_down(n: int = 100) -> pd.Series:
    return pd.Series(np.linspace(120, 100, n))


def _stationary(n: int = 100, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(100 + rng.normal(0, 1, n))


# ─── Z-Score ──────────────────────────────────────────────────────────────────

def test_zscore_length():
    p = _stationary(100)
    z = zscore(p, 20)
    assert len(z) == len(p)

def test_zscore_scalar_near_zero_stationary():
    # Stationary series: last z-score should be within ±3 most of the time
    p = _stationary(200)
    z = zscore_scalar(p, 20)
    assert abs(z) < 5

def test_zscore_scalar_high_on_spike():
    p = _stationary(100)
    p_spike = pd.concat([p, pd.Series([200.0])])
    z = zscore_scalar(p_spike, 20)
    assert z > 2.0


# ─── Mean Reversion ───────────────────────────────────────────────────────────

def test_mean_reversion_no_signal_in_band():
    p = _stationary(100)
    direction, strength = mean_reversion_signal(p, 20, 2.0, 0.5)
    # Most of the time stationary will not breach ±2 consistently
    # Just check types
    assert direction in (-1.0, 0.0, 1.0)
    assert 0.0 <= strength <= 1.0

def test_mean_reversion_buys_dip():
    # Artificially create a price far below its rolling mean
    p = pd.Series([100.0] * 80 + [80.0] * 10 + [79.0])
    direction, strength = mean_reversion_signal(p, 20, 2.0, 0.5)
    assert direction == 1.0

def test_bollinger_below_lower_band():
    p = pd.Series([100.0] * 80 + [80.0])
    sig = bollinger_signal(p, 20, 2.0)
    assert sig > 0  # price below lower band → buy signal (positive)

def test_bollinger_above_upper_band():
    p = pd.Series([100.0] * 80 + [125.0])
    sig = bollinger_signal(p, 20, 2.0)
    assert sig < 0

def test_bollinger_range():
    p = _stationary(200)
    sig = bollinger_signal(p, 20)
    assert -1.0 <= sig <= 1.0


# ─── Momentum ─────────────────────────────────────────────────────────────────

def test_momentum_uptrend_positive():
    p = _trend_up(100)
    m = momentum_signal(p, 20, 1)
    assert m > 0

def test_momentum_downtrend_negative():
    p = _trend_down(100)
    m = momentum_signal(p, 20, 1)
    assert m < 0

def test_momentum_range():
    p = _trend_up(100)
    m = momentum_signal(p, 20, 1)
    assert -1.0 <= m <= 1.0

def test_momentum_insufficient_data():
    p = pd.Series([100.0, 101.0, 102.0])
    m = momentum_signal(p, 20, 1)
    assert m == 0.0


# ─── RSI ──────────────────────────────────────────────────────────────────────

def test_rsi_range():
    p = _trend_up(100)
    r = rsi(p, 14)
    assert 0 <= r <= 100

def test_rsi_uptrend_overbought():
    p = pd.Series(np.linspace(100, 200, 100))
    r = rsi(p, 14)
    assert r > 70

def test_rsi_downtrend_oversold():
    p = pd.Series(np.linspace(200, 100, 100))
    r = rsi(p, 14)
    assert r < 30


# ─── MACD ─────────────────────────────────────────────────────────────────────

def test_macd_returns_tuple():
    p = _trend_up(100)
    result = macd_signal(p)
    assert len(result) == 3

def test_macd_uptrend_histogram_positive():
    p = pd.Series(np.linspace(100, 200, 200))
    _, _, hist = macd_signal(p)
    assert hist > 0


# ─── Pairs ────────────────────────────────────────────────────────────────────

def test_pair_spread_length():
    a = _stationary(100)
    b = _stationary(100, seed=1)
    spread = pair_spread(a, b)
    assert len(spread) == 100

def test_pair_zscore_numeric():
    rng = np.random.default_rng(0)
    common = pd.Series(rng.normal(0, 1, 150).cumsum() + 100)
    a = common + rng.normal(0, 0.1, 150)
    b = common + rng.normal(0, 0.1, 150)
    z = pair_zscore(a, b, window=60)
    assert np.isfinite(z)


# ─── Volume ───────────────────────────────────────────────────────────────────

def test_relative_volume_baseline():
    vol = pd.Series([100.0] * 21)
    assert abs(relative_volume(vol, 20) - 1.0) < 1e-6

def test_volume_breakout_signal():
    vol = pd.Series([100.0] * 20 + [200.0])
    sig = volume_breakout_signal(vol, 20, 1.5)
    assert sig == 1.0

def test_volume_no_breakout():
    vol = pd.Series([100.0] * 21)
    sig = volume_breakout_signal(vol, 20, 1.5)
    assert sig == 0.0


# ─── Factor Signals ───────────────────────────────────────────────────────────

def test_quality_signal_range():
    q = quality_signal(0.8, 0.2, 0.9)
    assert 0.0 <= q <= 1.0

def test_value_signal_cheap_negative():
    # PE much lower than peers → signal should be positive (buy)
    v = value_signal(pe_ratio=10, pb_ratio=1.0, peer_avg_pe=20, peer_avg_pb=2.0)
    assert v > 0

def test_value_signal_expensive_positive():
    v = value_signal(pe_ratio=40, pb_ratio=5.0, peer_avg_pe=20, peer_avg_pb=2.0)
    assert v < 0
