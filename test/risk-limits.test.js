'use strict';
// Unit tests for the account-level limits in server.js (risk register L5 gross exposure, L7 drawdown from peak).
// Run: node test/risk-limits.test.js
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
const block = src.slice(src.indexOf('// ─── Account-level limits (risk register L5/L7)'), src.indexOf('// ─── Broker-side protection (risk register L1/L2)'));
assert.ok(block.includes('function grossExposureRoom') && block.includes('function equityDrawdown'), 'limit helpers not found in server.js');

function load(maxGross, AT = {}) {
  // eslint-disable-next-line no-new-func
  return { AT, ...new Function('AT', 'MAX_GROSS_EXPOSURE', `${block}\nreturn { grossExposureRoom, equityDrawdown };`)(AT, maxGross) };
}

// L5 — gross exposure room
{
  const { grossExposureRoom } = load(1);
  const pos = [{ market_value: '40000' }, { market_value: '-25000' }];         // long 40k + short 25k = 65k gross
  assert.strictEqual(grossExposureRoom(pos, 100000), 35000);
  assert.strictEqual(grossExposureRoom([{ market_value: '120000' }], 100000), 0, 'already over the cap: no room, never negative');
  assert.strictEqual(grossExposureRoom([], 50000), 50000);
  assert.strictEqual(load(1.5).grossExposureRoom(pos, 100000), 85000, 'cap configurable via NEXUS_MAX_GROSS_EXPOSURE');
  console.log('✓ L5: new positions limited to equity × MAX_GROSS_EXPOSURE (no margin by default)');
}

// L7 — drawdown from the high-water mark
{
  const { AT, equityDrawdown } = load(1, {});
  assert.strictEqual(equityDrawdown(100000), 0);                    // start
  assert.strictEqual(equityDrawdown(120000), 0);                    // new peak
  const dd = equityDrawdown(102000);                                // +2% vs start, but −15% from the peak
  assert.ok(Math.abs(dd - 0.15) < 1e-9, `expected 15% from peak, got ${dd}`);
  assert.strictEqual(AT.peakEquity, 120000);
  assert.strictEqual(AT.sessionStartEquity, 100000, 'start equity kept for compatibility');
  // the old formula would have reported −2% (a gain): the halt would never have fired
  assert.ok((AT.sessionStartEquity - 102000) / AT.sessionStartEquity < 0);
  // peak restored from saved state survives a restart
  const r = load(1, { sessionStartEquity: 100000, peakEquity: 130000 });
  assert.ok(Math.abs(r.equityDrawdown(110500) - 0.15) < 1e-9);
  console.log('✓ L7: drawdown measured from the persisted peak');
}
console.log('all checks passed');
