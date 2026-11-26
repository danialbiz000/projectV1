'use strict';
// Unit tests for the broker-side protection helpers in server.js (risk register L1/L2).
// The helpers are extracted from server.js and run against a fake Alpaca. Run: node test/broker-protection.test.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const block = src.slice(src.indexOf('// ─── Broker-side protection (risk register L1/L2)'), src.indexOf('async function reviewDrawdownPositions('));
assert.ok(block.length > 500, 'protection helpers not found in server.js');

function makeEnv({ orders = [], positions = [], rejectBracketWith = null, paper = true, live = false } = {}) {
  const calls = [], logs = [], submitted = [];
  const resp = (status, body) => ({ ok: status < 300, status, text: async () => (body == null ? '' : JSON.stringify(body)) });
  const alpacaFetch = async (p, opt = {}) => {
    const method = opt.method || 'GET';
    calls.push({ method, path: p, body: opt.body ? JSON.parse(opt.body) : undefined });
    if (method === 'GET' && p.startsWith('/v2/orders')) {
      const m = /symbols=([^&]+)/.exec(p);
      return resp(200, m ? orders.filter(o => o.symbol === decodeURIComponent(m[1])) : orders);
    }
    if (method === 'GET' && p === '/v2/positions') return resp(200, positions);
    if (method === 'DELETE') return resp(204, null);
    if (method === 'POST') return resp(200, { id: 'new' });
    return resp(404, {});
  };
  const parseJsonResponse = async (r) => { const t = await r.text(); return t ? JSON.parse(t) : null; };
  const submitValidatedOrder = async (b) => {
    submitted.push(b);
    if (rejectBracketWith && b.order_class === 'bracket') { const e = new Error('rejected'); e.status = rejectBracketWith; throw e; }
    return { id: 'ord-' + submitted.length };
  };
  const atLog = (e) => logs.push(e);
  // eslint-disable-next-line no-new-func
  const api = new Function('alpacaFetch', 'parseJsonResponse', 'submitValidatedOrder', 'atLog', 'MAX_HARD_STOP_PCT', 'PAPER_MODE', 'LIVE_TRADING_ENABLED',
    `${block}\nreturn { hardStopPct, hardStopPrice, cancelOpenOrdersFor, ensureProtectiveStops, protectOpenPositions, submitEntryWithStop };`)(
    alpacaFetch, parseJsonResponse, submitValidatedOrder, atLog, 15, paper, live);
  return { api, calls, logs, submitted };
}

