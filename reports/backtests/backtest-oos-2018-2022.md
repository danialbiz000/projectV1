# Backtest — 2026-11-26

Period **2018-01-01 → 2022-12-31** · 25 symbols · data: yahoo · capital $10000
Costs (realistic mode): slippage 5 bps/side, commission 0 bps, short borrow 30 bps/yr.
Benchmark buy-and-hold SPY: return 42.78%, CAGR 7.39%, max DD 34.1%, Sharpe 0.237.

> Historical simulation, not live results. The universe is chosen today (survivorship bias).

| Strategy | Return | CAGR | Max DD | Sharpe | Win | PF | Trades | Legacy return |
|---|---|---|---|---|---|---|---|---|
| Momentum — 12-1 Factor (momentum) | 95.28% | 14.33% | 46.48% | 0.45 | 42% | 1.253 | 150 | — |
| Hawk — Breakout Momentum (hawk) | 32.14% | 5.74% | 18.97% | 0.16 | 44.5% | 1.135 | 317 | — |
| Bull — Golden Cross (bull) | 27.56% | 4.99% | 23.69% | 0.114 | 41.1% | 1.202 | 112 | — |
| MACD — Momentum Cross (macd) | 4.12% | 0.81% | 33.4% | -0.096 | 40.6% | 1.013 | 318 | — |
| Owl — Mean Reversion (owl) | -13.71% | -2.91% | 37.23% | -0.3 | 44.6% | 0.962 | 617 | — |
| Fox — Contrarian (fox) | -35.58% | -8.42% | 54.49% | -0.466 | 39.8% | 0.925 | 913 | — |
| Bear — Death Cross (bear) | -35.66% | -8.45% | 49.4% | -0.677 | 31.3% | 0.707 | 160 | — |
| RSI — Oversold Bounce (rsi) | -59.54% | -16.57% | 63.17% | -1.075 | 38.2% | 0.789 | 714 | — |
| Bollinger — Band Reversion (bb) | -62.78% | -17.95% | 64.13% | -1.461 | 34.5% | 0.797 | 914 | — |

## Red flags

**momentum**
- [MEDIUM] Sharpe 0.45 (< 0.5)
- [HIGH] max drawdown 46.48% (> 20%)
- [MEDIUM] 16 stops gapped through (worst -12.5% vs stop -8%)
- [MEDIUM] short side loses money (32 trades, P&L -409)

**hawk**
- [MEDIUM] Sharpe 0.16 (< 0.5)
- [MEDIUM] CAGR 5.74% below buy-and-hold 7.39%
- [MEDIUM] 19 stops gapped through (worst -5.6% vs stop -4%)

**bull**
- [MEDIUM] Sharpe 0.114 (< 0.5)
- [HIGH] max drawdown 23.69% (> 20%)
- [MEDIUM] CAGR 4.99% below buy-and-hold 7.39%
- [MEDIUM] 8 stops gapped through (worst -10.5% vs stop -6%)

**macd**
- [HIGH] Sharpe -0.096 (< 0.5)
- [HIGH] max drawdown 33.4% (> 20%)
- [MEDIUM] CAGR 0.81% below buy-and-hold 7.39%
- [MEDIUM] 24 stops gapped through (worst -9.9% vs stop -5%)
- [MEDIUM] short side loses money (169 trades, P&L -4163)

**owl**
- [HIGH] profit factor 0.962 < 1: loses money after costs
- [HIGH] Sharpe -0.3 (< 0.5)
- [HIGH] max drawdown 37.23% (> 20%)
- [MEDIUM] CAGR -2.91% below buy-and-hold 7.39%
- [HIGH] 54 stops gapped through (worst -15.1% vs stop -4%)

**fox**
- [HIGH] profit factor 0.925 < 1: loses money after costs
- [HIGH] Sharpe -0.466 (< 0.5)
- [HIGH] max drawdown 54.49% (> 20%)
- [MEDIUM] CAGR -8.42% below buy-and-hold 7.39%
- [HIGH] 77 stops gapped through (worst -14.6% vs stop -4%)
- [MEDIUM] short side loses money (462 trades, P&L -5203)

**bear**
- [HIGH] profit factor 0.707 < 1: loses money after costs
- [HIGH] Sharpe -0.677 (< 0.5)
- [HIGH] max drawdown 49.4% (> 20%)
- [MEDIUM] CAGR -8.45% below buy-and-hold 7.39%
- [MEDIUM] 17 stops gapped through (worst -7.9% vs stop -5%)
- [MEDIUM] short side loses money (160 trades, P&L -3566)

**rsi**
- [HIGH] profit factor 0.789 < 1: loses money after costs
- [HIGH] Sharpe -1.075 (< 0.5)
- [HIGH] max drawdown 63.17% (> 20%)
- [MEDIUM] CAGR -16.57% below buy-and-hold 7.39%
- [HIGH] 64 stops gapped through (worst -16.0% vs stop -4%)
- [MEDIUM] short side loses money (417 trades, P&L -5724)

**bb**
- [HIGH] profit factor 0.797 < 1: loses money after costs
- [HIGH] Sharpe -1.461 (< 0.5)
- [HIGH] max drawdown 64.13% (> 20%)
- [MEDIUM] CAGR -17.95% below buy-and-hold 7.39%
- [HIGH] 62 stops gapped through (worst -11.8% vs stop -3%)
- [MEDIUM] short side loses money (495 trades, P&L -5208)

## Exit mix (realistic)

- momentum: take_profit 32, stop_loss 68, max_hold 23, stop_loss_gap 16, take_profit_gap 8, eop 3
- hawk: take_profit 46, max_hold 111, stop_loss 126, stop_loss_gap 19, take_profit_gap 14, eop 1
- bull: take_profit 17, stop_loss 47, max_hold 35, take_profit_gap 3, stop_loss_gap 8, eop 2
- macd: stop_loss 137, max_hold 88, take_profit 47, take_profit_gap 19, stop_loss_gap 24, eop 3
- owl: max_hold 151, take_profit_gap 34, stop_loss 241, take_profit 133, stop_loss_gap 54, eop 4
- fox: max_hold 207, stop_loss 398, take_profit 189, take_profit_gap 39, stop_loss_gap 77, eop 3
- bear: stop_loss 76, max_hold 40, stop_loss_gap 17, take_profit_gap 7, take_profit 17, eop 3
- rsi: stop_loss_gap 64, stop_loss 303, take_profit 127, max_hold 189, take_profit_gap 27, eop 4
- bb: stop_loss 483, stop_loss_gap 62, take_profit 151, take_profit_gap 31, max_hold 185, eop 2

