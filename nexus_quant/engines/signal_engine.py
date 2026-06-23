"""
Signal Engine: wraps math/signals.py into a stateful engine.

Generates structured Signal objects per strategy, gated by RegimeState.
Strategies: momentum, mean_reversion, pairs, factor.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from ..math.signals import (
    momentum_signal, mean_reversion_signal, bollinger_signal,
    macd_signal, rsi, pair_zscore, cointegration_check,
    relative_volume, volume_breakout_signal,
    cross_sectional_momentum,
)
from .regime_engine import RegimeState


@dataclass
class Signal:
    strategy: str          # momentum / mean_reversion / pairs / factor
    asset: str
    direction: float       # +1 = long, -1 = short, 0 = flat
    strength: float        # 0–1 normalized signal strength
    confidence: float      # 0–1 composite confidence
    timeframe: str         # daily / intraday
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class SignalEngine:
    def __init__(self, config: dict):
        cfg = config.get("signals", {})

        mom = cfg.get("momentum", {})
        self.mom_lookback  = mom.get("lookback", 20)
        self.mom_skip_last = mom.get("skip_last", 1)

        mr = cfg.get("mean_reversion", {})
        self.mr_window   = mr.get("window", 20)
        self.mr_entry_z  = mr.get("entry_zscore", 2.0)
        self.mr_exit_z   = mr.get("exit_zscore", 0.5)

        pa = cfg.get("pairs", {})
        self.pairs_window  = pa.get("window", 60)
        self.pairs_entry_z = pa.get("entry_zscore", 2.0)
        self.pairs_min_coint_pvalue = pa.get("min_coint_pvalue", 0.05)

        fac = cfg.get("factor", {})
        self.factor_lookback = fac.get("momentum_lookback", 252)
        self.factor_top_n    = fac.get("cross_section_top_n", 5)

        vol = cfg.get("volume", {})
        self.vol_window    = vol.get("window", 20)
        self.vol_threshold = vol.get("threshold", 1.5)

    # ─── Public API ──────────────────────────────────────────────────────────

    def generate(
        self,
        symbol: str,
        prices: pd.Series,
        volume: Optional[pd.Series],
        regime: RegimeState,
        timeframe: str = "daily",
    ) -> list[Signal]:
        """Generate all enabled signals for a single asset."""
        signals: list[Signal] = []
        enabled = set(regime.enabled_strategies)

        if "momentum" in enabled:
            s = self._momentum(symbol, prices, volume, timeframe)
            if s:
                signals.append(s)

        if "mean_reversion" in enabled:
            s = self._mean_reversion(symbol, prices, volume, timeframe)
            if s:
                signals.append(s)

        return signals

    def generate_pairs(
        self,
        sym_a: str,
        sym_b: str,
        prices_a: pd.Series,
        prices_b: pd.Series,
        regime: RegimeState,
    ) -> Optional[Signal]:
        """Generate a pairs signal if 'pairs' strategy is enabled."""
        if "pairs" not in regime.enabled_strategies:
            return None
        return self._pairs(sym_a, sym_b, prices_a, prices_b)

    def generate_cross_section(
        self,
        returns_df: pd.DataFrame,
        regime: RegimeState,
        timeframe: str = "daily",
    ) -> list[Signal]:
        """Cross-sectional momentum across multiple assets."""
        if "momentum" not in regime.enabled_strategies:
            return []

        raw = cross_sectional_momentum(
            returns_df, self.factor_lookback, self.factor_top_n
        )
        signals = []
        for sym, direction in raw.items():
            if direction == 0.0:
                continue
            signals.append(Signal(
                strategy="momentum",
                asset=sym,
                direction=direction,
                strength=1.0,
                confidence=0.6,
                timeframe=timeframe,
                metadata={"type": "cross_sectional"},
            ))
        return signals

    # ─── Internal Strategy Builders ──────────────────────────────────────────

    def _momentum(
        self,
        symbol: str,
        prices: pd.Series,
        volume: Optional[pd.Series],
        timeframe: str,
    ) -> Optional[Signal]:
        raw = momentum_signal(prices, self.mom_lookback, self.mom_skip_last)
        if abs(raw) < 0.1:
            return None

        macd_line, sig_line, hist = macd_signal(prices)
        rsi14 = rsi(prices)
        vol_confirm = (
            volume_breakout_signal(volume, self.vol_window, self.vol_threshold)
            if volume is not None and len(volume) > self.vol_window
            else 0.0
        )

        direction = 1.0 if raw > 0 else -1.0
        strength = abs(raw)

        # Confidence: MACD alignment + RSI alignment + volume confirmation
        conf = 0.0
        if (hist > 0 and direction > 0) or (hist < 0 and direction < 0):
            conf += 0.35
        rsi_aligned = (direction > 0 and rsi14 > 50) or (direction < 0 and rsi14 < 50)
        if rsi_aligned:
            conf += 0.35
        conf += vol_confirm * 0.30

        return Signal(
            strategy="momentum",
            asset=symbol,
            direction=direction,
            strength=strength,
            confidence=round(conf, 3),
            timeframe=timeframe,
            metadata={
                "mom_raw": round(raw, 4),
                "macd_hist": round(hist, 4),
                "rsi_14": round(rsi14, 1),
                "vol_confirm": vol_confirm,
            },
        )

    def _mean_reversion(
        self,
        symbol: str,
        prices: pd.Series,
        volume: Optional[pd.Series],
        timeframe: str,
    ) -> Optional[Signal]:
        direction, strength = mean_reversion_signal(
            prices, self.mr_window, self.mr_entry_z, self.mr_exit_z
        )
        if direction == 0.0:
            return None

        bb = bollinger_signal(prices, self.mr_window)
        rsi14 = rsi(prices)

        # Confirm direction with Bollinger and RSI
        conf = 0.0
        if direction > 0:
            # Buying the dip: Bollinger and RSI should agree
            if bb > 0.3:
                conf += 0.35
            if rsi14 < 40:
                conf += 0.35
        else:
            if bb < -0.3:
                conf += 0.35
            if rsi14 > 60:
                conf += 0.35
        conf += min(strength, 1.0) * 0.30

        return Signal(
            strategy="mean_reversion",
            asset=symbol,
            direction=direction,
            strength=strength,
            confidence=round(conf, 3),
            timeframe=timeframe,
            metadata={
                "zscore": round(
                    float(
                        (prices.iloc[-1] - prices.iloc[-self.mr_window:].mean())
                        / max(prices.iloc[-self.mr_window:].std(), 1e-9)
                    ),
                    3,
                ),
                "bollinger": round(bb, 3),
                "rsi_14": round(rsi14, 1),
            },
        )

    def _pairs(
        self,
        sym_a: str,
        sym_b: str,
        prices_a: pd.Series,
        prices_b: pd.Series,
    ) -> Optional[Signal]:
        if len(prices_a) < self.pairs_window or len(prices_b) < self.pairs_window:
            return None

        z = pair_zscore(prices_a, prices_b, self.pairs_window)
        if abs(z) < self.pairs_entry_z:
            return None

        # Cointegration check on recent window to validate pair
        coint = cointegration_check(
            prices_a.iloc[-self.pairs_window:],
            prices_b.iloc[-self.pairs_window:],
        )
        if coint.get("p_value") is not None and coint["p_value"] > self.pairs_min_coint_pvalue:
            return None  # Not cointegrated — skip

        # z > +2 → spread too wide → sell A / buy B (direction = -1 for A)
        direction = -1.0 if z > 0 else 1.0
        strength = min(abs(z) / (self.pairs_entry_z * 2), 1.0)
        conf = 0.7 if coint.get("is_cointegrated") else 0.5

        return Signal(
            strategy="pairs",
            asset=f"{sym_a}/{sym_b}",
            direction=direction,
            strength=round(strength, 3),
            confidence=round(conf, 3),
            timeframe="daily",
            metadata={
                "zscore": round(z, 3),
                "pair_a": sym_a,
                "pair_b": sym_b,
                "coint_pvalue": coint.get("p_value"),
            },
        )
