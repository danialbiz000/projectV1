# REMIP — Guida al deployment cloud (M6)

> ⚠️ **Non eseguita in questo ambiente.** Il sandbox di sviluppo usato per
> costruire REMIP non ha accesso a provider cloud né, per policy di rete, a
> Internet in generale (stesso limite documentato per gli adapter dati live
> in `docs/INTEGRATIONS.md`). Questa guida descrive passi concreti e
> verificabili da un operatore con un account cloud reale, ma **nessuno di
> questi passi è stato eseguito o testato qui**. Non è un sostituto di un
> deployment reale collaudato. Lo stesso vale per le credenziali SMTP/OAuth
> reali (§9): richiedono un account presso un provider terzo che solo
> l'operatore può creare — non sono qualcosa che si possa "aggiungere" dal
> codice.

## 1. Architettura di riferimento

`docker-compose.yml` è già production-shaped: `db` (Postgres+PostGIS),
`redis`, `minio` (S3-compatibile), `backend`, `worker`, `scheduler`,
`frontend`, più `migrate` (M6, one-off — §3). Il modo più diretto per andare
in produzione è eseguire lo stesso Compose su una singola VM dietro un
reverse proxy TLS — opzione (A) sotto. Un PaaS a container (Fly.io, Render,
Railway) è un'alternativa valida se si preferisce non gestire la VM —
opzione (B), solo accennata: richiede sostituire `db`/`redis`/`minio` con i
servizi gestiti del provider, il resto (immagini Docker, env var) non
cambia.

## 2. Prerequisiti prima di qualunque deployment

Questi non sono opzionali — vedi anche `README.md` → Sicurezza e
`docs/PLAN.md` §3 (registro rischi):

| Voce | Perché |
|---|---|
| `REMIP_SECRET_KEY` reale (`openssl rand -hex 32`) | Il default in `core/config.py` è un valore di sviluppo pubblico nel repo — usarlo in produzione invalida ogni JWT emesso |
| `REMIP_DEMO_MODE=false` | Altrimenti `/auth/forgot-password` e `/auth/verify-email/request` continuano a restituire il token grezzo nella risposta (comodo per i test, vedi `schemas/auth.py::MessageResponse.dev_token` — **mai** accettabile in produzione) |
| `REMIP_SEED_ON_STARTUP=false` | Il seed demo crea utenti con password note (`docs` → Credenziali demo) — non deve girare contro un database di produzione |
| SMTP reale (`REMIP_SMTP_HOST`/`_PORT`/`_USER`/`_PASSWORD`/`_FROM`) | Senza queste, `services/email.py` usa l'adapter console (solo log) — verifica email e reset password non arrivano a nessuno. Vedi §9 per come ottenerle |
| OAuth reale (`REMIP_OAUTH_GOOGLE_CLIENT_ID`/`_CLIENT_SECRET`) | Senza queste, `GET /auth/oauth/providers` torna vuoto e i bottoni OAuth non compaiono in `/login` — non è un errore, è lo stato "non configurato" by design (vedi `services/oauth.py`). Vedi §9 per come ottenerle |
| `REMIP_CORS_ORIGINS` limitato al dominio reale del frontend | Il default include solo `http://localhost:3000` |
| Credenziali S3/MinIO e Postgres non di default | I default in `docker-compose.yml` sono valori di sviluppo |
| Migrazioni Alembic eseguite (§3) | Lo schema deve essere applicato con `alembic upgrade head`, non lasciato al solo `create_all` di comodo — vedi §3 per il perché |

## 3. Migrazioni database (Alembic, M6)

Lo schema ha una storia di migrazioni versionata da M6
(`backend/alembic/`), con una revisione baseline che copre l'intero schema
M1-M6. Prima del primo avvio di un deployment reale:

```bash
docker compose --profile tools run --rm migrate
# equivalente, senza Compose:
cd remip/backend && alembic upgrade head
```

Il backend continua comunque a chiamare `Base.metadata.create_all`
all'avvio (lifespan in `app/main.py`) — **non è stato rimosso**, perché è
ciò che rende il flusso di sviluppo rapido (`uvicorn app.main:app` su
SQLite, senza Docker) a zero configurazione, come documentato
nell'"Avvio rapido" del README. Una volta che Alembic ha già creato le
tabelle, `create_all` le trova già esistenti e non fa nulla — nessun
conflitto tra i due meccanismi. **Ma da qui in avanti ogni cambio di
schema va fatto con una nuova revisione Alembic**
(`alembic revision --autogenerate -m "..."`, poi rivista a mano prima di
applicarla), non lasciato al solo `create_all`: `create_all` sa solo
*creare* tabelle mancanti, non applicare `ALTER TABLE` su un database che
ha già dati — un nuovo campo non-nullable su una tabella esistente, ad
esempio, richiede una migrazione reale con eventuale backfill, non è
qualcosa che `create_all` gestisce.

