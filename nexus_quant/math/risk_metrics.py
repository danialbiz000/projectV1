"""
Risk metrics: VaR, Expected Shortfall, Kelly Criterion, Sharpe, Sortino, MDD.

VaR limitations (declare explicitly):
- Historical VaR assumes the past distribution repeats.
- Parametric VaR assumes normality (underestimates fat-tail risk).
- Neither captures liquidity risk, gap risk, or correlation breakdown.
- Use ES (CVaR) alongside VaR for a more complete tail picture.
"""

import numpy as np
import pandas as pd
from typing import Optional


# ─── Value at Risk ───────────────────────────────────────────────────────────

def var_historical(
    returns: pd.Series,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """
    Historical VaR: loss not exceeded at `confidence` level over `horizon_days`.
    Returns a positive number representing the loss.
    Assumes i.i.d. returns (scale by sqrt(horizon) — only valid under normality).
    """
    if len(returns) < 20:
        return float("nan")
    q = np.percentile(returns.dropna(), (1 - confidence) * 100)
    return float(-q * np.sqrt(horizon_days))


def var_parametric(
    returns: pd.Series,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """
    Parametric (Gaussian) VaR. Faster than historical but assumes normal distribution.
    Often underestimates tail risk in practice.
    """
    from scipy.stats import norm
    mu = returns.mean()
    sigma = returns.std()
    if np.isnan(sigma) or sigma == 0:
        return float("nan")
    z = norm.ppf(1 - confidence)
    return float(-(mu * horizon_days + z * sigma * np.sqrt(horizon_days)))


def expected_shortfall(
    returns: pd.Series,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """
    Expected Shortfall (CVaR): average loss in the worst (1-confidence)% scenarios.
    Always >= VaR. More informative for tail risk management.
    """
    if len(returns) < 20:
        return float("nan")
    r = returns.dropna()
    threshold = np.percentile(r, (1 - confidence) * 100)
    tail_losses = r[r <= threshold]
    if len(tail_losses) == 0:
        return float(-threshold * np.sqrt(horizon_days))
    es = -tail_losses.mean() * np.sqrt(horizon_days)
    return float(es)


def var_portfolio(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
    confidence: float = 0.95,
    horizon_days: int = 1,
) -> float:
    """
    Parametric portfolio VaR using mean-variance.
    weights: array of portfolio weights (must sum to 1).
    cov_matrix: daily covariance matrix of asset returns.
    """
    from scipy.stats import norm
    port_var = float(weights @ cov_matrix @ weights)
    port_sigma = np.sqrt(port_var)
    z = norm.ppf(1 - confidence)
    return float(-z * port_sigma * np.sqrt(horizon_days))


# ─── Kelly Criterion ─────────────────────────────────────────────────────────

def kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.25,
) -> float:
    """
    Fractional Kelly position sizing.
    f* = (win_rate / avg_loss - (1-win_rate) / avg_win)
    Returns fraction * f* clamped to [0, 1].

    fraction=0.25 means 25% of full Kelly (standard conservative practice).
    Full Kelly maximizes log-utility but results in massive drawdowns.

    avg_win and avg_loss should be positive decimals (e.g. 0.05 = 5%).
    Returns 0 if Kelly is negative (negative edge — do not trade).
    """
    if avg_loss <= 0 or avg_win <= 0:
        return 0.0
    win_loss_ratio = avg_win / avg_loss
    kelly = win_rate * win_loss_ratio - (1 - win_rate)
    kelly /= win_loss_ratio
    return float(np.clip(kelly * fraction, 0, 1))


def kelly_from_trades(
    pnl_series: pd.Series,
    fraction: float = 0.25,
) -> float:
    """Estimate Kelly fraction from historical P&L series."""
    wins  = pnl_series[pnl_series > 0]
    losses = pnl_series[pnl_series < 0]
    if len(wins) == 0 or len(losses) == 0:
        return 0.0
    win_rate = len(wins) / len(pnl_series)
    avg_win  = wins.mean()
    avg_loss = abs(losses.mean())
    return kelly_fraction(win_rate, avg_win, avg_loss, fraction)


# ─── Drawdown ────────────────────────────────────────────────────────────────

def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown from peak to trough. Returns a positive decimal (e.g. 0.15 = 15%)."""
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return float(abs(drawdown.min()))


def current_drawdown(equity_curve: pd.Series) -> float:
    """Current drawdown from peak. Returns a positive decimal."""
    peak = equity_curve.cummax().iloc[-1]
    current = equity_curve.iloc[-1]
    if peak == 0:
        return 0.0
    return float((peak - current) / peak)


def drawdown_series(equity_curve: pd.Series) -> pd.Series:
    """Full drawdown series (negative values showing depth below peak)."""
    rolling_max = equity_curve.cummax()
    return (equity_curve - rolling_max) / rolling_max


# ─── Performance Metrics ─────────────────────────────────────────────────────

def sharpe_ratio(
    returns: pd.Series,
    risk_free_daily: float = 0.0,
    annualize: bool = True,
    trading_days: int = 252,
) -> float:
    """
    Sharpe ratio. risk_free_daily = daily risk-free rate (e.g. 0.043/252).
    """
    excess = returns - risk_free_daily
    if excess.std() == 0:
        return float("nan")
    sr = excess.mean() / excess.std()
    if annualize:
        sr *= np.sqrt(trading_days)
    return float(sr)


def sortino_ratio(
    returns: pd.Series,
    risk_free_daily: float = 0.0,
    annualize: bool = True,
    trading_days: int = 252,
) -> float:
    """
    Sortino ratio: penalizes only downside deviation.
    """
    excess = returns - risk_free_daily
    downside = excess[excess < 0]
    downside_std = downside.std()
    if downside_std == 0 or np.isnan(downside_std):
        return float("nan")
    sr = excess.mean() / downside_std
    if annualize:
        sr *= np.sqrt(trading_days)
    return float(sr)


def calmar_ratio(
    equity_curve: pd.Series,
    annualized_return: Optional[float] = None,
    trading_days: int = 252,
) -> float:
    """Calmar = annualized return / max drawdown."""
    mdd = max_drawdown(equity_curve)
    if mdd == 0:
        return float("nan")
    if annualized_return is None:
        total_ret = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        n_years = len(equity_curve) / trading_days
        annualized_return = (1 + total_ret) ** (1 / n_years) - 1 if n_years > 0 else 0
    return float(annualized_return / mdd)


def profit_factor(pnl_series: pd.Series) -> float:
    """Gross profit / gross loss. > 1 = profitable system."""
    gross_profit = pnl_series[pnl_series > 0].sum()
    gross_loss   = abs(pnl_series[pnl_series < 0].sum())
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else float("nan")
    return float(gross_profit / gross_loss)


def win_rate(pnl_series: pd.Series) -> float:
    """Fraction of winning trades."""
    if len(pnl_series) == 0:
        return float("nan")
    return float((pnl_series > 0).sum() / len(pnl_series))


def expectancy(pnl_series: pd.Series) -> float:
    """Average P&L per trade (positive = edge exists)."""
    if len(pnl_series) == 0:
        return float("nan")
    return float(pnl_series.mean())


def full_performance_report(
    returns: pd.Series,
    equity_curve: pd.Series,
    pnl_per_trade: Optional[pd.Series] = None,
    risk_free_annual: float = 0.043,
    trading_days: int = 252,
) -> dict:
    """Compute all performance metrics in one call."""
    rf_daily = risk_free_annual / trading_days
    mdd = max_drawdown(equity_curve)
    ann_ret = ((equity_curve.iloc[-1] / equity_curve.iloc[0])
               ** (trading_days / len(equity_curve)) - 1)

    report = {
        "total_return_pct":      round((equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100, 2),
        "annualized_return_pct": round(ann_ret * 100, 2),
        "volatility_pct":        round(returns.std() * np.sqrt(trading_days) * 100, 2),
        "sharpe_ratio":          round(sharpe_ratio(returns, rf_daily, True, trading_days), 3),
        "sortino_ratio":         round(sortino_ratio(returns, rf_daily, True, trading_days), 3),
        "max_drawdown_pct":      round(mdd * 100, 2),
        "calmar_ratio":          round(calmar_ratio(equity_curve, ann_ret, trading_days), 3),
        "var_95_daily_pct":      round(var_historical(returns, 0.95, 1) * 100, 3),
        "es_95_daily_pct":       round(expected_shortfall(returns, 0.95, 1) * 100, 3),
    }
    if pnl_per_trade is not None:
        report.update({
            "num_trades":    int(len(pnl_per_trade)),
            "win_rate_pct":  round(win_rate(pnl_per_trade) * 100, 1),
            "profit_factor": round(profit_factor(pnl_per_trade), 3),
            "expectancy":    round(expectancy(pnl_per_trade), 4),
        })
    return report
