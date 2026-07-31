# REMIP — Real Estate Market Intelligence Platform
## Fase 1 — Analisi e Piano (v1.0, 2026-07-31)

> Questo documento è il primo deliverable richiesto: nessuna funzionalità è stata
> sviluppata prima del suo completamento. L'implementazione procede per milestone
> (vedi §9) partendo dalla Milestone 1.

---

## 1. Sintesi del prodotto

REMIP è una piattaforma web di market intelligence immobiliare per utenti privati.
Permette di:

1. analizzare il mercato immobiliare di una zona (prezzi, volumi, tempi, rendimenti);
2. monitorarne l'evoluzione nel tempo (serie storiche, variazioni 1m/3m/6m/12m/5y/10y);
3. visualizzare e analizzare singoli immobili (storico prezzi, comparabili, stima con intervallo);
4. confrontare immobili e aree geografiche;
5. ricevere notifiche su variazioni di annunci e condizioni di mercato;
6. generare previsioni baseline con scenari, intervalli e spiegazione del metodo.

Il prodotto è progettato come **internazionale** (configurazione per Paese: valuta,
lingua, livelli amministrativi, fonti, provider cartografici) con **priorità
sull'Italia e sul residenziale**. Nell'MVP i dati sono **sintetici (demo)**,
chiaramente etichettati, erogati tramite un'architettura ad **adapter** pronta
per fonti reali quando saranno disponibili accordi/API autorizzate.

## 2. Assunzioni

| # | Assunzione | Impatto se falsa |
|---|---|---|
| A1 | Nessun portale immobiliare italiano (Immobiliare.it, Idealista, Casa.it) offre oggi API pubbliche gratuite per uso commerciale; l'accesso richiede accordi. **Non verificato con i provider: da confermare commercialmente.** | Se esistesse un'API autorizzata, l'adapter reale si aggancia senza modifiche architetturali |
| A2 | Open data utilizzabili (ISTAT, OMI/Agenzia delle Entrate, Eurostat, BCE) hanno granularità comunale/semestrale, non per singolo annuncio | Le metriche di zona demo andranno ricalibrate sulla granularità reale |
| A3 | L'MVP gira in locale con Docker Compose; niente cloud in questa fase | — |
| A4 | Lo scraping non autorizzato è escluso by design (ToS + normativa) | — |
| A5 | Utente target: privato non professionale, lingua iniziale IT/EN | — |
| A6 | Budget/tempo/team non specificati → assumiamo profilo "MVP economico, piccolo team, dati demo, previsioni baseline, mappa con marker+clustering+heatmap" (vedi filtri di configurazione nel brief). Modificabile: la roadmap è parametrica | Roadmap e costi vanno ricalcolati |
| A7 | Nell'ambiente di sviluppo corrente i test girano su SQLite; PostGIS è usato via Docker Compose. I modelli sono scritti per essere portabili (lat/lon numerici in M1, geometrie PostGIS da M3) | — |

## 3. Rischi principali (registro)

| ID | Rischio | Prob. | Impatto | Mitigazione |
|---|---|---|---|---|
| R1 | **Accesso ai dati reali**: nessuna fonte annunci autorizzata → prodotto non utilizzabile oltre la demo | Alta | Critico | Architettura adapter + open data (OMI/ISTAT) come primo livello reale; trattative commerciali in parallelo; il valore analitico (zona) non dipende dal singolo annuncio |
| R2 | Violazione ToS/GDPR con scraping | — | Critico | Esclusione by design; adapter con flag `tos_compliant` e kill-switch |
| R3 | Deduplicazione annunci inter-fonte imprecisa → metriche distorte | Media | Alto | Confidence score, match conservativo, metriche con sample size esposto |
| R4 | Previsioni percepite come consulenza finanziaria | Media | Alto | Sempre intervalli+scenari+disclaimer; mai valore puntuale certo; pagina metodologia |
| R5 | Costi geospaziali/mappa a scala (tile, geocoding) | Media | Medio | MapLibre + tile OSM self-host/provider a consumo; caching aggressivo |
| R6 | Scope creep (il brief copre 3+ anni di prodotto) | Alta | Alto | MVP bloccato (§4), backlog V2 esplicito, milestone piccole |
| R7 | Qualità dati open (ritardi 6-12 mesi OMI) | Alta | Medio | Timestamp e "freshness" sempre esposti in UI |
| R8 | Sicurezza (dati utente, credenziali) | Media | Alto | JWT, hashing forte, rate limiting, audit log, secret scanning, niente segreti nel repo |

## 4. Proposta MVP (bloccata — coincide con "MVP OBBLIGATORIO" del brief)

Autenticazione; onboarding; ricerca per città/quartiere/area su mappa; dashboard di
zona; elenco immobili; dettaglio immobile con storico prezzi; comparabili base;
mappa con marker, clustering, heatmap; filtri essenziali; watchlist; versionamento
annunci; notifiche in-app simulate; previsioni baseline con scenari; fonti e
qualità dati visibili; pannello admin minimo; dati demo italiani; Docker Compose;
test automatici; README.