Verificato in questo ambiente: `alembic upgrade head` contro un file
SQLite temporaneo produce esattamente le tabelle descritte da
`Base.metadata` (test automatico, `tests/test_migrations.py`), incluso il
downgrade completo (`alembic downgrade base`). Non verificato: l'esecuzione
contro un Postgres reale (nessun Postgres raggiungibile in questo
ambiente) — il dialect target è lo stesso SQLAlchemy usato dall'app, quindi
non ci si aspettano differenze, ma non è stato osservato direttamente.

## 4. Opzione A — Docker Compose su una VM, dietro reverse proxy TLS

```bash
# 1. Provisioning: una VM Linux (2 vCPU / 4GB RAM è sufficiente per l'MVP),
#    Docker + Docker Compose plugin installati.
# 2. Clona il repo, configura .env (mai committarlo)
cp .env.example .env
# imposta: REMIP_SECRET_KEY, POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD,
#          REMIP_DEMO_MODE=false, REMIP_SEED_ON_STARTUP=false,
#          REMIP_SMTP_*, REMIP_OAUTH_GOOGLE_* (opzionale, §9),
#          REMIP_CORS_ORIGINS, NEXT_PUBLIC_API_URL (dominio reale)

# 3. Migrazioni (§3), poi avvio
docker compose --profile tools run --rm migrate
docker compose up -d --build

# 4. Reverse proxy con TLS automatico (esempio con Caddy — un Caddyfile,
#    nessuna configurazione nginx/certbot manuale):
```

```
# /etc/caddy/Caddyfile
app.tuodominio.it {
    reverse_proxy localhost:3000
}
api.tuodominio.it {
    reverse_proxy localhost:8000
    # Vedi §6: restringere l'accesso a /metrics separatamente se possibile
}
```

DNS: due record A verso l'IP della VM per i due (sub)domini sopra.

## 5. Opzione B — PaaS a container (cenni)

Backend/worker/scheduler/frontend sono le stesse quattro immagini Docker;
sostituire `db`→Postgres gestito (con estensione PostGIS abilitata),
`redis`→Redis gestito, `minio`→bucket S3 reale (AWS S3, Cloudflare R2,
ecc., impostando `REMIP_S3_ENDPOINT_URL`/`_BUCKET`/`_ACCESS_KEY`/`_SECRET_KEY`).
La maggior parte dei PaaS a container offre un "release command"/"pre-deploy
hook" dove far girare `alembic upgrade head` (§3) prima che il nuovo
codice riceva traffico — verificare la sintassi specifica del provider
scelto, non riprodotta qui perché non verificabile in questo ambiente.

## 6. Health check, monitoring e superficie esposta

- **Liveness/readiness**: `GET /health` (`backend`) — nessuna dipendenza da
  Redis/S3, quindi torna `ok` anche se worker/scheduler sono giù.
- **Metriche**: `GET /metrics` (M6, `core/metrics.py`) in formato Prometheus
  text-exposition. **Non autenticato by design** (come un endpoint
  Prometheus locale tipico) — in produzione va **ristretto a livello di
  rete** (regola firewall/security group che permetta solo all'IP del
  server Prometheus, o basic auth nel reverse proxy), non lasciato
  raggiungibile pubblicamente insieme al resto dell'API.
- Le metriche sono **per processo**: con più repliche del backend servono
  scraping per-istanza (un target per replica) o un push-gateway; i
  contatori non si aggregano da soli tra processi (vedi il docstring in
  `core/metrics.py`).
- Log strutturati per richiesta (`remip.access`, vedi `main.py`) su stdout
  — in produzione vanno raccolti da un log driver Docker verso un
  aggregatore (CloudWatch, Loki, ecc.), non lasciati solo su disco locale.

## 7. Backup e restore

