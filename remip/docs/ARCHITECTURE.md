# REMIP — Architettura

Monolite modulare (vedi `PLAN.md` §6 per le alternative valutate e la motivazione).

## Componenti

```mermaid
flowchart LR
    subgraph Client
        FE[Next.js Frontend<br/>M2]
        MAP[MapLibre GL<br/>marker/cluster/heatmap/draw — M3]
    end
    subgraph Backend["FastAPI (monolite modulare)"]
        API[API v1<br/>REST + OpenAPI]
        AUTH[Auth & Roles]
        GEO[Geo Module]
        MAPI[Map Search<br/>bbox/raggio/poligono — M3]
        LST[Listings & Versioning]
        MKT[Market Analytics]
        FC[Forecast Baseline]
        WL[Watchlist]
        NTF[Notifications]
        ADM[Admin]
    end
    subgraph Ingestion["Data Ingestion (adapter framework)"]
        BASE[BaseAdapter<br/>validate/normalize/dedup/retry/rate-limit]
        DEMO[DemoAdapter<br/>dati sintetici IT — seed-time]
        OMI[OmiAdapter<br/>M4 — struttura OMI reale, valori da fixture]
        EURO[EurostatHpiAdapter<br/>M4 — chiamata HTTP reale, nessun fallback]
        PORTAL[Portal Adapter<br/>solo interfaccia — richiede accordo]
    end
    subgraph Async["Job queue (M4)"]
        SCHED[Scheduler<br/>APScheduler, periodico]
        QUEUE[(Redis Queue)]
        WORKER[RQ Worker]
    end
    subgraph Storage
        PG[(PostgreSQL + PostGIS)]
        RD[(Redis<br/>cache + code)]
        S3[(S3/MinIO<br/>snapshot annunci — M4)]
    end
    subgraph External["Internet (M4)"]
        EUROSTAT[[Eurostat API pubblica<br/>nessuna chiave]]
    end
    FE -->|HTTPS JSON| API
    MAP -->|HTTPS JSON| API
    API --> AUTH & GEO & MAPI & LST & MKT & FC & WL & NTF & ADM
    ADM -.->|trigger manuale| QUEUE
    SCHED -->|enqueue per provider abilitato| QUEUE
    QUEUE --> WORKER
    WORKER --> BASE
    BASE --> DEMO & OMI & EURO & PORTAL
    DEMO -->|seed/update| LST
    OMI -->|upsert dedup| PG
    EURO -->|HTTPS GET| EUROSTAT
    EURO -->|upsert, o nessuna riga se il fetch fallisce| PG
    LST -->|snapshot versione| S3
    Backend --> PG
    Backend --> RD
    SCHED --> RD
    WORKER --> RD
```

## Flusso dei dati (aggiornamento annuncio → notifica)

```mermaid
sequenceDiagram
    participant SRC as Fonte (adapter)
    participant ING as Ingestion Service
    participant DB as PostgreSQL
    participant VER as Versioning Service
    participant NTF as Notification Service
    participant U as Utente

    SRC->>ING: raw listing (source_id, external_id, payload)
    ING->>ING: validate + normalize + dedup (confidence score)
    ING->>DB: upsert PhysicalProperty / PropertyListing
    ING->>VER: apply_update(listing, changes)
    VER->>DB: nuova ListingVersion (diff vs precedente)
    VER->>DB: PriceObservation (se prezzo variato)
    VER->>NTF: evento (price_drop, removed, relisted, …)
    NTF->>DB: Notification (dedup_key, per utenti con watchlist match)
    U->>DB: GET /notifications (in-app)
```

## Moduli e confini

Regole del monolite modulare:
1. i router API dipendono da `services/`/`jobs/`, mai l'inverso;
2. `adapters/` scrive solo tramite i servizi di ingestion (`jobs/ingestion.py`)/versioning, mai SQL diretto sui modelli di altri moduli;
3. eventi applicativi (notifiche via NotificationService; ingestion via coda Redis/RQ da M4) sono gli unici canali asincroni — nessun altro broker introdotto.

## API (v1, prefisso `/api/v1`)

