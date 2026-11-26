#!/usr/bin/env node
'use strict';
// Nexus paper-account health check — READ-ONLY.
// Reads the Alpaca account, positions, open orders and equity history, plus the AutoTrader
// state file, and flags the risks listed in docs/RISK_REGISTER.md as they show up live.
// It can only send GET requests (see alpacaGet) — it never places, changes or cancels orders.
//
//   node scripts/paper-health.js            → reports/paper/paper-health-<date>.md / .json
// Exit code: 0 ok · 1 error · 2 critical findings (useful for schedulers).

require('dotenv').config();
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const BASE = (process.env.ALPACA_BASE_URL || 'https://paper-api.alpaca.markets').replace(/\/$/, '');
const KEY = process.env.ALPACA_API_KEY, SECRET = process.env.ALPACA_SECRET_KEY;
const DATA_DIR = [process.env.NEXUS_DATA_DIR, path.join(ROOT, 'data')].find(d => d && fs.existsSync(d)) || path.join(ROOT, 'data');
const LIMITS = {
  maxGrossExposure: +(process.env.NEXUS_MAX_GROSS_EXPOSURE || 1.0),   // × equity
  maxPositionPct: +(process.env.NEXUS_HEALTH_MAX_POSITION_PCT || 20),
  ddWarnPct: 10, ddHighPct: 15, worstPosPct: -15,
};

