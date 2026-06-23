"""Tests for math/black_scholes.py"""

import math
import pytest
from ..math.black_scholes import bs_call, bs_put, bs_price, greeks, implied_vol


# ─── Basic pricing ────────────────────────────────────────────────────────────

def test_bs_call_atm_positive():
    price = bs_call(100, 100, 1.0, 0.05, 0.20)
    assert price > 0

def test_bs_put_atm_positive():
    price = bs_put(100, 100, 1.0, 0.05, 0.20)
    assert price > 0

def test_put_call_parity():
    """C - P = S*exp(-q*T) - K*exp(-r*T)"""
    S, K, T, r, sigma, q = 100, 100, 1.0, 0.05, 0.20, 0.02
    c = bs_call(S, K, T, r, sigma, q)
    p = bs_put(S, K, T, r, sigma, q)
    lhs = c - p
    rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
    assert abs(lhs - rhs) < 1e-8

def test_call_itm_greater_than_otm():
    itm = bs_call(110, 100, 1.0, 0.05, 0.20)
    otm = bs_call(90,  100, 1.0, 0.05, 0.20)
    assert itm > otm

def test_put_itm_greater_than_otm():
    itm = bs_put(90,  100, 1.0, 0.05, 0.20)
    otm = bs_put(110, 100, 1.0, 0.05, 0.20)
    assert itm > otm

def test_bs_price_call():
    assert bs_price(100, 100, 1.0, 0.05, 0.20, "call") == bs_call(100, 100, 1.0, 0.05, 0.20)

def test_bs_price_put():
    assert bs_price(100, 100, 1.0, 0.05, 0.20, "put") == bs_put(100, 100, 1.0, 0.05, 0.20)

def test_bs_price_invalid_type():
    with pytest.raises(ValueError):
        bs_price(100, 100, 1.0, 0.05, 0.20, "future")

def test_zero_time_call_payoff():
    # At expiry: call price ≈ max(S-K, 0)
    price = bs_call(110, 100, 1e-9, 0.05, 0.20)
    assert abs(price - 10.0) < 0.01

def test_zero_time_put_payoff():
    price = bs_put(90, 100, 1e-9, 0.05, 0.20)
    assert abs(price - 10.0) < 0.01


# ─── Greeks ───────────────────────────────────────────────────────────────────

def test_call_delta_range():
    g = greeks(100, 100, 1.0, 0.05, 0.20, "call")
    assert 0.0 < g["delta"] < 1.0

def test_put_delta_range():
    g = greeks(100, 100, 1.0, 0.05, 0.20, "put")
    assert -1.0 < g["delta"] < 0.0

def test_delta_put_call_relationship():
    # put_delta = call_delta - exp(-q*T), with q=0: call_delta + put_delta = 1 (approx -q*T)
    gc = greeks(100, 100, 1.0, 0.05, 0.20, "call")
    gp = greeks(100, 100, 1.0, 0.05, 0.20, "put")
    assert abs((gc["delta"] + gp["delta"]) - 0.0) < 0.01  # sum ≈ 0 for ATM, q=0

def test_gamma_positive():
    g = greeks(100, 100, 1.0, 0.05, 0.20, "call")
    assert g["gamma"] > 0

def test_vega_positive():
    g = greeks(100, 100, 1.0, 0.05, 0.20, "call")
    assert g["vega"] > 0

def test_theta_negative_for_long():
    # Theta = time decay; long options lose value over time
    g = greeks(100, 100, 1.0, 0.05, 0.20, "call")
    assert g["theta"] < 0

def test_greeks_keys():
    g = greeks(100, 100, 1.0, 0.05, 0.20, "call")
    for key in ("delta", "gamma", "vega", "theta", "rho"):
        assert key in g


# ─── Implied Volatility ───────────────────────────────────────────────────────

def test_implied_vol_roundtrip_call():
    S, K, T, r, sigma = 100, 100, 0.5, 0.04, 0.25
    market_price = bs_call(S, K, T, r, sigma)
    recovered_iv = implied_vol(market_price, S, K, T, r, "call")
    assert abs(recovered_iv - sigma) < 1e-4

def test_implied_vol_roundtrip_put():
    S, K, T, r, sigma = 100, 95, 0.5, 0.04, 0.30
    market_price = bs_put(S, K, T, r, sigma)
    recovered_iv = implied_vol(market_price, S, K, T, r, "put")
    assert abs(recovered_iv - sigma) < 1e-4

def test_implied_vol_intrinsic_raises():
    # Price below intrinsic value → cannot find IV
    with pytest.raises(Exception):
        implied_vol(0.001, 100, 200, 1.0, 0.05, "call")  # deep OTM, price too low
