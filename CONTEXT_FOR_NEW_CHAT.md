# Portfolio Nexus × Trading Desk — Contesto per nuova chat

## Stack tecnico
- **Backend**: Node.js + Express, file `server.js` (~3984 righe)
- **Frontend**: Single-page HTML, `public/index.html` (~4439 righe), nessun framework
- **Database**: SQLite via `better-sqlite3`, WAL mode, synchronous NORMAL — file `data/nexus.db`
- **AI agenti**: `claude-haiku-4-5` per decisioni agenti e requiem
- **AI AT**: `claude-haiku-4-5-20251001` per macro brief e symbol selection
- **AI chat/screener**: `claude-sonnet-4-6`
- **Broker**: Alpaca Markets (paper o live) via REST + WebSocket
- **Notifiche**: Telegram bot
- **Charts**: Chart.js 4.4.0
- **Real-time**: WebSocket broadcast server→client

## File principali
```
server.js              — backend Express + AutoTrader + Multi-Agent + Backtest
public/index.html      — frontend SPA completa
data/nexus.db          — database SQLite (NON committare — in .gitignore via data/)
.env                   — credenziali (NON committare)
patch.js               — script one-shot per fix manuali
validate-universe.js   — audit simboli contro Alpaca
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
NEXUS_ADMIN_TOKEN=...            ← token login
NEXUS_ENABLE_LIVE_TRADING=true   ← obbligatorio per trading reale
NEXUS_MAX_ORDER_NOTIONAL=5000
NEXUS_MAX_ORDER_QTY=1000
NEXUS_AUTOTRADER_MAX_DAILY_TRADES=8
```

---

## Sistema 1 — AutoTrader (AT)

### Ciclo AT (atCycle) — fasi in ordine:
1. **Macro research** — `claude-haiku` analizza mercato globale, FX, sentiment
2. **Symbol selection** — AI sceglie N simboli da `STOCK_UNIVERSE` (default 30)
3. **Position review (Phase 2.5)** — `reviewDrawdownPositions()` per posizioni in perdita
4. **Per-symbol loop** — per ogni simbolo: fetch barre → indicatori → AI decision → ordine

### Ordini AT
- BUY/SHORT: `order_class: 'oto'` con solo `take_profit` (NO stop_loss bracket)
- TP adattivo alla volatilità: `tpPct = annVol × 1.5 × √(60/252) × 100`, cappato 8–80%
- SL adattivo: `slPct = annVol × 0.55 × √(60/252) × 100`, cappato 3–25%
- Stop loss gestito da AT position review, non da bracket Alpaca

### Position Review System
- Trigger: perdita > 60% dello SL adattivo
- Emergency close: perdita > 220% dello SL (no AI)
- Cooldown: 2 giorni tra review dello stesso simbolo
- Max 1 ADD per posizione lifetime
- Supporta sia LONG che SHORT

---

## Sistema 2 — Multi-Agent Evolutionary System

### Personalità agenti (`AGENT_PERSONALITIES`)
| id   | Stile                       | riskPerTrade | SL  | TP  | short | cycleMs | killDrawdown |
|------|-----------------------------|-------------|-----|-----|-------|---------|--------------|
| hawk | Aggressivo, tech, rapido    | 15%         | 6%  | 15% | no    | 25 min  | 30%          |
| owl  | Conservativo, qualità       | 8%          | 4%  | 10% | no    | 60 min  | 20%          |
| fox  | Contrarian, oversold        | 12%         | 7%  | 20% | sì    | 45 min  | 25%          |
| bull | Momentum puro               | 12%         | 5%  | 18% | no    | 35 min  | 28%          |
| bear | Macro/ribassista, short     | 10%         | 5%  | 20% | sì    | 50 min  | 25%          |

Capitale iniziale: **$10.000 per agente**. Max agenti simultanei: 5.

