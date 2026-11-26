# Backtest — 2026-11-26

Period **2023-11-27 → 2026-11-26** · 25 symbols · data: yahoo · capital $10000 · LONG ONLY
Costs (realistic mode): slippage 5 bps/side, commission 0 bps, short borrow 30 bps/yr.
Benchmark buy-and-hold SPY: return 57.64%, CAGR 16.45%, max DD 19%, Sharpe 0.768.

> Historical simulation, not live results. The universe is chosen today (survivorship bias).

| Strategy | Return | CAGR | Max DD | Sharpe | Win | PF | Trades | Legacy return |
|---|---|---|---|---|---|---|---|---|
| Owl — Mean Reversion (owl) | 59.82% | 16.99% | 21.11% | 0.772 | 50.6% | 1.213 | 409 | — |
| RSI — Oversold Bounce (rsi) | 58.43% | 16.65% | 24.45% | 0.76 | 50% | 1.232 | 338 | — |
| Momentum — 12-1 Factor (momentum) | 68% | 18.96% | 28.82% | 0.654 | 48.7% | 1.432 | 76 | — |
| MACD — Momentum Cross (macd) | 28.32% | 8.7% | 26.68% | 0.346 | 49% | 1.165 | 157 | — |
| Bollinger — Band Reversion (bb) | 25.44% | 7.88% | 19.07% | 0.304 | 44.2% | 1.132 | 371 | — |
| Bear — Death Cross (bear) | 0% | 0% | 0% | 0 | 0% | 0 | 0 | — |
| Fox — Contrarian (fox) | 9.02% | 2.93% | 24.68% | -0.005 | 45% | 1.039 | 347 | — |
| Bull — Golden Cross (bull) | -8.46% | -2.92% | 23.58% | -0.432 | 43.2% | 0.905 | 81 | — |
| Hawk — Breakout Momentum (hawk) | -15.29% | -5.4% | 33.47% | -0.553 | 39.8% | 0.907 | 216 | — |

## Red flags

**owl**
- [HIGH] max drawdown 21.11% (> 20%)
- [HIGH] 25 stops gapped through (worst -12.7% vs stop -4%)

**rsi**
- [HIGH] max drawdown 24.45% (> 20%)
- [HIGH] 27 stops gapped through (worst -12.7% vs stop -4%)

**momentum**
- [HIGH] max drawdown 28.82% (> 20%)
- [MEDIUM] 17 stops gapped through (worst -13.3% vs stop -8%)

**macd**
- [MEDIUM] Sharpe 0.346 (< 0.5)
- [HIGH] max drawdown 26.68% (> 20%)
- [MEDIUM] CAGR 8.7% below buy-and-hold 16.45%
- [MEDIUM] 13 stops gapped through (worst -9.2% vs stop -5%)

**bb**
- [MEDIUM] Sharpe 0.304 (< 0.5)
- [MEDIUM] CAGR 7.88% below buy-and-hold 16.45%
- [HIGH] 31 stops gapped through (worst -12.7% vs stop -3%)

**bear**
- [MEDIUM] only 0 trades: too few to trust the statistics
- [HIGH] profit factor 0 < 1: loses money after costs
- [MEDIUM] Sharpe 0 (< 0.5)
- [MEDIUM] CAGR 0% below buy-and-hold 16.45%

**fox**
- [HIGH] Sharpe -0.005 (< 0.5)
- [HIGH] max drawdown 24.68% (> 20%)
- [MEDIUM] CAGR 2.93% below buy-and-hold 16.45%
- [HIGH] 36 stops gapped through (worst -12.7% vs stop -4%)

**bull**
- [HIGH] profit factor 0.905 < 1: loses money after costs
- [HIGH] Sharpe -0.432 (< 0.5)
- [HIGH] max drawdown 23.58% (> 20%)
- [MEDIUM] CAGR -2.92% below buy-and-hold 16.45%
- [MEDIUM] 5 stops gapped through (worst -9.3% vs stop -6%)

**hawk**
- [HIGH] profit factor 0.907 < 1: loses money after costs
- [HIGH] Sharpe -0.553 (< 0.5)
- [HIGH] max drawdown 33.47% (> 20%)
- [MEDIUM] CAGR -5.4% below buy-and-hold 16.45%
- [HIGH] 21 stops gapped through (worst -17.0% vs stop -4%)

## Exit mix (realistic)

- owl: take_profit 89, stop_loss_gap 25, max_hold 117, take_profit_gap 33, stop_loss 143, eop 2
- rsi: max_hold 97, take_profit 71, stop_loss 118, stop_loss_gap 27, take_profit_gap 22, eop 3
- momentum: take_profit_gap 5, max_hold 18, stop_loss_gap 17, take_profit 14, stop_loss 19, eop 3
- macd: stop_loss 54, max_hold 56, take_profit 26, take_profit_gap 6, stop_loss_gap 13, eop 2
- bb: take_profit 80, max_hold 83, take_profit_gap 16, stop_loss 160, stop_loss_gap 31, eop 1
- bear: 
- fox: max_hold 80, take_profit 77, stop_loss_gap 36, stop_loss 135, take_profit_gap 17, eop 2
- bull: stop_loss 40, take_profit 9, max_hold 24, stop_loss_gap 5, take_profit_gap 1, eop 2
- hawk: stop_loss 92, take_profit 32, max_hold 63, stop_loss_gap 21, take_profit_gap 7, eop 1

