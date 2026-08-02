# REMIP — Real Estate Market Intelligence Platform

Piattaforma di market intelligence immobiliare per utenti privati: analisi di
zona, monitoraggio nel tempo, dettaglio immobili con storico e comparabili,
watchlist, notifiche e previsioni baseline con scenari.

> ⚠️ **La maggior parte dei dati è sintetica (demo).** Un'eccezione:
> `eurostat_hpi` è un adapter a dato **genuinamente live** (chiamata HTTP
> reale, nessun fallback a valori finti), **verificato con dati reali**
> (House Price Index italiano, 126 osservazioni, 2026-08-01 — vedi
> `docs/INTEGRATIONS.md`). Ogni risposta analitica dell'API dichiara
> `is_demo_data` nel blocco `data_context`; le fonti candidate non ancora
> integrate e i prerequisiti legali/commerciali sono in
> [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md).

**Stato: Milestone 6 completata** — backend (M1: API, modello dati, versionamento
annunci, notifiche, forecast baseline, seed demo, test) + frontend Next.js (M2:
landing, auth, onboarding, dashboard di zona con grafici, ricerca, dettaglio
immobile, watchlist, centro notifiche, dark/light) + mappa interattiva (M3:
MapLibre GL con marker, clustering, heatmap €/m², disegno poligoni e ricerca
per raggio) + ingestion asincrona (M4: job queue RQ/Redis + scheduler
APScheduler, adapter open data OMI-shaped, **adapter Eurostat a dato live**
(House Price Index, chiamata HTTP reale senza fallback sintetico),
deduplicazione cross-agenzia con confidence, snapshot annunci su object
storage, digest notifiche) + confronti, valutazioni e admin esteso (M5:
valutazione persistita con intervallo (`/listings/{id}/valuations`), motore di
spiegazione driver del trend (`/market/explanation`, correlazioni dichiarate
non causalità), confronto annunci (`/compare`) e zone (dashboard), preferenze
notifiche per tipo, pagina `/admin` — utenti, fonti dati, job di ingestion) +
hardening (M6: verifica email e reset password, rate limiting distribuito su
login/registrazione/reset, login OAuth2 generico — nessun provider reale
configurato, vedi sotto —, export/cancellazione account GDPR, metriche
Prometheus su `/metrics`, backup on-demand del database, guida al deployment
cloud non eseguita in questo ambiente). Prossima: nessuna milestone
ulteriore ancora pianificata (roadmap: [`docs/PLAN.md`](docs/PLAN.md)).

## Documentazione

| File | Contenuto |
|---|---|
| [`docs/PLAN.md`](docs/PLAN.md) | Analisi, assunzioni, rischi, roadmap, backlog, costi |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architettura, diagrammi Mermaid, API, strategia test/deploy |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | ER e dizionario dati |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | Fonti esterne: stato e autorizzazioni necessarie |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Guida al deployment cloud (M6, non eseguita in questo ambiente) |

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

## Avvio con Docker Compose (PostgreSQL + PostGIS + Redis + MinIO + worker + scheduler)

```bash
cd remip
cp .env.example .env        # poi imposta REMIP_SECRET_KEY (openssl rand -hex 32)
docker compose up --build
```

