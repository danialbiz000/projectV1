"""
Signal generation functions. Each returns a value in [-1, +1] or a z-score.

All functions are pure (no side effects). They consume pandas Series/DataFrames
and return numeric signals. Signal interpretation is the Signal Engine's job.
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple


# ─── Mean Reversion ──────────────────────────────────────────────────────────

def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """Rolling z-score: (x - μ) / σ. Positive = overextended above mean."""
    rolling_mean = series.rolling(window).mean()
    rolling_std  = series.rolling(window).std()
    return (series - rolling_mean) / rolling_std


def zscore_scalar(series: pd.Series, window: int = 20) -> float:
    """Most recent z-score."""
    z = zscore(series, window)
    return float(z.iloc[-1])


def mean_reversion_signal(
    prices: pd.Series,
    window: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
) -> Tuple[float, float]:
    """
    Returns (signal_direction, signal_strength) for mean reversion.
    signal_direction: +1 (buy dip), -1 (sell rally), 0 (no entry)
    signal_strength: normalized 0–1 based on |z| beyond threshold
    """
    z = zscore_scalar(prices, window)
    if np.isnan(z):
        return 0.0, 0.0

    if z <= -entry_z:        # price too far below mean → buy
        strength = min(abs(z) / (entry_z * 2), 1.0)
        return 1.0, strength
    if z >= entry_z:         # price too far above mean → sell
        strength = min(abs(z) / (entry_z * 2), 1.0)
        return -1.0, strength
    if abs(z) <= exit_z:     # back near mean → signal flat
        return 0.0, 0.0

    return 0.0, 0.0


def bollinger_signal(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> float:
    """
    Bollinger Bands signal in [-1, +1].
    -1 = price at/above upper band (overbought), +1 = price at/below lower band.
    """
    sma = prices.rolling(window).mean()
    std = prices.rolling(window).std()
    upper = sma + num_std * std
    lower = sma - num_std * std

    last = prices.iloc[-1]
    u = upper.iloc[-1]
    l = lower.iloc[-1]

    if np.isnan(u) or np.isnan(l) or (u - l) == 0:
        return 0.0

    # Normalize position within band: 0 at lower, 1 at upper
    position = (last - l) / (u - l)
    return float(np.clip(1 - 2 * position, -1, 1))


# ─── Momentum ────────────────────────────────────────────────────────────────

def momentum_signal(
    prices: pd.Series,
    lookback: int = 20,
    skip_last: int = 1,
) -> float:
    """
    Time-series momentum signal in [-1, +1].
    skip_last: skip the most recent N bars (avoid reversal of short-term noise).
    Returns normalized return over [lookback, skip_last] window.
    """
    if len(prices) < lookback + skip_last + 1:
        return 0.0

    past_price   = prices.iloc[-(lookback + skip_last)]
    recent_price = prices.iloc[-(skip_last + 1)]
    ret = (recent_price - past_price) / past_price
    return float(np.tanh(ret * 10))  # tanh squashes to (-1, +1)


def cross_sectional_momentum(
    returns_df: pd.DataFrame,
    lookback: int = 20,
    top_n: int = 5,
) -> pd.Series:
    """
    Cross-sectional momentum: rank assets by trailing return.
    Returns a Series of signals: +1 for top_n, -1 for bottom_n, 0 otherwise.
    returns_df: columns = symbols, rows = dates
    """
    trailing = returns_df.iloc[-lookback:].sum()
    ranked = trailing.rank(ascending=False)
    n = len(ranked)
    signals = pd.Series(0.0, index=ranked.index)
    signals[ranked <= top_n] = 1.0
    signals[ranked > n - top_n] = -1.0
    return signals


def rsi(prices: pd.Series, period: int = 14) -> float:
    """
    RSI(14). Returns value in [0, 100].
    < 30 = oversold (bullish), > 70 = overbought (bearish).
    """
    delta_p = prices.diff().dropna()
    gains = delta_p.clip(lower=0)
    losses = (-delta_p).clip(lower=0)

    avg_gain = gains.ewm(com=period - 1, adjust=False).mean().iloc[-1]
    avg_loss = losses.ewm(com=period - 1, adjust=False).mean().iloc[-1]

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))


def macd_signal(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[float, float, float]:
    """Returns (MACD line, Signal line, Histogram). Histogram > 0 = bullish momentum."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


