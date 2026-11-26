'use strict';
// ─── Nexus backtest engine ─────────────────────────────────────────────────────
// Shared by server.js (POST /api/backtest) and scripts/backtest.js (CLI used by the agents).
//
// mode 'legacy'    — identical to the original server.js engine (kept for comparability).
// mode 'realistic' — fixes the biases found in the legacy engine:
//   1. stops/targets are checked against the bar's LOW/HIGH, with gap handling at the OPEN
//      (legacy only looked at the close, so a -4% stop could exit at -12%);
//   2. commissions + slippage per side, and a borrow fee on shorts;
//   3. position size = equity / maxConc (legacy used the remaining cash, so later
//      positions were smaller and results depended on symbol order);
//   4. cash is only debited when the order actually fills (next bar's open);
//   5. warm-up bars before `start` feed the indicators, trades only from `start`.
// Neither mode models survivorship bias: the symbol list is chosen today.

// ─── Indicators (copied verbatim from server.js) ──────────────────────────────
function computeRSI(closes, period = 14) {
  if (closes.length < period + 1) return null;
  let avgGain = 0, avgLoss = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    if (delta > 0) avgGain += delta / period;
    else avgLoss += Math.abs(delta) / period;
  }
  if (avgLoss === 0) return 100;
  return 100 - 100 / (1 + avgGain / avgLoss);
}

function computeEMASeries(closes, period) {
  if (closes.length < period) return new Array(closes.length).fill(null);
  const k = 2 / (period + 1);
  const result = new Array(closes.length).fill(null);
  let ema = closes.slice(0, period).reduce((a, b) => a + b, 0) / period;
  result[period - 1] = ema;
  for (let i = period; i < closes.length; i++) {
    ema = closes[i] * k + ema * (1 - k);
    result[i] = ema;
  }
  return result;
}

function computeMACDSignal(closes) {
  if (closes.length < 35) return null;
  const ema12 = computeEMASeries(closes, 12);
  const ema26 = computeEMASeries(closes, 26);
  const macdArr = [];
  for (let i = 25; i < closes.length; i++) macdArr.push(ema12[i] - ema26[i]);
  if (macdArr.length < 10) return null;
  const sigArr = computeEMASeries(macdArr, 9);
  const n = sigArr.length;
  if (sigArr[n - 1] === null || sigArr[n - 2] === null) return null;
  const ml = macdArr[macdArr.length - 1], mlp = macdArr[macdArr.length - 2];
  const sl = sigArr[n - 1], slp = sigArr[n - 2];
  if (mlp < slp && ml > sl) return 'cross_up';
  if (mlp > slp && ml < sl) return 'cross_down';
  return null;
}

