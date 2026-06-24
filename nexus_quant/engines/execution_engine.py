"""
Execution Engine: translates RebalanceTrades and Signals into Alpaca orders.

Implements:
- Bracket orders (OTO: entry + TP/SL) for directional trades
- Market / limit order routing
- Pre-trade risk gate via RiskEngine
- Retry logic with exponential backoff
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import numpy as np

from ..data.alpaca_client import AlpacaClient
from .risk_engine import RiskEngine, PositionSize
from .portfolio_engine import RebalanceTrade
from .signal_engine import Signal
from .volatility_engine import VolatilityEstimate

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    symbol: str
    order_id: Optional[str]
    side: str
    qty: int
    notional: float
    order_type: str
    status: str          # "submitted" / "skipped" / "failed"
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ExecutionEngine:
    def __init__(self, config: dict, alpaca: AlpacaClient, risk: RiskEngine):
        cfg = config.get("execution", {})
        self.alpaca            = alpaca
        self.risk              = risk
        self.order_type        = cfg.get("default_order_type", "market")
        self.time_in_force     = cfg.get("time_in_force", "day")
        self.max_retries       = cfg.get("max_retries", 3)
        self.retry_base_s      = cfg.get("retry_base_seconds", 2)
        self.tp_atr_mult       = cfg.get("tp_atr_multiplier", 1.5)
        self.sl_atr_mult       = cfg.get("sl_atr_multiplier", 0.55)
        self.live_trading      = cfg.get("live_trading", False)

    # ─── Directional Signal Orders ────────────────────────────────────────────

    def execute_signal(
        self,
        signal: Signal,
        price: float,
        size: PositionSize,
        vol_est: VolatilityEstimate,
        equity: float,
        gross_exposure: float,
    ) -> OrderResult:
        """Submit a bracket order for a directional signal."""
        if not size.approved or size.shares <= 0:
            return OrderResult(
                symbol=signal.asset, order_id=None,
                side="buy", qty=0, notional=0,
                order_type="none", status="skipped",
                reason=size.reason,
            )

        ok, msg = self.risk.check_order(signal.asset, size.notional, equity, gross_exposure)
        if not ok:
            return OrderResult(
                symbol=signal.asset, order_id=None,
                side="buy", qty=0, notional=0,
                order_type="none", status="skipped",
                reason=f"Risk gate: {msg}",
            )

        side = "buy" if signal.direction > 0 else "sell"
        tp_pct, sl_pct = self._brackets(vol_est)

        if side == "buy":
            tp_price = round(price * (1 + tp_pct), 2)
            sl_price = round(price * (1 - sl_pct), 2)
        else:
            tp_price = round(price * (1 - tp_pct), 2)
            sl_price = round(price * (1 + sl_pct), 2)

        order = {
            "symbol":        signal.asset,
            "qty":           str(size.shares),
            "side":          side,
            "type":          self.order_type,
            "time_in_force": self.time_in_force,
            "order_class":   "bracket",
            "take_profit":   {"limit_price": str(tp_price)},
            "stop_loss":     {"stop_price": str(sl_price)},
        }

        return self._submit_with_retry(signal.asset, order, size.shares, size.notional, "bracket")

    # ─── Portfolio Rebalance Orders ───────────────────────────────────────────

    def execute_rebalance(
        self,
        trades: list[RebalanceTrade],
        prices: dict[str, float],
        equity: float,
        gross_exposure: float,
    ) -> list[OrderResult]:
        """Execute a list of rebalance trades (simple market orders, no brackets)."""
        results = []
        for trade in trades:
            if trade.direction == "hold" or trade.notional <= 0:
                continue

            price = prices.get(trade.symbol, 0)
            if price <= 0:
                results.append(OrderResult(
                    symbol=trade.symbol, order_id=None, side=trade.direction,
                    qty=0, notional=0, order_type="market",
                    status="skipped", reason="No price available",
                ))
                continue

            qty = int(trade.notional / price)
            if qty <= 0:
                continue

            ok, msg = self.risk.check_order(trade.symbol, trade.notional, equity, gross_exposure)
            if not ok:
                results.append(OrderResult(
                    symbol=trade.symbol, order_id=None, side=trade.direction,
                    qty=0, notional=trade.notional, order_type="market",
                    status="skipped", reason=f"Risk gate: {msg}",
                ))
                continue

            order = {
                "symbol":        trade.symbol,
                "qty":           str(qty),
                "side":          trade.direction,
                "type":          "market",
                "time_in_force": self.time_in_force,
            }
            results.append(
                self._submit_with_retry(trade.symbol, order, qty, trade.notional, "market")
            )

        return results

    # ─── Options Orders ───────────────────────────────────────────────────────

    def execute_option_order(
        self,
        option_symbol: str,
        side: str,        # "buy" or "sell"
        qty: int,
        order_type: str = "limit",
        limit_price: Optional[float] = None,
    ) -> OrderResult:
        """Submit an options order on Alpaca paper."""
        notional = (limit_price or 0) * qty * 100  # options contracts = 100 shares

        order: dict = {
            "symbol":        option_symbol,
            "qty":           str(qty),
            "side":          side,
            "type":          order_type,
            "time_in_force": "day",
        }
        if order_type == "limit" and limit_price is not None:
            order["limit_price"] = str(round(limit_price, 2))

        return self._submit_with_retry(option_symbol, order, qty, notional, order_type)

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _submit_with_retry(
        self,
        symbol: str,
        order: dict,
        qty: int,
        notional: float,
        order_type: str,
    ) -> OrderResult:
        if not self.live_trading:
            logger.info(f"[DRY-RUN] Would submit: {order}")
            return OrderResult(
                symbol=symbol, order_id="dry-run",
                side=order.get("side", "buy"),
                qty=qty, notional=notional,
                order_type=order_type, status="submitted",
                reason="Dry-run mode",
            )

        last_exc = None
        for attempt in range(self.max_retries):
            try:
                resp = self.alpaca.submit_order(order)
                return OrderResult(
                    symbol=symbol,
                    order_id=resp.get("id"),
                    side=order.get("side", "buy"),
                    qty=qty,
                    notional=notional,
                    order_type=order_type,
                    status="submitted",
                    reason="OK",
                )
            except Exception as e:
                last_exc = e
                wait = self.retry_base_s * (2 ** attempt)
                logger.warning(f"Order attempt {attempt+1} failed for {symbol}: {e}. Retry in {wait}s")
                time.sleep(wait)

        return OrderResult(
            symbol=symbol, order_id=None,
            side=order.get("side", "buy"),
            qty=qty, notional=notional,
            order_type=order_type, status="failed",
            reason=str(last_exc),
        )

    def _brackets(self, vol_est: VolatilityEstimate) -> tuple[float, float]:
        """Compute TP/SL percentages from annualized vol (adaptive brackets)."""
        ann_vol = vol_est.spot_vol if vol_est.spot_vol > 0 else 0.20
        # Scale to 60-day horizon
        horizon_scale = np.sqrt(60 / 252)
        tp = ann_vol * self.tp_atr_mult * horizon_scale
        sl = ann_vol * self.sl_atr_mult * horizon_scale
        # Clamp to reasonable bounds
        tp = float(np.clip(tp, 0.01, 0.20))
        sl = float(np.clip(sl, 0.005, 0.10))
        return tp, sl
