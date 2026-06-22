/**
 * AutoTrader Dry-Run — testa l'intero ciclo AT senza aprire ordini reali.
 * Chiama Alpaca (read-only: bars, account, positions) e Anthropic (AI decisions).
 * NON esegue ordini. Stampa il risultato per ogni simbolo.
 *
 * Uso: node dry-run.js
 */

require('dotenv').config();

const ANTHROPIC_KEY  = process.env.ANTHROPIC_API_KEY;
const ALPACA_KEY     = process.env.ALPACA_API_KEY;
const ALPACA_SECRET  = process.env.ALPACA_SECRET_KEY;
const ALPACA_BASE    = process.env.ALPACA_BASE_URL  || 'https://paper-api.alpaca.markets';
const ALPACA_DATA    = process.env.ALPACA_DATA_URL  || 'https://data.alpaca.markets';

const CONFIDENCE_THRESHOLD = 0.65;
const TAKE_PROFIT_PCT      = 30;
const STOP_LOSS_PCT        = 8;
const MAX_POSITIONS        = 5;
const DRY_RUN_SYMBOLS      = ['AAPL','MSFT','NVDA','JPM','SPY','QQQ','AMZN','GOOGL','META','XOM'];

const SYSTEM_PROMPT = `You are an autonomous trading AI. Given macro context, technical indicators, Black-Scholes probabilities, and portfolio state, respond with ONLY a JSON object:
{"action":"BUY"|"SELL"|"SHORT"|"COVER"|"HOLD","confidence":0.0-1.0,"reasoning":"<1 sentence>","suggestedNotional":number|null}
Rules: confidence>=0.75 only for very clear setups. HOLD when uncertain. Never suggest action already held.`;

// ─── Helpers ──────────────────────────────────────────────────────────────────
const alpacaHeaders = () => ({
  'APCA-API-KEY-ID':     ALPACA_KEY,
  'APCA-API-SECRET-KEY': ALPACA_SECRET,
  'Content-Type':        'application/json',
});

async function alpacaGet(path) {
  const r = await fetch(`${ALPACA_BASE}${path}`, { headers: alpacaHeaders() });
  return r.json();
}

async function alpacaDataGet(path) {
  const r = await fetch(`${ALPACA_DATA}${path}`, { headers: alpacaHeaders() });
  return r.json();
}

// ─── Technical Indicators ─────────────────────────────────────────────────────
function computeSMA(c, n) {
  if (c.length < n) return null;
  return c.slice(-n).reduce((a, b) => a + b, 0) / n;
}
function computeEMA(c, n) {
  if (c.length < n) return null;
  const k = 2 / (n + 1);
  let ema = c.slice(0, n).reduce((a, b) => a + b, 0) / n;
  for (let i = n; i < c.length; i++) ema = c[i] * k + ema * (1 - k);
  return ema;
}
function computeRSI(c, p = 14) {
  if (c.length < p + 1) return null;
  let g = 0, l = 0;
  for (let i = c.length - p; i < c.length; i++) {
    const d = c[i] - c[i - 1];
    d >= 0 ? g += d : l -= d;
  }
  g /= p; l /= p;
  return l === 0 ? 100 : 100 - 100 / (1 + g / l);
}
function computeMACD(c) {
  const e12 = computeEMA(c, 12), e26 = computeEMA(c, 26);
  return e12 != null && e26 != null ? e12 - e26 : null;
}
function computeVol(c) {
  if (c.length < 10) return null;
  const rets = [];
  for (let i = 1; i < c.length; i++) if (c[i-1] > 0) rets.push(Math.log(c[i]/c[i-1]));
  if (rets.length < 5) return null;
  const mean = rets.reduce((a,b) => a+b, 0) / rets.length;
  const variance = rets.reduce((a,b) => a + (b-mean)**2, 0) / rets.length;
  return Math.sqrt(variance * 252);
}