// ─── Strategies (moved from server.js, unchanged) ─────────────────────────────
const BACKTEST_STRATEGIES = {
  hawk: {
    name: 'Hawk — Breakout Momentum', lookback: 20, tp: 0.08, sl: 0.04, maxHold: 15, maxConc: 3,
    entry(bars, i) {
      if (i < 21) return null;
      const hi20 = Math.max(...bars.slice(i - 20, i).map(b => b.h));
      if (bars[i].c > hi20 && bars[i].v > bars[i - 1].v) return 'long';
      return null;
    }
  },
  owl: {
    name: 'Owl — Mean Reversion', lookback: 20, tp: 0.06, sl: 0.04, maxHold: 10, maxConc: 4,
    entry(bars, i) {
      if (i < 21) return null;
      const slice = bars.slice(i - 20, i).map(b => b.c);
      const sma = slice.reduce((a, b) => a + b, 0) / 20;
      const std = Math.sqrt(slice.reduce((a, b) => a + (b - sma) ** 2, 0) / 20);
      if (std === 0) return null;
      if ((bars[i].c - sma) / std < -1.8) return 'long';
      return null;
    }
  },
  fox: {
    name: 'Fox — Contrarian', lookback: 10, tp: 0.07, sl: 0.04, maxHold: 8, maxConc: 4,
    entry(bars, i) {
      if (i < 11) return null;
      const ret10 = (bars[i].c - bars[i - 10].c) / bars[i - 10].c;
      if (ret10 < -0.08) return 'long';
      if (ret10 > 0.10) return 'short';
      return null;
    }
  },
  bull: {
    name: 'Bull — Golden Cross', lookback: 50, tp: 0.15, sl: 0.06, maxHold: 40, maxConc: 3,
    entry(bars, i) {
      if (i < 52) return null;
      const sma10 = bars.slice(i - 10, i).reduce((a, b) => a + b.c, 0) / 10;
      const sma50 = bars.slice(i - 50, i).reduce((a, b) => a + b.c, 0) / 50;
      const pSma10 = bars.slice(i - 11, i - 1).reduce((a, b) => a + b.c, 0) / 10;
      const pSma50 = bars.slice(i - 51, i - 1).reduce((a, b) => a + b.c, 0) / 50;
      if (pSma10 <= pSma50 && sma10 > sma50) return 'long';
      return null;
    }
  },
  bear: {
    name: 'Bear — Death Cross', lookback: 50, tp: 0.12, sl: 0.05, maxHold: 30, maxConc: 3,
    entry(bars, i) {
      if (i < 52) return null;
      const sma10 = bars.slice(i - 10, i).reduce((a, b) => a + b.c, 0) / 10;
      const sma50 = bars.slice(i - 50, i).reduce((a, b) => a + b.c, 0) / 50;
      const pSma10 = bars.slice(i - 11, i - 1).reduce((a, b) => a + b.c, 0) / 10;
      const pSma50 = bars.slice(i - 51, i - 1).reduce((a, b) => a + b.c, 0) / 50;
      if (pSma10 >= pSma50 && sma10 < sma50) return 'short';
      return null;
    }
  },
  rsi: {
    name: 'RSI — Oversold Bounce', lookback: 20, tp: 0.07, sl: 0.04, maxHold: 12, maxConc: 4,
    entry(bars, i) {
      if (i < 15) return null;
      const closes = bars.slice(i - 14, i + 1).map(b => b.c);
      const rsi = computeRSI(closes, 14);
      if (rsi === null) return null;
      if (rsi < 30) return 'long';
      if (rsi > 70) return 'short';
      return null;
    }
  },
  macd: {
    name: 'MACD — Momentum Cross', lookback: 36, tp: 0.10, sl: 0.05, maxHold: 20, maxConc: 3,
    entry(bars, i) {
      if (i < 36) return null;
      const closes = bars.slice(Math.max(0, i - 60), i + 1).map(b => b.c);
      const signal = computeMACDSignal(closes);
      if (signal === 'cross_up') return 'long';
      if (signal === 'cross_down') return 'short';
      return null;
    }
  },
  bb: {
    name: 'Bollinger — Band Reversion', lookback: 22, tp: 0.06, sl: 0.03, maxHold: 10, maxConc: 4,
    entry(bars, i) {
      if (i < 21) return null;
      const closes = bars.slice(i - 19, i + 1).map(b => b.c);
      const sma = closes.reduce((a, b) => a + b, 0) / 20;
      const std = Math.sqrt(closes.reduce((a, b) => a + (b - sma) ** 2, 0) / 20);
      if (std === 0) return null;
      const price = bars[i].c;
      if (price < sma - 2 * std) return 'long';
      if (price > sma + 2 * std) return 'short';
      return null;
    }
  },
  momentum: {
    name: 'Momentum — 12-1 Factor', lookback: 253, tp: 0.20, sl: 0.08, maxHold: 60, maxConc: 3,
    entry(bars, i) {
      if (i < 253) return null;
      const ret = (bars[i - 21].c - bars[i - 252].c) / bars[i - 252].c;
      if (ret > 0.15) return 'long';
      if (ret < -0.15) return 'short';
      return null;
    }
  }
};

// Calendar days of history to fetch before `start` so every lookback is warm (realistic mode).
function warmupDays(strat) {
  return Math.ceil(((strat.lookback || 60) + 10) * 365 / 252) + 7;
}