- **Backup**: `POST /admin/backup` (solo admin, M6) — copia il file SQLite
  o esegue `pg_dump` su Postgres, e salva il risultato tramite
  `services/storage.py` (stesso bucket S3/MinIO degli snapshot annunci, o
  disco locale se non configurato S3). Non è schedulato automaticamente:
  va richiamato da un cron esterno o da un job dell'orchestratore scelto
  (es. una entry cron sulla VM che chiama l'endpoint con un token admin).
- **Restore**: **nessun endpoint automatico**, deliberatamente — vedi il
  docstring in `services/backup.py`. Procedura manuale:
  1. Scarica il file dallo storage (chiave restituita da `/admin/backup`,
     es. `s3://remip-snapshots/backups/remip-<timestamp>.sql`).
  2. Postgres: `psql "$REMIP_DATABASE_URL" < remip-<timestamp>.sql` (idealmente
     contro un database vuoto/nuovo, non sovrascrivendo quello in uso).
  3. SQLite: sostituisci il file `.db` fermando prima il processo backend.
  4. Riavvia backend/worker/scheduler.

## 8. Scalabilità

Il backend è stateless (JWT, nessuna sessione server-side) quindi più
repliche dietro un load balancer funzionano senza modifiche architetturali,
con due eccezioni da tenere presenti:

- **Rate limiting** (`core/rate_limit.py`, M6): con Redis raggiungibile è
  già correttamente distribuito tra repliche; senza Redis degrada a un
  contatore in-memory per processo (limita ogni replica singolarmente, non
  il totale) — in produzione multi-replica, Redis è quindi da considerare
  un prerequisito, non solo un'ottimizzazione.
- **Metriche** (§6): per-processo, serve scraping per-istanza.

`worker`/`scheduler` possono scalare orizzontalmente sul numero di worker
RQ; lo scheduler APScheduler va tenuto a una singola replica attiva per
evitare doppie esecuzioni schedulate (nessun lock distribuito implementato
in M6 — gap noto, vedi `docs/PLAN.md`).

## 9. Come ottenere credenziali SMTP/OAuth reali

Queste due voci richiedono un account presso un provider terzo che **solo
l'operatore del deployment può creare** — non è possibile ottenerle dal
codice o da questo ambiente di sviluppo (nessun accesso di rete/account).
Il codice è già pronto a riceverle via `.env`; questa sezione spiega solo
dove procurarsele.

**SMTP** — qualunque provider SMTP standard funziona (`services/email.py`
usa `smtplib`, nessuna integrazione proprietaria). Opzioni comuni:
- **SendGrid/Mailgun/Postmark** (servizi email transazionali dedicati):
  creare un account, verificare il dominio mittente (record SPF/DKIM sul
  DNS), generare una API key da usare come `REMIP_SMTP_USER`/`REMIP_SMTP_PASSWORD`
  secondo la loro documentazione SMTP relay.
- **Gmail/Workspace**: richiede una "App Password" (non la password
  dell'account) generata da account Google con 2FA attivo; `REMIP_SMTP_HOST=smtp.gmail.com`,
  `REMIP_SMTP_PORT=587`. Va bene per volumi bassi, non per traffico di
  produzione (limiti di invio giornalieri stretti).

Una volta ottenute, impostarle in `.env` (mai committarlo) e verificare con
`POST /auth/verify-email/request` (con `REMIP_DEMO_MODE=false`): se l'email
arriva davvero, la configurazione è corretta.

**OAuth (Google)** — `services/oauth.py` è scritto per il flusso
authorization-code standard di Google:
1. [Google Cloud Console](https://console.cloud.google.com/) → creare un
   progetto (o usarne uno esistente) → "APIs & Services" → "Credentials" →
   "Create Credentials" → "OAuth client ID" → tipo "Web application".
2. **Authorized redirect URI**: `<dominio del frontend>/login/oauth/google/callback`
   (deve combaciare esattamente con quanto REMIP costruisce da
   `REMIP_OAUTH_REDIRECT_BASE_URL`, vedi `api/v1/oauth.py::authorize`) — se
   non combacia, Google rifiuta il redirect con un errore visibile
   all'utente, non un errore silenzioso.
3. Copiare "Client ID" e "Client secret" in `REMIP_OAUTH_GOOGLE_CLIENT_ID`/
   `REMIP_OAUTH_GOOGLE_CLIENT_SECRET`.
4. Verificare con `GET /auth/oauth/providers`: deve rispondere
   `{"providers": ["google"]}` invece che vuoto — a quel punto il bottone
   "Continua con Google" compare automaticamente su `/login` (nessuna
   modifica di codice necessaria, vedi `frontend/src/app/login/page.tsx`).

Un provider aggiuntivo (GitHub, Microsoft, ecc.) richiederebbe invece
codice nuovo: `services/oauth.py::configured_providers` oggi conosce solo
la forma "Google" (endpoint authorize/token/userinfo standard OAuth2/OIDC);
aggiungerne un altro è un'estensione dello stesso pattern, non riprogettato
da zero, ma non è stata implementata perché non richiesta.

## 10. Cosa manca prima di un rilascio con utenti reali

Elenco esplicito, non un "tutto pronto":

1. Le credenziali reali di §9 (SMTP, OAuth) — il meccanismo è pronto, i
   valori no.
2. Lock distribuito per lo scheduler se si scala a più repliche (§8).
3. Rotazione/backup automatico schedulato (oggi solo on-demand via
   `POST /admin/backup`, §7).
4. Un vero WAF/rate limiting a livello di reverse proxy come difesa
   aggiuntiva — `core/rate_limit.py` protegge gli endpoint auth applicativi,
   non sostituisce una protezione perimetrale.
5. Un secondo provider OAuth se richiesto (§9, ultimo paragrafo).