// ─── Black-Scholes ────────────────────────────────────────────────────────────
function normalCDF(x) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const poly = t*(0.319381530 + t*(-0.356563782 + t*(1.781477937 + t*(-1.821255978 + t*1.330274429))));
  const cdf = 1 - Math.exp(-0.5*x*x)/Math.sqrt(2*Math.PI) * poly;
  return x >= 0 ? cdf : 1 - cdf;
}
function blackScholes(S, sigma, T = 60/252, r = 0.043) {
  if (!S || !sigma || sigma <= 0) return null;
  const sqrtT = Math.sqrt(T);
  const d2_atm = (r - 0.5*sigma*sigma)*T / (sigma*sqrtT);
  const d1_atm = (r + 0.5*sigma*sigma)*T / (sigma*sqrtT);
  const K_tp = S * (1 + TAKE_PROFIT_PCT/100);
  const K_sl = S * (1 - STOP_LOSS_PCT/100);
  return {
    probAbove: Math.round(normalCDF(d2_atm)*100),
    probTP:    Math.round(normalCDF((Math.log(S/K_tp)+(r-0.5*sigma*sigma)*T)/(sigma*sqrtT))*100),
    probSL:    Math.round((1-normalCDF((Math.log(S/K_sl)+(r-0.5*sigma*sigma)*T)/(sigma*sqrtT)))*100),
    delta:     Math.round(normalCDF(d1_atm)*100)/100,
  };
}