// ─── Metrics (same formulas as the original server.js) ────────────────────────
function computeMetrics(equityCurve, closedTrades, initialCapital, tradingDays, riskFreeRate) {
  const finalEq = equityCurve.length ? equityCurve[equityCurve.length - 1].equity : initialCapital;
  const totalReturn = +(((finalEq - initialCapital) / initialCapital) * 100).toFixed(2);
  const years = tradingDays / 252;
  const annReturn = years > 0 ? +((Math.pow(finalEq / initialCapital, 1 / years) - 1) * 100).toFixed(2) : 0;
  let peak = initialCapital, maxDD = 0;
  for (const pt of equityCurve) {
    if (pt.equity > peak) peak = pt.equity;
    const dd = peak > 0 ? (peak - pt.equity) / peak * 100 : 0;
    if (dd > maxDD) maxDD = dd;
  }
  const dailyRets = equityCurve.slice(1).map((pt, i) => equityCurve[i].equity > 0 ? (pt.equity - equityCurve[i].equity) / equityCurve[i].equity : 0);
  const mu = dailyRets.length ? dailyRets.reduce((a, b) => a + b, 0) / dailyRets.length : 0;
  const sigma = dailyRets.length > 1 ? Math.sqrt(dailyRets.reduce((a, b) => a + (b - mu) ** 2, 0) / dailyRets.length) : 0;
  const sharpe = sigma > 0 ? +((((mu - riskFreeRate / 252) / sigma) * Math.sqrt(252))).toFixed(3) : 0;
  const wins = closedTrades.filter(t => t.pnl > 0);
  const losses = closedTrades.filter(t => t.pnl <= 0);
  const grossProfit = +wins.reduce((a, t) => a + t.pnl, 0).toFixed(2);
  const grossLoss = +Math.abs(losses.reduce((a, t) => a + t.pnl, 0)).toFixed(2);
  return {
    totalReturn, annReturn, maxDrawdown: +maxDD.toFixed(2), sharpe,
    winRate: closedTrades.length ? +(wins.length / closedTrades.length * 100).toFixed(1) : 0,
    profitFactor: grossLoss > 0 ? +(grossProfit / grossLoss).toFixed(3) : grossProfit > 0 ? 999 : 0,
    totalTrades: closedTrades.length, grossProfit, grossLoss,
    finalEquity: +finalEq.toFixed(2), tradingDays,
    equityCurve,
  };
}

// ─── Legacy simulator (exact copy of the original loop) ───────────────────────
function simulateLegacy(strat, symbols, allBars, initialCapital, riskFreeRate, btId = null) {
  const dateSet = new Set();
  for (const bars of Object.values(allBars)) bars.forEach(b => dateSet.add(b.t));
  const dates = [...dateSet].sort();
  const barMaps = {};
  for (const [sym, bars] of Object.entries(allBars)) barMaps[sym] = new Map(bars.map((b, i) => [b.t, i]));

  let cash = initialCapital;
  const positions = {};
  const closedTrades = [];
  const equityCurve = [];

  for (const date of dates) {
    for (const sym of Object.keys(positions)) {
      const pos = positions[sym];
      const bIdx = barMaps[sym]?.get(date);
      const bar = bIdx !== undefined ? allBars[sym][bIdx] : undefined;
      if (!bar) { pos.days++; continue; }
      pos.days++;
      const price = bar.c;
      const ret = pos.side === 'long' ? (price - pos.entry_price) / pos.entry_price : (pos.entry_price - price) / pos.entry_price;
      let exitReason = null;
      if (ret >= strat.tp) exitReason = 'take_profit';
      else if (ret <= -strat.sl) exitReason = 'stop_loss';
      else if (pos.days >= strat.maxHold) exitReason = 'max_hold';
      if (exitReason) {
        const pnl = pos.side === 'long' ? (price - pos.entry_price) * pos.qty : (pos.entry_price - price) * pos.qty;
        cash += pos.qty * pos.entry_price + pnl;
        closedTrades.push({ btId, sym, side: pos.side, qty: pos.qty, entry_date: pos.entry_date, exit_date: date, entry_price: pos.entry_price, exit_price: price, pnl, ret_pct: ret * 100, exit_reason: exitReason });
        delete positions[sym];
      }
    }
    if (Object.keys(positions).length < strat.maxConc) {
      for (const sym of symbols) {
        if (positions[sym] || Object.keys(positions).length >= strat.maxConc) continue;
        const bars = allBars[sym] || [];
        const idx = barMaps[sym]?.get(date);
        if (idx === undefined || idx < 0) continue;
        const signal = strat.entry(bars, idx);
        if (!signal) continue;
        const nextBar = bars[idx + 1];
        if (!nextBar) continue;
        const alloc = Math.min(cash * (1 / strat.maxConc), cash * 0.95);
        const price = nextBar.o;
        const qty = Math.floor(alloc / price);
        if (qty < 1) continue;
        cash -= qty * price;
        positions[sym] = { side: signal, qty, entry_price: price, entry_date: nextBar.t, days: 0 };
      }
    }
    let posValue = 0;
    for (const [sym, pos] of Object.entries(positions)) {
      const bIdx2 = barMaps[sym]?.get(date);
      const bar = bIdx2 !== undefined ? allBars[sym][bIdx2] : undefined;
      const price = bar ? bar.c : pos.entry_price;
      const pnl = pos.side === 'long' ? (price - pos.entry_price) * pos.qty : (pos.entry_price - price) * pos.qty;
      posValue += pos.qty * pos.entry_price + pnl;
    }
    equityCurve.push({ date, equity: Math.round((cash + posValue) * 100) / 100 });
  }

  for (const [sym, pos] of Object.entries(positions)) {
    const bars = allBars[sym] || [];
    const lastBar = bars[bars.length - 1];
    if (!lastBar) continue;
    const price = lastBar.c;
    const ret = pos.side === 'long' ? (price - pos.entry_price) / pos.entry_price : (pos.entry_price - price) / pos.entry_price;
    const pnl = pos.side === 'long' ? (price - pos.entry_price) * pos.qty : (pos.entry_price - price) * pos.qty;
    cash += pos.qty * pos.entry_price + pnl;
    closedTrades.push({ btId, sym, side: pos.side, qty: pos.qty, entry_date: pos.entry_date, exit_date: dates[dates.length - 1] || '', entry_price: pos.entry_price, exit_price: price, pnl, ret_pct: ret * 100, exit_reason: 'eop' });
  }
  return { closedTrades, ...computeMetrics(equityCurve, closedTrades, initialCapital, dates.length, riskFreeRate) };
}

