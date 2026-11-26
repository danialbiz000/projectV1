#!/usr/bin/env node
'use strict';
// Nexus backtest CLI — runs the same strategies as POST /api/backtest, without the server.
// READ-ONLY: it only downloads historical daily bars. It never places, changes or cancels orders.
//
//   node scripts/backtest.js                                  # all strategies, core universe, last 3 years, realistic + legacy
//   node scripts/backtest.js --strategies hawk,owl --start 2022-01-01 --end 2025-12-31
//   node scripts/backtest.js --source yahoo                   # free data, no keys (also: stooq)
//   node scripts/backtest.js --long-only                      # ignore short signals
//   node scripts/backtest.js --source csv=./my-data           # <SYMBOL>.csv with Date,Open,High,Low,Close,Volume
//
// Output: reports/backtests/backtest-<date>.md and .json (read by the agents and by JARVIS).

require('dotenv').config();
const fs = require('fs');
const path = require('path');
const engine = require('../lib/backtest/engine');

const ROOT = path.resolve(__dirname, '..');
const CORE_UNIVERSE = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'JPM', 'V', 'UNH', 'LLY',
  'XOM', 'CVX', 'CAT', 'HON', 'WMT', 'COST', 'HD', 'AMD', 'CRM', 'BAC', 'GS', 'PFE', 'MRK', 'LMT', 'TSLA'];

// ---------------------------------------------------------------- args
function parseArgs(argv) {
  const a = { strategies: 'all', symbols: null, start: null, end: null, capital: 10000, mode: 'both', source: 'auto',
    out: path.join(ROOT, 'reports', 'backtests'), benchmark: 'SPY', rf: 0.043, slippageBps: 5, commissionBps: 0, borrowBpsYear: 30 };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i].replace(/^--/, ''), v = argv[i + 1];
    const take = () => { i++; return v; };
    if (k === 'strategies') a.strategies = take();
    else if (k === 'symbols') a.symbols = take().split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    else if (k === 'start') a.start = take();
    else if (k === 'end') a.end = take();
    else if (k === 'capital') a.capital = +take();
    else if (k === 'mode') a.mode = take();
    else if (k === 'source') a.source = take();
    else if (k === 'out') a.out = path.resolve(take());
    else if (k === 'benchmark') a.benchmark = take().toUpperCase();
    else if (k === 'long-only') a.longOnly = true;
    else if (k === 'slippage-bps') a.slippageBps = +take();
    else if (k === 'commission-bps') a.commissionBps = +take();
    else if (k === 'help' || k === 'h') { console.log(fs.readFileSync(__filename, 'utf8').split('\n').slice(2, 12).join('\n')); process.exit(0); }
  }
  const today = new Date();
  a.end = a.end || today.toISOString().slice(0, 10);
  a.start = a.start || new Date(today.getTime() - 3 * 365.25 * 86400000).toISOString().slice(0, 10);
  a.symbols = a.symbols || CORE_UNIVERSE;
  a.strategyKeys = a.strategies === 'all' ? Object.keys(engine.BACKTEST_STRATEGIES) : a.strategies.split(',').map(s => s.trim());
  for (const k of a.strategyKeys) if (!engine.BACKTEST_STRATEGIES[k]) throw new Error(`Unknown strategy "${k}". Available: ${Object.keys(engine.BACKTEST_STRATEGIES).join(', ')}`);
  if (a.source === 'auto') a.source = process.env.ALPACA_API_KEY && !/your_/.test(process.env.ALPACA_API_KEY) ? 'alpaca' : 'yahoo';
  return a;
}

