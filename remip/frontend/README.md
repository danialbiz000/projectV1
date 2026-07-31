# REMIP Frontend (Milestone 2)

Next.js 14 (App Router) + React + TypeScript + Tailwind CSS + Recharts.
La mappa interattiva (MapLibre GL) arriva con la Milestone 3.

## Pagine

| Route | Contenuto |
|---|---|
| `/` | Landing page |
| `/register`, `/login` | Registrazione e accesso (JWT) |
| `/onboarding` | Scelta dell'obiettivo (compra/vendi/affitta/investi/monitora) |
| `/dashboard` | Dashboard di zona: selettore città/quartiere, KPI, variazioni multi-periodo, trend €/m², volumi, previsioni con scenari, blocco trasparenza fonti |
| `/listings` | Ricerca con filtri (contratto, tipologia, prezzo, locali), ordinamento e paginazione |
| `/listings/[id]` | Dettaglio: caratteristiche, stima a intervallo, storico prezzi, cronologia versioni con diff, comparabili, aggiunta a watchlist |
| `/watchlist` | Elementi osservati (annunci e zone) |
| `/notifications` | Centro notifiche con non lette, filtro e "segna come letta" |

Dark/light mode (toggle + `prefers-color-scheme`), layout responsive mobile-first,
form etichettati e ruoli ARIA per l'accessibilità. Il badge "Dati demo" è sempre
visibile nella barra di navigazione.

## Sviluppo

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL (default http://localhost:8000)
npm run dev                  # richiede il backend attivo
```

## Qualità

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # eslint
npm run build       # build di produzione
npm run e2e         # Playwright: avvia backend (SQLite dedicato) + app buildata
```

Per l'E2E in ambienti con Chromium preinstallato:
`PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium npm run e2e`.