| Area | Endpoint principali |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/verify-email/request`\|`confirm`, `POST /auth/forgot-password`, `POST /auth/reset-password` (M6, rate-limited — `core/rate_limit.py`) |
| OAuth | `GET /auth/oauth/providers`, `GET /auth/oauth/{provider}/authorize`, `GET /auth/oauth/{provider}/callback` (M6 — vuoto/404 finché nessun provider è configurato, vedi `services/oauth.py`) |
| Geo | `GET /geo/countries`, `GET /geo/areas` (filtri country/level/parent/q), `GET /geo/areas/{id}` |
| Listings | `GET /listings` (filtri, paginazione, sort), `GET /listings/{id}`, `GET /listings/{id}/history`, `GET /listings/{id}/comparables`, `GET /listings/{id}/versions/{n}/snapshot` (M4), `POST`/`GET /listings/{id}/valuations` (stima persistita, M5), `POST /listings/compare` (2-4 annunci, M5 — ora include `price_trend`/`market_score` per zona, M7), `GET /listings/{id}/floorplan` (pianta generata algoritmicamente, illustrativa, M7) |
| Market | `GET /market/metrics` (serie storica per area), `GET /market/summary` (KPI + variazioni 1/3/6/12m,5y), `GET /market/forecast`, `GET /market/omi-quotations` (bande OMI per zona, M4), `GET /market/economic-indicators` (indicatori live Eurostat, M4), `GET /market/compare-areas` (2-4 aree, M5 — ora include `price_trend`/`market_score` per riga, M7), `GET /market/explanation` (motore driver, M5 — ora include `market_score`, M7) |
| Watchlist | CRUD `/watchlists`, `/watchlists/{id}/items` |
| Notifications | `GET /notifications`, `GET /notifications/digest` (M4), `POST /notifications/{id}/read`, `POST /notifications/read-all`, `GET`/`PUT /notifications/preferences` (frequenza + tipi silenziati, M5) |
| Users | `GET /users/me/export` (export dati, GDPR art. 20, M6), `DELETE /users/me` (cancellazione/anonimizzazione, GDPR art. 17, M6) |
| Sources | `GET /sources` (provider, ToS, qualità, is_demo) |
| Admin | `GET /admin/stats`, `POST /admin/simulate/listing-update` (motore demo variazioni), `POST /admin/ingestion/run/{provider_code}`, `GET /admin/ingestion/jobs` (M4), `GET /admin/users`, `POST /admin/users/{id}/deactivate`\|`reactivate` (M5), `POST /admin/sources/{code}/toggle` (kill-switch ToS, M5), `POST /admin/backup` (M6, storage — nessun restore automatico) |
| Map | `POST /map/search` (marker per bbox/raggio/poligono), `GET /map/areas-geo` (centroidi per livello amministrativo) |
| Health | `GET /health`, `GET /metrics` (Prometheus text format, M6 — per-processo, non autenticato: da restringere a livello di rete in produzione, vedi `docs/DEPLOYMENT.md`) |

Convenzioni: paginazione `limit/offset` con `total`; errori JSON uniformi
(`{"detail": ...}`); ogni risposta analitica include il blocco `data_context`
(source, period, observations, updated_at, quality, limitations, is_demo_data).

## Mappa e ricerca geospaziale (M3)

**Filtri spaziali in Python, non in SQL PostGIS.** `POST /map/search` applica
bounding-box, raggio e poligono disegnato a mano interamente in
`services/geo.py` (haversine + ray-casting PNPOLY), con un pre-filtro SQL sulla
bounding box per limitare i candidati prima del test esatto. Motivazione:
questa logica deve funzionare identica su SQLite (dev/test locale, come da
M1) e su PostgreSQL (compose) — query `ST_DWithin`/`ST_Contains` esisterebbero
solo su Postgres, spezzando l'avvio locale "zero servizi esterni" descritto
nel README. L'estensione PostGIS viene comunque abilitata all'avvio quando il
dialetto è PostgreSQL (`db/base.py::ensure_postgis`), così lo schema è pronto
per colonne geometry indicizzate quando il volume di annunci lo giustificherà
(M4+): a quel punto la sostituzione è isolata a `services/geo.py`, senza
toccare i router.

**Rendering mappa**: MapLibre GL con marker, clustering (nativo, via
supercluster integrato) e layer heatmap (nativo, pesato su `price_per_sqm`),
poligono disegnato a mano e cerchio di ricerca per raggio renderizzati come
overlay GeoJSON. Le tile di base sono raster OpenStreetMap pubbliche, a basso
volume, solo per la demo — vedi `docs/INTEGRATIONS.md` per i vincoli di ToS e
il provider da adottare prima di traffico in produzione.

## Ingestion asincrona, dedup e snapshot (M4)

**Job queue con fallback senza servizi esterni.** `POST /admin/ingestion/run/{provider}`
e lo scheduler passano da `jobs/ingestion.py::enqueue_or_run_ingestion`, che
prova a mettere in coda su Redis/RQ e, se Redis non è raggiungibile (`ping()`
fallisce), esegue l'ingestion **in-process nella stessa richiesta** invece di
fallire. Questo significa che l'ingestion funziona sia con `docker compose up`
(worker+scheduler dedicati) sia con il solo `uvicorn` locale su SQLite senza
Redis — coerente con l'obiettivo "avviabile in locale senza servizi esterni"
di M1. Verificato con un test dedicato che forza una connessione Redis non
raggiungibile e osserva il fallback (`test_ingestion_jobs.py`).

**Ogni job è tracciato**: `DataIngestionJob` registra provider, trigger
(seed/manual/scheduled), stato, conteggi (fetched/created/updated) ed errori —
consultabile via `GET /admin/ingestion/jobs`. Il bootstrap del seed esegue
l'adapter OMI una volta in-process (`trigger="seed"`) così un'installazione
pulita ha già dati senza dover avviare `worker`/`scheduler` separatamente; in
compose lo scheduler la ri-esegue periodicamente (`REMIP_INGESTION_INTERVAL_MINUTES`,
default 360) con upsert per chiave naturale (nessun duplicato a ogni run).

**Adapter OMI-shaped**: `adapters/omi.py` riproduce la struttura reale delle
quotazioni OMI (comune/zona/tipologia/stato conservativo, bande min-max €/m²
per compravendite e locazioni, per semestre) — dato aggregato di zona, non per
singolo annuncio, coerente con l'assunzione A2 del piano. `fetch_raw()` legge
una fixture locale versionata anziché un endpoint live: questo ambiente non
può verificare una connessione OMI/ISTAT reale (rete esterna non raggiungibile
in sandbox; OMI distribuisce comunque CSV/Excel, non una API REST
convenzionale). La pipeline downstream (validate → normalize → risoluzione
area interna per nome comune/zona → upsert dedup) è realistica e testata; solo
i *valori* sono dimostrativi (`is_demo_data: true` in ogni risposta). Vedi
`docs/INTEGRATIONS.md`.

**Adapter Eurostat — dato genuinamente live**: `adapters/eurostat.py` fa una
chiamata HTTP reale all'API pubblica di dissemination Eurostat (dataset
`prc_hpi_q`, House Price Index trimestrale, nessuna chiave richiesta) per
l'Italia. A differenza di OMI, **non c'è nessun fallback a valori sintetici**:
se la richiesta fallisce, `BaseAdapter` esaurisce i retry con backoff
esponenziale e solleva `AdapterError`, che `jobs/ingestion.py` trasforma in un
`DataIngestionJob` con `status="failed"` e il messaggio d'errore reale — nessuna
riga viene scritta. Il parser SDMX-JSON (`parse_sdmx_json`) è deliberatamente
generico: deriva l'ordine delle dimensioni e i codici categoria dai campi
`id`/`size`/`dimension` della risposta stessa anziché assumerne posizioni
fisse, così resta corretto anche se i codici esatti di filtro/unità
differiscono da quanto documentato. Non eseguito al bootstrap del seed (a
differenza di OMI) per non richiedere rete in uscita all'avvio locale — parte
solo su trigger admin o scheduler.

Verificato in due modi complementari: (1) `tests/test_eurostat_adapter.py`
testa il parser SDMX-JSON contro un campione costruito a mano e verificato
matematicamente (deterministico, nessuna rete); (2) lo stesso file include un
test che esegue la chiamata HTTP *reale* e usa `pytest.skip()` (non un fail)
quando la rete non è raggiungibile — in questo sandbox (proxy che nega
esplicitamente l'accesso a host esterni, verificato anche su `example.com`)
il test si skippa con l'errore reale come motivo; in qualunque ambiente con
accesso a internet vero (inclusa la CI di GitHub Actions) verifica per
davvero la chiamata live. Provato manualmente end-to-end in questo ambiente:
`POST /admin/ingestion/run/eurostat_hpi` produce onestamente un job
`status="failed", error_message="403 Forbidden"` e
`GET /market/economic-indicators` resta vuoto — nessun dato inventato.
**Verificato con successo dall'utente in un ambiente con internet reale
(2026-08-01)**: job `status="success"`, 126 osservazioni, `I15_Q`/`RCH_A`
decodificati correttamente e cross-validati a mano (variazione annua
2026-Q1 calcolata dall'indice = 5.2%, combacia col valore `RCH_A`
restituito) — la pipeline live è confermata funzionante contro Eurostat
reale, non solo in teoria.

**Deduplicazione cross-agenzia**: `services/dedup.py` assegna un punteggio di
confidenza (distanza geografica, similarità superficie/locali, sovrapposizione
testuale dell'indirizzo) per decidere se un nuovo annuncio descrive un
immobile fisico già noto. Il seed demo genera deliberatamente un sottoinsieme
di annunci "ripubblicati" da una seconda agenzia, instradati attraverso questo
servizio, così `PropertyListing.dedup_confidence` riflette un punteggio reale
e non un valore fittizio — verificabile in `/listings/{id}` tramite
`duplicate_listings`.

**Snapshot su object storage**: ogni `ListingVersion` (creazione o
aggiornamento) salva il payload grezzo su storage S3-compatibile
(`services/storage.py`) e registra la chiave in `snapshot_key`. Senza
`REMIP_S3_ENDPOINT_URL` configurato, lo storage scrive su disco locale
(`snapshot_local_dir`) invece di richiedere MinIO — stesso principio di
fallback del job queue. Recuperabile via
`GET /listings/{id}/versions/{n}/snapshot`.

## Confronto avanzato e pianta generata (M7)

**Nessuna nuova tabella o migrazione**: entrambe le funzionalità M7 sono
servizi puramente computazionali, eseguiti on-demand sui dati già persistiti
(`MarketMetric`, `PhysicalProperty`) e mai scritti su disco.

**`services/zone_quality.py` — indicatore di mercato della zona**: riusa la
stessa classificazione dei driver del motore di spiegazione M5
(`services/explanation.py`, correlazioni non causalità) e pesa i driver
positivi/negativi (`{"weak": 8, "moderate": 16}`) attorno a una base di 50,
saturato a [0,100]. **Non è un punteggio di vivibilità/sicurezza/scuole** —
nessun dataset di quel tipo è integrato in questo ambiente — ma un'etichetta
derivata dall'andamento dei prezzi della zona. Esposto sia in
`GET /market/explanation` sia nelle righe di `POST /listings/compare` e
`GET /market/compare-areas` insieme a `price_trend` (serie `€/m²` a 24 mesi
per zona, `services/market.py:price_trend_and_score`), usato dal frontend
per il grafico a linee in `/compare`.

**`services/floorplan.py` — pianta illustrativa generata**: algoritmo
deterministico di partizione ricorsiva del rettangolo (slice-and-dice,
alternando tagli orizzontali/verticali) proporzionale alla quota di area di
ogni vano, calcolata da `rooms`/`bathrooms`/`size_sqm`/`property_type` già
presenti su `Property` — nessun campo o migrazione nuovi. Stesso input →
stesso output (nessuna casualità). Esposto da
`GET /listings/{id}/floorplan`; il frontend la mostra come SVG con una
didascalia permanente "pianta generata, non è la planimetria reale".

## Strategia di testing

- **Unit**: servizi (versioning diff, forecast, comparables, geo, dedup) — pytest.
- **Integration/API**: TestClient httpx su SQLite in-memory, seed ridotto deterministico.
- **Sicurezza base**: isolamento utenti, accesso admin, token invalidi.
- **E2E**: Playwright da M2 (frontend), incluse le interazioni mappa da M3.
- **Geospaziali**: filtri raggio/poligono testati contro SQLite (portabili su Postgres, vedi sopra); PostGIS reale in compose non eseguito nella suite automatica.
- **Ingestion (M4)**: adapter OMI (fetch/validate/normalize/determinismo), adapter Eurostat (parser SDMX-JSON deterministico + un test a chiamata reale che si skippa se la rete non è raggiungibile, non un mock), job (provider sconosciuto/disabilitato/force, upsert idempotente per entrambi gli adapter, persistenza `DataIngestionJob`), fallback coda→inline con Redis reale non raggiungibile (test dedicato, non un mock).
- **Storage (M4)**: percorso disco locale eseguito realmente; percorso S3 verificato contro un client boto3 mockato (nessun MinIO richiesto in CI).
- **Auth estesa (M6)**: verifica email/reset password end-to-end (token emesso → consumato → single-use verificato), rate limiting (unit test diretti su `core/rate_limit.py`, non tramite l'app, per usare limiti bassi senza disturbare il resto della suite — vedi `tests/conftest.py`), OAuth verificato contro un provider HTTP mock (non Google live, stesso approccio di Eurostat), backup verificato contro un file SQLite temporaneo reale (non il DB in-memory dei test, che non ha un file da copiare — quel caso è invece il test del 400 onesto).
- **Migrazioni (M6)**: `alembic upgrade head` verificato contro un file SQLite temporaneo reale (non il DB in-memory condiviso dagli altri test), con assert che l'insieme di tabelle prodotto combaci esattamente con `Base.metadata` — più il downgrade completo (`tests/test_migrations.py`). Non verificato contro PostgreSQL (nessuna istanza raggiungibile in questo ambiente).
- CI (GitHub Actions): ruff → mypy → pytest su ogni push.

## Strategia di deployment

- Dev: `docker compose up` (Postgres+PostGIS, Redis, MinIO, backend, worker, scheduler, frontend) oppure backend standalone su SQLite (ingestion e storage funzionano comunque, vedi sopra).
- Ambienti separati via `.env` (mai committati); `.env.example` come contratto.
- Prod: guida completa in `docs/DEPLOYMENT.md` (M6) — non eseguita in questo
  ambiente (nessun accesso cloud/rete), ma con passi concreti: migrazioni
  Alembic come step esplicito pre-deploy (`docker compose --profile tools
  run --rm migrate`, M6 — vedi sotto), Docker Compose su una VM dietro
  reverse proxy TLS, checklist di variabili d'ambiente obbligatorie, backup
  on-demand (`POST /admin/backup`, M6) con restore manuale documentato,
  note su scalabilità (rate limiting e metriche sono per-processo senza
  Redis condiviso) e gap noti (lock distribuito per lo scheduler,
  credenziali SMTP/OAuth reali — richiedono un account presso un provider
  terzo, non ottenibili dal codice).

## Sicurezza e privacy (implementato in M1 / pianificato)

M1: JWT HS256 con scadenza, PBKDF2-HMAC-SHA256 (210k iterazioni, salt per utente,
formato hash auto-descrittivo → migrabile ad argon2), ruoli user/admin, audit log,
validazione input Pydantic, ORM parametrizzato (no injection), CORS esplicito,
nessun segreto nel repo, dati demo privi di persone reali.
M4: trigger di ingestion e log job riservati al ruolo admin; il kill-switch
`enabled=False` di un provider blocca l'esecuzione schedulata (bypassabile solo
esplicitamente da admin con `force=True`); nessuna credenziale S3/Redis hardcoded
(da `.env`).
M6: rate limiting distribuito su login/registrazione/reset (Redis con
fallback in-memory, `core/rate_limit.py`), verifica email e reset password
(token hash single-use con scadenza, mai il valore grezzo persistito —
`services/auth_tokens.py`), login OAuth2 generico disattivato finché non
configurato con credenziali reali (`services/oauth.py`),
export/cancellazione account (GDPR art. 20/17 — `api/v1/users.py`),
migrazioni Alembic con storia versionata dello schema (`backend/alembic/`,
baseline M1-M6, vedi `docs/DEPLOYMENT.md` §3).
Ancora pianificato: dependency/secret scanning in CI, retention policy,
consensi granulari (cookie/marketing) — vedi `docs/DEPLOYMENT.md` §10 per
l'elenco completo dei gap pre-produzione (in gran parte credenziali reali
da provider terzi, non codice mancante).