async function alpacaGet(p) {
  // The only network call in this file. GET only, by construction.
  const r = await fetch(`${BASE}${p}`, { method: 'GET', headers: { 'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET } });
  if (!r.ok) throw new Error(`Alpaca GET ${p.split('?')[0]} → ${r.status}`);
  return r.json();
}

function readATState() {
  const file = path.join(DATA_DIR, 'autotrader-state.json');
  if (!fs.existsSync(file)) return null;
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return null; }
}

function readDecisions() {
  const file = path.join(DATA_DIR, 'nexus.db');
  if (!fs.existsSync(file)) return null;
  try {
    const Database = require('better-sqlite3');
    const db = new Database(file, { readonly: true, fileMustExist: true });
    const since = Date.now() - 7 * 86400000;
    const cols = db.prepare('PRAGMA table_info(decisions)').all().map(c => c.name);
    if (!cols.length) return null;
    const ts = cols.includes('ts') ? 'ts' : null;
    const where = ts ? `WHERE ${ts} >= ?` : '';
    const args = ts ? [since] : [];
    const total = db.prepare(`SELECT COUNT(*) n FROM decisions ${where}`).get(...args).n;
    const executed = cols.includes('executed') ? db.prepare(`SELECT COUNT(*) n FROM decisions ${where} ${where ? 'AND' : 'WHERE'} executed = 1`).get(...args).n : null;
    const errors = cols.includes('action') ? db.prepare(`SELECT COUNT(*) n FROM decisions ${where} ${where ? 'AND' : 'WHERE'} action = 'ERROR'`).get(...args).n : null;
    db.close();
    return { last7d: { decisions: total, executed, errors } };
  } catch (e) { return { error: e.message }; }
}

(async () => {
  if (!KEY || !SECRET || /your_/.test(KEY)) throw new Error('ALPACA_API_KEY / ALPACA_SECRET_KEY missing in .env');
  const isPaper = /paper-api/.test(BASE);
  const [account, positions, orders, history] = await Promise.all([
    alpacaGet('/v2/account'),
    alpacaGet('/v2/positions'),
    alpacaGet('/v2/orders?status=open&nested=true&limit=500'),
    alpacaGet('/v2/account/portfolio/history?period=3M&timeframe=1D').catch(() => null),
  ]);
  const equity = +account.equity;
  const findings = [];
  const add = (sev, id, msg, extra = {}) => findings.push({ sev, id, msg, ...extra });

  if (!isPaper) add('info', 'L0', `LIVE account (${BASE}) — real money`);
  if (account.trading_blocked || account.account_blocked) add('critical', 'ACC', 'Account trading is blocked');

  // Protective stops: any stop / stop_limit / trailing_stop on the opposite side, including bracket legs.
  const flat = [];
  for (const o of orders) { flat.push(o); for (const leg of o.legs || []) flat.push(leg); }
  const stopFor = (sym, side) => flat.some(o => o.symbol === sym && ['stop', 'stop_limit', 'trailing_stop'].includes(o.type)
    && o.side === (side === 'long' ? 'sell' : 'buy') && !['canceled', 'expired', 'filled'].includes(o.status));
  const unprotected = positions.filter(p => !stopFor(p.symbol, p.side));
  if (unprotected.length) add('critical', 'L1', `${unprotected.length}/${positions.length} positions have NO stop order at the broker`, { symbols: unprotected.map(p => p.symbol) });

  const gross = positions.reduce((a, p) => a + Math.abs(+p.market_value), 0);
  const shortMv = positions.filter(p => p.side === 'short').reduce((a, p) => a + Math.abs(+p.market_value), 0);
  if (equity > 0 && gross / equity > LIMITS.maxGrossExposure) add('high', 'L5', `Gross exposure ${(gross / equity * 100).toFixed(0)}% of equity (limit ${LIMITS.maxGrossExposure * 100}%) — using margin`);
  if (shortMv > 0) add('medium', 'L6', `Short exposure $${shortMv.toFixed(0)} (${(shortMv / equity * 100).toFixed(0)}% of equity) — shorts lost money in every backtested strategy`);
  for (const p of positions) {
    const pct = Math.abs(+p.market_value) / equity * 100;
    if (pct > LIMITS.maxPositionPct) add('medium', 'CONC', `${p.symbol} is ${pct.toFixed(0)}% of equity`);
    const pl = +p.unrealized_plpc * 100;
    if (pl <= LIMITS.worstPosPct) add('high', 'L2', `${p.symbol} ${p.side} at ${pl.toFixed(1)}% — deep loss still open`);
  }

  let peak = null, ddPct = null;
  if (history && Array.isArray(history.equity)) {
    const eq = history.equity.filter(x => x != null && x > 0);
    if (eq.length) {
      peak = Math.max(...eq, equity);
      ddPct = (peak - equity) / peak * 100;
      if (ddPct >= LIMITS.ddHighPct) add('high', 'L7', `Drawdown from 3-month peak ${ddPct.toFixed(1)}%`);
      else if (ddPct >= LIMITS.ddWarnPct) add('medium', 'L7', `Drawdown from 3-month peak ${ddPct.toFixed(1)}%`);
    }
  }

  const at = readATState();
  if (at && at.halted) add('high', 'AT', `AutoTrader HALTED: ${at.haltReason || 'no reason recorded'}`);
  if (at && at.config && at.config.allowShort) add('medium', 'L6', 'AutoTrader config allows shorts');
  const decisions = readDecisions();
  if (decisions && decisions.last7d && decisions.last7d.errors > 5) add('medium', 'ERR', `${decisions.last7d.errors} ERROR decisions in the last 7 days`);

  const order = { critical: 0, high: 1, medium: 2, info: 3 };
  findings.sort((a, b) => order[a.sev] - order[b.sev]);
  const summary = {
    generated_at: new Date().toISOString(), account: isPaper ? 'paper' : 'LIVE',
    equity, cash: +account.cash, buying_power: +account.buying_power, positions: positions.length,
    gross_exposure_pct: equity ? +(gross / equity * 100).toFixed(1) : null, short_exposure_pct: equity ? +(shortMv / equity * 100).toFixed(1) : null,
    peak_equity_3m: peak, drawdown_from_peak_pct: ddPct != null ? +ddPct.toFixed(2) : null,
    autotrader: at ? { halted: !!at.halted, enabled: !!at.enabled } : null, decisions, findings,
  };

  const outDir = path.join(ROOT, 'reports', 'paper');
  fs.mkdirSync(outDir, { recursive: true });
  const stamp = new Date().toISOString().slice(0, 10);
  fs.writeFileSync(path.join(outDir, `paper-health-${stamp}.json`), JSON.stringify(summary, null, 1));
  const md = [
    `# Paper account health — ${stamp}`, '',
    `Account **${summary.account}** · equity $${equity.toFixed(2)} · ${positions.length} positions · gross exposure ${summary.gross_exposure_pct}% · short ${summary.short_exposure_pct}%`,
    ddPct != null ? `Drawdown from 3-month peak: ${ddPct.toFixed(1)}% (peak $${peak.toFixed(2)})` : '',
    at ? `AutoTrader: ${at.enabled ? 'enabled' : 'disabled'}${at.halted ? ' — HALTED' : ''}` : 'AutoTrader state file not found',
    '', '## Findings', '',
    ...(findings.length ? findings.map(f => `- **[${f.sev.toUpperCase()}] ${f.id}** — ${f.msg}${f.symbols ? ` (${f.symbols.join(', ')})` : ''}`) : ['- No findings.']),
  ].join('\n');
  fs.writeFileSync(path.join(outDir, `paper-health-${stamp}.md`), md + '\n');
  console.log(md);
  process.exit(findings.some(f => f.sev === 'critical') ? 2 : 0);
})().catch(e => { console.error('Paper health check failed:', e.message); process.exit(1); });