Oltre a `db`/`backend`/`frontend`, avvia `redis` (coda ingestion), `minio`
(snapshot annunci) e i processi `worker`/`scheduler` che eseguono l'adapter
OMI periodicamente. Nessuno di questi è obbligatorio per lo sviluppo rapido:
avviando solo `uvicorn app.main:app` (senza Docker), l'ingestion e gli
snapshot funzionano comunque — l'ingestion gira in-process se Redis non è
raggiungibile e gli snapshot si scrivono su disco locale se S3 non è
configurato (vedi `docs/ARCHITECTURE.md`).

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
ADMIN_TOKEN=$(curl -s localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"demo1234"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

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
# 4c. Quotazioni OMI per zona (struttura reale, valori dimostrativi — M4)
curl -s "localhost:8000/api/v1/market/omi-quotations?area_id=<AREA_ID>"
# 4d. Indicatore Eurostat live (House Price Index) — vuoto finché l'ingestion
#     non è riuscita almeno una volta (nessun fallback a valori finti)
curl -s "localhost:8000/api/v1/market/economic-indicators?country=IT"
# 5. Simulare una variazione (admin) → nuova versione + notifica ai watcher
curl -s -X POST localhost:8000/api/v1/admin/simulate/listing-update \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H 'Content-Type: application/json' \
  -d '{"listing_id":"<LISTING_ID>","changes":{"price":250000}}'
# 6. Stato ingestion e trigger manuale (admin) — M4
curl -s localhost:8000/api/v1/admin/ingestion/jobs -H "Authorization: Bearer $ADMIN_TOKEN"
curl -s -X POST localhost:8000/api/v1/admin/ingestion/run/omi_it -H "Authorization: Bearer $ADMIN_TOKEN"
# 6b. Trigger dell'adapter live: in un ambiente con internet reale popola
#     economic-indicators; qui in sandbox fallisce onestamente (403 di rete)
curl -s -X POST localhost:8000/api/v1/admin/ingestion/run/eurostat_hpi -H "Authorization: Bearer $ADMIN_TOKEN"
# 7. Valutazione persistita, confronti e spiegazione del trend — M5
curl -s -X POST localhost:8000/api/v1/listings/<LISTING_ID>/valuations -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/api/v1/listings/compare -H 'Content-Type: application/json' \
  -d '{"listing_ids":["<ID1>","<ID2>"]}'
curl -s "localhost:8000/api/v1/market/compare-areas?area_ids=<AREA_ID1>&area_ids=<AREA_ID2>"
curl -s "localhost:8000/api/v1/market/explanation?area_id=<AREA_ID>"
# 8. Preferenze notifiche e amministrazione utenti/fonti — M5
curl -s -X PUT localhost:8000/api/v1/notifications/preferences -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"frequency":"instant","muted_types":["photos_change"]}'
curl -s localhost:8000/api/v1/admin/users -H "Authorization: Bearer $ADMIN_TOKEN"
# 9. Verifica email, reset password (in demo_mode il token torna nella
#    risposta invece di essere solo "inviato" — mai così in produzione) — M6
curl -s -X POST localhost:8000/api/v1/auth/verify-email/request -H "Authorization: Bearer $TOKEN"
curl -s -X POST localhost:8000/api/v1/auth/forgot-password -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com"}'
# 10. Provider OAuth configurati (vuoto di default — nessuna credenziale reale) — M6
curl -s localhost:8000/api/v1/auth/oauth/providers
# 11. Esporta/elimina i propri dati (GDPR) — M6
curl -s localhost:8000/api/v1/users/me/export -H "Authorization: Bearer $TOKEN"
# 12. Metriche Prometheus e backup on-demand (admin) — M6
curl -s localhost:8000/metrics
curl -s -X POST localhost:8000/api/v1/admin/backup -H "Authorization: Bearer $ADMIN_TOKEN"
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
parametrizzato, CORS esplicito, isolamento dati utente coperto da test. Gli
endpoint di ingestion (trigger e log job) sono riservati al ruolo admin; il
kill-switch `enabled=false` di una fonte blocca l'esecuzione schedulata.
Nessun segreto nel repository: configurazione via `.env` (vedi `.env.example`).
**M6**: rate limiting su login/registrazione/reset password (Redis con
fallback in-memory per-processo, vedi `docs/DEPLOYMENT.md` §7 per il limite
in scenari multi-replica); token di verifica email/reset password hashati
(mai il valore grezzo persistito) e single-use; risposta identica a
`/auth/forgot-password` che esista o meno l'email (nessuna enumerazione
account); `/metrics` non autenticato per design (da restringere a livello
di rete in produzione, non applicativo).

## Limitazioni note

- Dati esclusivamente sintetici o illustrativi; le stime/previsioni sono
  dimostrative e non costituiscono consulenza finanziaria.
