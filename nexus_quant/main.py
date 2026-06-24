"""
nexus_quant main loop.

Usage:
    python -m nexus_quant.main [--config config/config.yaml] [--dry-run]

Runs the full quant pipeline on a configurable schedule:
  1. Fetch market data via Alpaca
  2. Classify regime
  3. Estimate volatility
  4. Generate signals
  5. Size positions via RiskEngine
  6. Execute trades via ExecutionEngine (or dry-run)
  7. Ship signals + snapshots to Nexus via NexusBridge
  8. Monitor and alert
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("nexus_quant.main")


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(config: dict, dry_run: bool = True) -> None:
    from nexus_quant.data.alpaca_client import AlpacaClient
    from nexus_quant.engines.regime_engine import RegimeEngine
    from nexus_quant.engines.signal_engine import SignalEngine
    from nexus_quant.engines.volatility_engine import VolatilityEngine
    from nexus_quant.engines.risk_engine import RiskEngine
    from nexus_quant.engines.portfolio_engine import PortfolioEngine
    from nexus_quant.engines.execution_engine import ExecutionEngine
    from nexus_quant.engines.monitoring_engine import MonitoringEngine
    from nexus_quant.bridge.nexus_bridge import NexusBridge

    # ── Initialise engines ────────────────────────────────────────────────────
    alpaca    = AlpacaClient()
    regime_e  = RegimeEngine(config)
    signal_e  = SignalEngine(config)
    vol_e     = VolatilityEngine(config)
    risk_e    = RiskEngine(config)
    portfolio_e = PortfolioEngine(config)
    monitor_e   = MonitoringEngine(config)
    bridge      = NexusBridge(config)

    if not dry_run and config.get("execution", {}).get("live_trading"):
        logger.warning("LIVE TRADING MODE ACTIVE")
    else:
        dry_run = True
        logger.info("Dry-run mode (no real orders)")

    # Override execution live_trading flag
    if dry_run:
        config.setdefault("execution", {})["live_trading"] = False

    exec_e = ExecutionEngine(config, alpaca, risk_e)

    watchlist = config.get("system", {}).get("watchlist", ["SPY", "QQQ", "AAPL"])
    index_sym = config.get("regime", {}).get("index_symbol", "SPY")
    data_bars = config.get("system", {}).get("data_bars", 300)
    loop_interval_s = config.get("system", {}).get("loop_interval_seconds", 300)

    _shutdown = {"requested": False}

    def _sighandler(sig, frame):
        logger.info("Shutdown requested")
        _shutdown["requested"] = True

    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    prev_regime = None

    logger.info(f"Starting main loop | watchlist={watchlist} | interval={loop_interval_s}s")

    while not _shutdown["requested"]:
        loop_start = time.monotonic()
        try:
            _cycle(
                alpaca, regime_e, signal_e, vol_e, risk_e, portfolio_e,
                exec_e, monitor_e, bridge,
                watchlist, index_sym, data_bars, dry_run,
            )
        except Exception as e:
            logger.exception(f"Cycle error: {e}")
            monitor_e._emit("ERROR", "main_loop", f"Cycle exception: {e}")

        elapsed = time.monotonic() - loop_start
        sleep_s = max(0, loop_interval_s - elapsed)
        logger.debug(f"Cycle done in {elapsed:.1f}s, sleeping {sleep_s:.0f}s")

        deadline = time.monotonic() + sleep_s
        while not _shutdown["requested"] and time.monotonic() < deadline:
            time.sleep(1)

    logger.info("nexus_quant shutdown complete")


def _cycle(
    alpaca, regime_e, signal_e, vol_e, risk_e, portfolio_e,
    exec_e, monitor_e, bridge,
    watchlist, index_sym, data_bars, dry_run,
):
    # 1. Fetch index data for regime classification
    index_bars = alpaca.get_bars(index_sym, "1Day", limit=data_bars)
    if index_bars.empty:
        logger.warning(f"No bars for index {index_sym}")
        return

    # 2. Regime
    index_prices = index_bars["close"]
    regime = regime_e.classify(index_prices)
    bridge.send_regime(regime)
    logger.info(f"Regime: {regime.regime} | vol: {regime.vol_regime} | conf={regime.confidence:.2f}")

    # 3. Fetch equity
    equity = bridge.get_equity() or 100_000.0

    # 4. Fetch prices for watchlist
    bars_multi = alpaca.get_bars_multi(watchlist, "1Day", limit=data_bars)
    prices: dict[str, float] = {}
    all_signals = []

    for sym in watchlist:
        df = bars_multi.get(sym, pd.DataFrame())
        if df.empty or len(df) < 60:
            continue

        prices[sym] = float(df["close"].iloc[-1])
        monitor_e.on_market_data(sym, df.index[-1].to_pydatetime())

        # 5. Volatility
        vol_est = vol_e.estimate(
            sym, df["close"],
            highs=df.get("high"), lows=df.get("low"),
            use_garch=True,
        )

        # 6. Signals
        vols = df.get("volume")
        sigs = signal_e.generate(sym, df["close"], vols, regime)
        all_signals.extend(sigs)

        for sig in sigs:
            monitor_e.on_signal(sig.strategy, sig.asset, sig.confidence)
            bridge.send_signal(sig, regime)
            logger.info(
                f"Signal: {sig.strategy}/{sym} dir={sig.direction:+.0f} "
                f"str={sig.strength:.2f} conf={sig.confidence:.2f}"
            )

            if not dry_run and sig.confidence >= 0.5 and abs(sig.direction) > 0:
                # 7. Size
                positions = bridge.get_positions()
                gross_exp = sum(abs(float(p.get("market_value", 0))) for p in positions) / max(equity, 1)
                size = risk_e.size_position(sym, prices[sym], equity, vol_est, regime)

                # 8. Execute
                result = exec_e.execute_signal(sig, prices[sym], size, vol_est, equity, gross_exp)
                if result.status == "submitted":
                    monitor_e.on_order_submitted(sym, result.notional)
                    logger.info(f"Order submitted: {sym} {result.side} {result.qty}sh")
                elif result.status == "failed":
                    monitor_e.on_order_failed(sym, result.reason)

    # 9. Risk snapshot
    positions_raw = bridge.get_positions()
    from nexus_quant.math.risk_metrics import current_drawdown
    eq_series = pd.Series([equity])  # single-point; real impl would track history
    returns   = pd.Series(dtype=float)

    risk_snap = risk_e.snapshot(eq_series, returns, positions_raw, equity)
    bridge.send_risk_snapshot(risk_snap)

    if risk_snap.kill_switch_active:
        monitor_e.on_kill_switch("Risk limits breached")

    # 10. Monitoring snapshot
    mon_snap = monitor_e.snapshot(
        equity=equity,
        drawdown=risk_snap.current_drawdown,
        open_positions=risk_snap.num_positions,
        regime=regime.regime,
        vol_regime=regime.vol_regime,
        kill_switch_active=risk_snap.kill_switch_active,
    )
    bridge.send_monitoring_snapshot(mon_snap)
    monitor_e.clear_alerts()


def main():
    parser = argparse.ArgumentParser(description="nexus_quant trading loop")
    parser.add_argument("--config", default="nexus_quant/config/config.yaml")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live",    action="store_true", default=False,
                        help="Enable live execution (requires NEXUS_ENABLE_LIVE_TRADING=true)")
    args = parser.parse_args()

    import os
    live = args.live and os.environ.get("NEXUS_ENABLE_LIVE_TRADING") == "true"

    config = load_config(args.config)
    run(config, dry_run=not live)


if __name__ == "__main__":
    main()