### Ciclo agente (`_agentCycleInner`)
1. `agentUpdatePrices()` — fetch 1Min bars per simboli watchlist + posizioni aperte
2. `agentFetchTechIndicators()` — fetch 30 barre daily → computa RSI(14) per simbolo
3. Check stop loss / take profit su posizioni aperte
4. Check kill: se drawdown ≥ `killDrawdown` → `killAgent()` → genera requiem
5. AI decision (Haiku) — prompt include: prezzi con % variazione + RSI, posizioni aperte, memoria requiem
6. Se confidence ≥ entryThreshold e slot libero (<3 posizioni) → apre posizione virtuale

### Guard critici
- `agentRunning` Set — previene cicli sovrapposti sullo stesso agente
- `isMarketHours()` — decisioni solo 13:30–21:00 UTC (9:30–17:00 ET) lun-ven
- Duplicate position guard — no doppia posizione sullo stesso simbolo per lo stesso agente

### Requiem memory
- Alla morte dell'agente: Haiku genera 3-4 frasi di lezioni
- Salvate in tabella `requiem` filtrate per `personalityType` (es. `fox_%`)
- Agenti successivi della stessa personalità leggono i requiem dei predecessori

### Formato prompt agente
```
Prezzi: AAPL:$180.50(+0.3%) RSI42  MSFT:$420.00(-0.1%) RSI58 ...
```
RSI < 30 = ipervenduto, RSI > 70 = ipercomprato.

---

## Sistema 3 — Backtest Engine

### 9 strategie disponibili
| key      | Nome                     | Fonte                | Logica entry                        |
|----------|--------------------------|----------------------|-------------------------------------|
| hawk     | Breakout Momentum        | classico             | prezzo > hi20 + volume spike        |
| owl      | Mean Reversion           | classico             | z-score < -1.8 rispetto SMA20       |
| fox      | Contrarian               | classico             | rendimento -8% su 10gg → long       |
| bull     | Golden Cross             | classico             | SMA10 incrocia sopra SMA50          |
| bear     | Death Cross              | classico             | SMA10 incrocia sotto SMA50          |
| rsi      | RSI Oversold Bounce      | Kakushadze §3.9      | RSI(14) < 30 → long, > 70 → short  |
| macd     | MACD Momentum Cross      | Kakushadze §3.11-3.13| EMA12/26 crossover + signal line    |
| bb       | Bollinger Band Reversion | Kakushadze §3.9      | prezzo < lower band 2σ → long       |
| momentum | Momentum 12-1 Factor     | Kakushadze §3.1      | rendimento 12 mesi skip 1 → long    |

### Fix critici backtest
- **Look-ahead bias**: entry al `nextBar.o` (apertura bar successiva), non alla chiusura del segnale
- **O(1) lookup**: `barMaps` = `Map(date → index)` per evitare `find()` O(n) su ogni bar
- **Rate limit**: batch multi-symbol (`/v2/stocks/bars?symbols=...`) + retry esponenziale su 429
- **Equity curve**: non troncata (curva completa)

### Helper indicatori tecnici
```js
computeRSI(closes, period)       // RSI da array di close
computeEMASeries(closes, period) // array EMA, null prima del period
computeMACDSignal(closes)        // 'cross_up' | 'cross_down' | null
```

---

## Schema SQLite (`data/nexus.db`)

Tabelle principali:
```
sessions        — digest + expires_at (autenticazione)
at_state        — chiave/valore persistenza AT
decisions       — log decisioni AI (AT e agenti)
agent_positions — posizioni virtuali agenti (open/closed)
agents          — anagrafica agenti (alive/dead, capitale, drawdown)
requiem         — memoria errori agenti morti
backtests       — metadati run backtest
backtest_trades — trade storici simulati
options_log     — log operazioni opzioni
```

---

## Endpoint API principali

### Auth
```
POST /api/session          — exchange NEXUS_ADMIN_TOKEN → session token
```

### AutoTrader
```
GET  /api/autotrader/status       — stato AT + ultimi log
POST /api/autotrader/config       — salva config
POST /api/autotrader/run-now      — forza ciclo immediato
POST /api/autotrader/watchlist    — aggiorna watchlist manuale
GET  /api/autotrader/history      — storico trade (?date=YYYY-MM-DD)
POST /api/autotrader/refresh-macro — rigenera brief macro
```

