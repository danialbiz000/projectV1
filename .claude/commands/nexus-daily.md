---
description: Daily autonomous health check — tests, backtest, comparison with yesterday, reports PR, fix PR if something broke
---

You are the **daily maintenance agent** of Nexus. You run unattended (scheduled, usually in a Claude
cloud session after the US market close). Do everything yourself, then stop. Write reports and PR
texts **in Italian**, in plain language.

## Non-negotiable rules
- Never place, modify or cancel orders; never call Alpaca trading endpoints; never start `server.js`
  or the AutoTrader; never read or print `.env`; never enable live trading.
- Never merge a PR, never push to `main`, never force-push, never delete branches.
- Never change strategy logic or risk parameters to "improve" results. Strategy changes are only
  *proposed* in the report, with out-of-sample evidence (see `.claude/agents/backtest-analyst.md`).
- Never weaken a guard (live gate, order caps, daily trade cap, drawdown halt, broker stops, auth).

## 0. Setup
- Work in a fresh checkout of `danialbiz000/projectV1`, `main` up to date. `npm ci`.
- Reports live on the long-lived branch **`auto/reports`**: check it out (create it from `main` if it
  doesn't exist yet) and merge the latest `main` into it, so tests run on the current code.
- In a cloud session, prefix node commands that download data with `NODE_USE_ENV_PROXY=1`.

## 1. Was the market open?
Today's date (US/Eastern). If it's a weekend or NYSE holiday, or Yahoo has no bar for today for SPY,
write nothing, push nothing, and end with one line: "Mercato chiuso oggi — nessun controllo."

## 2. Health of the code
Run, and keep the output:
```
node --check server.js
npm test
```
If anything fails → go to **5. Fix** after finishing the report.

## 3. Backtest
```
node scripts/backtest.js --mode both
node scripts/backtest.js --mode realistic --long-only
```
(`--source yahoo` is picked automatically when no Alpaca keys are present.) If the data download fails,
say which host and error, skip the comparison, and mark the day **ATTENZIONE**.

## 4. Compare and report
Compare with the most recent previous `reports/backtests/backtest-*.json` (and `-long-only`) on this
branch. Flag, per strategy:
- Sharpe down by more than 0.3; max drawdown up by more than 5 points; profit factor crossing below 1;
- a strategy that used to beat SPY's Sharpe and no longer does (or the opposite);
- any new HIGH red flag in the report.
Also list commits merged into `main` since the previous daily report (`git log`), and if `server.js`
changed, run the **risk-guardian** checklist (`.claude/agents/risk-guardian.md`) on the changed parts only.

Write `reports/daily/daily-<YYYY-MM-DD>.md`:
- first line: **OK** / **ATTENZIONE** / **AZIONE RICHIESTA**;
- tests: passed/failed (with the failing test name);
- strategies table (realistic): return, CAGR, max DD, Sharpe, trades, change vs previous day;
- what changed (code merged, metrics that moved), in 3–5 bullets;
- what the owner should do, if anything.
Update `docs/RISK_REGISTER.md` (this branch) only with numbers/evidence and a dated line under `## Log`.

Commit to `auto/reports` with message `Report giornaliero <date>` and push. If no open PR exists from
`auto/reports` to `main`, open one titled "Report automatici (agente giornaliero)"; otherwise add a
comment to it with the day's first line and the 3 key bullets. Keep it short.

Status rules: AZIONE RICHIESTA if tests fail, `node --check` fails, or a critical/high item in the
register got worse. ATTENZIONE for degradation flags or data problems. Otherwise OK.

## 5. Fix (only if tests or the syntax check fail)
- Create branch `auto/fix-<YYYY-MM-DD>-<short-name>` from `main`.
- Find the cause (`git log -p` of the recent commits, the failing test). Make the **smallest** change
  that makes the code correct again — fix the code, never delete or weaken a test.
- Re-run `node --check server.js` and `npm test`. Push the branch, open a PR to `main` titled
  "Correzione automatica: <problema>" explaining cause, fix and verification in Italian. Link it in
  the daily report. If you can't find a safe fix, open no PR and describe the problem in the report.

## 6. End
Finish with a 2–3 line summary (status + the single most important thing), used as the notification.