// ─── Realistic simulator ──────────────────────────────────────────────────────
const DEFAULT_COSTS = { commissionBps: 0, slippageBps: 5, borrowBpsYear: 30 };

function simulateRealistic(strat, symbols, allBars, initialCapital, riskFreeRate, { start, costs = {}, btId = null, longOnly = false } = {}) {
  const c = { ...DEFAULT_COSTS, ...costs };
  const slip = c.slippageBps / 1e4, comm = c.commissionBps / 1e4;
  const dateSet = new Set();
  for (const bars of Object.values(allBars)) bars.forEach(b => { if (!start || b.t >= start) dateSet.add(b.t); });
  const dates = [...dateSet].sort();
  const barMaps = {};
  for (const [sym, bars] of Object.entries(allBars)) barMaps[sym] = new Map(bars.map((b, i) => [b.t, i]));

  let cash = initialCapital;
  const positions = {};       // open
  let pending = [];           // signals waiting for the next bar's open
  const closedTrades = [];
  const equityCurve = [];
  let lastEquity = initialCapital;

  const close = (sym, pos, date, rawPrice, reason) => {
    // pay slippage against us on the way out
    const px = pos.side === 'long' ? rawPrice * (1 - slip) : rawPrice * (1 + slip);
    const gross = pos.side === 'long' ? (px - pos.entry_price) * pos.qty : (pos.entry_price - px) * pos.qty;
    const fees = px * pos.qty * comm + (pos.side === 'short' ? pos.entry_price * pos.qty * (c.borrowBpsYear / 1e4) * (pos.days / 252) : 0);
    const pnl = gross - fees - pos.entryFees;
    cash += pos.qty * pos.entry_price + gross - fees;
    closedTrades.push({ btId, sym, side: pos.side, qty: pos.qty, entry_date: pos.entry_date, exit_date: date, entry_price: pos.entry_price, exit_price: px, pnl, ret_pct: pnl / (pos.qty * pos.entry_price) * 100, exit_reason: reason });
    delete positions[sym];
  };

  for (const date of dates) {
    // 1) fill yesterday's signals at today's open (size on equity, never above available cash)
    for (const p of pending) {
      if (positions[p.sym] || Object.keys(positions).length >= strat.maxConc) continue;
      const bar = allBars[p.sym][barMaps[p.sym].get(date)];
      if (!bar) continue;
      const px = p.side === 'long' ? bar.o * (1 + slip) : bar.o * (1 - slip);
      const alloc = Math.min(lastEquity / strat.maxConc, cash * 0.98);
      const qty = Math.floor(alloc / px);
      if (qty < 1) continue;
      const entryFees = px * qty * comm;
      cash -= qty * px + entryFees;
      positions[p.sym] = { side: p.side, qty, entry_price: px, entry_date: date, days: 0, entryFees, filledToday: true };
    }
    pending = [];

    // 2) exits — intrabar stop/target with gap handling; the stop wins if both are touched
    for (const sym of Object.keys(positions)) {
      const pos = positions[sym];
      const bar = allBars[sym][barMaps[sym].get(date)];
      pos.days++;
      if (!bar) continue;
      const long = pos.side === 'long';
      const stop = long ? pos.entry_price * (1 - strat.sl) : pos.entry_price * (1 + strat.sl);
      const target = long ? pos.entry_price * (1 + strat.tp) : pos.entry_price * (1 - strat.tp);
      const o = pos.filledToday ? pos.entry_price : bar.o;   // on the entry day we start from the fill
      pos.filledToday = false;
      if (long ? o <= stop : o >= stop) { close(sym, pos, date, o, 'stop_loss_gap'); continue; }
      if (long ? o >= target : o <= target) { close(sym, pos, date, o, 'take_profit_gap'); continue; }
      const hitStop = long ? bar.l <= stop : bar.h >= stop;
      const hitTarget = long ? bar.h >= target : bar.l <= target;
      if (hitStop) { close(sym, pos, date, stop, 'stop_loss'); continue; }
      if (hitTarget) { close(sym, pos, date, target, 'take_profit'); continue; }
      if (pos.days >= strat.maxHold) close(sym, pos, date, bar.c, 'max_hold');
    }

    // 3) new signals on today's close → filled at tomorrow's open
    const slots = strat.maxConc - Object.keys(positions).length;
    if (slots > 0) {
      for (const sym of symbols) {
        if (pending.length >= slots) break;
        if (positions[sym]) continue;
        const bars = allBars[sym] || [];
        const idx = barMaps[sym]?.get(date);
        if (idx === undefined || !bars[idx + 1]) continue;
        const side = strat.entry(bars, idx);
        if (side && !(longOnly && side === 'short')) pending.push({ sym, side });
      }
    }

    // 4) mark to market at the close
    let posValue = 0;
    for (const [sym, pos] of Object.entries(positions)) {
      const bar = allBars[sym][barMaps[sym].get(date)];
      const price = bar ? bar.c : pos.entry_price;
      const pnl = pos.side === 'long' ? (price - pos.entry_price) * pos.qty : (pos.entry_price - price) * pos.qty;
      posValue += pos.qty * pos.entry_price + pnl;
    }
    lastEquity = cash + posValue;
    equityCurve.push({ date, equity: Math.round(lastEquity * 100) / 100 });
  }

  const lastDate = dates[dates.length - 1] || '';
  for (const [sym, pos] of Object.entries(positions)) {
    const bars = allBars[sym] || [];
    const lastBar = bars.filter(b => b.t <= lastDate).pop();
    if (lastBar) close(sym, pos, lastDate, lastBar.c, 'eop');
  }
  if (equityCurve.length) equityCurve[equityCurve.length - 1].equity = Math.round(cash * 100) / 100;
  return { closedTrades, ...computeMetrics(equityCurve, closedTrades, initialCapital, dates.length, riskFreeRate) };
}

