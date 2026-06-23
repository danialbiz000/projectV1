"""
Portfolio optimization via scipy.optimize (no cvxpy dependency).

Markowitz mean-variance optimization.

Known limitations:
- Very sensitive to input estimates (garbage in, garbage out).
- Expected returns are hard to forecast reliably; vol and correlations are easier.
- Consider min-variance portfolios in practice (no return input needed).
- Black-Litterman or robust optimization are more stable in production.
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Optional


def _portfolio_return(weights: np.ndarray, expected_returns: np.ndarray) -> float:
    return float(weights @ expected_returns)


def _portfolio_vol(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    return float(np.sqrt(weights @ cov_matrix @ weights))


def _neg_sharpe(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free: float,
) -> float:
    ret = _portfolio_return(weights, expected_returns)
    vol = _portfolio_vol(weights, cov_matrix)
    if vol == 0:
        return 0.0
    return -(ret - risk_free) / vol


def max_sharpe_portfolio(
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free: float = 0.043,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> dict:
    """
    Maximize Sharpe ratio. Returns optimal weights.

    expected_returns: array of annualized expected returns (e.g. [0.08, 0.12, ...])
    cov_matrix: annualized covariance matrix
    Returns dict with weights, expected_return, expected_vol, sharpe.
    """
    n = len(expected_returns)
    if n == 0:
        return {}

    bounds = [(min_weight, max_weight)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    x0 = np.ones(n) / n

    result = minimize(
        _neg_sharpe,
        x0,
        args=(expected_returns, cov_matrix, risk_free),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    if not result.success:
        # Fallback to equal weight
        weights = np.ones(n) / n
    else:
        weights = result.x

    weights = np.clip(weights, 0, 1)
    weights /= weights.sum()

    ret = _portfolio_return(weights, expected_returns)
    vol = _portfolio_vol(weights, cov_matrix)

    return {
        "weights": weights.tolist(),
        "expected_return": round(ret, 6),
        "expected_vol": round(vol, 6),
        "sharpe": round((ret - risk_free) / vol if vol > 0 else 0, 4),
        "converged": result.success,
    }


def min_variance_portfolio(
    cov_matrix: np.ndarray,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> dict:
    """
    Minimum variance portfolio. Does NOT require expected return estimates.
    More robust than max-Sharpe in practice.
    """
    n = cov_matrix.shape[0]
    bounds = [(min_weight, max_weight)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    x0 = np.ones(n) / n

    result = minimize(
        lambda w: _portfolio_vol(w, cov_matrix),
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    weights = result.x if result.success else x0
    weights = np.clip(weights, 0, 1)
    weights /= weights.sum()

    return {
        "weights": weights.tolist(),
        "expected_vol": round(_portfolio_vol(weights, cov_matrix), 6),
        "converged": result.success,
    }


def risk_parity_portfolio(cov_matrix: np.ndarray) -> dict:
    """
    Risk parity: each asset contributes equally to portfolio volatility.
    Does not require expected returns. More diversified than min-variance.
    """
    n = cov_matrix.shape[0]

    def risk_contribution_diff(weights: np.ndarray) -> float:
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        if port_vol == 0:
            return float("inf")
        marginal_risk = cov_matrix @ weights / port_vol
        risk_contrib = weights * marginal_risk
        target = port_vol / n
        return float(np.sum((risk_contrib - target) ** 2))

    bounds = [(0.01, 1.0)] * n
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1}
    x0 = np.ones(n) / n

    result = minimize(
        risk_contribution_diff,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 2000},
    )

    weights = result.x if result.success else x0
    weights = np.clip(weights, 0, 1)
    weights /= weights.sum()

    return {
        "weights": weights.tolist(),
        "expected_vol": round(_portfolio_vol(weights, cov_matrix), 6),
        "converged": result.success,
    }


def efficient_frontier(
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n_points: int = 20,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
) -> list[dict]:
    """
    Trace the efficient frontier across n_points target return levels.
    Returns list of {target_return, weights, vol, sharpe} dicts.
    """
    min_ret = expected_returns.min()
    max_ret = expected_returns.max()
    target_returns = np.linspace(min_ret, max_ret, n_points)

    n = len(expected_returns)
    frontier = []

    for target in target_returns:
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "eq", "fun": lambda w, t=target: _portfolio_return(w, expected_returns) - t},
        ]
        result = minimize(
            lambda w: _portfolio_vol(w, cov_matrix),
            np.ones(n) / n,
            method="SLSQP",
            bounds=[(min_weight, max_weight)] * n,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 500},
        )
        if result.success:
            w = np.clip(result.x, 0, 1)
            w /= w.sum()
            vol = _portfolio_vol(w, cov_matrix)
            frontier.append({
                "target_return": round(float(target), 6),
                "weights": w.tolist(),
                "vol": round(vol, 6),
            })

    return frontier


def covariance_from_returns(
    returns_df: pd.DataFrame,
    method: str = "sample",
    trading_days: int = 252,
) -> np.ndarray:
    """
    Estimate annualized covariance matrix.
    method: "sample" (standard), "shrinkage" (Ledoit-Wolf).
    """
    if method == "shrinkage":
        from sklearn.covariance import LedoitWolf
        lw = LedoitWolf().fit(returns_df.dropna())
        return lw.covariance_ * trading_days

    return returns_df.dropna().cov().values * trading_days