- Schema creato con `create_all`, non ancora con migrazioni Alembic — gap
  esplicito e bloccante prima di un database di produzione con dati reali,
  vedi `docs/DEPLOYMENT.md` §2 e §8.
- Notifiche solo in-app (con digest riassuntivo in-app da M4); l'invio email
  reale (verifica/reset password, M6) richiede SMTP configurato — senza,
  `services/email.py` usa un adapter console (solo log), nessuna email
  arriva davvero a nessuno (vedi sotto).
- **Mappa (M3)**: i filtri per raggio/poligono girano in Python (portabili tra
  SQLite e PostgreSQL) invece che con query PostGIS indicizzate — vedi
  `docs/ARCHITECTURE.md`; l'estensione PostGIS è comunque abilitata e pronta
  per M4+. Le tile di base (OpenStreetMap) e i font dei cluster (demo MapLibre)
  sono servizi pubblici a basso volume, non adatti a traffico di produzione
  senza un provider a licenza (vedi `docs/INTEGRATIONS.md`); richiedono
  accesso di rete in uscita per il rendering della mappa. Nessun dato di
  confine amministrativo reale (solo marker/cluster/heatmap di annunci).
  Ricerca per indirizzo libero (geocoding) non ancora implementata.
- **Ingestion (M4)**: l'adapter OMI legge da una fixture locale versionata,
  non da un endpoint live verificato (vedi `docs/INTEGRATIONS.md`) — la
  pipeline (coda, scheduler, dedup/upsert, tracciamento job) è reale, i
  *valori* delle quotazioni sono dimostrativi. L'adapter Eurostat
  (`eurostat_hpi`) fa invece una chiamata HTTP reale senza alcun fallback:
  in ambienti con rete in uscita bloccata (come il sandbox di sviluppo — 403
  anche verso host generici) l'ingestion fallisce onestamente e
  `/market/economic-indicators` resta vuoto. **Verificato funzionante con
  dati reali** dall'utente in un ambiente con internet normale
  (2026-08-01): 126 osservazioni ingerite, indice House Price Index IT
  2010→2026 corretto e incrociato con la variazione annua dichiarata.
  `SavedSearch`/`AlertRule` e digest via email restano V2/M6.
- **Confronti e valutazioni (M5)**: `NotificationPreference.frequency`
  (`daily_digest`/`weekly_digest`) è persistita e restituita dall'API ma non
  ancora applicata da un job di invio raggruppato — solo `muted_types` è già
  rispettato in tempo reale da `services/notifications.py` (il digest per
  frequenza — `daily_digest`/`weekly_digest` — resta da implementare, nessuna
  milestone ancora assegnata). La valutazione persistita richiede almeno 3
  comparabili nella stessa area — sotto soglia l'endpoint risponde 422
  invece di restituire un numero non fondato.
- **Hardening (M6)**: nessun provider OAuth reale è configurato in questo
  deployment (`GET /auth/oauth/providers` torna vuoto) — il codice di scambio
  authorization-code→token→userinfo è reale ma verificato nei test contro un
  provider HTTP mock, non contro Google live, per lo stesso motivo per cui
  l'adapter Eurostat è verificato così quando la rete non è raggiungibile.
  Nessun SMTP reale configurato: verifica email e reset password funzionano
  end-to-end (in `demo_mode` il token torna nella risposta API, mai in
  produzione) ma non recapitano un'email reale finché non si imposta
  `REMIP_SMTP_HOST` e le altre variabili SMTP. Le metriche `/metrics` e il
  rate limiter in-memory sono per-processo, non aggregati tra repliche senza
  Redis condiviso (`docs/DEPLOYMENT.md` §7). Nessun deployment cloud è stato
  eseguito in questo ambiente (nessun accesso di rete/cloud) — vedi
  `docs/DEPLOYMENT.md` per la guida non verificata e l'elenco esplicito dei
  gap pre-produzione (§8), incluse le migrazioni Alembic ancora mancanti.
