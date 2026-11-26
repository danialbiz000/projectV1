---
description: Weekly Nexus check — backtest, risk audit and paper-account health, then one summary
---

Run the Nexus weekly check. Use the three agents in `.claude/agents/`, one after the other
(each writes its own report), then combine their results.

1. **paper-monitor** — run the paper-account health check and write its summary.
2. **backtest-analyst** — run the realistic and long-only backtests, compare with the previous run,
   update the S*/B*/L6 rows of `docs/RISK_REGISTER.md`.
3. **risk-guardian** — audit the code against every L* item of the register and write the risk audit.
   Don't create fix branches during the weekly check unless a **critical** item got worse; just report.

Then write `reports/weekly-<YYYY-MM-DD>.md` with:
- a one-line status: OK / WATCH / ACTION NEEDED;
- the 3 most important findings across the three reports, most dangerous first;
- what changed since the previous weekly report (read the latest `reports/weekly-*.md`);
- the decisions the owner needs to take (e.g. "approve the L1 fix on branch risk/L1-broker-stop").

Rules for everyone: read-only towards Alpaca, never place orders, never touch `.env`, never enable
live trading, never merge or push. $ARGUMENTS
