# Portfolio Nexus × Trading Desk — Contesto per nuova chat

## Stack tecnico
- **Backend**: Node.js + Express, file `server.js` (~2400 righe)
- **Frontend**: Single-page HTML, `public/index.html` (~2900 righe), nessun framework
- **AI**: Anthropic `claude-sonnet-4-6` per decisioni di trading, `claude-haiku-4-5-20251001` per macro
- **Broker**: Alpaca Markets paper trading API
- **Notifiche**: Telegram bot
- **Charts**: Chart.js 4.4.0
- **Real-time**: WebSocket broadcast dal server al frontend
- **Stato persistente**: `data/autotrader-state.json` (atomic write via temp file + rename)

## File principali
```
server.js              — backend Express + AutoTrader engine
public/index.html      — frontend SPA completa
data/autotrader-state.json  — stato persistente AT (NON committare)
.env                   — credenziali (NON committare, nel .gitignore)
patch.js               — script one-shot per applicare fix
```

## Variabili d'ambiente (.env)
```
ANTHROPIC_API_KEY=...
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NEXUS_ENABLE_LIVE_TRADING=true   ← obbligatorio per trading reale
```

## Architettura AutoTrader (AT)

### Ciclo AT (atCycle) — fasi in ordine:
1. **Macro research** — `claude-haiku` analizza mercato globale, FX, sentiment
2. **Symbol selection** — AI sceglie N simboli da `STOCK_UNIVERSE` (default 30)
3. **Position review (Phase 2.5)** — `reviewDrawdownPositions()` per posizioni in perdita
4. **Per-symbol loop** — per ogni simbolo: fetch barre → indicatori → AI decision → ordine

### Ordini
- BUY/SHORT: `order_class: 'oto'` con solo `take_profit` (NO stop_loss bracket)
- Stop loss gestito da AI review, non da bracket Alpaca
- TP adattivo alla volatilità: `tpPct = annVol × 1.5 × √(60/252) × 100`, cappato 8–80%
- SL adattivo: `slPct = annVol × 0.55 × √(60/252) × 100`, cappato 3–25%

### Position Review System
- Trigger: perdita > 60% dello SL adattivo
- Emergency close: perdita > 220% dello SL (no AI)
- Cooldown: 2 giorni tra review dello stesso simbolo
- Max 1 ADD per posizione lifetime
- ADD: cancella TP esistenti, mette TP unificato per qty totale
- Supporta sia LONG che SHORT

### Fetch barre giornaliere
```js
// CORRETTO — senza feed=iex (iex = solo intraday real-time, non storico)
const qs = new URLSearchParams({ timeframe: '1Day', limit: '60' });
```
**IMPORTANTE**: NON aggiungere `feed: 'iex'` alle barre giornaliere — restituisce solo 1 barra.
`feed: 'iex'` va usato SOLO per barre intraday (1Min, 5Min).

### Stato AT (oggetto in memoria + persistito)
```js
AT = {
  enabled, halted, haltReason,
  intervalMs, confidenceThreshold,
  maxPositions, maxPositionPct, maxPositionsPerSector,
  drawdownLimit, allowShort, targetVolatility,
  aiManagedWatchlist,   // true = AI sceglie simboli
  watchlistSize: 30,    // quanti simboli per ciclo
  watchlist,            // simboli manuali (se aiManagedWatchlist=false)
  aiSelectedWatchlist,  // ultima selezione AI
  addHistory,           // { [symbol]: addCount }
  lastReviewDate,       // { [symbol]: 'YYYY-MM-DD' }
  log, todayTrades, dailyTradeHistory,
  lastRunAt, nextRunAt, timer,
}
```

## STOCK_UNIVERSE
~130 titoli US liquidi coperti da Alpaca. Rimossi i micro-cap problematici:
BBAI, ARQQ, OPEN, DAVE, RELY, DOMO, ACMR, LILM, RDW, JOBY, ACHR, WOLF, FORM, WISH.

Tutti i titoli nel frontend (`STOCKS` array) sono US tradeable con dati Q1 2026:
AAPL, MSFT, NVDA, GOOGL, META, AMZN, AMD, TSM, AVGO, QCOM, JPM, GS, V, MA,
UNH, LLY, ABBV, XOM, CVX, TSLA, PLTR, CRWD, SNOW, NET, AMGN, COST, WMT, RTX, LMT, CAT

## Endpoint API principali
```
GET  /api/autotrader/status          — stato AT + ultimi 20 log
POST /api/autotrader/config          — salva config (watchlistSize, aiManagedWatchlist, ecc.)
POST /api/autotrader/run-now         — forza ciclo immediato
POST /api/autotrader/watchlist       — aggiorna watchlist manuale
GET  /api/autotrader/history         — storico trade
GET  /api/autotrader/intraday/:sym   — barre 1Min intraday da apertura mercato
POST /api/autotrader/refresh-macro   — rigenera brief macro
GET  /api/alpaca/positions           — posizioni aperte
GET  /api/alpaca/account             — info account
```