// ---------------------------------------------------------------- data (read-only)
const CACHE = path.join(ROOT, 'data', 'cache', 'bars');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getJSON(url, headers, tries = 5) {
  let delay = 1000;
  for (let t = 0; t < tries; t++) {
    const r = await fetch(url, { headers });
    if (r.status === 429) { await sleep(delay); delay *= 2; continue; }
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${url.split('?')[0]}`);
    return r.json();
  }
  throw new Error('rate limited: ' + url.split('?')[0]);
}

async function fromAlpaca(symbols, start, end) {
  const base = process.env.ALPACA_DATA_URL || 'https://data.alpaca.markets';
  const headers = { 'APCA-API-KEY-ID': process.env.ALPACA_API_KEY, 'APCA-API-SECRET-KEY': process.env.ALPACA_SECRET_KEY };
  const out = {};
  for (let i = 0; i < symbols.length; i += 10) {
    const params = new URLSearchParams({ symbols: symbols.slice(i, i + 10).join(','), timeframe: '1Day', start, end, limit: '10000', adjustment: 'split', sort: 'asc' });
    let token = null;
    do {
      if (token) params.set('page_token', token);
      const data = await getJSON(`${base}/v2/stocks/bars?${params}`, headers);
      for (const [sym, bars] of Object.entries(data.bars || {})) {
        (out[sym] = out[sym] || []).push(...bars.map(b => ({ t: b.t.slice(0, 10), o: b.o, h: b.h, l: b.l, c: b.c, v: b.v })));
      }
      token = data.next_page_token || null;
    } while (token);
    await sleep(400);
  }
  return out;
}

function parseCSV(text) {
  const lines = text.trim().split(/\r?\n/);
  const head = lines.shift().toLowerCase().split(',');
  const idx = (n) => head.findIndex(h => h.trim() === n);
  const [d, o, h, l, c, v] = ['date', 'open', 'high', 'low', 'close', 'volume'].map(idx);
  if ([d, o, h, l, c].some(x => x < 0)) throw new Error('CSV needs Date,Open,High,Low,Close[,Volume] columns');
  return lines.map(line => line.split(',')).filter(x => x[c] && x[c] !== 'null')
    .map(x => ({ t: x[d].slice(0, 10), o: +x[o], h: +x[h], l: +x[l], c: +x[c], v: v >= 0 ? +x[v] || 0 : 0 }))
    .filter(b => b.c > 0).sort((a, b) => (a.t < b.t ? -1 : 1));
}

async function fromStooq(symbols, start, end) {
  fs.mkdirSync(CACHE, { recursive: true });
  const out = {};
  for (const sym of symbols) {
    const file = path.join(CACHE, `stooq-${sym}.csv`);
    let text = null;
    if (fs.existsSync(file) && Date.now() - fs.statSync(file).mtimeMs < 12 * 3600e3) text = fs.readFileSync(file, 'utf8');
    else {
      const r = await fetch(`https://stooq.com/q/d/l/?s=${sym.toLowerCase().replace('.', '-')}.us&i=d`);
      if (!r.ok) throw new Error(`stooq ${sym}: ${r.status}`);
      text = await r.text();
      if (!/^Date,/i.test(text)) { console.warn(`  ! stooq has no data for ${sym}`); continue; }
      fs.writeFileSync(file, text);
      await sleep(250);
    }
    out[sym] = parseCSV(text).filter(b => b.t >= start && b.t <= end);
  }
  return out;
}

