"""
Monitoring Engine: tracks live system health, emits structured alerts.

Monitors: strategy P&L, drawdown, signal quality, execution failures,
data staleness, and regime transitions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─── Alert Levels ─────────────────────────────────────────────────────────────

INFO  = "INFO"
WARN  = "WARN"
ERROR = "ERROR"
FATAL = "FATAL"


@dataclass
class Alert:
    level: str           # INFO / WARN / ERROR / FATAL
    source: str          # which engine / metric triggered this
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SystemSnapshot:
    timestamp: datetime
    equity: float
    daily_pnl: float
    daily_pnl_pct: float
    drawdown: float
    open_positions: int
    orders_today: int
    signals_today: int
    regime: str
    vol_regime: str
    data_staleness_seconds: float
    kill_switch_active: bool
    alerts: list[Alert]


class MonitoringEngine:
    def __init__(self, config: dict):
        cfg = config.get("monitoring", {})
        self.alert_drawdown_warn   = cfg.get("alert_drawdown_warn", 0.08)
        self.alert_drawdown_error  = cfg.get("alert_drawdown_error", 0.12)
        self.alert_daily_loss_warn = cfg.get("alert_daily_loss_warn", 0.015)
        self.alert_daily_loss_err  = cfg.get("alert_daily_loss_error", 0.025)
        self.data_stale_seconds    = cfg.get("data_stale_warn_seconds", 300)
        self.min_signal_quality    = cfg.get("min_signal_quality", 0.30)

        self._alerts: list[Alert] = []
        self._daily_orders: int   = 0
        self._daily_signals: int  = 0
        self._daily_pnl: float    = 0.0
        self._sod_equity: Optional[float] = None
        self._last_data_ts: Optional[datetime] = None
        self._current_date = date.today()

    # ─── Event Ingestion ──────────────────────────────────────────────────────

    def on_market_data(self, symbol: str, timestamp: datetime) -> None:
        self._last_data_ts = timestamp

    def on_signal(self, strategy: str, symbol: str, confidence: float) -> None:
        self._check_day_rollover()
        self._daily_signals += 1
        if confidence < self.min_signal_quality:
            self._emit(WARN, "signal_quality",
                       f"Low-confidence signal: {strategy}/{symbol}",
                       value=confidence, threshold=self.min_signal_quality)

    def on_order_submitted(self, symbol: str, notional: float) -> None:
        self._check_day_rollover()
        self._daily_orders += 1

    def on_order_failed(self, symbol: str, reason: str) -> None:
        self._emit(ERROR, "execution", f"Order failed for {symbol}: {reason}")

    def on_pnl_update(self, pnl_delta: float, equity: float) -> None:
        self._check_day_rollover()
        self._daily_pnl += pnl_delta
        if self._sod_equity is None:
            self._sod_equity = equity

        daily_loss_pct = -self._daily_pnl / max(self._sod_equity or equity, 1)
        if daily_loss_pct >= self.alert_daily_loss_err:
            self._emit(ERROR, "daily_pnl",
                       f"Daily loss {daily_loss_pct:.1%} exceeds error threshold",
                       value=daily_loss_pct, threshold=self.alert_daily_loss_err)
        elif daily_loss_pct >= self.alert_daily_loss_warn:
            self._emit(WARN, "daily_pnl",
                       f"Daily loss {daily_loss_pct:.1%} exceeds warn threshold",
                       value=daily_loss_pct, threshold=self.alert_daily_loss_warn)

    def on_drawdown(self, drawdown: float) -> None:
        if drawdown >= self.alert_drawdown_error:
            self._emit(ERROR, "drawdown",
                       f"Drawdown {drawdown:.1%} exceeds error threshold",
                       value=drawdown, threshold=self.alert_drawdown_error)
        elif drawdown >= self.alert_drawdown_warn:
            self._emit(WARN, "drawdown",
                       f"Drawdown {drawdown:.1%} exceeds warn threshold",
                       value=drawdown, threshold=self.alert_drawdown_warn)

    def on_regime_change(self, old_regime: str, new_regime: str) -> None:
        self._emit(INFO, "regime",
                   f"Regime transition: {old_regime} → {new_regime}")

    def on_kill_switch(self, reason: str) -> None:
        self._emit(FATAL, "kill_switch", f"Kill switch activated: {reason}")

    # ─── Snapshot ─────────────────────────────────────────────────────────────

    def snapshot(
        self,
        equity: float,
        drawdown: float,
        open_positions: int,
        regime: str,
        vol_regime: str,
        kill_switch_active: bool,
    ) -> SystemSnapshot:
        staleness = 0.0
        if self._last_data_ts:
            staleness = (datetime.utcnow() - self._last_data_ts).total_seconds()
            if staleness > self.data_stale_seconds:
                self._emit(WARN, "data_feed",
                           f"Market data stale for {staleness:.0f}s",
                           value=staleness, threshold=self.data_stale_seconds)

        daily_pnl_pct = (
            self._daily_pnl / max(self._sod_equity or equity, 1)
        )

        snap = SystemSnapshot(
            timestamp=datetime.utcnow(),
            equity=equity,
            daily_pnl=round(self._daily_pnl, 2),
            daily_pnl_pct=round(daily_pnl_pct, 4),
            drawdown=drawdown,
            open_positions=open_positions,
            orders_today=self._daily_orders,
            signals_today=self._daily_signals,
            regime=regime,
            vol_regime=vol_regime,
            data_staleness_seconds=round(staleness, 1),
            kill_switch_active=kill_switch_active,
            alerts=list(self._alerts),
        )
        return snap

    def clear_alerts(self) -> None:
        self._alerts.clear()

    def recent_alerts(self, level: Optional[str] = None) -> list[Alert]:
        if level:
            return [a for a in self._alerts if a.level == level]
        return list(self._alerts)

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _emit(
        self,
        level: str,
        source: str,
        message: str,
        value: Optional[float] = None,
        threshold: Optional[float] = None,
    ) -> None:
        alert = Alert(level=level, source=source, message=message,
                      value=value, threshold=threshold)
        self._alerts.append(alert)
        log_fn = {
            INFO:  logger.info,
            WARN:  logger.warning,
            ERROR: logger.error,
            FATAL: logger.critical,
        }.get(level, logger.info)
        log_fn(f"[{source}] {message}")

    def _check_day_rollover(self) -> None:
        today = date.today()
        if today != self._current_date:
            self._daily_orders  = 0
            self._daily_signals = 0
            self._daily_pnl     = 0.0
            self._sod_equity    = None
            self._current_date  = today
