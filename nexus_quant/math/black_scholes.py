"""
Black-Scholes model: European option pricing, Greeks, implied volatility.

Assumptions (declare explicitly):
- European-style exercise only (no early exercise premium)
- Constant volatility across strikes and maturities (no smile/skew)
- Continuous dividend yield (q) instead of discrete dividends
- No transaction costs or taxes
- Log-normal price distribution (fat tails not captured)
- Risk-free rate constant over option life

These assumptions break down in practice. Use BS as a baseline, not a truth.
"""

import math
from typing import Literal
from scipy.stats import norm
from scipy.optimize import brentq


def _d1(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    return _d1(S, K, T, r, sigma, q) - sigma * math.sqrt(T)


def bs_call(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Black-Scholes call price. q = continuous dividend yield."""
    if T <= 0 or sigma <= 0:
        return max(S * math.exp(-q * T) - K * math.exp(-r * T), 0.0)
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = d1 - sigma * math.sqrt(T)
    return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def bs_put(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Black-Scholes put price."""
    if T <= 0 or sigma <= 0:
        return max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def bs_price(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: Literal["call", "put"] = "call", q: float = 0.0
) -> float:
    if option_type == "call":
        return bs_call(S, K, T, r, sigma, q)
    return bs_put(S, K, T, r, sigma, q)


# ─── Greeks ──────────────────────────────────────────────────────────────────

def delta(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: Literal["call", "put"] = "call", q: float = 0.0
) -> float:
    """Rate of change of option price w.r.t. underlying price."""
    if T <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    if option_type == "call":
        return math.exp(-q * T) * norm.cdf(d1)
    return math.exp(-q * T) * (norm.cdf(d1) - 1)


def gamma(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Rate of change of delta w.r.t. underlying price (same for call and put)."""
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    return math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Sensitivity to 1% change in volatility (same for call and put)."""
    if T <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T) * 0.01  # per 1% vol


def theta(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: Literal["call", "put"] = "call", q: float = 0.0
) -> float:
    """Daily time decay (divided by 365 to get per-calendar-day value)."""
    if T <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma, q)
    d2 = d1 - sigma * math.sqrt(T)
    common = -(S * math.exp(-q * T) * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
    if option_type == "call":
        return (common - r * K * math.exp(-r * T) * norm.cdf(d2)
                + q * S * math.exp(-q * T) * norm.cdf(d1)) / 365
    return (common + r * K * math.exp(-r * T) * norm.cdf(-d2)
            - q * S * math.exp(-q * T) * norm.cdf(-d1)) / 365


def rho(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: Literal["call", "put"] = "call", q: float = 0.0
) -> float:
    """Sensitivity to 1% change in risk-free rate."""
    if T <= 0:
        return 0.0
    d2 = _d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return K * T * math.exp(-r * T) * norm.cdf(d2) * 0.01
    return -K * T * math.exp(-r * T) * norm.cdf(-d2) * 0.01


def greeks(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: Literal["call", "put"] = "call", q: float = 0.0
) -> dict:
    """Return all Greeks in a single dict."""
    return {
        "delta": delta(S, K, T, r, sigma, option_type, q),
        "gamma": gamma(S, K, T, r, sigma, q),
        "vega":  vega(S, K, T, r, sigma, q),
        "theta": theta(S, K, T, r, sigma, option_type, q),
        "rho":   rho(S, K, T, r, sigma, option_type, q),
    }


# ─── Implied Volatility ───────────────────────────────────────────────────────

def implied_vol(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: Literal["call", "put"] = "call",
    q: float = 0.0,
    tol: float = 1e-6,
    max_iter: int = 100,
) -> float | None:
    """
    Compute implied volatility via Brent's method.
    Returns None if no solution found (e.g. price violates bounds).
    """
    if T <= 0:
        return None

    # Intrinsic value bounds check
    if option_type == "call":
        intrinsic = max(S * math.exp(-q * T) - K * math.exp(-r * T), 0.0)
    else:
        intrinsic = max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)

    if market_price < intrinsic - tol:
        return None  # price below intrinsic — arbitrage or bad quote

    def objective(sigma: float) -> float:
        return bs_price(S, K, T, r, sigma, option_type, q) - market_price

    try:
        # Brent requires sign change: search in [0.001, 20.0] (0.1% to 2000% vol)
        if objective(0.001) * objective(20.0) > 0:
            return None
        iv = brentq(objective, 0.001, 20.0, xtol=tol, maxiter=max_iter)
        return float(iv)
    except (ValueError, RuntimeError):
        return None


def iv_surface_point(
    market_price: float, S: float, K: float, T: float, r: float,
    option_type: Literal["call", "put"] = "call", q: float = 0.0
) -> dict:
    """
    Single point on the IV surface with moneyness and Greeks at implied vol.
    Returns dict with iv, moneyness, greeks, theoretical_price, mispricing.
    """
    iv = implied_vol(market_price, S, K, T, r, option_type, q)
    if iv is None:
        return {"iv": None, "moneyness": K / S, "error": "no_iv_solution"}

    theo = bs_price(S, K, T, r, iv, option_type, q)
    g = greeks(S, K, T, r, iv, option_type, q)

    return {
        "iv": round(iv, 6),
        "moneyness": round(K / S, 4),           # > 1 = OTM call / ITM put
        "theoretical_price": round(theo, 4),
        "market_price": round(market_price, 4),
        "mispricing": round(market_price - theo, 4),  # should be ~0 by construction
        **{k: round(v, 6) for k, v in g.items()},
    }