## 5. Escluse dall'MVP (backlog V2+)

- Fonti dati reali (richiedono accordi — vedi `docs/INTEGRATIONS.md`), email/push/webhook,
  pagamenti, ruoli professionali (agenti/fondi/banche/periti), marketplace, social,
  ML avanzato/ensemble, layer territoriali avanzati (rischi climatici, rumore, sicurezza),
  aste, commerciale/industriale/terreni, multi-lingua completo, mobile app,
  export dati utente automatizzato (V2 early per GDPR), TimescaleDB (finché i volumi non lo giustificano).

## 6. Alternative architetturali

### Opzione A — Monolite modulare (FastAPI + Next.js + PostgreSQL/PostGIS + Redis)
Un backend Python (FastAPI) organizzato in moduli a confini netti (auth, geo,
listings, market, notifications, ingestion), un frontend Next.js, un DB Postgres
con PostGIS, Redis per cache/code, worker asincrono per ingestion e notifiche.

- ✅ Un solo deploy, dev locale semplice, Python ideale per data/ML/geo (pandas, scikit-learn, shapely)
- ✅ I moduli diventano servizi estraibili in futuro (confini già definiti)
- ❌ Scala tutto insieme; disciplina necessaria sui confini interni

### Opzione B — Microservizi da subito (API gateway + servizi ingestion/analytics/geo/notify + event bus)
- ✅ Scala e deploy indipendenti, team paralleli, event-driven nativo per gli aggiornamenti annunci
- ❌ Complessità operativa (orchestrazione, osservabilità, contratti) ingiustificata per un MVP demo con un piccolo team; costo infra 3-5×

### Raccomandazione: **Opzione A**, con due regole che preservano l'opzione B:
1. ogni modulo comunica solo via interfacce interne esplicite (no import incrociati dei modelli);
2. l'ingestion è già asincrona (job queue) e parla col resto solo tramite il DB e eventi applicativi.

## 7. Stack confermato

| Layer | Scelta | Note |
|---|---|---|
| Frontend | Next.js 14+, React, TypeScript, Tailwind, shadcn/ui (accessibile), Recharts, **MapLibre GL** | Milestone 2 |
| Backend | **FastAPI (Python 3.11)**, SQLAlchemy 2.0, Pydantic v2 | Python scelto per data engineering/ML/geospatial |
| DB | PostgreSQL 16 + PostGIS (compose); SQLite per test/dev rapido; TimescaleDB rimandato finché le serie non lo richiedono | Modelli portabili |
| Cache/code | Redis (compose); scheduler: worker dedicato (RQ/arq in M4) | |
| Storage | S3-compatible (MinIO in compose, da M4) per snapshot/immagini | |
| Auth | JWT HS256 (PyJWT), hashing PBKDF2-HMAC-SHA256 stdlib (swap-ready per argon2), ruoli user/admin, OAuth predisposto | |
| Deploy | Docker + Docker Compose; CI GitHub Actions (lint+type+test); cloud target: qualunque container host | |
| Testing | pytest + httpx (API/integration/unit), Playwright (E2E, da M2), ruff + mypy | |

## 8. Schema dati iniziale

Vedi `docs/DATA_MODEL.md` (ER Mermaid + dizionario). Entità implementate in M1:
User, Country, AdministrativeArea, DataProvider, Agency, PhysicalProperty,
PropertyListing, ListingVersion, PriceObservation, MarketMetric, MarketForecast,
Watchlist, WatchlistItem, Notification, AuditLog.
Le restanti entità del brief (GeographicBoundary, Address normalizzata,
EconomicIndicator, Valuation, SavedSearch, AlertRule, DataIngestionJob,
SourceCitation, UserPreference, NotificationPreference…) sono definite nel modello
logico e aggiunte nelle milestone in cui servono (vedi §9), per non creare tabelle
vuote non testate.

Principi: ID stabili (UUID), timestamp UTC, valuta esplicita su ogni importo
(ISO 4217), separazione netta **immobile fisico / annuncio / versione / fonte / agenzia**.

## 9. Roadmap (milestone)

| M | Contenuto | Complessità | Criterio di uscita |
|---|---|---|---|
| **M1** | Fondamenta backend: modello dati core, auth JWT, API v1 (geo, listings, market, forecast baseline, watchlist, notifiche in-app, sources, admin), versionamento annunci, adapter demo + seed sintetico Italia, Docker Compose, test, lint, type-check, docs | M | §14 del piano |
| M2 | Frontend Next.js: landing, auth, onboarding, dashboard zona, lista+dettaglio immobile, watchlist, centro notifiche, dark/light, E2E Playwright | L | Criteri di accettazione UI del brief |
| M3 | Mappa interattiva (MapLibre): marker, clustering, heatmap €/m², disegno poligoni, PostGIS attivo, query geospaziali indicizzate | M | Ricerca per poligono/raggio funzionante |
| M4 | Ingestion asincrona reale: job queue + scheduler, adapter open data (OMI/ISTAT), deduplicazione con confidence, MinIO snapshot, digest notifiche | L | Un adapter open data reale in produzione |
| M5 | Confronti (immobili/zone), valutazione automatica con intervallo, motore di spiegazione driver, preferenze notifiche, admin esteso | M | |
| M6 | Hardening: email verification, reset password, OAuth, rate limiting distribuito, export/cancellazione dati (GDPR), monitoring, backup, deploy cloud | M | Production-ready |

