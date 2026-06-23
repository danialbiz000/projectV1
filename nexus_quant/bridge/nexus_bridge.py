"""
Nexus Bridge: HTTP REST adapter between nexus_quant Python system and the Node.js Nexus server.

Sends structured signal payloads to POST /api/quant/signal on the Nexus server.
Polls Nexus for current portfolio state (positions, equity) via GET /api/alpaca/account.
Runs as a lightweight background loop.
"""

import logging
import time
from dataclasses import asdict
from datetime import datetime
from typing import Optional

import requests

from ..engines.signal_engine import Signal
from ..engines.regime_engine import RegimeState
from ..engines.risk_engine import RiskSnapshot
from ..engines.monitoring_engine import SystemSnapshot

logger = logging.getLogger(__name__)


class NexusBridge:
    def __init__(self, config: dict):
        cfg = config.get("nexus", {})
        self.base_url = cfg.get("url", "http://localhost:3000").rstrip("/")
        self.api_key  = cfg.get("api_key", "")
        self.timeout  = cfg.get("timeout_seconds", 10)
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"x-nexus-api-key": self.api_key})
        self._session.headers.update({"Content-Type": "application/json"})

    # ─── Outbound: Python → Node.js ───────────────────────────────────────────

    def send_signal(self, signal: Signal, regime: RegimeState) -> bool:
        """
        POST a trading signal to Nexus /api/quant/signal.
        Nexus can choose to act on it or log it.
        Returns True if accepted (2xx).
        """
        payload = {
            "strategy":    signal.strategy,
            "asset":       signal.asset,
            "direction":   signal.direction,
            "strength":    signal.strength,
            "confidence":  signal.confidence,
            "timeframe":   signal.timeframe,
            "regime":      regime.regime,
            "vol_regime":  regime.vol_regime,
            "metadata":    signal.metadata,
            "timestamp":   signal.timestamp.isoformat(),
        }
        return self._post("/api/quant/signal", payload)

    def send_risk_snapshot(self, snap: RiskSnapshot) -> bool:
        """POST risk snapshot to Nexus for display in the dashboard."""
        payload = {
            "portfolio_var_95":  snap.portfolio_var_95,
            "portfolio_es_95":   snap.portfolio_es_95,
            "current_drawdown":  snap.current_drawdown,
            "max_drawdown":      snap.max_drawdown,
            "gross_exposure":    snap.gross_exposure,
            "net_exposure":      snap.net_exposure,
            "num_positions":     snap.num_positions,
            "kill_switch_active": snap.kill_switch_active,
            "warnings":          snap.warnings,
            "timestamp":         snap.timestamp.isoformat(),
        }
        return self._post("/api/quant/risk", payload)

    def send_monitoring_snapshot(self, snap: SystemSnapshot) -> bool:
        """POST monitoring snapshot to Nexus."""
        payload = {
            "equity":               snap.equity,
            "daily_pnl":            snap.daily_pnl,
            "daily_pnl_pct":        snap.daily_pnl_pct,
            "drawdown":             snap.drawdown,
            "open_positions":       snap.open_positions,
            "orders_today":         snap.orders_today,
            "signals_today":        snap.signals_today,
            "regime":               snap.regime,
            "vol_regime":           snap.vol_regime,
            "data_staleness_s":     snap.data_staleness_seconds,
            "kill_switch_active":   snap.kill_switch_active,
            "alert_count":          len(snap.alerts),
            "timestamp":            snap.timestamp.isoformat(),
        }
        return self._post("/api/quant/monitoring", payload)

    def send_regime(self, regime: RegimeState) -> bool:
        """POST current regime to Nexus."""
        payload = {
            "regime":              regime.regime,
            "vol_regime":          regime.vol_regime,
            "trend":               regime.trend,
            "annualized_vol":      regime.annualized_vol,
            "rsi_14":              regime.rsi_14,
            "drawdown_from_peak":  regime.drawdown_from_peak,
            "confidence":          regime.confidence,
            "enabled_strategies":  regime.enabled_strategies,
            "notes":               regime.notes,
            "timestamp":           regime.timestamp.isoformat(),
        }
        return self._post("/api/quant/regime", payload)

    # ─── Inbound: Node.js → Python ────────────────────────────────────────────

    def get_account(self) -> dict:
        """Fetch Alpaca account data via Nexus proxy."""
        return self._get("/api/alpaca/account")

    def get_positions(self) -> list[dict]:
        """Fetch current positions via Nexus proxy."""
        data = self._get("/api/alpaca/positions")
        return data if isinstance(data, list) else []

    def get_equity(self) -> float:
        """Return portfolio equity from account data."""
        try:
            acc = self.get_account()
            return float(acc.get("equity", acc.get("portfolio_value", 0)))
        except Exception:
            return 0.0

    def get_config(self) -> dict:
        """Fetch current Nexus config (autotrader settings, watchlist)."""
        return self._get("/api/autotrader/status")

    # ─── Health ───────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Check if Nexus server is reachable."""
        try:
            resp = self._session.get(f"{self.base_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict) -> bool:
        try:
            url = f"{self.base_url}{path}"
            resp = self._session.post(url, json=payload, timeout=self.timeout)
            if not resp.ok:
                logger.warning(f"Nexus POST {path} → {resp.status_code}: {resp.text[:200]}")
            return resp.ok
        except Exception as e:
            logger.warning(f"Nexus POST {path} failed: {e}")
            return False

    def _get(self, path: str) -> dict | list:
        try:
            url = f"{self.base_url}{path}"
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Nexus GET {path} failed: {e}")
            return {}
