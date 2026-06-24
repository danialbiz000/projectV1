"""
Backtest Engine: vectorized event-driven backtest with walk-forward validation.

Design:
- Walk-forward splits: train on N bars, test on M bars, step by M bars.
- Each bar: classify regime → generate signals → size positions → simulate fills.
- Outputs: equity curve, trade log, full_performance_report per fold.
- Slippage and commission modeled.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
import numpy as np
import pandas as pd

from ..math.risk_metrics import full_performance_report, max_drawdown
from ..math.signals import rsi, momentum_signal, mean_reversion_signal
from .regime_engine import RegimeEngine, RegimeState
from .signal_engine import SignalEngine, Signal
from .volatility_engine import VolatilityEngine
from .risk_engine import RiskEngine

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    entry_date: str
    exit_date: Optional[str]
    side: str          # "long" / "short"
    entry_price: float
    exit_price: Optional[float]
    qty: int
    pnl: float
    pnl_pct: float
    exit_reason: str   # "tp" / "sl" / "signal_exit" / "eod" / "open"
    strategy: str


@dataclass
class BacktestFold:
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    equity_curve: pd.Series
    returns: pd.Series
    trades: list[BacktestTrade]
    performance: dict
    regime_counts: dict[str, int]


@dataclass
class BacktestResult:
    folds: list[BacktestFold]
    combined_equity: pd.Series
    combined_returns: pd.Series
    combined_performance: dict
    all_trades: list[BacktestTrade]
    total_folds: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BacktestEngine:
    def __init__(self, config: dict):
        cfg = config.get("backtest", {})
        self.initial_capital  = cfg.get("initial_capital", 100_000)
        self.commission_pct   = cfg.get("commission_pct", 0.001)
        self.slippage_pct     = cfg.get("slippage_pct", 0.0005)
        self.train_bars       = cfg.get("train_bars", 252)
        self.test_bars        = cfg.get("test_bars", 63)
        self.max_positions    = cfg.get("max_positions", 5)
        self.position_size_pct = cfg.get("position_size_pct", 0.10)

        self._regime_engine    = RegimeEngine(config)
        self._signal_engine    = SignalEngine(config)
        self._vol_engine       = VolatilityEngine(config)

    # ─── Walk-forward ─────────────────────────────────────────────────────────

    def run_walk_forward(
        self,
        prices_df: pd.DataFrame,    # columns = symbols, index = dates
        index_prices: pd.Series,    # regime classification series (e.g. SPY)
        volume_df: Optional[pd.DataFrame] = None,
    ) -> BacktestResult:
        """
        Walk-forward backtest across all available data.
        Returns BacktestResult with per-fold and combined metrics.
        """
        total_bars = len(prices_df)
        min_bars   = self.train_bars + self.test_bars

        if total_bars < min_bars:
            raise ValueError(
                f"Need at least {min_bars} bars; got {total_bars}"
            )

        folds: list[BacktestFold] = []
        fold_id = 0
        start   = 0

        while start + self.train_bars + self.test_bars <= total_bars:
            train_slice = prices_df.iloc[start : start + self.train_bars]
            test_slice  = prices_df.iloc[
                start + self.train_bars : start + self.train_bars + self.test_bars
            ]
            idx_test = index_prices.iloc[
                start + self.train_bars : start + self.train_bars + self.test_bars
            ]
            vol_slice = (
                volume_df.iloc[
                    start + self.train_bars : start + self.train_bars + self.test_bars
                ]
                if volume_df is not None else None
            )

            fold = self._run_fold(
                fold_id, train_slice, test_slice, idx_test, vol_slice
            )
            folds.append(fold)
            fold_id += 1
            start   += self.test_bars   # step by test_bars (walk forward)

        if not folds:
            raise ValueError("No complete folds generated")

        # Combine equity curves (chain each fold's returns, start at 100)
        all_returns = pd.concat([f.returns for f in folds])
        combined_eq = (1 + all_returns).cumprod() * self.initial_capital
        all_trades  = [t for f in folds for t in f.trades]
        combined_perf = full_performance_report(
            all_returns,
            combined_eq,
            pd.Series([t.pnl for t in all_trades]) if all_trades else None,
        )

        return BacktestResult(
            folds=folds,
            combined_equity=combined_eq,
            combined_returns=all_returns,
            combined_performance=combined_perf,
            all_trades=all_trades,
            total_folds=fold_id,
        )

    # ─── Single Fold ──────────────────────────────────────────────────────────

    def _run_fold(
        self,
        fold_id: int,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        index_test: pd.Series,
        volume_df: Optional[pd.DataFrame],
    ) -> BacktestFold:
        equity    = float(self.initial_capital)
        equity_curve: list[float] = [equity]
        returns_list: list[float] = []
        trades: list[BacktestTrade] = []
        open_positions: dict[str, dict] = {}
        regime_counts: dict[str, int] = {}

        # Full history up to test period (for lookbacks)
        full_history = pd.concat([train_df, test_df])

        for i, (dt, row) in enumerate(test_df.iterrows()):
            bar_idx = len(train_df) + i

            # Slice history up to current bar for each symbol
            bar_pnl = 0.0

            # Regime classification (uses SPY-like index)
            idx_slice = pd.concat([
                index_test.iloc[:i],
            ]) if i > 0 else pd.Series(dtype=float)
            # Use full index prices up to this bar
            idx_full = full_history.iloc[:bar_idx].get(
                index_test.name or test_df.columns[0],
                full_history.iloc[:bar_idx, 0],
            )
            regime = self._regime_engine.classify(idx_full)
            regime_counts[regime.regime] = regime_counts.get(regime.regime, 0) + 1

            # Check open positions for exits
            to_close = []
            for sym, pos in open_positions.items():
                if sym not in row.index:
                    continue
                cur_price = row[sym]
                entry_price = pos["entry_price"]
                side = pos["side"]

                if side == "long":
                    pnl_pct = (cur_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - cur_price) / entry_price

                exit_reason = None
                if pnl_pct >= pos["tp_pct"]:
                    exit_reason = "tp"
                elif pnl_pct <= -pos["sl_pct"]:
                    exit_reason = "sl"

                if exit_reason:
                    pnl = pnl_pct * pos["notional"]
                    pnl -= abs(pnl_pct * pos["notional"]) * self.commission_pct
                    bar_pnl += pnl
                    trades.append(BacktestTrade(
                        symbol=sym,
                        entry_date=pos["entry_date"],
                        exit_date=str(dt)[:10],
                        side=side,
                        entry_price=entry_price,
                        exit_price=cur_price,
                        qty=pos["qty"],
                        pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 4),
                        exit_reason=exit_reason,
                        strategy=pos["strategy"],
                    ))
                    to_close.append(sym)

            for sym in to_close:
                del open_positions[sym]

            # Generate new signals if capacity available
            if len(open_positions) < self.max_positions:
                for sym in test_df.columns:
                    if sym in open_positions:
                        continue
                    if sym not in row.index or np.isnan(row[sym]):
                        continue

                    prices_hist = full_history[sym].iloc[:bar_idx].dropna()
                    if len(prices_hist) < 60:
                        continue

                    vol_est = self._vol_engine.estimate(sym, prices_hist, use_garch=False)

                    vols = (
                        volume_df[sym].iloc[:bar_idx].dropna()
                        if volume_df is not None and sym in volume_df.columns
                        else None
                    )

                    sigs = self._signal_engine.generate(sym, prices_hist, vols, regime)
                    if not sigs:
                        continue

                    best = max(sigs, key=lambda s: s.strength * s.confidence)
                    if best.direction == 0 or best.confidence < 0.3:
                        continue

                    price = float(row[sym])
                    if price <= 0:
                        continue

                    notional = equity * self.position_size_pct
                    qty = max(1, int(notional / price))
                    actual_notional = qty * price

                    # Slippage
                    fill_price = price * (1 + self.slippage_pct * best.direction)
                    actual_notional += qty * abs(fill_price - price)

                    # Commission
                    actual_notional += actual_notional * self.commission_pct

                    tp_pct, sl_pct = self._brackets(vol_est.spot_vol)

                    open_positions[sym] = {
                        "entry_price": fill_price,
                        "entry_date":  str(dt)[:10],
                        "side":        "long" if best.direction > 0 else "short",
                        "qty":         qty,
                        "notional":    actual_notional,
                        "tp_pct":      tp_pct,
                        "sl_pct":      sl_pct,
                        "strategy":    best.strategy,
                    }

                    if len(open_positions) >= self.max_positions:
                        break

            # Mark-to-market open positions
            mtm_pnl = 0.0
            for sym, pos in open_positions.items():
                if sym in row.index and not np.isnan(row[sym]):
                    cur_p = row[sym]
                    entry_p = pos["entry_price"]
                    if pos["side"] == "long":
                        mtm_pnl += (cur_p - entry_p) * pos["qty"]
                    else:
                        mtm_pnl += (entry_p - cur_p) * pos["qty"]

            equity += bar_pnl
            daily_ret = (equity - equity_curve[-1]) / equity_curve[-1] if equity_curve[-1] > 0 else 0.0
            equity_curve.append(equity)
            returns_list.append(daily_ret)

        # Force-close remaining positions at last price
        last_row = test_df.iloc[-1]
        for sym, pos in open_positions.items():
            if sym in last_row.index and not np.isnan(last_row[sym]):
                exit_price = last_row[sym]
                entry_price = pos["entry_price"]
                if pos["side"] == "long":
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - exit_price) / entry_price
                pnl = pnl_pct * pos["notional"]
                trades.append(BacktestTrade(
                    symbol=sym,
                    entry_date=pos["entry_date"],
                    exit_date=str(test_df.index[-1])[:10],
                    side=pos["side"],
                    entry_price=entry_price,
                    exit_price=exit_price,
                    qty=pos["qty"],
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 4),
                    exit_reason="eod",
                    strategy=pos["strategy"],
                ))

        eq_series  = pd.Series(equity_curve, index=[test_df.index[0]] + list(test_df.index))
        ret_series = pd.Series(returns_list, index=list(test_df.index))

        pnl_series = pd.Series([t.pnl for t in trades]) if trades else None
        perf = full_performance_report(ret_series, eq_series, pnl_series)

        dates = list(test_df.index)
        return BacktestFold(
            fold_id=fold_id,
            train_start=str(train_df.index[0])[:10],
            train_end=str(train_df.index[-1])[:10],
            test_start=str(dates[0])[:10],
            test_end=str(dates[-1])[:10],
            equity_curve=eq_series,
            returns=ret_series,
            trades=trades,
            performance=perf,
            regime_counts=regime_counts,
        )

    def _brackets(self, ann_vol: float) -> tuple[float, float]:
        horizon_scale = np.sqrt(60 / 252)
        tp = float(np.clip(ann_vol * 1.5 * horizon_scale, 0.01, 0.20))
        sl = float(np.clip(ann_vol * 0.55 * horizon_scale, 0.005, 0.10))
        return tp, sl
