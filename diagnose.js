/**
 * diagnose.js — AutoTrader diagnostic & stress test
 * Run: node diagnose.js
 */
require('dotenv').config();

const BASE = `http://localhost:${process.env.PORT || 3000}`;
const ADMIN_TOKEN = process.env.NEXUS_ADMIN_TOKEN || '';

let sessionToken = '';

async function getSession() {
  const res = await fetch(`${BASE}/api/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Origin': `http://localhost:${process.env.PORT || 3000}` },
    body: JSON.stringify({ token: ADMIN_TOKEN }),
  });
  const d = await res.json();
  if (!d.sessionToken) throw new Error('Auth failed: ' + JSON.stringify(d));
  sessionToken = d.sessionToken;
  console.log('✅ Auth OK — paper:', d.paperMode, '| Telegram:', d.telegramConfigured, '| Alpaca:', d.alpacaConfigured);
  return d;
}

function auth() {
  return {
    'Authorization': `Bearer ${sessionToken}`,
    'Content-Type': 'application/json',
    'Origin': `http://localhost:${process.env.PORT || 3000}`,
  };
}

async function checkMarketHours() {
  function getNth(year, month, dow, nth) {
    const d = new Date(Date.UTC(year, month, 1));
    let c = 0;
    while (true) { if (d.getUTCDay() === dow) { c++; if (c === nth) return d.getTime(); } d.setUTCDate(d.getUTCDate() + 1); }
  }
  const now = new Date();
  const utcMs = now.getTime();
  const y = now.getUTCFullYear();
  const dstStart = getNth(y, 2, 0, 2);
  const dstEnd = getNth(y, 10, 0, 1);
  const isDST = utcMs >= dstStart && utcMs < dstEnd;
  const et = new Date(utcMs + (isDST ? -4 : -5) * 3600000);
  const day = et.getUTCDay();
  const mins = et.getUTCHours() * 60 + et.getUTCMinutes();
  const open = day !== 0 && day !== 6 && mins >= 570 && mins < 960;
  const days = ['Dom','Lun','Mar','Mer','Gio','Ven','Sab'];
  console.log(`\n🕐 Ora ET: ${String(et.getUTCHours()).padStart(2,'0')}:${String(et.getUTCMinutes()).padStart(2,'0')} ${days[day]}`);
  console.log(`📈 Mercato NYSE: ${open ? '✅ APERTO' : '❌ CHIUSO (AT skipperà il ciclo)'}`);
  return open;
}

async function getStatus() {
  const res = await fetch(`${BASE}/api/autotrader/status`, { headers: auth() });
  const d = await res.json();
  console.log('\n📊 STATUS AUTOTRADER:');
  console.log(`   Abilitato: ${d.enabled ? '✅ SI' : '❌ NO — ATTIVALO DAL PANNELLO!'}`);
  console.log(`   Halted: ${d.halted ? '🚨 SI — ' + d.haltReason : '✅ no'}`);
  console.log(`   Soglia confidenza: ${d.confidenceThreshold} (AI deve superare questo valore per tradare)`);
  console.log(`   Intervallo: ogni ${Math.round(d.intervalMs / 60000)} minuti`);
  console.log(`   Trades oggi: ${d.todayTradesCount}/${d.maxDailyTrades}`);
  console.log(`   Posizioni aperte: ${d.openPositionsCount}/${d.maxPositions}`);
  console.log(`   Buying power: $${parseFloat(d.buyingPower || 0).toFixed(2)}`);
  console.log(`   Ultima run: ${d.lastRunAt ? new Date(d.lastRunAt).toLocaleTimeString('it-IT') : 'mai'}`);
  console.log(`   Prossima run: ${d.nextRunAt ? new Date(d.nextRunAt).toLocaleTimeString('it-IT') : '—'}`);
  console.log(`   Watchlist: ${(d.watchlist || []).join(', ')}`);

  if (d.log && d.log.length) {
    console.log('\n📋 ULTIMI LOG AI:');
    d.log.slice(0, 10).forEach(e => {
      const t = new Date(e.ts).toLocaleTimeString('it-IT');
      const exec = e.executed ? `✅ ESEGUITO: ${e.executedAction}` : '— non eseguito';
      const conf = e.confidence > 0 ? ` [${(e.confidence * 100).toFixed(0)}%]` : '';
      console.log(`   [${t}] ${e.symbol.padEnd(6)} ${e.action.padEnd(6)}${conf} ${exec}`);
      if (e.reasoning && e.reasoning.length > 10) {
        console.log(`           → ${e.reasoning.slice(0, 120)}${e.reasoning.length > 120 ? '…' : ''}`);
      }
    });
  } else {
    console.log('\n⚠️  Nessun log — l\'AT non ha ancora girato. Forzo un ciclo ora...');
  }
  return d;
}

