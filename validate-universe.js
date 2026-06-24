/**
 * validate-universe.js
 *
 * Checks every symbol in STOCK_UNIVERSE against the Alpaca /v2/assets API.
 * Removes symbols that are inactive, not tradeable, or unknown.
 * Patches server.js in-place with the cleaned list.
 *
 * Usage:
 *   node validate-universe.js           # dry-run, prints results only
 *   node validate-universe.js --patch   # also rewrites server.js
 */

require('dotenv').config();

const fs   = require('fs');
const path = require('path');

const ALPACA_BASE_URL    = process.env.ALPACA_BASE_URL    || 'https://paper-api.alpaca.markets';
const ALPACA_API_KEY     = process.env.ALPACA_API_KEY     || '';
const ALPACA_SECRET_KEY  = process.env.ALPACA_SECRET_KEY  || '';
const PATCH              = process.argv.includes('--patch');
const CONCURRENCY        = 10;   // parallel requests

if (!ALPACA_API_KEY || !ALPACA_SECRET_KEY) {
  console.error('❌  ALPACA_API_KEY / ALPACA_SECRET_KEY missing in .env');
  process.exit(1);
}

// ── Parse STOCK_UNIVERSE out of server.js ────────────────────────────────────
const serverPath = path.join(__dirname, 'server.js');
const serverSrc  = fs.readFileSync(serverPath, 'utf8');

const universeMatch = serverSrc.match(/const STOCK_UNIVERSE = \[([\s\S]*?)\];/);
if (!universeMatch) {
  console.error('❌  Could not find STOCK_UNIVERSE in server.js');
  process.exit(1);
}

const STOCK_UNIVERSE = (universeMatch[1].match(/'([A-Z][A-Z0-9.]*)'/g) || [])
  .map(s => s.replace(/'/g, ''));

console.log(`\n📋 Universe loaded: ${STOCK_UNIVERSE.length} symbols\n`);

// ── Alpaca asset check ────────────────────────────────────────────────────────
const headers = {
  'APCA-API-KEY-ID':     ALPACA_API_KEY,
  'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY,
};

async function checkSymbol(symbol) {
  try {
    const res  = await fetch(`${ALPACA_BASE_URL}/v2/assets/${encodeURIComponent(symbol)}`, { headers });
    if (res.status === 404) return { symbol, ok: false, reason: 'not found' };
    const data = await res.json();
    if (!data || data.status !== 'active')  return { symbol, ok: false, reason: `status=${data?.status}` };
    if (!data.tradable)                     return { symbol, ok: false, reason: 'not tradeable' };
    if (data.easy_to_borrow === false && data.shortable === false) {
      // Still ok for longs, just note it
      return { symbol, ok: true, reason: 'long-only (not shortable/ETB)' };
    }
    return { symbol, ok: true, reason: '' };
  } catch (e) {
    return { symbol, ok: false, reason: `error: ${e.message}` };
  }
}

async function runPool(items, fn, concurrency) {
  const results = [];
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const item = items[i++];
      results.push(await fn(item));
      process.stdout.write(`\r  Checked ${results.length}/${items.length}…`);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, worker));
  process.stdout.write('\n');
  return results;
}

