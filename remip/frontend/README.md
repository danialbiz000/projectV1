# REMIP Frontend (Milestone 4)

Next.js 14 (App Router) + React + TypeScript + Tailwind CSS + Recharts + MapLibre GL.

## Pagine

| Route | Contenuto |
|---|---|
| `/` | Landing page |
| `/register`, `/login` | Registrazione e accesso (JWT) |
| `/onboarding` | Scelta dell'obiettivo (compra/vendi/affitta/investi/monitora) |
| `/dashboard` | Dashboard di zona: selettore città/quartiere, KPI, variazioni multi-periodo, trend €/m², volumi, previsioni con scenari, blocco trasparenza fonti |
| `/listings` | Ricerca con filtri (contratto, tipologia, prezzo, locali), ordinamento e paginazione |
| `/listings/[id]` | Dettaglio: caratteristiche, stima a intervallo, storico prezzi, cronologia versioni con diff, comparabili, altri annunci per lo stesso immobile (dedup cross-agenzia, M4), aggiunta a watchlist |
| `/map` | Mappa interattiva: marker con popup, clustering, toggle heatmap €/m², disegno di un'area a mano libera e ricerca per raggio |
| `/watchlist` | Elementi osservati (annunci e zone) |
| `/notifications` | Centro notifiche con non lette, riepilogo digest per tipo (M4), filtro e "segna come letta" |

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

Nota: la pagina `/map` richiede accesso di rete in uscita per caricare le
tile OpenStreetMap e i font dei cluster (demo MapLibre); in ambienti senza
accesso a internet il basemap resta bianco ma marker, cluster, heatmap e
disegno di poligoni/raggio restano pienamente funzionanti (non dipendono
dalle tile — vedi `docs/ARCHITECTURE.md`).
