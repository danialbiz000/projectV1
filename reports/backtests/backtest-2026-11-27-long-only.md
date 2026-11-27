# Backtest — 2026-11-27

Period **2023-11-28 → 2026-11-27** · 25 symbols · data: yahoo · capital $10000 · LONG ONLY
Costs (realistic mode): slippage 5 bps/side, commission 0 bps, short borrow 30 bps/yr.
Benchmark buy-and-hold SPY: return 60.39%, CAGR 17.13%, max DD 19%, Sharpe 0.799.

> Historical simulation, not live results. The universe is chosen today (survivorship bias).

| Strategy | Return | CAGR | Max DD | Sharpe | Win | PF | Trades | Legacy return |
|---|---|---|---|---|---|---|---|---|
| RSI — Oversold Bounce (rsi) | 59.29% | 16.86% | 24.45% | 0.771 | 50.1% | 1.235 | 339 | — |
| Owl — Mean Reversion (owl) | 59.46% | 16.9% | 21.28% | 0.768 | 50.6% | 1.211 | 411 | — |
| Momentum — 12-1 Factor (momentum) | 68.5% | 19.08% | 28.85% | 0.658 | 48.7% | 1.44 | 76 | — |
| MACD — Momentum Cross (macd) | 30.47% | 9.31% | 26.68% | 0.383 | 50% | 1.178 | 158 | — |
| Bollinger — Band Reversion (bb) | 25.91% | 8.02% | 19.06% | 0.313 | 44.2% | 1.134 | 371 | — |
| Bear — Death Cross (bear) | 0% | 0% | 0% | 0 | 0% | 0 | 0 | — |
| Fox — Contrarian (fox) | 8.95% | 2.91% | 24.68% | -0.006 | 45% | 1.039 | 349 | — |
| Bull — Golden Cross (bull) | -7.74% | -2.66% | 23.58% | -0.413 | 43.2% | 0.913 | 81 | — |
| Hawk — Breakout Momentum (hawk) | -15.07% | -5.32% | 33.47% | -0.548 | 39.8% | 0.908 | 216 | — |

## Red flags

**rsi**
- [HIGH] max drawdown 24.45% (> 20%)
- [MEDIUM] CAGR 16.86% below buy-and-hold 17.13%
- [HIGH] 27 stops gapped through (worst -12.7% vs stop -4%)

**owl**
- [HIGH] max drawdown 21.28% (> 20%)
- [MEDIUM] CAGR 16.9% below buy-and-hold 17.13%
- [HIGH] 25 stops gapped through (worst -12.7% vs stop -4%)

**momentum**
- [HIGH] max drawdown 28.85% (> 20%)
- [MEDIUM] 17 stops gapped through (worst -13.3% vs stop -8%)

**macd**
- [MEDIUM] Sharpe 0.383 (< 0.5)
- [HIGH] max drawdown 26.68% (> 20%)
- [MEDIUM] CAGR 9.31% below buy-and-hold 17.13%
- [MEDIUM] 13 stops gapped through (worst -9.2% vs stop -5%)

**bb**
- [MEDIUM] Sharpe 0.313 (< 0.5)
- [MEDIUM] CAGR 8.02% below buy-and-hold 17.13%
- [HIGH] 31 stops gapped through (worst -12.7% vs stop -3%)

**bear**
- [MEDIUM] only 0 trades: too few to trust the statistics
- [HIGH] profit factor 0 < 1: loses money after costs
- [MEDIUM] Sharpe 0 (< 0.5)
- [MEDIUM] CAGR 0% below buy-and-hold 17.13%

**fox**
- [HIGH] Sharpe -0.006 (< 0.5)
- [HIGH] max drawdown 24.68% (> 20%)
- [MEDIUM] CAGR 2.91% below buy-and-hold 17.13%
- [HIGH] 36 stops gapped through (worst -12.7% vs stop -4%)

**bull**
- [HIGH] profit factor 0.913 < 1: loses money after costs
- [HIGH] Sharpe -0.413 (< 0.5)
- [HIGH] max drawdown 23.58% (> 20%)
- [MEDIUM] CAGR -2.66% below buy-and-hold 17.13%
- [MEDIUM] 5 stops gapped through (worst -9.3% vs stop -6%)

**hawk**
- [HIGH] profit factor 0.908 < 1: loses money after costs
- [HIGH] Sharpe -0.548 (< 0.5)
- [HIGH] max drawdown 33.47% (> 20%)
- [MEDIUM] CAGR -5.32% below buy-and-hold 17.13%
- [HIGH] 21 stops gapped through (worst -17.0% vs stop -4%)

## Exit mix (realistic)

- rsi: max_hold 97, take_profit 71, stop_loss 118, stop_loss_gap 27, take_profit_gap 22, eop 4
- owl: take_profit 89, stop_loss_gap 25, max_hold 117, take_profit_gap 33, stop_loss 144, eop 3
- momentum: take_profit 15, max_hold 18, stop_loss_gap 17, stop_loss 19, take_profit_gap 4, eop 3
- macd: stop_loss 54, max_hold 56, take_profit 26, take_profit_gap 6, stop_loss_gap 13, eop 3
- bb: take_profit 80, max_hold 83, take_profit_gap 16, stop_loss 160, stop_loss_gap 31, eop 1
- bear: 
- fox: max_hold 81, take_profit 77, stop_loss_gap 36, stop_loss 136, take_profit_gap 17, eop 2
- bull: stop_loss 40, take_profit 9, max_hold 24, stop_loss_gap 5, take_profit_gap 1, eop 2
- hawk: stop_loss 92, take_profit 32, max_hold 64, stop_loss_gap 21, take_profit_gap 7