// ─── Macro Brief ─────────────────────────────────────────────────────────────
async function fetchMacro() {
  let fxStr = 'unavailable';
  try {
    const fx = await (await fetch('https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY,CHF')).json();
    const r = fx.rates || {};
    fxStr = `EUR/USD ${r.EUR} · GBP/USD ${r.GBP} · USD/JPY ${r.JPY} · USD/CHF ${r.CHF}`;
  } catch(_) {}

  const macroPrompt = `Today: ${new Date().toUTCString()}\nFX: ${fxStr}\n\nReturn JSON only:\n{"regime":"RISK-ON"|"RISK-OFF"|"NEUTRAL","summary":"2 sentences max on global equity outlook and key risks"}`;
  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 200, messages: [{ role: 'user', content: macroPrompt }] }),
    });
    const d = await res.json();
    let raw = (d.content?.[0]?.text || '{}').trim().replace(/^```[a-z]*\n?/,'').replace(/```$/,'').trim();
    return { ...JSON.parse(raw), fxStr };
  } catch(_) { return { regime: 'NEUTRAL', summary: 'No macro data.', fxStr }; }
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  console.log('\n╔══════════════════════════════════════════════════════╗');
  console.log('║         AutoTrader DRY-RUN — NESSUN ORDINE REALE    ║');
  console.log('╚══════════════════════════════════════════════════════╝\n');

  if (!ANTHROPIC_KEY || !ALPACA_KEY) {
    console.error('❌ Mancano ANTHROPIC_API_KEY o ALPACA_API_KEY nel .env');
    process.exit(1);
  }

  // 1. Account
  console.log('📊 Carico account Alpaca...');
  const account = await alpacaGet('/v2/account');
  const equity      = +account.equity;
  const buyingPower = +account.buying_power;
  console.log(`   Equity: $${equity.toFixed(2)} | Buying power: $${buyingPower.toFixed(2)} | Paper: ${account.account_type === 'paper' || ALPACA_BASE.includes('paper') ? 'YES ✓' : 'NO ⚠'}\n`);

  // 2. Positions
  const positions = await alpacaGet('/v2/positions');
  const posMap = new Map((Array.isArray(positions) ? positions : []).map(p => [p.symbol, p]));
  console.log(`📦 Posizioni aperte: ${posMap.size} — ${[...posMap.keys()].join(', ') || 'nessuna'}\n`);

  // 3. Macro
  console.log('🌍 Genero macro brief...');
  const macro = await fetchMacro();
  console.log(`   Regime: ${macro.regime}`);
  console.log(`   ${macro.summary}`);
  console.log(`   FX: ${macro.fxStr}\n`);

  // 4. Per ogni simbolo
  const results = [];
  for (const symbol of DRY_RUN_SYMBOLS) {
    process.stdout.write(`\n🔍 ${symbol.padEnd(6)}`);

    // Bars
    const qs = new URLSearchParams({ timeframe: '1Day', limit: '60', feed: 'iex' });
    const bd = await alpacaDataGet(`/v2/stocks/${symbol}/bars?${qs}`);
    if (!Array.isArray(bd.bars) || !bd.bars.length) {
      console.log(` ❌ Bars error: ${bd.message || JSON.stringify(bd).slice(0,60)}`);
      results.push({ symbol, action: 'SKIP', reason: 'no bars' });
      continue;
    }
    const closes  = bd.bars.map(b => b.c);
    const volumes = bd.bars.map(b => b.v);
    const S       = closes[closes.length - 1];
    const avgVol  = volumes.slice(-20).reduce((a,b)=>a+b,0) / Math.min(20,volumes.length);
    const relVol  = volumes[volumes.length-1] / avgVol;

    const rsi    = computeRSI(closes);
    const macd   = computeMACD(closes);
    const sma20  = computeSMA(closes, 20);
    const sma50  = computeSMA(closes, 50);
    const annVol = computeVol(closes);
    const bs     = blackScholes(S, annVol);

    process.stdout.write(` $${S.toFixed(2)} | RSI:${rsi?.toFixed(1)||'?'} MACD:${macd?.toFixed(3)||'?'} Vol:${annVol ? (annVol*100).toFixed(0)+'%' : '?'}`);
    if (bs) process.stdout.write(` | BS↑:${bs.probAbove}% TP:${bs.probTP}% SL:${bs.probSL}%`);

    // AI decision
    const pos = posMap.get(symbol);
    const prompt = `MACRO: regime=${macro.regime}. ${macro.summary}\nFX: ${macro.fxStr}

SYMBOL: ${symbol} | Price: $${S.toFixed(2)}
RSI(14): ${rsi?.toFixed(1)||'?'} | MACD: ${macd?.toFixed(3)||'?'} | SMA20: $${sma20?.toFixed(2)||'?'} | SMA50: $${sma50?.toFixed(2)||'?'}
RelVolume: ${relVol.toFixed(2)}x | AnnVol: ${annVol ? (annVol*100).toFixed(1)+'%' : '?'}
Black-Scholes 60d: P(above)=${bs?.probAbove||'?'}% P(TP+${TAKE_PROFIT_PCT}%)=${bs?.probTP||'?'}% P(SL-${STOP_LOSS_PCT}%)=${bs?.probSL||'?'}% delta=${bs?.delta||'?'}
Position: ${pos ? `${pos.side} qty=${pos.qty} entry=$${pos.avg_entry_price} PnL=${(+pos.unrealized_plpc*100).toFixed(1)}%` : 'none'}
Portfolio: ${posMap.size}/${MAX_POSITIONS} positions | buyingPower: $${buyingPower.toFixed(0)}`;

    let decision = { action: 'HOLD', confidence: 0, reasoning: 'parse error' };
    try {
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': ANTHROPIC_KEY, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'claude-sonnet-4-6', max_tokens: 200, system: SYSTEM_PROMPT, messages: [{ role: 'user', content: prompt }] }),
      });
      const d = await res.json();
      let raw = (d.content?.[0]?.text || '{}').trim().replace(/^```[a-z]*\n?/,'').replace(/```$/,'').trim();
      decision = JSON.parse(raw);
    } catch(e) { decision.reasoning = e.message; }

    const wouldTrade = decision.confidence >= CONFIDENCE_THRESHOLD && decision.action !== 'HOLD';
    const flag = wouldTrade ? '🟢 TRADE' : '⚪ HOLD ';
    console.log(`\n         ${flag} → ${decision.action} (conf: ${(decision.confidence*100).toFixed(0)}%) — ${decision.reasoning}`);
    if (wouldTrade && decision.suggestedNotional) console.log(`         Notional suggerito: $${decision.suggestedNotional}`);

    results.push({ symbol, ...decision, wouldTrade });
    await new Promise(r => setTimeout(r, 600)); // rate limit
  }

  // ─── Riepilogo ───────────────────────────────────────────────────────────────
  console.log('\n\n═══════════════════════ RIEPILOGO ═══════════════════════');
  const trades = results.filter(r => r.wouldTrade);
  if (trades.length === 0) {
    console.log('   Nessun trade sarebbe eseguito in questo ciclo.');
  } else {
    trades.forEach(t => console.log(`   🟢 ${t.action.padEnd(5)} ${t.symbol.padEnd(6)} — conf: ${(t.confidence*100).toFixed(0)}% — ${t.reasoning}`));
  }
  console.log(`\n   Simboli analizzati: ${results.length} | Trade che scatterebbero: ${trades.length}`);
  console.log('   NESSUN ORDINE INVIATO — dry-run completato ✓\n');
}

main().catch(e => { console.error('\n❌ Errore:', e.message); process.exit(1); });