# ─── Pairs / Statistical Arbitrage ───────────────────────────────────────────

def pair_spread(
    series_a: pd.Series,
    series_b: pd.Series,
    hedge_ratio: Optional[float] = None,
) -> pd.Series:
    """
    Compute the spread between two cointegrated series.
    If hedge_ratio is None, estimates it via OLS (ratio of means over window).
    spread = A - hedge_ratio * B
    """
    if hedge_ratio is None:
        # OLS estimate: regress A on B
        b_demean = series_b - series_b.mean()
        a_demean = series_a - series_a.mean()
        if b_demean.var() == 0:
            hedge_ratio = 1.0
        else:
            hedge_ratio = float(np.cov(a_demean, b_demean)[0, 1] / b_demean.var())
    return series_a - hedge_ratio * series_b


def pair_zscore(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int = 20,
    hedge_ratio: Optional[float] = None,
) -> float:
    """
    Z-score of the pair spread over a rolling window.
    > +2 → sell A / buy B (spread too wide)
    < -2 → buy A / sell B (spread too narrow)
    """
    spread = pair_spread(series_a, series_b, hedge_ratio)
    z = zscore(spread, window)
    return float(z.iloc[-1])


def cointegration_check(
    series_a: pd.Series,
    series_b: pd.Series,
) -> dict:
    """
    Quick cointegration check via Engle-Granger (ADF on spread residuals).
    Returns p_value and is_cointegrated flag.
    Requires statsmodels.
    """
    try:
        from statsmodels.tsa.stattools import coint
        score, p_value, _ = coint(series_a, series_b)
        return {
            "p_value": round(float(p_value), 4),
            "is_cointegrated": p_value < 0.05,
            "coint_score": round(float(score), 4),
        }
    except ImportError:
        return {"p_value": None, "is_cointegrated": None, "error": "statsmodels missing"}


# ─── Volume ──────────────────────────────────────────────────────────────────

def relative_volume(volume: pd.Series, window: int = 20) -> float:
    """Relative volume = current / rolling average. > 1.5 = volume confirmation."""
    avg = volume.iloc[-window:].mean()
    if avg == 0:
        return 1.0
    return float(volume.iloc[-1] / avg)


def volume_breakout_signal(volume: pd.Series, window: int = 20, threshold: float = 1.5) -> float:
    """Returns 1.0 if volume is a breakout (above threshold × avg), else 0.0."""
    return 1.0 if relative_volume(volume, window) >= threshold else 0.0


# ─── Factor Signals ──────────────────────────────────────────────────────────

def quality_signal(
    roe: float,
    debt_to_equity: float,
    earnings_stability: float,
) -> float:
    """
    Simple quality score in [0, 1].
    Inputs are normalized (0-1) versions of ROE, D/E (inverted), earnings stability.
    """
    quality = (roe * 0.4 + (1 - min(debt_to_equity, 1)) * 0.3 + earnings_stability * 0.3)
    return float(np.clip(quality, 0, 1))


def value_signal(pe_ratio: float, pb_ratio: float, peer_avg_pe: float, peer_avg_pb: float) -> float:
    """
    Value score: negative = cheap (attractive), positive = expensive.
    Returns z-score of combined P/E and P/B vs peers.
    """
    z_pe = (pe_ratio - peer_avg_pe) / max(peer_avg_pe * 0.3, 1e-9)
    z_pb = (pb_ratio - peer_avg_pb) / max(peer_avg_pb * 0.3, 1e-9)
    combined = -(z_pe * 0.5 + z_pb * 0.5)  # negative = cheap = buy signal
    return float(np.tanh(combined))
