# Nexus agents

Three Claude Code sub-agents keep watching the weaknesses listed in `docs/RISK_REGISTER.md`.
They live in `.claude/agents/` and are available whenever you run `claude` in this folder.

| Agent | What it does | Writes |
|---|---|---|
| **backtest-analyst** | Runs the realistic and long-only backtests, compares with the last run and with SPY, validates any proposed strategy change out of sample. | `reports/backtests/` |
| **risk-guardian** | Audits `server.js` against every L* risk (broker stop, hard stop, cooldown, averaging down, margin, shorts, drawdown base); proposes minimal fixes on `risk/<ID>-…` branches. | `reports/risk/`, fix branches |
| **paper-monitor** | Read-only check of the Alpaca paper account: unprotected positions, margin, shorts, drawdown from peak, AutoTrader halt/errors. | `reports/paper/` |

All three update `docs/RISK_REGISTER.md` (status + dated log lines).

## What they can't do (by design)
- Place, change or cancel orders; start the server or the AutoTrader; enable live trading.
- Read `.env` (blocked in `.claude/settings.json`); the scripts read the keys themselves.
- Merge or push. Fixes wait on a branch for your approval.

## How to use them
In this folder:
```
claude                                   # then e.g. "use the risk-guardian to check the bot"
claude -p "/nexus-check"                 # weekly check, non-interactive
```
`/nexus-check` runs paper-monitor → backtest-analyst → risk-guardian and writes `reports/weekly-<date>.md`.

## Run it automatically every week (Windows)
`scripts/schedule-weekly-check.ps1` registers a Windows scheduled task that runs
`claude -p "/nexus-check"` every Saturday at 09:17. Run once in PowerShell, from this folder:
```
powershell -ExecutionPolicy Bypass -File scripts\schedule-weekly-check.ps1
```
Remove it with `Unregister-ScheduledTask -TaskName "Nexus weekly check"`.

## JARVIS
If JARVIS's `JARVIS_SOURCE` points at this folder, its HUD shows the backtest table
(from `reports/backtests/*.json`) and you can ask "Hey Jarvis, what did the weekly check say?".
