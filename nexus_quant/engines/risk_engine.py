"""
Risk Engine: position sizing, drawdown control, VaR/ES limits, kill switch.

All sizing goes through this engine before an order is submitted.
Hard limits are enforced regardless of signal strength.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import numpy as np
import pandas as pd

from ..math.risk_metrics import (
    var_historical, var_parametric, expected_shortfall,
    kelly_from_trades, current_drawdown, max_drawdown,
)
from .regime_engine import RegimeState
from .volatility_engine import VolatilityEstimate


@dataclass
class PositionSize:
    symbol: str
    notional: float          # dollar notional to trade
    shares: int              # floor(notional / price)
    reason: str              # how size was determined
    kelly_fraction: float
    vol_scalar: float
    regime_scalar: float
    approved: bool           # False if any hard limit is breached


@dataclass
class RiskSnapshot:
    portfolio_var_95: float
    portfolio_es_95: float
    current_drawdown: float
    max_drawdown: float
    gross_exposure: float
    net_exposure: float
    num_positions: int
    kill_switch_active: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    warnings: list[str] = field(default_factory=list)


class RiskEngine:
    def __init__(self, config: dict):
        cfg = config.get("risk", {})
        self.max_position_pct    = cfg.get("max_position_pct", 0.10)
        self.max_gross_exposure  = cfg.get("max_gross_exposure", 1.50)
        self.max_net_exposure    = cfg.get("max_net_exposure", 0.80)
        self.daily_loss_limit    = cfg.get("daily_loss_limit_pct", 0.02)
        self.drawdown_limit      = cfg.get("drawdown_limit_pct", 0.15)
        self.var_limit_pct       = cfg.get("var_limit_pct", 0.03)
        self.target_vol          = cfg.get("target_vol", 0.15)
        self.kelly_fraction      = cfg.get("kelly_fraction", 0.25)
        self.min_equity          = cfg.get("min_equity", 1000.0)
        self._kill_switch        = False
        self._daily_pnl          = 0.0
        self._daily_pnl_date     = None

    # ─── Kill Switch ──────────────────────────────────────────────────────────

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch

    def activate_kill_switch(self, reason: str) -> None:
        self._kill_switch = True

    def reset_kill_switch(self) -> None:
        self._kill_switch = False

    def update_daily_pnl(self, pnl: float) -> None:
        today = date.today()
        if self._daily_pnl_date != today:
            self._daily_pnl = 0.0
            self._daily_pnl_date = today
        self._daily_pnl += pnl

    # ─── Position Sizing ──────────────────────────────────────────────────────

    def size_position(
        self,
        symbol: str,
        price: float,
        equity: float,
        vol_est: VolatilityEstimate,
        regime: RegimeState,
        pnl_history: Optional[pd.Series] = None,
    ) -> PositionSize:
        """
        Compute position size via volatility targeting × Kelly × regime scaling.
        Returns PositionSize with approved=False if hard limits are breached.
        """
        if self._kill_switch:
            return PositionSize(
                symbol=symbol, notional=0, shares=0,
                reason="Kill switch active", kelly_fraction=0,
                vol_scalar=0, regime_scalar=0, approved=False,
            )

        if equity < self.min_equity:
            return PositionSize(
                symbol=symbol, notional=0, shares=0,
                reason=f"Equity ${equity:.0f} below minimum ${self.min_equity:.0f}",
                kelly_fraction=0, vol_scalar=0, regime_scalar=0, approved=False,
            )

        # 1. Vol-targeted notional
        spot_vol = vol_est.spot_vol if vol_est.spot_vol > 0 else self.target_vol
        vol_scalar = min(self.target_vol / spot_vol, 2.0)

        # 2. Kelly fraction from trade history
        kf = self.kelly_fraction
        if pnl_history is not None and len(pnl_history) >= 20:
            kf = kelly_from_trades(pnl_history, self.kelly_fraction)
            kf = max(kf, 0.05)  # floor at 5% to avoid going to zero

        # 3. Regime scalar
        regime_scalar = self._regime_scalar(regime)

        # 4. Max position cap
        max_notional = equity * self.max_position_pct

        notional = equity * vol_scalar * kf * regime_scalar
        notional = min(notional, max_notional)

        if price <= 0:
            return PositionSize(
                symbol=symbol, notional=0, shares=0,
                reason="Invalid price", kelly_fraction=kf,
                vol_scalar=vol_scalar, regime_scalar=regime_scalar, approved=False,
            )

        shares = int(notional / price)
        if shares <= 0:
            return PositionSize(
                symbol=symbol, notional=0, shares=0,
                reason="Computed 0 shares",
                kelly_fraction=kf, vol_scalar=vol_scalar,
                regime_scalar=regime_scalar, approved=True,
            )

        reason = (
            f"vol_scalar={vol_scalar:.2f} × kelly={kf:.3f} × regime={regime_scalar:.2f} "
            f"→ ${notional:.0f}"
        )
        return PositionSize(
            symbol=symbol,
            notional=round(notional, 2),
            shares=shares,
            reason=reason,
            kelly_fraction=round(kf, 4),
            vol_scalar=round(vol_scalar, 4),
            regime_scalar=round(regime_scalar, 4),
            approved=True,
        )

    # ─── Portfolio Risk Snapshot ───────────────────────────────────────────────

    def snapshot(
        self,
        equity_curve: pd.Series,
        returns: pd.Series,
        positions: list[dict],
        equity: float,
    ) -> RiskSnapshot:
        """Compute aggregate portfolio risk metrics."""
        warnings = []

        var95 = var_historical(returns) if len(returns) >= 20 else float("nan")
        es95  = expected_shortfall(returns) if len(returns) >= 20 else float("nan")

        dd_current = current_drawdown(equity_curve) if len(equity_curve) >= 2 else 0.0
        dd_max     = max_drawdown(equity_curve) if len(equity_curve) >= 2 else 0.0

        gross_exp = sum(abs(p.get("market_value", 0)) for p in positions) / max(equity, 1)
        net_exp   = sum(p.get("market_value", 0) for p in positions) / max(equity, 1)

        # Hard limit checks
        kill = self._kill_switch
        if dd_current >= self.drawdown_limit:
            warnings.append(f"Drawdown {dd_current:.1%} >= limit {self.drawdown_limit:.1%}")
            self.activate_kill_switch("Drawdown limit breached")
            kill = True

        if not np.isnan(var95) and var95 >= self.var_limit_pct:
            warnings.append(f"Daily VaR {var95:.1%} >= limit {self.var_limit_pct:.1%}")

        if gross_exp > self.max_gross_exposure:
            warnings.append(f"Gross exposure {gross_exp:.1%} > limit {self.max_gross_exposure:.1%}")

        daily_loss_pct = -self._daily_pnl / max(equity, 1)
        if daily_loss_pct >= self.daily_loss_limit:
            warnings.append(f"Daily loss {daily_loss_pct:.1%} >= limit {self.daily_loss_limit:.1%}")
            self.activate_kill_switch("Daily loss limit hit")
            kill = True

        return RiskSnapshot(
            portfolio_var_95=round(var95, 4) if not np.isnan(var95) else 0.0,
            portfolio_es_95=round(es95, 4) if not np.isnan(es95) else 0.0,
            current_drawdown=round(dd_current, 4),
            max_drawdown=round(dd_max, 4),
            gross_exposure=round(gross_exp, 4),
            net_exposure=round(net_exp, 4),
            num_positions=len(positions),
            kill_switch_active=kill,
            warnings=warnings,
        )

    # ─── Checks ───────────────────────────────────────────────────────────────

    def check_order(
        self,
        symbol: str,
        notional: float,
        equity: float,
        gross_exposure: float,
    ) -> tuple[bool, str]:
        """Pre-trade check. Returns (approved, reason)."""
        if self._kill_switch:
            return False, "Kill switch active"
        if notional / max(equity, 1) > self.max_position_pct:
            return False, f"Single position > {self.max_position_pct:.0%} of equity"
        if gross_exposure + notional / equity > self.max_gross_exposure:
            return False, f"Order would breach gross exposure limit {self.max_gross_exposure:.0%}"
        return True, "OK"

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _regime_scalar(self, regime: RegimeState) -> float:
        """Reduce position sizes in adverse regimes."""
        scalars = {
            "crisis":     0.20,
            "high_vol":   0.50,
            "bear_trend": 0.60,
            "sideways":   0.80,
            "low_vol":    0.90,
            "bull_trend": 1.00,
        }
        return scalars.get(regime.regime, 0.80)
