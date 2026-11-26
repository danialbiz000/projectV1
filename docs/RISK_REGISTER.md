# Nexus — Risk register

Single source of truth for known weaknesses of the trading system. Maintained by the agents in
`.claude/agents/` (see `docs/AGENTS.md`). Each item has an ID, a severity, an owner agent and a status.

Status values: `open` → `fix-proposed` (patch on a branch, waiting for the owner's approval) →
`fixed` (merged + verified by a backtest or a test) → `accepted` (owner consciously keeps the risk).

Severity: **critical** (can lose a large share of the account), **high**, **medium**, **low**.

> Rule: agents may propose fixes, never merge them, never enable live trading, never place orders.

---

## Live AutoTrader (`server.js`, AT)

| ID | Severity | Status | Owner | Finding | Proposed fix |
|----|----------|--------|-------|---------|--------------|
| L1 | critical | merged #13 — verify on paper | risk-guardian | BUY/SHORT orders are `oto` with **take profit only** — no stop loss at the broker (`server.js`, "No bracket stop_loss"). If the server is down, asleep or crashes, positions have no protection at all; gaps of −10…−17% overnight were observed in the backtest. | Use `order_class: 'bracket'` with a broker-side **catastrophic stop** (e.g. 1.5 × adaptive SL). AI review can still exit earlier. |
| L2 | critical | merged #13 — verify on paper | risk-guardian | Emergency close only at **2.2 × adaptive SL**; adaptive SL is capped at 25% → a position can lose up to **−55%** before the hard stop. | Cap the hard stop (e.g. min(2.2×SL, 15%)) and enforce it at the broker (L1). |
| L3 | high | open | risk-guardian | AI position review has a **2-day cooldown** per symbol. The emergency close is checked every cycle, but between the review zone (−SL×reviewPct) and the hard stop (−2.2×SL) a losing position can drift for 2 days with no decision. | Re-review if the loss deepened by ≥ 0.5×SL since the last review; shorten the cooldown in RISK-OFF. |
| L4 | high | open | risk-guardian | Review can **ADD** to a losing position (averaging down, max 1 per position). | Disable ADD on positions below −SL, or require the regime to be RISK-ON and the backtest to support it. |
| L5 | high | fix-proposed (`claude/risk-limits-l5-l7`) | risk-guardian | Sizing uses `buyingPower * 0.95`; Alpaca buying power includes **margin (2×–4×)**. 20 positions × 15% = up to 300% gross exposure. | Cap gross exposure at 100% of equity (sum of position market values ≤ equity) unless explicitly allowed. |
| L6 | high | merged #13 — verify on paper | backtest-analyst | `allowShort: true`. In the 3-year realistic backtest **every strategy lost money on the short side** (e.g. RSI −9.5% → +58% when long-only). | Default `allowShort: false`; re-enable only for a strategy whose short side is profitable out-of-sample. |
| L7 | medium | fix-proposed (`claude/risk-limits-l5-l7`) | risk-guardian | Drawdown halt is measured from `sessionStartEquity` (start value), not from the **high-water mark**: after a +20% run the account can give back 35% before halting. | Track and persist peak equity; halt on drawdown from peak. |
| L8 | medium | open | paper-monitor | The live AT is AI-driven (Claude + Black-Scholes filter); the 9 backtest strategies **do not validate it**. Its only evidence is the paper account. | Compare paper P&L, hit rate and drawdown with expectations every week (paper-monitor). |
| L9 | low | open | risk-guardian | Multi-agent sizing: `riskPerTrade` is actually the **position size** (8–15% of capital per trade), not the risk. Virtual only today. | Rename / document; if agents ever trade real money, size by risk (stop distance). |

## Strategies (backtest, `lib/backtest/engine.js`)

Baseline: realistic backtest 2023-11-27 → 2026-11-26, 25 large caps, Yahoo daily data, 5 bps slippage/side.
Benchmark buy-and-hold SPY: **+57.6%**, CAGR 16.5%, max DD 19.0%, Sharpe 0.77.

| ID | Severity | Status | Owner | Finding |
|----|----------|--------|-------|---------|
| S1 | high | open | backtest-analyst | 7 of 9 strategies have profit factor < 1 after costs (long+short): hawk, fox, bull, bear, rsi, macd, bb. |
| S2 | high | open | backtest-analyst | Short side loses in all strategies that short (rsi, bb, fox, bear, macd). Long-only: rsi +58%, momentum +68%, macd +28%, bb +25%. |
| S3 | medium | open | backtest-analyst | No strategy beats SPY on a risk-adjusted basis: best are owl (Sharpe 0.77, DD 21%) and long-only rsi (0.76) / momentum (0.65, DD 29%). |
| S4 | high | open | backtest-analyst | Stops gap through: 4% stops realised down to **−17%** (hawk), −13% (owl, fox, macd). Daily-bar stops are not a hard limit. |
| S5 | high | open | backtest-analyst | Out-of-sample check 2018–2022 (SPY +42.8%, Sharpe 0.24, DD 34%): **owl −13.7%** and **rsi long-only −25%** — the two best recent strategies don't survive another regime. Only **momentum long-only** is good in both periods (+158%, Sharpe 0.64 / +68%, Sharpe 0.65); macd long-only mixed (+101% / +28%). Shorts lose in both periods. Universe still chosen today (survivorship bias). Reports: `reports/backtests/backtest-oos-2018-2022*.md`. |
| S6 | medium | open | backtest-analyst | Hawk "volume spike" is just `v > previous v` (true ~50% of days) — not a real volume filter. |

## Backtest engine

| ID | Severity | Status | Owner | Finding |
|----|----------|--------|-------|---------|
| B1 | high | fixed | backtest-analyst | Legacy engine checked stops/targets on the **close only** and had **no costs**; it overstated returns by up to 40 points (macd, hawk, fox). Realistic mode (intrabar stops, gaps, slippage, borrow, equity sizing, warm-up) is now the default; legacy kept for comparison (`test/backtest-engine.test.js` proves it is identical to the old code). |
| B2 | medium | fixed | backtest-analyst | No warm-up history: long lookbacks (momentum = 253 bars) spent most of the period without signals. Realistic mode fetches warm-up bars before `start`. |

---

## Log

- 2026-11-26 — S5: out-of-sample 2018–2022 run; owl/rsi not robust, momentum long-only robust, shorts lose in both periods.
- 2026-11-26 — L5+L7 fix proposed on `claude/risk-limits-l5-l7`: gross exposure capped at 1× equity (`NEXUS_MAX_GROSS_EXPOSURE`), drawdown halt from the persisted peak.
- 2026-11-26 — L1, L2, L6 merged in #13; dashboard close fixed in #15. Status stays 'verify on paper' until paper-monitor confirms every position has a broker stop.
- 2026-11-26 — L1+L2 fix proposed on `risk/L1-L2-broker-stop`: bracket entries with a GTC broker stop at min(2.2×SL, 15%), `ensureProtectiveStops` each cycle (also when halted), open TP/stop legs cancelled before every close.
- 2026-11-26 — L6 fix proposed on `risk/L6-shorts-off`: `allowShort: false` by default, one-time switch-off for saved states.
- 2026-11-26 — register created from the first full analysis (realistic backtest + code review). Reports: `reports/backtests/backtest-2026-11-26.md`, `reports/backtests/backtest-2026-11-26-long-only.md`.
