"""
Volatility Engine: forecasts volatility, term structure, and regime for position sizing.

Combines EWMA, GARCH(1,1), and Parkinson estimators.
Primary output: annualized forward vol estimate (scalar) per symbol.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from ..math.volatility import (
    ewma_vol_scalar, historical_vol_scalar, parkinson_vol,
    garch_vol_forecast, vol_regime_label, vol_term_structure,
)


@dataclass
class VolatilityEstimate:
    symbol: str
    spot_vol: float             # annualized current vol (primary estimate)
    ewma_vol: float
    hist_vol: float
    garch_vol: Optional[float]  # None if GARCH failed
    garch_forecast_5d: Optional[list[float]]
    parkinson_vol: Optional[float]
    vol_regime: str             # low_vol / normal_vol / high_vol / crisis_vol
    term_structure: list[float] # [10d, 30d, 60d, 252d]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class VolatilityEngine:
    def __init__(self, config: dict):
        cfg = config.get("volatility", {})
        self.ewma_lambda       = cfg.get("ewma_lambda", 0.94)
        self.hist_window       = cfg.get("hist_window", 60)
        self.garch_horizon     = cfg.get("garch_forecast_horizon", 5)
        self.parkinson_window  = cfg.get("parkinson_window", 20)
        self.vol_low           = cfg.get("vol_low_threshold", 0.15)
        self.vol_high          = cfg.get("vol_high_threshold", 0.35)
        self.vol_crisis        = cfg.get("vol_crisis_threshold", 0.55)
        self._cache: dict[str, VolatilityEstimate] = {}

    def estimate(
        self,
        symbol: str,
        prices: pd.Series,
        highs: Optional[pd.Series] = None,
        lows: Optional[pd.Series] = None,
        use_garch: bool = True,
    ) -> VolatilityEstimate:
        """
        Produce a full vol estimate for a symbol.
        Caches result; call invalidate(symbol) to force refresh.
        """
        ewma = ewma_vol_scalar(prices, self.ewma_lambda)
        hist = historical_vol_scalar(prices, self.hist_window)

        # Parkinson (needs OHLC)
        park = None
        if highs is not None and lows is not None and len(highs) >= self.parkinson_window:
            p_series = parkinson_vol(highs, lows, self.parkinson_window)
            if not p_series.empty:
                park = float(p_series.iloc[-1]) if not np.isnan(p_series.iloc[-1]) else None

        # GARCH
        garch_current = None
        garch_fcast = None
        if use_garch and len(prices) >= 100:
            try:
                g = garch_vol_forecast(prices, self.garch_horizon)
                garch_current = g.get("current_vol")
                garch_fcast = g.get("forecast_vols")
            except Exception:
                pass

        # Blend: EWMA primary, adjust if GARCH differs significantly
        spot = ewma
        if garch_current is not None and abs(garch_current - ewma) / max(ewma, 1e-6) > 0.20:
            # Weight 60/40 toward EWMA (faster, more reactive)
            spot = 0.60 * ewma + 0.40 * garch_current

        vol_label = vol_regime_label(spot, self.vol_low, self.vol_high, self.vol_crisis)

        ts = vol_term_structure(prices, windows=[10, 30, 60, 252])

        est = VolatilityEstimate(
            symbol=symbol,
            spot_vol=round(spot, 6),
            ewma_vol=round(ewma, 6),
            hist_vol=round(hist, 6),
            garch_vol=round(garch_current, 6) if garch_current is not None else None,
            garch_forecast_5d=[round(v, 6) for v in garch_fcast] if garch_fcast else None,
            parkinson_vol=round(park, 6) if park is not None else None,
            vol_regime=vol_label,
            term_structure=[round(float(v), 6) for v in ts.values()],
        )
        self._cache[symbol] = est
        return est

    def spot_vol(self, symbol: str) -> Optional[float]:
        """Return cached spot vol, or None if not yet computed."""
        est = self._cache.get(symbol)
        return est.spot_vol if est else None

    def invalidate(self, symbol: str) -> None:
        self._cache.pop(symbol, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    def vol_scaling_factor(
        self,
        symbol: str,
        target_vol: float = 0.15,
    ) -> float:
        """
        Vol targeting scalar: target_vol / spot_vol.
        Clamps to [0.25, 2.0] to avoid extreme leverage or under-sizing.
        """
        v = self.spot_vol(symbol)
        if v is None or v <= 0:
            return 1.0
        return float(np.clip(target_vol / v, 0.25, 2.0))

    def portfolio_vol(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        annualize: bool = True,
        trading_days: int = 252,
    ) -> float:
        """Annualized portfolio vol given weight vector and covariance matrix."""
        daily_var = float(weights @ cov_matrix @ weights)
        daily_vol = np.sqrt(daily_var)
        return float(daily_vol * np.sqrt(trading_days)) if annualize else float(daily_vol)