(async () => {
  console.log(`🔍 Querying Alpaca (${CONCURRENCY} parallel)…`);
  const results = await runPool(STOCK_UNIVERSE, checkSymbol, CONCURRENCY);

  const ok      = results.filter(r => r.ok);
  const bad     = results.filter(r => !r.ok);
  const longOnly = ok.filter(r => r.reason.includes('long-only'));

  console.log(`\n✅ Tradeable:    ${ok.length}`);
  console.log(`❌ Removed:      ${bad.length}`);
  if (longOnly.length) console.log(`⚠️  Long-only:   ${longOnly.length} (shortable=false, kept)`);

  if (bad.length) {
    console.log('\n❌ Symbols to remove:');
    bad.forEach(r => console.log(`   ${r.symbol.padEnd(8)} — ${r.reason}`));
  }

  if (longOnly.length) {
    console.log('\n⚠️  Long-only (not shortable on IEX):');
    longOnly.forEach(r => console.log(`   ${r.symbol}`));
  }

  const cleanSymbols = ok.map(r => r.symbol);
  console.log(`\n📦 Clean universe: ${cleanSymbols.length} symbols`);

  if (!PATCH) {
    console.log('\nRun with --patch to update server.js automatically.\n');
    return;
  }

  // ── Patch server.js ─────────────────────────────────────────────────────────
  // Rebuild the STOCK_UNIVERSE block preserving grouped comments where possible
  const sectorGroups = {
    'Mega-cap tech':            ['AAPL','MSFT','NVDA','GOOGL','AMZN','META','TSLA','AVGO','ORCL','AMD','CRM','INTU','NOW','ADBE','PANW','FTNT','KLAC','LRCX','AMAT','MU','QCOM','TXN','ADI','MCHP','ON','NXPI','INTC','IBM'],
    'Financials':               ['JPM','BAC','GS','MS','BLK','AXP','V','MA','PYPL','SCHW','C','WFC','USB','COF','ICE','CME','SPGI','MCO','CB','PGR','MET','PRU'],
    'Healthcare & pharma':      ['UNH','JNJ','LLY','PFE','ABBV','MRK','CVS','AMGN','GILD','ISRG','TMO','DHR','SYK','MDT','VRTX','REGN','BIIB','BMY','ALNY','DXCM','EW'],
    'Energy':                   ['XOM','CVX','COP','SLB','HAL','MPC','VLO','OXY','PSX','DVN'],
    'Industrials & Defense':    ['LMT','RTX','CAT','HON','GE','BA','UPS','MMM','EMR','NOC','GD','LDOS','SAIC'],
    'Consumer':                 ['WMT','COST','HD','TGT','NKE','SBUX','MCD','PG','KO','PEP','LOW','TJX','ROST','CL','PM','STZ','HSY','EL','YUM','CMG'],
    'Materials':                ['LIN','FCX','NEM','AA','CLF','NUE','ALB'],
    'Utilities':                ['NEE','DUK','SO','D','AEP','EXC'],
    'REITs':                    ['SPG','PLD','AMT','EQIX','O','VICI','CCI'],
    'Broad & sector ETFs':      ['SPY','QQQ','IWM','DIA','XLK','XLF','XLE','XLV','XLI','XLB','XLC','XLU','XLP','XLRE','GLD','SLV','TLT','HYG','LQD'],
    'Commodities ETFs':         ['GDX','GDXJ','USO','UNG'],
    'Leveraged ETFs':           ['TQQQ','SQQQ','UPRO','SPXU','SOXL','SOXS','UVXY','LABU','LABD'],
    'Growth / high-momentum':   ['PLTR','COIN','CRWD','NET','DDOG','SNOW','ZS','MSTR','RBLX','HOOD','UBER','LYFT','ABNB','DASH','DKNG','RDDT','SNAP','PINS'],
    'Crypto-adjacent':          ['MARA','RIOT','CLSK','BTBT','HUT','CIFR'],
    'AI & Quantum':             ['IONQ','RGTI','QUBT','SOUN','AI','PATH','BBAI','ARQQ'],
    'Fintech':                  ['SQ','AFRM','SOFI','UPST','NU','SMAR','RELY'],
    'SaaS & cloud':             ['SHOP','HUBS','BILL','GTLB','MNDY','BRZE','APP','WDAY','OKTA','MDB','VEEV','SPLK','COUR','U','ASAN','DOCN','ESTC','CFLT'],
    'Semiconductors mid-cap':   ['SMCI','AMBA','CRUS','LSCC','WOLF','MPWR','FORM','SWKS'],
    'Biotech':                  ['MRNA','BNTX','RXRX','BEAM','EDIT','NTLA','HIMS','TDOC','NVAX','SRPT','CRSP','ILMN','PACB','FATE'],
    'Clean energy & EV':        ['FSLR','ENPH','PLUG','RIVN','LCID','QS','BE','RUN','CHPT','NIO','XPEV','LI'],
    'Space & defense innovation':['RKLB','ASTS','PL','LUNR','JOBY','ACHR'],
    'Media & streaming':        ['NFLX','DIS','PARA','WBD','SPOT','ROKU','TTD'],
    'International ADRs':       ['TSM','BABA','BIDU','JD','PDD','SE','MELI','GRAB','CPNG','CHWY','ETSY','W'],
    'Consumer tech & mobility': ['MTCH','ZG','IAC'],
  };

  const cleanSet = new Set(cleanSymbols);
  let block = '// Covers mega-cap anchors + mid/small-cap growth. Supplemented each cycle by live market movers.\n';
  block += 'const STOCK_UNIVERSE = [\n';
  for (const [label, syms] of Object.entries(sectorGroups)) {
    const kept = syms.filter(s => cleanSet.has(s));
    if (!kept.length) continue;
    block += `  // ── ${label} ${'─'.repeat(Math.max(0, 65 - label.length))}\n`;
    block += `  ${kept.map(s => `'${s}'`).join(',')},\n`;
  }
  // Any symbols not in sector groups (came from dynamic movers, manually added)
  const grouped = new Set(Object.values(sectorGroups).flat());
  const extra = cleanSymbols.filter(s => !grouped.has(s));
  if (extra.length) {
    block += `  // ── Other (validated)\n  ${extra.map(s => `'${s}'`).join(',')},\n`;
  }
  block += '];';

  const patched = serverSrc.replace(/\/\/ Covers mega-cap anchors[\s\S]*?const STOCK_UNIVERSE = \[[\s\S]*?\];/, block);
  if (patched === serverSrc) {
    console.error('❌  Patch failed — regex did not match. Check server.js manually.');
    process.exit(1);
  }

  fs.writeFileSync(serverPath, patched, 'utf8');
  console.log(`\n✅ server.js patched — ${cleanSymbols.length} tradeable symbols written.\n`);
})();
