# Portfolio Nexus × Trading Desk

Professional portfolio monitoring + AI advisor + real trading via Alpaca Markets.

## Setup in 6 Steps

### 1. Get Alpaca API Keys (free paper account)
1. Go to [alpaca.markets](https://alpaca.markets) and sign up for a free account
2. In the dashboard, navigate to **Paper Trading** → **API Keys**
3. Click **Generate New Key** — copy the API Key ID and Secret Key
4. Paper trading is free, safe, and uses simulated money — no risk

### 2. Get Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Navigate to **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-`)
4. Add credits if needed (very low cost per conversation)

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your keys:
nano .env
```

Fill in:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
ALPACA_API_KEY=PKyour-alpaca-key
ALPACA_SECRET_KEY=your-alpaca-secret
NEXUS_ADMIN_TOKEN=use-a-long-random-private-token
NEXUS_MAX_ORDER_NOTIONAL=5000
NEXUS_MAX_ORDER_QTY=1000
NEXUS_AUTOTRADER_MAX_DAILY_TRADES=8
```

### 4. Install & Start
```bash
npm install
node server.js
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 5. Login
On the lock screen, enter `NEXUS_ADMIN_TOKEN`.

Alpaca and Anthropic keys stay server-side in `.env`. The browser stores only a short-lived session token in `sessionStorage`.

### 6. Switch from Paper to Live Trading
Edit `.env`, change the Alpaca base URL, and explicitly enable live orders:
```bash
# Paper (default — safe, simulated money)
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Live (real money — only when ready)
ALPACA_BASE_URL=https://api.alpaca.markets
NEXUS_ENABLE_LIVE_TRADING=true
```

Then restart: `node server.js`

> ⚠️ **Warning**: Live trading uses real money. Only switch when you understand the risks.

---

## Security & AutoTrader Persistence

- All `/api/*`, `/health`, and WebSocket connections require an authenticated server session.
- `NEXUS_ADMIN_TOKEN` is exchanged for a short-lived session token; broker/API keys are never sent to the browser.
- CORS and WebSocket origins are limited by `NEXUS_ALLOWED_ORIGINS`.
- Order creation is validated server-side: symbol, side, order type, qty/notional, max order size, and tradeability are checked before Alpaca receives the request.
- Live orders are blocked unless both `ALPACA_BASE_URL=https://api.alpaca.markets` and `NEXUS_ENABLE_LIVE_TRADING=true` are set.
- AutoTrader state persists to `data/autotrader-state.json`: enabled/config state, halt state, daily trade map, decision log, and daily trade history survive restarts.
- After each submitted BUY/SELL, the server refreshes Alpaca account and positions so buying power and open-position counts are updated before the next decision.

---

## File Structure

```
portfolio-nexus/
├── server.js          # Backend (Express + WebSocket + Alpaca proxy)
├── public/
│   └── index.html     # Frontend (single-file vanilla JS)
├── package.json
├── .env               # Your keys (never commit this)
├── .env.example       # Template
└── README.md
```

---

## API Endpoints

All endpoints except `POST /api/session` require `Authorization: Bearer <sessionToken>`.

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/session | Exchange `NEXUS_ADMIN_TOKEN` for a short-lived session token |

### Alpaca Proxy
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/alpaca/account | Account info (balance, equity, buying power) |
| GET | /api/alpaca/positions | Open positions |
| GET | /api/alpaca/orders | Orders (pass ?status=open or ?status=all) |
| POST | /api/alpaca/orders | Place new order |
| DELETE | /api/alpaca/orders/:id | Cancel order |
| GET | /api/alpaca/orders/:id | Get order status |
| GET | /api/alpaca/portfolio/history | Equity curve data |
| GET | /api/alpaca/assets/:symbol | Check if symbol is tradeable |
| GET | /api/alpaca/bars/:symbol | 30-day price bars |

### AI
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/chat | AI trading advisor (Italian) |
| POST | /api/screen | Stock screener (JSON output) |

### AutoTrader
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/autotrader/status | Current config, halt state, last log, today's persistent trade history |
| GET | /api/autotrader/history | Persistent daily trade history (`?date=YYYY-MM-DD`) |
| POST | /api/autotrader/config | Update persisted config and enable/disable engine |
| POST | /api/autotrader/run-now | Run a cycle immediately when enabled |

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/fx | FX rates (EUR, GBP, JPY, SEK, KRW, SGD vs USD) |
| GET | /health | Server health + Alpaca connection status |

### WebSocket
Connect to `ws://localhost:3000` — receives real-time messages:
- `{ type: 'quote', symbol, price, bid, ask }` — live price update
- `{ type: 'account', account }` — account update (every 5s)
- `{ type: 'positions', positions }` — positions update (every 5s)
- `{ type: 'trade_update', order }` — order status change

---

## Sections Overview

1. **Dashboard** — KPIs, allocation donut, portfolio history chart
2. **Equity Desk** — 15 non-mainstream stocks with live prices + AI analysis
3. **Trading** — Full Alpaca integration: positions, orders, new order form
4. **Heatmap** — Fundamental scoring grid (FCF, PE, PB, CR, Div)
5. **Watchdog** — 12 primary/backup pairs with alert monitoring
6. **Screener** — AI-powered fundamental/technical/quant analysis
7. **Macro** — Geographic signals, FX rates, geopolitical risks
8. **Trading Desk AI** — Multi-turn chat advisor with trade execution
9. **Allocatore** — Budget allocation by risk profile + execute orders
10. **Impostazioni** — Settings, API status, WebSocket health
