"""
Walk-forward backtest example using synthetic data.

Run:
    python -m nexus_quant.examples.backtest_example

Requires: nexus_quant installed (pip install -e .) or run from projectV1 root.
"""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

from nexus_quant.engines.backtest_engine import BacktestEngine
from nexus_quant.math.risk_metrics import full_performance_report


CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def synthetic_prices(
    symbols: list[str],
    n_bars: int = 800,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV-like close price DataFrame."""
    rng = np.random.default_rng(seed)
    data = {}
    for i, sym in enumerate(symbols):
        drift = rng.uniform(-0.0001, 0.0005)
        vol   = rng.uniform(0.008, 0.020)
        r     = rng.normal(drift, vol, n_bars)
        prices = 100 * np.exp(np.cumsum(r))
        data[sym] = prices

    idx = pd.bdate_range("2020-01-01", periods=n_bars)
    return pd.DataFrame(data, index=idx)


def main():
    # Load config
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    # Shorten lookbacks for example speed
    config.setdefault("backtest", {}).update({
        "initial_capital":   100_000,
        "train_bars":        252,
        "test_bars":         63,
        "position_size_pct": 0.10,
        "max_positions":     3,
    })

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    prices_df = synthetic_prices(symbols, n_bars=800)

    # Use first symbol as regime index (proxy for SPY)
    index_prices = prices_df[symbols[0]]

    engine = BacktestEngine(config)
    print(f"Running walk-forward backtest on {symbols} ({len(prices_df)} bars)...")

    result = engine.run_walk_forward(prices_df, index_prices)

    print(f"\n{'='*60}")
    print(f"Walk-Forward Summary  ({result.total_folds} folds)")
    print(f"{'='*60}")

    perf = result.combined_performance
    print(f"Total Return:      {perf.get('total_return_pct', 0):>8.2f}%")
    print(f"Annualized Return: {perf.get('annualized_return_pct', 0):>8.2f}%")
    print(f"Volatility:        {perf.get('volatility_pct', 0):>8.2f}%")
    print(f"Sharpe Ratio:      {perf.get('sharpe_ratio', 0):>8.3f}")
    print(f"Sortino Ratio:     {perf.get('sortino_ratio', 0):>8.3f}")
    print(f"Max Drawdown:      {perf.get('max_drawdown_pct', 0):>8.2f}%")
    print(f"Calmar Ratio:      {perf.get('calmar_ratio', 0):>8.3f}")
    print(f"VaR 95% (daily):   {perf.get('var_95_daily_pct', 0):>8.3f}%")
    print(f"ES 95% (daily):    {perf.get('es_95_daily_pct', 0):>8.3f}%")

    if "num_trades" in perf:
        print(f"\nTrades:            {perf['num_trades']:>8d}")
        print(f"Win Rate:          {perf.get('win_rate_pct', 0):>8.1f}%")
        print(f"Profit Factor:     {perf.get('profit_factor', 0):>8.3f}")
        print(f"Expectancy:        {perf.get('expectancy', 0):>8.4f}")

    print(f"\n{'─'*60}")
    print("Per-Fold Results:")
    print(f"{'─'*60}")
    print(f"{'Fold':<6} {'Test Period':<25} {'Return%':>8} {'Sharpe':>8} {'MaxDD%':>8} {'Trades':>7}")
    print(f"{'─'*60}")

    for fold in result.folds:
        fp = fold.performance
        trade_count = fp.get("num_trades", len(fold.trades))
        print(
            f"{fold.fold_id:<6} "
            f"{fold.test_start} → {fold.test_end}  "
            f"{fp.get('total_return_pct', 0):>7.2f}% "
            f"{fp.get('sharpe_ratio', 0):>8.3f} "
            f"{fp.get('max_drawdown_pct', 0):>7.2f}% "
            f"{trade_count:>7d}"
        )

    print(f"\n{'='*60}")
    print("Regime distribution across all folds:")
    regime_totals: dict[str, int] = {}
    for fold in result.folds:
        for r, count in fold.regime_counts.items():
            regime_totals[r] = regime_totals.get(r, 0) + count
    total_bars = sum(regime_totals.values())
    for r, count in sorted(regime_totals.items()):
        pct = count / total_bars * 100 if total_bars else 0
        print(f"  {r:<20} {count:>5} bars  ({pct:.1f}%)")


if __name__ == "__main__":
    main()