async function runNow() {
  console.log('\n🚀 Avvio ciclo di ricerca immediato...');
  const res = await fetch(`${BASE}/api/autotrader/run-now`, { method: 'POST', headers: auth() });
  const d = await res.json();
  if (d.ok) {
    console.log('   Ciclo avviato. Attendo 45 secondi per i risultati...');
    await new Promise(r => setTimeout(r, 45000));
    const status = await fetch(`${BASE}/api/autotrader/status`, { headers: auth() });
    const s = await status.json();
    console.log('\n📋 LOG DOPO IL CICLO:');
    if (s.log && s.log.length) {
      s.log.slice(0, 15).forEach(e => {
        const t = new Date(e.ts).toLocaleTimeString('it-IT');
        const exec = e.executed ? `✅ ESEGUITO: ${e.executedAction}` : '';
        const conf = e.confidence > 0 ? ` [${(e.confidence * 100).toFixed(0)}% conf]` : '';
        console.log(`   [${t}] ${e.symbol.padEnd(6)} ${(e.action || '').padEnd(6)}${conf} ${exec}`);
        if (e.reasoning) console.log(`           → ${e.reasoning.slice(0, 130)}${e.reasoning.length > 130 ? '…' : ''}`);
      });
    }
    const trades = s.todayTradesCount;
    if (trades > 0) {
      console.log(`\n✅ TRADES ESEGUITI OGGI: ${trades}`);
    } else {
      console.log('\n💡 NESSUN TRADE ESEGUITO — motivazioni probabili:');
      console.log(`   1. Confidence AI < soglia ${s.confidenceThreshold} per tutti i simboli`);
      console.log(`      → Prova ad abbassare la soglia a 0.60 dal pannello`);
      console.log('   2. L\'AI vede il mercato neutro/ribassista e preferisce HOLD');
      console.log('   3. Posizioni già aperte per i simboli della watchlist');
      console.log('   4. Buying power insufficiente (< $100)');
    }
  } else {
    console.log('   ❌ Errore:', d.error, '— Verifica che l\'AT sia abilitato dal pannello');
  }
}

async function checkAccount() {
  console.log('\n💰 ACCOUNT ALPACA:');
  try {
    const res = await fetch(`${BASE}/api/alpaca/account`, { headers: auth() });
    const a = await res.json();
    console.log(`   Equity: $${parseFloat(a.equity || 0).toFixed(2)}`);
    console.log(`   Cash: $${parseFloat(a.cash || 0).toFixed(2)}`);
    console.log(`   Buying power: $${parseFloat(a.buying_power || 0).toFixed(2)}`);
    console.log(`   Tipo account: ${a.account_type || a.pattern_day_trader ? 'Margin (short OK)' : 'Cash'}`);
  } catch (e) {
    console.log('   ❌ Errore Alpaca:', e.message);
  }
}

async function checkPositions() {
  const res = await fetch(`${BASE}/api/alpaca/positions`, { headers: auth() });
  const positions = await res.json();
  if (Array.isArray(positions) && positions.length) {
    console.log(`\n📁 POSIZIONI APERTE (${positions.length}):`);
    positions.forEach(p => {
      const pl = parseFloat(p.unrealized_pl || 0).toFixed(2);
      const plPct = (parseFloat(p.unrealized_plpc || 0) * 100).toFixed(2);
      console.log(`   ${p.symbol.padEnd(6)} ${p.side.padEnd(5)} qty:${p.qty.padEnd(8)} entry:$${p.avg_entry_price.padEnd(10)} P&L: ${pl >= 0 ? '+' : ''}$${pl} (${plPct}%)`);
    });
  } else {
    console.log('\n📁 Nessuna posizione aperta');
  }
}

async function main() {
  console.log('═══════════════════════════════════════════');
  console.log('  Portfolio Nexus — Diagnosi AutoTrader');
  console.log('═══════════════════════════════════════════');

  try {
    await getSession();
    const marketOpen = await checkMarketHours();
    await checkAccount();
    await checkPositions();
    const status = await getStatus();

    if (!status.enabled) {
      console.log('\n❌ PROBLEMA: AutoTrader NON abilitato. Attivalo dal pannello web.');
      return;
    }
    if (status.halted) {
      console.log('\n🚨 PROBLEMA: AutoTrader in HALT. Clicca "Ripristina sistema" dal pannello.');
      return;
    }
    if (!marketOpen) {
      console.log('\n⚠️  Mercato chiuso. L\'AT inizierà automaticamente alle 15:30 ora italiana.');
      return;
    }

    await runNow();

  } catch (e) {
    console.error('\n❌ Errore:', e.message);
    if (e.message.includes('ECONNREFUSED')) {
      console.error('   Il server non risponde su localhost:3000 — avvialo prima con: node server.js');
    }
  }
}

main();
