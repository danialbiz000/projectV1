# Portfolio Nexus × Trading Desk — instructions for Claude

Node/Express server (`server.js`) with the AutoTrader (Claude-driven, Alpaca **paper** account),
a virtual multi-agent system and a backtest engine; `nexus_quant/` is a Python quant library.
More background: `CONTEXT_FOR_NEW_CHAT.md` (Italian).

## Safety rules (non-negotiable)
- Never place, modify or cancel orders, never call Alpaca trading endpoints, never start the server
  or the AutoTrader on your own.
- Never read, print or edit `.env`; never set `NEXUS_ENABLE_LIVE_TRADING` or change `ALPACA_BASE_URL`.
- Never weaken an existing guard (live gate, order caps, daily trade cap, drawdown halt, auth, CORS).
- Work on a branch, never on `main`; don't merge or push unless the owner asks.
- The owner is Italian: write reports and summaries **in Italian**, in plain language (code and
  identifiers stay in English).

## Agents (`.claude/agents/`) — they own the items in `docs/RISK_REGISTER.md`
| Agent | Owns | Typical request |
|---|---|---|
| `backtest-analyst` | S*, B*, L6 | "run the backtest", "is strategy X still working?" |
| `risk-guardian` | L1–L5, L7, L9 | "is the bot safe?", after any change to `server.js` |
| `paper-monitor` | L1, L5–L8 (evidence) | "how is the paper account?", daily check |

`/nexus-check` runs all three and writes `reports/weekly-<date>.md`. Details: `docs/AGENTS.md`.

## Useful commands
- `node scripts/backtest.js` — realistic + legacy backtest of the 9 strategies → `reports/backtests/`
  (`--long-only`, `--strategies hawk,owl`, `--start/--end`, `--source alpaca|yahoo|stooq|csv=DIR`).
- `node scripts/paper-health.js` — read-only paper-account health check → `reports/paper/`.
- `node test/backtest-engine.test.js` — engine tests (set `ORIGINAL_SERVER=<old server.js>` to
  re-prove that legacy mode equals the pre-refactor engine).
- `node --check server.js` before every restart.

## Backtest engine
`lib/backtest/engine.js` is shared by `POST /api/backtest` and the CLI. Mode `realistic` (default):
intrabar stops with gap handling, slippage, short borrow, equity-based sizing, warm-up history.
Mode `legacy` reproduces the original engine exactly, for comparison only.