### Multi-Agent
```
GET  /api/agents                  — lista agenti + requiem + personalità
POST /api/agents                  — spawn agente ({ personalityId })
DELETE /api/agents/:id            — kill agente manuale
GET  /api/agents/:id/positions    — posizioni agente
GET  /api/agents/:id/decisions    — decisioni agente
```

### Backtest
```
POST /api/backtest                — avvia backtest ({ personality, symbols, start_date, end_date, initial_capital })
GET  /api/backtest                — lista ultimi 50 backtest
GET  /api/backtest/:id            — risultati + trade
DELETE /api/backtest/:id          — elimina backtest
```

### Alpaca proxy
```
GET  /api/alpaca/account
GET  /api/alpaca/positions
GET  /api/alpaca/orders
POST /api/alpaca/orders
DELETE /api/alpaca/orders/:id
GET  /api/alpaca/portfolio/history
GET  /api/alpaca/bars/:symbol
```

---

## WebSocket events (broadcast server→client)
```
autotrader_status    — stato AT aggiornato
autotrader_log       — nuovo log entry
autotrader_trade     — trade AT eseguito
autotrader_macro     — nuovo brief macro
agent_started        — nuovo agente spawnato
agent_trade          — agente ha aperto posizione virtuale
agent_died           — agente eliminato (con requiem)
backtest_done        — backtest completato (con results)
backtest_error       — backtest fallito
positions            — posizioni Alpaca reali aggiornate
account              — account Alpaca aggiornato
quote                — live quote simbolo
```

---

## Regole Alpaca API

- Barre giornaliere: **NO `feed=iex`** — IEX è solo real-time intraday, restituisce 1 barra
- Barre intraday (1Min, 5Min): `feed=iex` va bene
- Multi-symbol: `/v2/stocks/bars?symbols=AAPL,MSFT,...`
- Errori Alpaca: `{ message: "..." }` non `{ error: "..." }`
- Ordini OTO: `order_class: 'oto'`, solo `take_profit`, NO `stop_loss`

---

## Sicurezza (vincoli hard — non modificare)
- Chiavi Alpaca MAI inviate al browser — solo server-side in `.env`
- `.env` NON committato (`.gitignore`)
- Ordini manuali richiedono conferma modale esplicita
- Token in `sessionStorage` ONLY, mai `localStorage`
- `NEXUS_ENABLE_LIVE_TRADING=true` richiesto per live trading
- Short trading è rischioso — non rilassare le condizioni senza analisi

---

## Consigli per nuovi sviluppi

### Modifica server.js
- Testa sempre con `node --check server.js` prima di riavviare
- Usa `db.prepare(...).run(...)` per scritture SQLite — è sincrono, niente callback
- Usa `atLog()` per log visibili nel frontend AT, non `console.log()`
- `alpacaDataFetch()` restituisce un `Response` — chiama `.json()` esplicitamente
- `agentFetchTechIndicators()` torna `{ [symbol]: { rsi: number|null } }`

### Modifica index.html
- `secureFetch()` al posto di `fetch()` — aggiunge automaticamente il session token
- WebSocket handler in `init()` → switch su `data.type`
- `BT_PERSONALITY_META` contiene le 9 strategie backtest con icon/label/color
- `PERSONALITY_META` contiene le 5 personalità agenti

### Anthropic API — modelli corretti
- Agenti e requiem: `claude-haiku-4-5`
- Macro brief e symbol selection: `claude-haiku-4-5-20251001`
- Chat e screener: `claude-sonnet-4-6`
- Output sempre JSON puro (no markdown, no backtick), temperature 0 per trading

---

## Come iniziare una nuova chat

Incolla questo file come primo messaggio, poi descrivi il problema o la feature.
Includi sempre:
1. Il messaggio di errore esatto (dal terminale Node o dalla console browser F12)
2. Quale sistema è coinvolto (AT, Agenti, Backtest, Trading, Dashboard...)
3. Se l'errore è lato server (terminale) o lato client (browser)