(async () => {
  // L2: hard stop capped at 15%
  const { api } = makeEnv();
  assert.strictEqual(api.hardStopPct(5), 11);
  assert.strictEqual(api.hardStopPct(25), 15, '2.2 × 25% must be capped at 15%');
  assert.strictEqual(api.hardStopPrice('long', 100, 5), 89);
  assert.strictEqual(api.hardStopPrice('short', 100, 5), 111);
  assert.strictEqual(api.hardStopPrice('long', 100, 25), 85);
  console.log('✓ hard stop level capped (L2)');

  // L1: ensureProtectiveStops
  const orders = [
    { id: 'tp-aapl', symbol: 'AAPL', side: 'sell', type: 'limit', limit_price: '120' },
    { id: 'st-msft', symbol: 'MSFT', side: 'sell', type: 'stop', stop_price: '300' },
    { id: 'tp-msft', symbol: 'MSFT', side: 'sell', type: 'limit', limit_price: '450' },
  ];
  const positions = [
    { symbol: 'AAPL', side: 'long', qty: '10', avg_entry_price: '100', current_price: '98' },   // TP only → OCO
    { symbol: 'MSFT', side: 'long', qty: '5', avg_entry_price: '350', current_price: '360' },  // already protected
    { symbol: 'TSLA', side: 'short', qty: '-5', avg_entry_price: '200', current_price: '190' }, // nothing → buy stop
    { symbol: 'NVDA', side: 'long', qty: '3', avg_entry_price: '100', current_price: '80' },   // already below −15%
    { symbol: 'FRAC', side: 'long', qty: '0.5', avg_entry_price: '10', current_price: '10' },  // fractional → skip
  ];
  const env = makeEnv({ orders, positions });
  const added = await env.api.protectOpenPositions();
  const posts = env.calls.filter(c => c.method === 'POST').map(c => c.body);
  const by = (s) => posts.find(b => b.symbol === s);
  assert.strictEqual(added, 3, 'three positions should get a stop');
  assert.ok(env.calls.some(c => c.method === 'DELETE' && c.path === '/v2/orders/tp-aapl'), 'AAPL TP cancelled before OCO');
  assert.deepStrictEqual({ oc: by('AAPL').order_class, tp: by('AAPL').take_profit.limit_price, st: by('AAPL').stop_loss.stop_price, tif: by('AAPL').time_in_force },
    { oc: 'oco', tp: 120, st: 85, tif: 'gtc' });
  assert.ok(!by('MSFT'), 'MSFT already has a stop: untouched');
  assert.ok(!env.calls.some(c => c.method === 'DELETE' && c.path.includes('msft')), 'MSFT orders not cancelled');
  assert.deepStrictEqual({ side: by('TSLA').side, type: by('TSLA').type, stop: by('TSLA').stop_price }, { side: 'buy', type: 'stop', stop: 230 });
  assert.strictEqual(by('NVDA').stop_price, 78.4, 'price already beyond −15%: stop just below the market');
  assert.ok(!by('FRAC'), 'fractional position skipped');
  console.log('✓ protective stops added where missing, existing ones untouched (L1)');

  // live account without NEXUS_ENABLE_LIVE_TRADING: no writes at all
  const gated = makeEnv({ orders, positions, paper: false, live: false });
  assert.strictEqual(await gated.api.protectOpenPositions(), 0);
  assert.ok(!gated.calls.some(c => c.method !== 'GET'), 'no POST/DELETE on a gated live account');
  console.log('✓ respects the live-trading gate');

  // cancelOpenOrdersFor only touches that symbol
  const env2 = makeEnv({ orders });
  assert.strictEqual(await env2.api.cancelOpenOrdersFor('MSFT'), 2);
  assert.deepStrictEqual(env2.calls.filter(c => c.method === 'DELETE').map(c => c.path), ['/v2/orders/st-msft', '/v2/orders/tp-msft']);
  console.log('✓ cancelOpenOrdersFor cancels only the given symbol');

  // submitEntryWithStop: bracket first, TP-only fallback on 4xx, never on 403 (live gate) or 5xx
  const ok = makeEnv();
  await ok.api.submitEntryWithStop({ symbol: 'X', order_class: 'bracket' }, { symbol: 'X', order_class: 'oto' });
  assert.deepStrictEqual(ok.submitted.map(b => b.order_class), ['bracket']);
  const fb = makeEnv({ rejectBracketWith: 422 });
  await fb.api.submitEntryWithStop({ symbol: 'X', order_class: 'bracket' }, { symbol: 'X', order_class: 'oto' });
  assert.deepStrictEqual(fb.submitted.map(b => b.order_class), ['bracket', 'oto']);
  assert.ok(fb.logs.some(l => l.action === 'WARN'), 'fallback is logged');
  for (const status of [403, 500]) {
    const no = makeEnv({ rejectBracketWith: status });
    await assert.rejects(no.api.submitEntryWithStop({ symbol: 'X', order_class: 'bracket' }, { symbol: 'X', order_class: 'oto' }));
    assert.strictEqual(no.submitted.length, 1, `no fallback on ${status}`);
  }
  console.log('✓ entries use a bracket stop, with a logged TP-only fallback');
  console.log('all checks passed');
})().catch(e => { console.error(e); process.exit(1); });