## WebSocket events (broadcast server→client)
```
autotrader_status    — stato AT aggiornato
autotrader_log       — nuovo log entry
autotrader_trade     — trade eseguito
autotrader_macro     — nuovo brief macro
autotrader_watchlist — nuova selezione simboli
positions            — posizioni aggiornate
```

## Bug noti e fix applicati

### watchlistSize non si salvava
**Causa**: `POST /api/autotrader/config` non leggeva `watchlistSize` né `aiManagedWatchlist` dal body.
**Fix**: Aggiungere nel config endpoint:
```js
const { aiManagedWatchlist, watchlistSize } = req.body;
if (typeof aiManagedWatchlist === 'boolean') AT.aiManagedWatchlist = aiManagedWatchlist;
if (watchlistSize != null && Number.isFinite(+watchlistSize)) AT.watchlistSize = Math.max(3, Math.min(50, +watchlistSize));
saveAtState();
```

### Barre giornaliere restituiscono solo 1 barra
**Causa**: `feed: 'iex'` nelle barre `timeframe: '1Day'` — IEX è real-time, non storico.
**Fix**: Rimuovere `feed: 'iex'` dal fetch giornaliero. Tenerlo solo per intraday.

### watchdog "vendi X" apre sidebar vuota
**Causa**: `openOrderPanel()` apriva `#order-panel` slide-in vuoto.
**Fix**: Navigare a sezione Trading → tab "Nuovo Ordine" invece.

### Heatmap con stock non-US
**Causa**: Array `STOCKS` aveva 15 titoli internazionali (ENB, JDSC, MFG...).
**Fix**: Sostituiti con 30 titoli US liquidi.

### Tickers micro-cap senza dati IEX
**Causa**: AI selezionava AIXI, OPI, GETY, NATS, NKTR dall'universo — non coperti da Alpaca IEX.
**Fix**: 
1. Rimossi dall'universo i titoli illiquidi
2. Guard: se `closes.length < 27` e nessuna posizione aperta → SKIP senza chiamata AI

### aiSelectWatchlist cappava a 30 simboli
**Causa**: `Math.min(30, AT.watchlistSize || 10)` hardcodato.
**Fix**: `Math.min(50, AT.watchlistSize || 30)`

## Consigli per nuovi sviluppi

### Modifica server.js
- Testa sempre con `node --check server.js` prima di riavviare
- `saveAtState()` va chiamato dopo ogni modifica a `AT.*` che deve persistere
- Usa `atLog()` per log visibili nel frontend, non `console.log()`
- `alpacaDataFetch()` restituisce un `Response` — ricorda di chiamare `.json()`

### Modifica index.html
- La funzione `updateAutoTraderUI(data)` popola tutti i campi AT dal backend
- `saveAutoTraderConfig()` invia a `POST /api/autotrader/config`
- WebSocket handler in `init()` → switch su `data.type`
- Usa `secureFetch()` invece di `fetch()` — aggiunge il token di sessione

### Deploy (Windows Server)
- Il server non ha accesso a internet (GitHub bloccato)
- Per trasferire file: editare manualmente con Notepad++ / VSCode
- Oppure usare `node -e "..."` one-liner da CMD per patch programmatiche
- `patch.js` nella root applica tutti i fix pendenti con `node patch.js`

### Alpaca API
- Paper trading: `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- Dati storici: `ALPACA_DATA_URL=https://data.alpaca.markets`
- Barre giornaliere: NO `feed=iex`, usa default o ometti il param
- Barre intraday: `feed=iex` va bene (1Min, 5Min)
- Ordini OTO (bracket senza stop): `order_class: 'oto'`, solo `take_profit`
- Alpaca restituisce errori come `{ message: "..." }` non `{ error: "..." }`

### Anthropic API
- Trading decisions: `claude-sonnet-4-6`
- Macro brief: `claude-haiku-4-5-20251001`
- Output sempre JSON puro (no markdown, no backtick)
- Temperature 0 per decisioni di trading

### Sicurezza (vincoli hard)
- Chiavi Alpaca MAI inviate al browser — solo server-side in .env
- .env NON committato (.gitignore)
- Ordini manuali richiedono conferma modale esplicita
- Token in sessionStorage ONLY, mai localStorage
- Credenziali reali MAI in .env.example o file versionati
- `NEXUS_ENABLE_LIVE_TRADING=true` richiesto per live trading

## Come iniziare una nuova chat

Incolla questo file come primo messaggio, poi descrivi il problema o la feature.
Includi sempre:
1. Il messaggio di errore esatto (dal log AT o dalla console browser)
2. Quale sezione dell'app è coinvolta (AT, Trading, Portfolio, Heatmap...)
3. Se l'errore è lato server (terminale Node) o lato client (F12 Console)
