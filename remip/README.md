# REMIP — Real Estate Market Intelligence Platform

Piattaforma di market intelligence immobiliare per utenti privati: analisi di
zona, monitoraggio nel tempo, dettaglio immobili con storico e comparabili,
watchlist, notifiche e previsioni baseline con scenari.

> ⚠️ **Tutti i dati sono sintetici (demo).** Nessuna fonte reale è integrata:
> le fonti candidate e i prerequisiti legali/commerciali sono in
> [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md). Ogni risposta analitica
> dell'API dichiara `is_demo_data: true` nel blocco `data_context`.

**Stato: Milestone 3 completata** — backend (M1: API, modello dati, versionamento
annunci, notifiche, forecast baseline, seed demo, test) + frontend Next.js (M2:
landing, auth, onboarding, dashboard di zona con grafici, ricerca, dettaglio
immobile, watchlist, centro notifiche, dark/light) + mappa interattiva (M3:
MapLibre GL con marker, clustering, heatmap €/m², disegno poligoni e ricerca
per raggio, E2E Playwright). Prossima: ingestion asincrona reale in
Milestone 4 (roadmap: [`docs/PLAN.md`](docs/PLAN.md)).

## Documentazione

| File | Contenuto |
|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | Analisi, assunzioni, rischi, roadmap, backlog, costi |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architettura, diagrammi Mermaid, API, strategia test/deploy |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | ER e dizionario dati |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | Fonti esterne: stato e autorizzazioni necessarie |

## Avvio rapido (senza Docker — SQLite)

```bash
# Backend (terminale 1)
cd remip/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (terminale 2)
cd remip/frontend
npm install
npm run dev
```

Al primo avvio il database viene creato e popolato con i dati demo
(3 città, 9 quartieri, ~100 annunci, 36 mesi di metriche, previsioni).
App: <http://localhost:3000> — API interattive: <http://localhost:8000/docs> —
health: <http://localhost:8000/health>.

## Avvio con Docker Compose (PostgreSQL + PostGIS + Redis)

```bash
cd remip
cp .env.example .env        # poi imposta REMIP_SECRET_KEY (openssl rand -hex 32)
docker compose up --build
```

## Credenziali demo (solo sviluppo, create dal seed)

| Utente | Email | Password | Ruolo |
|---|---|---|---|
| Demo | `demo@example.com` | `demo1234` | user |
| Admin | `admin@example.com` | `demo1234` | admin |

## Percorso di prova in 2 minuti (via `/docs` o curl)

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"demo1234"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 1. Zone disponibili e dashboard di zona
curl -s "localhost:8000/api/v1/geo/areas?level=city"
curl -s "localhost:8000/api/v1/market/summary?area_id=<AREA_ID>"
# 2. Ricerca immobili con filtri, dettaglio con storico e comparabili
curl -s "localhost:8000/api/v1/listings?area_id=<AREA_ID>&max_price=400000&sort_by=price"
curl -s "localhost:8000/api/v1/listings/<LISTING_ID>"
# 3. Watchlist e notifiche
curl -s localhost:8000/api/v1/watchlists -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/api/v1/notifications -H "Authorization: Bearer $TOKEN"
# 4. Previsioni con scenari e trasparenza
curl -s "localhost:8000/api/v1/market/forecast?area_id=<AREA_ID>"
# 4b. Ricerca sulla mappa per raggio (2km) o poligono disegnato
curl -s -X POST localhost:8000/api/v1/map/search -H 'Content-Type: application/json' \
  -d '{"radius":{"lat":45.4642,"lon":9.19,"radius_km":2},"limit":100}'
# 5. Simulare una variazione (admin) → nuova versione + notifica ai watcher
curl -s -X POST localhost:8000/api/v1/admin/simulate/listing-update \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"listing_id":"<LISTING_ID>","changes":{"price":250000}}'
```

## Qualità

```bash
# Backend
cd remip/backend
ruff check app tests      # lint
mypy app                  # type checking
pytest -q                 # test (SQLite in-memory, seed ridotto)

# Frontend
cd remip/frontend
npm run lint && npm run typecheck && npm run build
npm run e2e               # E2E Playwright (avvia backend + app buildata)
```

## Sicurezza

JWT con scadenza, hashing PBKDF2-HMAC-SHA256 (salt per utente, formato
migrabile), ruoli user/admin, audit log, validazione Pydantic, ORM
parametrizzato, CORS esplicito, isolamento dati utente coperto da test.
Nessun segreto nel repository: configurazione via `.env` (vedi `.env.example`).

## Limitazioni note

- Dati esclusivamente sintetici; le stime/previsioni sono dimostrative e non
  costituiscono consulenza finanziaria.
- Schema creato con `create_all` (migrazioni Alembic da M2).
- Notifiche solo in-app; email/push da M6. Rate limiting distribuito da M6.
- **Mappa (M3)**: i filtri per raggio/poligono girano in Python (portabili tra
  SQLite e PostgreSQL) invece che con query PostGIS indicizzate — vedi
  `docs/ARCHITECTURE.md`; l'estensione PostGIS è comunque abilitata e pronta
  per M4+. Le tile di base (OpenStreetMap) e i font dei cluster (demo MapLibre)
  sono servizi pubblici a basso volume, non adatti a traffico di produzione
  senza un provider a licenza (vedi `docs/INTEGRATIONS.md`); richiedono
  accesso di rete in uscita per il rendering della mappa. Nessun dato di
  confine amministrativo reale (solo marker/cluster/heatmap di annunci).
  Ricerca per indirizzo libero (geocoding) non ancora implementata.
