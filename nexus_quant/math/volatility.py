"""
Volatility estimation: historical, EWMA, GARCH, Parkinson.

Notes:
- All functions return annualized volatility (σ annual) unless stated.
- GARCH requires the `arch` library: pip install arch
- Parkinson estimator uses high/low and is ~5x more efficient than close-to-close
  but assumes no overnight gaps (violates for stocks).
"""

import numpy as np
import pandas as pd
from typing import Optional


def log_returns(prices: pd.Series) -> pd.Series:
    """Compute log returns from a price series. Drops NaN."""
    return np.log(prices / prices.shift(1)).dropna()


def historical_vol(
    prices: pd.Series,
    window: int = 20,
    trading_days: int = 252,
) -> pd.Series:
    """
    Rolling close-to-close historical volatility.
    Returns annualized σ series (same index as prices).
    """
    rets = log_returns(prices)
    return rets.rolling(window).std() * np.sqrt(trading_days)


def historical_vol_scalar(
    prices: pd.Series,
    window: Optional[int] = None,
    trading_days: int = 252,
) -> float:
    """Single annualized vol estimate from last `window` prices (or all if None)."""
    rets = log_returns(prices)
    if window is not None:
        rets = rets.iloc[-window:]
    if len(rets) < 2:
        return float("nan")
    return float(rets.std() * np.sqrt(trading_days))


def ewma_vol(
    prices: pd.Series,
    lam: float = 0.94,
    trading_days: int = 252,
) -> pd.Series:
    """
    EWMA (RiskMetrics) volatility. λ=0.94 is the JP Morgan standard for daily data.
    σ²_t = λ·σ²_{t-1} + (1-λ)·r²_t
    Higher λ → longer memory, slower adaptation.
    """
    rets = log_returns(prices)
    var = rets.ewm(alpha=1 - lam, adjust=False).var()
    return np.sqrt(var * trading_days)


def ewma_vol_scalar(
    prices: pd.Series,
    lam: float = 0.94,
    trading_days: int = 252,
) -> float:
    """Single EWMA vol estimate (most recent value)."""
    series = ewma_vol(prices, lam, trading_days)
    val = series.iloc[-1]
    return float(val) if not np.isnan(val) else float("nan")


def parkinson_vol(
    high: pd.Series,
    low: pd.Series,
    window: int = 20,
    trading_days: int = 252,
) -> pd.Series:
    """
    Parkinson (1980) high-low range estimator.
    ~5x more efficient than close-to-close but assumes no drift and no gaps.
    σ² = (1/4ln2) * E[(ln(H/L))²]
    """
    hl_ratio = np.log(high / low)
    variance = hl_ratio.pow(2).rolling(window).mean() / (4 * np.log(2))
    return np.sqrt(variance * trading_days)


def garch_vol_forecast(
    prices: pd.Series,
    horizon: int = 5,
    trading_days: int = 252,
) -> dict:
    """
    GARCH(1,1) volatility forecast using the `arch` library.

    Returns dict with:
    - current_vol: annualized conditional vol today
    - forecast_vols: list of annualized vol forecasts for next `horizon` days
    - params: fitted omega, alpha, beta
    - persistence: alpha + beta (< 1 required for stationarity)

    Raises ImportError if `arch` not installed.
    Limitation: GARCH assumes symmetric shocks. For leverage effects, use EGARCH or GJR-GARCH.
    """
    try:
        from arch import arch_model
    except ImportError:
        raise ImportError("Install 'arch' package: pip install arch")

    rets = log_returns(prices) * 100  # arch works better with percentage returns

    model = arch_model(rets, vol="Garch", p=1, q=1, dist="normal", rescale=False)
    result = model.fit(disp="off", show_warning=False)

    forecasts = result.forecast(horizon=horizon, reindex=False)
    variance_forecasts = forecasts.variance.iloc[-1].values  # in (%)^2

    # Convert % variance back to annualized decimal vol
    forecast_vols = [float(np.sqrt(v * trading_days / 100**2)) for v in variance_forecasts]
    current_conditional_var = float(result.conditional_volatility.iloc[-1])
    current_vol = current_conditional_var / 100 * np.sqrt(trading_days)

    params = result.params
    persistence = float(params.get("alpha[1]", 0)) + float(params.get("beta[1]", 0))

    return {
        "current_vol": round(current_vol, 6),
        "forecast_vols": [round(v, 6) for v in forecast_vols],
        "params": {k: round(float(v), 6) for k, v in params.items()},
        "persistence": round(persistence, 6),
        "aic": round(float(result.aic), 2),
        "warning": "alpha+beta>=1: non-stationary" if persistence >= 1.0 else None,
    }


def vol_term_structure(
    prices: pd.Series,
    windows: list[int] = [5, 10, 20, 60],
    trading_days: int = 252,
) -> dict:
    """
    Compare realized volatility across multiple lookback windows.
    Useful for detecting vol term structure shape.
    """
    rets = log_returns(prices)
    result = {}
    for w in windows:
        r = rets.iloc[-w:] if len(rets) >= w else rets
        result[f"vol_{w}d"] = round(float(r.std() * np.sqrt(trading_days)), 6)
    return result


def vol_regime_label(annualized_vol: float, low: float = 0.15, high: float = 0.35, crisis: float = 0.55) -> str:
    """Classify annualized vol into a regime label."""
    if annualized_vol < low:
        return "low_vol"
    if annualized_vol < high:
        return "normal_vol"
    if annualized_vol < crisis:
        return "high_vol"
    return "crisis_vol"