// Yahoo chart API: daily OHLCV, split-adjusted (same convention as Alpaca adjustment=split).
async function fromYahoo(symbols, start, end) {
  fs.mkdirSync(CACHE, { recursive: true });
  const p1 = Math.floor(Date.parse(start) / 1000), p2 = Math.floor(Date.parse(end) / 1000) + 86400;
  const out = {};
  for (const sym of symbols) {
    const file = path.join(CACHE, `yahoo-${sym}-${start}-${end}.json`);
    let data;
    if (fs.existsSync(file) && Date.now() - fs.statSync(file).mtimeMs < 12 * 3600e3) data = JSON.parse(fs.readFileSync(file, 'utf8'));
    else {
      try {
        data = await getJSON(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?period1=${p1}&period2=${p2}&interval=1d&events=split`, { 'User-Agent': 'Mozilla/5.0' });
      } catch (e) { console.warn(`  ! yahoo ${sym}: ${e.message}`); continue; }
      fs.writeFileSync(file, JSON.stringify(data));
      await sleep(200);
    }
    const r = data.chart && data.chart.result && data.chart.result[0];
    if (!r || !r.timestamp) { console.warn(`  ! yahoo has no data for ${sym}`); continue; }
    const q = r.indicators.quote[0];
    out[sym] = r.timestamp.map((ts, i) => ({ t: new Date((ts + (r.meta.gmtoffset || 0)) * 1000).toISOString().slice(0, 10),
      o: q.open[i], h: q.high[i], l: q.low[i], c: q.close[i], v: q.volume[i] || 0 }))
      .filter(b => [b.o, b.h, b.l, b.c].every(x => x != null && x > 0));
  }
  return out;
}

function fromCSV(dir, symbols, start, end) {
  const out = {};
  for (const sym of symbols) {
    const file = path.join(dir, `${sym}.csv`);
    if (!fs.existsSync(file)) { console.warn(`  ! missing ${file}`); continue; }
    out[sym] = parseCSV(fs.readFileSync(file, 'utf8')).filter(b => b.t >= start && b.t <= end);
  }
  return out;
}

async function loadBars(a, symbols, start, end) {
  if (a.source === 'alpaca') return fromAlpaca(symbols, start, end);
  if (a.source === 'stooq') return fromStooq(symbols, start, end);
  if (a.source === 'yahoo') return fromYahoo(symbols, start, end);
  if (a.source.startsWith('csv=')) return fromCSV(path.resolve(a.source.slice(4)), symbols, start, end);
  throw new Error('Unknown --source ' + a.source);
}

// ---------------------------------------------------------------- diagnostics
// Automatic red flags, so the agents (and you) don't have to eyeball every number.
function diagnose(key, real, legacy, bench) {
  const flags = [];
  const s = engine.BACKTEST_STRATEGIES[key];
  if (real.totalTrades < 30) flags.push({ sev: 'medium', msg: `only ${real.totalTrades} trades: too few to trust the statistics` });
  if (real.profitFactor < 1) flags.push({ sev: 'high', msg: `profit factor ${real.profitFactor} < 1: loses money after costs` });
  if (real.sharpe < 0.5) flags.push({ sev: real.sharpe < 0 ? 'high' : 'medium', msg: `Sharpe ${real.sharpe} (< 0.5)` });
  if (real.maxDrawdown > 20) flags.push({ sev: 'high', msg: `max drawdown ${real.maxDrawdown}% (> 20%)` });
  if (bench && real.annReturn < bench.annReturn) flags.push({ sev: 'medium', msg: `CAGR ${real.annReturn}% below buy-and-hold ${bench.annReturn}%` });
  const gaps = real.closedTrades.filter(t => t.exit_reason === 'stop_loss_gap');
  if (gaps.length) {
    const worst = Math.min(...gaps.map(t => t.ret_pct));
    flags.push({ sev: worst < -2 * s.sl * 100 ? 'high' : 'medium', msg: `${gaps.length} stops gapped through (worst ${worst.toFixed(1)}% vs stop -${s.sl * 100}%)` });
  }
  if (legacy) {
    const d = +(legacy.totalReturn - real.totalReturn).toFixed(2);
    if (Math.abs(d) > 5) flags.push({ sev: 'medium', msg: `legacy engine ${d > 0 ? 'overstates' : 'understates'} return by ${Math.abs(d)} pts (close-only stops, no costs)` });
  }
  const shorts = real.closedTrades.filter(t => t.side === 'short');
  if (shorts.length >= 10) {
    const pnl = shorts.reduce((x, t) => x + t.pnl, 0);
    if (pnl < 0) flags.push({ sev: 'medium', msg: `short side loses money (${shorts.length} trades, P&L ${pnl.toFixed(0)})` });
  }
  return flags;
}

const pick = (m) => m && ({ totalReturn: m.totalReturn, annReturn: m.annReturn, maxDrawdown: m.maxDrawdown, sharpe: m.sharpe,
  winRate: m.winRate, profitFactor: m.profitFactor, totalTrades: m.totalTrades, finalEquity: m.finalEquity });

function exitMix(trades) {
  const mix = {};
  for (const t of trades) mix[t.exit_reason] = (mix[t.exit_reason] || 0) + 1;
  return mix;
}

// ---------------------------------------------------------------- main
(async () => {
  const a = parseArgs(process.argv.slice(2));
  const maxWarm = Math.max(...a.strategyKeys.map(k => engine.warmupDays(engine.BACKTEST_STRATEGIES[k])));
  const fetchStart = new Date(Date.parse(a.start) - maxWarm * 86400000).toISOString().slice(0, 10);
  const symbols = [...new Set([...a.symbols, a.benchmark])];
  console.log(`Backtest ${a.start} → ${a.end} | ${a.symbols.length} symbols | source ${a.source} | strategies ${a.strategyKeys.join(',')}`);
  const bars = await loadBars(a, symbols, fetchStart, a.end);
  const got = Object.keys(bars).filter(s => bars[s].length > 50);
  if (!got.length) throw new Error('No price data downloaded — check the data source / keys / network.');
  const tradable = a.symbols.filter(s => got.includes(s));
  const benchBars = bars[a.benchmark];
  const legacyBars = Object.fromEntries(tradable.map(s => [s, bars[s].filter(b => b.t >= a.start)]));
  const costs = { slippageBps: a.slippageBps, commissionBps: a.commissionBps, borrowBpsYear: a.borrowBpsYear };
  const bench = benchBars ? engine.buyAndHold(benchBars, a.capital, a.rf, a.start) : null;

  const rows = [];
  for (const key of a.strategyKeys) {
    const real = a.mode !== 'legacy' ? engine.simulate(key, tradable, bars, { mode: 'realistic', initialCapital: a.capital, riskFreeRate: a.rf, start: a.start, costs, longOnly: a.longOnly }) : null;
    const legacy = a.mode !== 'realistic' ? engine.simulate(key, tradable, legacyBars, { mode: 'legacy', initialCapital: a.capital, riskFreeRate: a.rf }) : null;
    const main = real || legacy;
    const label = `${key}${a.longOnly ? ' long-only' : ''}`;
    rows.push({ key, name: engine.BACKTEST_STRATEGIES[key].name,
      realistic: real && { strategy: label, ...pick(real) }, legacy: legacy && { strategy: `${label} (legacy)`, ...pick(legacy) },
      exits: exitMix(main.closedTrades), flags: diagnose(key, main, real ? legacy : null, bench) });
    console.log(`  ${key.padEnd(9)} return ${String(main.totalReturn).padStart(7)}%  CAGR ${String(main.annReturn).padStart(6)}%  DD ${String(main.maxDrawdown).padStart(5)}%  Sharpe ${String(main.sharpe).padStart(6)}  trades ${main.totalTrades}`);
  }
  rows.sort((x, y) => ((y.realistic || y.legacy).sharpe - (x.realistic || x.legacy).sharpe));

  const stamp = new Date().toISOString().slice(0, 10);
  fs.mkdirSync(a.out, { recursive: true });
  const report = { generated_at: new Date().toISOString(), period: { start: a.start, end: a.end }, source: a.source, longOnly: !!a.longOnly, symbols: tradable,
    missing: a.symbols.filter(s => !tradable.includes(s)), costs, capital: a.capital, benchmark: { symbol: a.benchmark, ...pick(bench) },
    note: 'Historical simulation, not live results. Universe chosen today (survivorship bias).', strategies: rows };
  const suffix = a.longOnly ? '-long-only' : '';
  const jsonPath = path.join(a.out, `backtest-${stamp}${suffix}.json`);
  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 1));

  const f = (v, s = '') => (v == null ? '—' : `${v}${s}`);
  const md = [
    `# Backtest — ${stamp}`, '',
    `Period **${a.start} → ${a.end}** · ${tradable.length} symbols · data: ${a.source} · capital $${a.capital}${a.longOnly ? ' · LONG ONLY' : ''}`,
    `Costs (realistic mode): slippage ${a.slippageBps} bps/side, commission ${a.commissionBps} bps, short borrow ${a.borrowBpsYear} bps/yr.`,
    bench ? `Benchmark buy-and-hold ${a.benchmark}: return ${bench.totalReturn}%, CAGR ${bench.annReturn}%, max DD ${bench.maxDrawdown}%, Sharpe ${bench.sharpe}.` : '',
    '', '> Historical simulation, not live results. The universe is chosen today (survivorship bias).', '',
    '| Strategy | Return | CAGR | Max DD | Sharpe | Win | PF | Trades | Legacy return |',
    '|---|---|---|---|---|---|---|---|---|',
    ...rows.map(r => { const m = r.realistic || r.legacy; return `| ${r.name} (${r.key}) | ${f(m.totalReturn, '%')} | ${f(m.annReturn, '%')} | ${f(m.maxDrawdown, '%')} | ${f(m.sharpe)} | ${f(m.winRate, '%')} | ${f(m.profitFactor)} | ${m.totalTrades} | ${r.legacy && r.realistic ? f(r.legacy.totalReturn, '%') : '—'} |`; }),
    '', '## Red flags', '',
    ...rows.flatMap(r => r.flags.length ? [`**${r.key}**`, ...r.flags.map(x => `- [${x.sev.toUpperCase()}] ${x.msg}`), ''] : []),
    '## Exit mix (realistic)', '',
    ...rows.map(r => `- ${r.key}: ${Object.entries(r.exits).map(([k, v]) => `${k} ${v}`).join(', ')}`),
    report.missing.length ? `\nMissing data for: ${report.missing.join(', ')}` : '',
  ].join('\n');
  const mdPath = path.join(a.out, `backtest-${stamp}${suffix}.md`);
  fs.writeFileSync(mdPath, md + '\n');
  console.log(`\nReport: ${path.relative(ROOT, mdPath)} (+ .json)`);
})().catch(e => { console.error('Backtest failed:', e.message); process.exit(1); });
