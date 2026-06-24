"""
Portfolio Engine: target-weight construction via Markowitz / min-variance / risk parity.

Converts signal strengths and regime context into target portfolio weights,
then sizes positions against current holdings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from ..math.optimization import (
    max_sharpe_portfolio, min_variance_portfolio,
    risk_parity_portfolio, covariance_from_returns,
)
from ..math.risk_metrics import current_drawdown
from .regime_engine import RegimeState
from .signal_engine import Signal


@dataclass
class TargetAllocation:
    method: str                          # max_sharpe / min_variance / risk_parity / equal_weight
    weights: dict[str, float]            # symbol → weight (sum = 1)
    expected_vol: float
    expected_return: Optional[float]
    sharpe: Optional[float]
    converged: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: list[str] = field(default_factory=list)


@dataclass
class RebalanceTrade:
    symbol: str
    current_weight: float
    target_weight: float
    delta_weight: float
    direction: str   # "buy" / "sell" / "hold"
    notional: float  # abs dollar amount


class PortfolioEngine:
    def __init__(self, config: dict):
        cfg = config.get("portfolio", {})
        self.method             = cfg.get("optimization_method", "min_variance")
        self.risk_free          = cfg.get("risk_free_rate", 0.043)
        self.min_weight         = cfg.get("min_weight", 0.0)
        self.max_weight         = cfg.get("max_weight", 0.30)
        self.rebalance_thresh   = cfg.get("rebalance_threshold_pct", 0.05)
        self.cov_method         = cfg.get("cov_method", "shrinkage")
        self.cash_buffer        = cfg.get("cash_buffer_pct", 0.05)
        self.trading_days       = cfg.get("trading_days", 252)

    def compute_target(
        self,
        symbols: list[str],
        returns_df: pd.DataFrame,
        signals: list[Signal],
        regime: RegimeState,
        expected_returns: Optional[np.ndarray] = None,
    ) -> TargetAllocation:
        """
        Compute target weights for a portfolio.

        symbols: ordered list of tickers
        returns_df: DataFrame of daily returns (columns = symbols)
        signals: Signal objects driving direction preference
        regime: current market regime
        expected_returns: optional array; required for max_sharpe
        """
        if len(symbols) == 0:
            return self._empty_allocation()

        # Universe filter: only include symbols with sufficient return history
        valid = [s for s in symbols if s in returns_df.columns
                 and returns_df[s].dropna().shape[0] >= 60]

        if len(valid) == 0:
            return self._equal_weight(symbols, "Insufficient history for all symbols")

        ret_sub = returns_df[valid].dropna()
        if ret_sub.shape[0] < 30:
            return self._equal_weight(valid, "Too few observations for optimization")

        cov = covariance_from_returns(ret_sub, method=self.cov_method,
                                       trading_days=self.trading_days)

        # Choose method based on regime (override config in crisis)
        method = self.method
        if regime.regime == "crisis":
            method = "min_variance"   # most defensive

        notes = [f"Method: {method}, regime: {regime.regime}"]

        if method == "max_sharpe":
            if expected_returns is None:
                notes.append("No expected_returns supplied → falling back to min_variance")
                method = "min_variance"
            else:
                res = max_sharpe_portfolio(
                    expected_returns, cov,
                    risk_free=self.risk_free,
                    min_weight=self.min_weight,
                    max_weight=self.max_weight,
                )
                if not res:
                    return self._equal_weight(valid, "max_sharpe returned empty")
                return TargetAllocation(
                    method="max_sharpe",
                    weights=dict(zip(valid, res["weights"])),
                    expected_vol=res["expected_vol"],
                    expected_return=res.get("expected_return"),
                    sharpe=res.get("sharpe"),
                    converged=res.get("converged", False),
                    notes=notes,
                )

        if method == "risk_parity":
            res = risk_parity_portfolio(cov)
        else:
            res = min_variance_portfolio(
                cov, min_weight=self.min_weight, max_weight=self.max_weight
            )

        weights = dict(zip(valid, res["weights"]))
        weights = self._apply_signal_tilt(weights, signals, valid)

        # Fill zeros for symbols not in valid set
        for sym in symbols:
            if sym not in weights:
                weights[sym] = 0.0

        return TargetAllocation(
            method=method,
            weights=weights,
            expected_vol=res.get("expected_vol", 0.0),
            expected_return=None,
            sharpe=None,
            converged=res.get("converged", False),
            notes=notes,
        )

    def compute_rebalance(
        self,
        target: TargetAllocation,
        current_positions: dict[str, float],  # symbol → current weight
        equity: float,
    ) -> list[RebalanceTrade]:
        """
        Determine which trades to execute to move from current to target weights.
        Only flags trades exceeding rebalance_threshold_pct drift.
        Respects cash_buffer: investable equity = equity × (1 - cash_buffer).
        """
        investable = equity * (1 - self.cash_buffer)
        trades = []

        all_symbols = set(target.weights) | set(current_positions)
        for sym in all_symbols:
            tgt = target.weights.get(sym, 0.0)
            cur = current_positions.get(sym, 0.0)
            delta = tgt - cur

            if abs(delta) < self.rebalance_thresh:
                direction = "hold"
            elif delta > 0:
                direction = "buy"
            else:
                direction = "sell"

            trades.append(RebalanceTrade(
                symbol=sym,
                current_weight=round(cur, 4),
                target_weight=round(tgt, 4),
                delta_weight=round(delta, 4),
                direction=direction,
                notional=round(abs(delta) * investable, 2),
            ))

        # Sort: sells first (free up cash), then buys
        trades.sort(key=lambda t: (t.direction != "sell", t.symbol))
        return [t for t in trades if t.direction != "hold"]

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _apply_signal_tilt(
        self,
        weights: dict[str, float],
        signals: list[Signal],
        valid_symbols: list[str],
    ) -> dict[str, float]:
        """
        Tilt optimizer weights toward signal direction.
        Maximum tilt: ±5% per signal (soft adjustment, not override).
        """
        tilt = 0.05
        for sig in signals:
            sym = sig.asset
            if sym not in weights:
                continue
            adjustment = sig.direction * sig.strength * sig.confidence * tilt
            weights[sym] = max(0.0, weights[sym] + adjustment)

        # Re-normalize after tilt
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        return weights

    def _equal_weight(self, symbols: list[str], note: str) -> TargetAllocation:
        n = len(symbols)
        w = 1.0 / n if n > 0 else 0.0
        return TargetAllocation(
            method="equal_weight",
            weights={s: round(w, 6) for s in symbols},
            expected_vol=0.0,
            expected_return=None,
            sharpe=None,
            converged=True,
            notes=[note],
        )

    def _empty_allocation(self) -> TargetAllocation:
        return TargetAllocation(
            method="none",
            weights={},
            expected_vol=0.0,
            expected_return=None,
            sharpe=None,
            converged=False,
            notes=["No symbols provided"],
        )
