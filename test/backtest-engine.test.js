'use strict';
// Checks that lib/backtest/engine.js (legacy mode) reproduces the original server.js engine bit for bit,
// and that the realistic mode behaves sanely. Run: node test/backtest-engine.test.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const engine = require('../lib/backtest/engine');

// Deterministic synthetic market: random walks with drift, gaps and volume.
function rng(seed) { return () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }; }
function makeBars(seed, n = 600, start = '2021-01-04') {
  const r = rng(seed); const out = []; let p = 50 + r() * 200; let d = new Date(start + 'T00:00:00Z');
  for (let i = 0; i < n; i++) {
    while ([0, 6].includes(d.getUTCDay())) d = new Date(d.getTime() + 86400000);
    const gap = (r() - 0.5) * 0.03, o = p * (1 + gap), c = o * (1 + (r() - 0.48) * 0.05);
    const h = Math.max(o, c) * (1 + r() * 0.02), l = Math.min(o, c) * (1 - r() * 0.02);
    out.push({ t: d.toISOString().slice(0, 10), o: +o.toFixed(2), h: +h.toFixed(2), l: +l.toFixed(2), c: +c.toFixed(2), v: Math.round(1e6 * (0.5 + r())) });
    p = c; d = new Date(d.getTime() + 86400000);
  }
  return out;
}
const symbols = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF'];
const allBars = Object.fromEntries(symbols.map((s, i) => [s, makeBars(i + 1)]));

// Pull the ORIGINAL engine out of the server.js committed before the refactor, if available.
function originalEngine() {
  const src = process.env.ORIGINAL_SERVER && fs.existsSync(process.env.ORIGINAL_SERVER) ? fs.readFileSync(process.env.ORIGINAL_SERVER, 'utf8') : null;
  if (!src) return null;
  const grab = (a, b) => src.slice(src.indexOf(a), src.indexOf(b));
  const helpers = grab('function computeRSI(closes, period = 14)', 'function computeMACD(closes)')
    + grab('function computeEMASeries(closes, period)', '// ─── BACKTEST ENGINE');
  const strategies = grab('const BACKTEST_STRATEGIES = {', 'const sleep = ms');
  const loop = grab('    const dateSet = new Set();', "    const ins = db.prepare('INSERT INTO backtest_trades");
  // eslint-disable-next-line no-new-func
  return new Function('allBars', 'symbols', 'personality', 'initial_capital', 'riskFreeRate',
    `${helpers}\n${strategies}\nconst strat = BACKTEST_STRATEGIES[personality]; const row = { initial_capital }; const btId = null;\n${loop}\nreturn { results, closedTrades };`);
}

const orig = originalEngine();
for (const key of Object.keys(engine.BACKTEST_STRATEGIES)) {
  const legacy = engine.simulate(key, symbols, allBars, { mode: 'legacy', initialCapital: 10000, riskFreeRate: 0.043 });
  if (orig) {
    const o = orig(allBars, symbols, key, 10000, 0.043);
    const { equityCurve: e1, ...m1 } = o.results;
    const { equityCurve: e2, closedTrades, ...m2 } = legacy;
    assert.deepStrictEqual(m2, m1, `${key}: metrics differ from original server.js`);
    assert.deepStrictEqual(e2, e1, `${key}: equity curve differs`);
    assert.strictEqual(closedTrades.length, o.closedTrades.length, `${key}: trade count differs`);
  }
  const real = engine.simulate(key, symbols, allBars, { mode: 'realistic', initialCapital: 10000, riskFreeRate: 0.043, start: allBars.AAA[260].t });
  assert.ok(Number.isFinite(real.finalEquity) && real.finalEquity > 0, `${key}: realistic equity invalid`);
  // realistic stops can never lose more than the stop + slippage unless the bar gapped through it
  const strat = engine.BACKTEST_STRATEGIES[key];
  for (const t of real.closedTrades.filter(t => t.exit_reason === 'stop_loss')) {
    assert.ok(t.ret_pct >= -(strat.sl * 100) - 0.5, `${key}: stop_loss trade lost ${t.ret_pct.toFixed(2)}% (> sl ${strat.sl * 100}%)`);
  }
  console.log(`${key.padEnd(9)} legacy ${orig ? '== original ✓' : '(original not given)'}  trades legacy/realistic ${legacy.totalTrades}/${real.totalTrades}  return ${legacy.totalReturn}% / ${real.totalReturn}%`);
}
console.log('all checks passed');
