"""
Regime Engine: classifies current market state and decides which strategies to enable.

Regimes: bull_trend, bear_trend, sideways, high_vol, low_vol, crisis.
Classification uses: vol, MA slope, drawdown from peak, cross-asset signals.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd

from ..math.volatility import ewma_vol_scalar, vol_regime_label
from ..math.signals import rsi


@dataclass
class RegimeState:
    regime: str                   # primary regime label
    vol_regime: str               # low_vol / normal_vol / high_vol / crisis_vol
    trend: str                    # bull_trend / bear_trend / sideways
    annualized_vol: float
    rsi_14: float
    ma_fast: float
    ma_slow: float
    drawdown_from_peak: float
    enabled_strategies: list[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: list[str] = field(default_factory=list)


class RegimeEngine:
    def __init__(self, config: dict):
        cfg = config.get("regime", {})
        self.vol_low       = cfg.get("vol_low_threshold", 0.15)
        self.vol_high      = cfg.get("vol_high_threshold", 0.35)
        self.vol_crisis    = cfg.get("vol_crisis_threshold", 0.55)
        self.ma_fast       = cfg.get("trend_ma_fast", 20)
        self.ma_slow       = cfg.get("trend_ma_slow", 50)
        self.dd_crisis     = cfg.get("drawdown_crisis_threshold", 0.10)
        self.strategy_map  = cfg.get("strategy_map", {})
        self._equity_peak  = None

    def classify(
        self,
        index_prices: pd.Series,       # e.g. SPY daily closes
        vol_override: Optional[float] = None,
    ) -> RegimeState:
        """
        Classify the current market regime from index price series.
        Returns a RegimeState with enabled strategies.
        """
        if len(index_prices) < self.ma_slow + 5:
            return self._default_regime("Insufficient data for regime classification")

        ann_vol = vol_override or ewma_vol_scalar(index_prices)
        vol_label = vol_regime_label(ann_vol, self.vol_low, self.vol_high, self.vol_crisis)

        ma_f = float(index_prices.iloc[-self.ma_fast:].mean())
        ma_s = float(index_prices.iloc[-self.ma_slow:].mean())
        rsi14 = rsi(index_prices)

        # Drawdown from 52-week peak
        peak = index_prices.iloc[-252:].max() if len(index_prices) >= 252 else index_prices.max()
        current = index_prices.iloc[-1]
        drawdown = float((peak - current) / peak)

        notes = []

        # ── Crisis override ───────────────────────────────────────────────────
        if vol_label == "crisis_vol" or drawdown >= self.dd_crisis:
            notes.append(f"CRISIS: vol={ann_vol:.1%}, drawdown={drawdown:.1%}")
            return RegimeState(
                regime="crisis",
                vol_regime=vol_label,
                trend="bear_trend",
                annualized_vol=ann_vol,
                rsi_14=rsi14,
                ma_fast=ma_f,
                ma_slow=ma_s,
                drawdown_from_peak=drawdown,
                enabled_strategies=self.strategy_map.get("crisis", []),
                confidence=0.9,
                notes=notes,
            )

        # ── Trend classification ──────────────────────────────────────────────
        ma_spread = (ma_f - ma_s) / ma_s  # positive = price above slow MA = bull
        if ma_spread > 0.02 and rsi14 > 50:
            trend = "bull_trend"
            notes.append(f"MA fast {ma_spread:+.1%} above slow, RSI={rsi14:.0f}")
        elif ma_spread < -0.02 and rsi14 < 50:
            trend = "bear_trend"
            notes.append(f"MA fast {ma_spread:+.1%} below slow, RSI={rsi14:.0f}")
        else:
            trend = "sideways"
            notes.append(f"MAs converged ({ma_spread:+.1%}), RSI={rsi14:.0f}")

        # ── Primary regime: vol takes priority over trend in high-vol environments
        if vol_label == "high_vol":
            regime = "high_vol"
        elif vol_label == "low_vol":
            regime = "low_vol"
        else:
            regime = trend   # normal vol → regime = trend direction

        confidence = self._compute_confidence(ma_spread, vol_label, rsi14, drawdown)
        enabled = self.strategy_map.get(regime, self.strategy_map.get("sideways", []))

        return RegimeState(
            regime=regime,
            vol_regime=vol_label,
            trend=trend,
            annualized_vol=ann_vol,
            rsi_14=rsi14,
            ma_fast=ma_f,
            ma_slow=ma_s,
            drawdown_from_peak=drawdown,
            enabled_strategies=enabled,
            confidence=confidence,
            notes=notes,
        )

    def is_strategy_enabled(self, strategy_name: str, regime: RegimeState) -> bool:
        return strategy_name in regime.enabled_strategies

    def _compute_confidence(
        self, ma_spread: float, vol_label: str, rsi14: float, drawdown: float
    ) -> float:
        score = 0.0
        # Strong MA signal
        score += min(abs(ma_spread) / 0.05, 1.0) * 0.40
        # RSI alignment
        if (ma_spread > 0 and rsi14 > 55) or (ma_spread < 0 and rsi14 < 45):
            score += 0.30
        # Vol regime is clear (not borderline)
        if vol_label in ("low_vol", "crisis_vol"):
            score += 0.20
        # Low drawdown = stable regime
        score += max(0, 0.10 - drawdown)
        return round(min(score, 1.0), 3)

    def _default_regime(self, note: str) -> RegimeState:
        return RegimeState(
            regime="sideways",
            vol_regime="normal_vol",
            trend="sideways",
            annualized_vol=0.20,
            rsi_14=50.0,
            ma_fast=100.0,
            ma_slow=100.0,
            drawdown_from_peak=0.0,
            enabled_strategies=self.strategy_map.get("sideways", []),
            confidence=0.0,
            notes=[note],
        )