## 10. Struttura del repository

```
remip/
├── docker-compose.yml        # postgres+postgis, redis, backend (frontend da M2)
├── .env.example
├── README.md
├── docs/
│   ├── PLAN.md               # questo documento
│   ├── ARCHITECTURE.md       # architettura + diagrammi Mermaid + flusso dati
│   ├── DATA_MODEL.md         # ER + dizionario dati
│   └── INTEGRATIONS.md       # integrazioni da autorizzare + assunzioni sulle fonti
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/             # config, security
│   │   ├── db/               # engine/session, seed demo
│   │   ├── models/           # SQLAlchemy (entità §8)
│   │   ├── schemas/          # Pydantic I/O
│   │   ├── api/v1/           # router versionati
│   │   ├── services/         # versioning, market, forecast, comparables
│   │   └── adapters/         # base adapter + demo adapter (fonti reali qui)
│   └── tests/
└── frontend/                 # M2 (Next.js) — placeholder documentato
```

## 11. Backlog — prime 10 attività (ordinate)

1. Scaffold repo `remip/`, config Pydantic Settings, `.env.example`, compose
2. Modelli SQLAlchemy core + convenzioni (UUID, UTC, currency)
3. Auth: register/login/me, JWT, ruoli, audit log
4. Adapter framework (base + demo) e seed sintetico Italia deterministico
5. API geo (paesi/aree) e listings (filtri, paginazione, ordinamento)
6. Versionamento annunci: servizio diff + endpoint storico + simulazione variazione
7. Market metrics API (serie, variazioni multi-periodo, qualità dato)
8. Forecast baseline (3 orizzonti brevi + scenari strutturali) con metodologia esposta
9. Watchlist + notifiche in-app (trigger su variazioni simulate, dedup)
10. Test suite + ruff + mypy + README + CI config

## 12. Domande tecniche realmente bloccanti

Nessuna blocca la Milestone 1 (dati demo). Bloccanti **prima della produzione**:

1. **Fonti annunci**: esiste budget/volontà di negoziare accesso dati con un portale
   o un data provider (es. feed MLS-like), o si parte solo da open data OMI/ISTAT?
2. **Copertura iniziale reale**: quali città italiane al lancio? (determina costi geocoding/tile)
3. **Hosting**: preferenza cloud (AWS/GCP/Hetzner/EU-only per GDPR)?
4. **Budget operativo mensile** accettabile a regime? (vedi §13)
5. Serve conformità a requisiti specifici (es. AI Act per le previsioni, disclaimer legali per Paese)?

## 13. Stima qualitativa costi infrastrutturali

| Fase | Setup | Costo mensile (ordine di grandezza) | Driver |
|---|---|---|---|
| MVP demo (M1-M3) | locale/1 VPS | **0–50 €** | 1 VPS piccolo, tile OSM gratuiti a basso volume |
| Open data + primi utenti (M4-M6) | cloud singola region | **100–400 €** | Postgres gestito, Redis, object storage, tile provider, email |
| Prima fonte commerciale | — | **500–3.000+ €** | licenza dati (dominante), scaling DB |
| Scala nazionale multi-fonte | — | **3.000–15.000+ €** | licenze dati, geocoding, infra HA, monitoring |

Il costo dominante non è l'infrastruttura ma **le licenze dati**.

## 14. Criteri di completamento Milestone 1

- [ ] `docker compose up` avvia Postgres+PostGIS, Redis e backend; backend eseguibile anche standalone (SQLite) con istruzioni chiare
- [ ] Registrazione e login funzionanti (JWT); endpoint protetti; ruolo admin separato
- [ ] Seed demo italiano: ≥3 città, ≥8 quartieri, ≥80 annunci, 36 mesi di metriche per area, versioni e variazioni di prezzo, annunci rimossi
- [ ] API v1 documentate (OpenAPI): geo, listings (filtri+paginazione+sort), dettaglio con storico versioni e comparabili, market metrics con variazioni multi-periodo, forecast con 3 scenari+confidenza+metodo, watchlist, notifiche, sources con qualità dato, admin
- [ ] Una variazione simulata di un annuncio produce: nuova versione con diff, price observation, notifica (non duplicata) agli utenti con l'annuncio in watchlist
- [ ] Ogni risposta di metriche/forecast espone: fonte, periodo, n. osservazioni, timestamp, qualità, limitazioni, flag `is_demo_data`
- [ ] Isolamento dati utente verificato da test (watchlist/notifiche non leggibili da altri utenti)
- [ ] `ruff check`, `mypy`, `pytest` verdi; nessun segreto nel repo; README completo
