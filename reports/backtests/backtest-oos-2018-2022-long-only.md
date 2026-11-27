# Backtest — 2026-11-26

Period **2018-01-01 → 2022-12-31** · 25 symbols · data: yahoo · capital $10000 · LONG ONLY
Costs (realistic mode): slippage 5 bps/side, commission 0 bps, short borrow 30 bps/yr.
Benchmark buy-and-hold SPY: return 42.78%, CAGR 7.39%, max DD 34.1%, Sharpe 0.237.

> Historical simulation, not live results. The universe is chosen today (survivorship bias).

| Strategy | Return | CAGR | Max DD | Sharpe | Win | PF | Trades | Legacy return |
|---|---|---|---|---|---|---|---|---|
| Momentum — 12-1 Factor (momentum) | 157.68% | 20.86% | 39.82% | 0.637 | 47.4% | 1.441 | 133 | — |
| MACD — Momentum Cross (macd) | 101.11% | 15.01% | 24.25% | 0.623 | 52% | 1.393 | 246 | — |
| Hawk — Breakout Momentum (hawk) | 32.14% | 5.74% | 18.97% | 0.16 | 44.5% | 1.135 | 317 | — |
| Bull — Golden Cross (bull) | 27.56% | 4.99% | 23.69% | 0.114 | 41.1% | 1.202 | 112 | — |
| Fox — Contrarian (fox) | 17.66% | 3.31% | 28.58% | 0.046 | 42.8% | 1.05 | 523 | — |
| Bear — Death Cross (bear) | 0% | 0% | 0% | 0 | 0% | 0 | 0 | — |
| Owl — Mean Reversion (owl) | -13.71% | -2.91% | 37.23% | -0.3 | 44.6% | 0.962 | 617 | — |
| RSI — Oversold Bounce (rsi) | -25.36% | -5.69% | 36.5% | -0.495 | 40.4% | 0.903 | 492 | — |
| Bollinger — Band Reversion (bb) | -23.56% | -5.23% | 32.59% | -0.581 | 36.1% | 0.915 | 607 | — |

## Red flags

**momentum**
- [HIGH] max drawdown 39.82% (> 20%)
- [MEDIUM] 13 stops gapped through (worst -12.5% vs stop -8%)

**macd**
- [HIGH] max drawdown 24.25% (> 20%)
- [MEDIUM] 14 stops gapped through (worst -9.9% vs stop -5%)

**hawk**
- [MEDIUM] Sharpe 0.16 (< 0.5)
- [MEDIUM] CAGR 5.74% below buy-and-hold 7.39%
- [MEDIUM] 19 stops gapped through (worst -5.6% vs stop -4%)

**bull**
- [MEDIUM] Sharpe 0.114 (< 0.5)
- [HIGH] max drawdown 23.69% (> 20%)
- [MEDIUM] CAGR 4.99% below buy-and-hold 7.39%
- [MEDIUM] 8 stops gapped through (worst -10.5% vs stop -6%)

**fox**
- [MEDIUM] Sharpe 0.046 (< 0.5)
- [HIGH] max drawdown 28.58% (> 20%)
- [MEDIUM] CAGR 3.31% below buy-and-hold 7.39%
- [HIGH] 37 stops gapped through (worst -8.8% vs stop -4%)

**bear**
- [MEDIUM] only 0 trades: too few to trust the statistics
- [HIGH] profit factor 0 < 1: loses money after costs
- [MEDIUM] Sharpe 0 (< 0.5)
- [MEDIUM] CAGR 0% below buy-and-hold 7.39%

**owl**
- [HIGH] profit factor 0.962 < 1: loses money after costs
- [HIGH] Sharpe -0.3 (< 0.5)
- [HIGH] max drawdown 37.23% (> 20%)
- [MEDIUM] CAGR -2.91% below buy-and-hold 7.39%
- [HIGH] 54 stops gapped through (worst -15.1% vs stop -4%)

**rsi**
- [HIGH] profit factor 0.903 < 1: loses money after costs
- [HIGH] Sharpe -0.495 (< 0.5)
- [HIGH] max drawdown 36.5% (> 20%)
- [MEDIUM] CAGR -5.69% below buy-and-hold 7.39%
- [HIGH] 39 stops gapped through (worst -8.8% vs stop -4%)

**bb**
- [HIGH] profit factor 0.915 < 1: loses money after costs
- [HIGH] Sharpe -0.581 (< 0.5)
- [HIGH] max drawdown 32.59% (> 20%)
- [MEDIUM] CAGR -5.23% below buy-and-hold 7.39%
- [HIGH] 41 stops gapped through (worst -8.2% vs stop -3%)

## Exit mix (realistic)

- momentum: take_profit 30, stop_loss 53, max_hold 29, stop_loss_gap 13, take_profit_gap 5, eop 3
- macd: max_hold 98, stop_loss 84, take_profit 39, stop_loss_gap 14, take_profit_gap 8, eop 3
- hawk: take_profit 46, max_hold 111, stop_loss 126, stop_loss_gap 19, take_profit_gap 14, eop 1
- bull: take_profit 17, stop_loss 47, max_hold 35, take_profit_gap 3, stop_loss_gap 8, eop 2
- fox: stop_loss 234, take_profit 125, max_hold 99, take_profit_gap 24, stop_loss_gap 37, eop 4
- bear: 
- owl: max_hold 151, take_profit_gap 34, stop_loss 241, take_profit 133, stop_loss_gap 54, eop 4
- rsi: stop_loss 211, take_profit 97, take_profit_gap 19, max_hold 122, stop_loss_gap 39, eop 4
- bb: take_profit_gap 27, stop_loss 322, take_profit 115, max_hold 100, stop_loss_gap 41, eop 2