function simulate(strategyKey, symbols, allBars, { initialCapital = 10000, riskFreeRate = 0.043, mode = 'legacy', start, costs, btId, longOnly = false } = {}) {
  const strat = BACKTEST_STRATEGIES[strategyKey];
  if (!strat) throw new Error('Unknown personality: ' + strategyKey);
  return mode === 'realistic'
    ? simulateRealistic(strat, symbols, allBars, initialCapital, riskFreeRate, { start, costs, btId, longOnly })
    : simulateLegacy(strat, symbols, allBars, initialCapital, riskFreeRate, btId);
}

// Buy-and-hold benchmark on one symbol (e.g. SPY) over the same dates.
function buyAndHold(bars, initialCapital, riskFreeRate, start) {
  const b = bars.filter(x => !start || x.t >= start);
  if (b.length < 2) return null;
  const qty = initialCapital / b[0].o;
  const curve = b.map(x => ({ date: x.t, equity: Math.round(qty * x.c * 100) / 100 }));
  return computeMetrics(curve, [], initialCapital, b.length, riskFreeRate);
}

module.exports = {
  BACKTEST_STRATEGIES, DEFAULT_COSTS,
  computeRSI, computeEMASeries, computeMACDSignal,
  simulate, simulateLegacy, simulateRealistic, computeMetrics, buyAndHold, warmupDays,
};
