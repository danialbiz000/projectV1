# REMIP — Guida al deployment cloud (M6)

> ⚠️ **Non eseguita in questo ambiente.** Il sandbox di sviluppo usato per
> costruire REMIP non ha accesso a provider cloud né, per policy di rete, a
> Internet in generale (stesso limite documentato per gli adapter dati live
> in `docs/INTEGRATIONS.md`). Questa guida descrive passi concreti e
> verificabili da un operatore con un account cloud reale, ma **nessuno di
> questi passi è stato eseguito o testato qui**. Non è un sostituto di un
> deployment reale collaudato.

## 1. Architettura di riferimento

`docker-compose.yml` è già production-shaped: `db` (Postgres+PostGIS),
`redis`, `minio` (S3-compatibile), `backend`, `worker`, `scheduler`,
`frontend`. Il modo più diretto per andare in produzione è eseguire lo
stesso Compose su una singola VM dietro un reverse proxy TLS — opzione (A)
sotto. Un PaaS a container (Fly.io, Render, Railway) è un'alternativa
valida se si preferisce non gestire la VM — opzione (B), solo accennata:
richiede sostituire `db`/`redis`/`minio` con i servizi gestiti del
provider, il resto (immagini Docker, env var) non cambia.

## 2. Prerequisiti prima di qualunque deployment

Questi non sono opzionali — vedi anche `README.md` → Sicurezza e
`docs/PLAN.md` §3 (registro rischi):

| Voce | Perché |
|---|---|
| `REMIP_SECRET_KEY` reale (`openssl rand -hex 32`) | Il default in `core/config.py` è un valore di sviluppo pubblico nel repo — usarlo in produzione invalida ogni JWT emesso |
| `REMIP_DEMO_MODE=false` | Altrimenti `/auth/forgot-password` e `/auth/verify-email/request` continuano a restituire il token grezzo nella risposta (comodo per i test, vedi `schemas/auth.py::MessageResponse.dev_token` — **mai** accettabile in produzione) |
| `REMIP_SEED_ON_STARTUP=false` | Il seed demo crea utenti con password note (`docs` → Credenziali demo) — non deve girare contro un database di produzione |
| SMTP reale (`REMIP_SMTP_HOST`/`_PORT`/`_USER`/`_PASSWORD`/`_FROM`) | Senza queste, `services/email.py` usa l'adapter console (solo log) — verifica email e reset password non arrivano a nessuno |
| `REMIP_CORS_ORIGINS` limitato al dominio reale del frontend | Il default include solo `http://localhost:3000` |
| Credenziali S3/MinIO e Postgres non di default | I default in `docker-compose.yml` sono valori di sviluppo |
| Migrazioni | Lo schema è creato con `Base.metadata.create_all` (M1), non Alembic — accettabile per l'MVP demo, **non** per aggiornamenti futuri dello schema in un database con dati reali. Introdurre Alembic è un prerequisito bloccante prima del primo rilascio con dati reali (vedi `docs/PLAN.md` §12) |

## 3. Opzione A — Docker Compose su una VM, dietro reverse proxy TLS

```bash
# 1. Provisioning: una VM Linux (2 vCPU / 4GB RAM è sufficiente per l'MVP),
#    Docker + Docker Compose plugin installati.
# 2. Clona il repo, configura .env (mai committarlo)
cp .env.example .env
# imposta: REMIP_SECRET_KEY, POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD,
#          REMIP_DEMO_MODE=false, REMIP_SEED_ON_STARTUP=false,
#          REMIP_SMTP_*, REMIP_CORS_ORIGINS, NEXT_PUBLIC_API_URL (dominio reale)

# 3. Avvio
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
    # Vedi §5: restringere l'accesso a /metrics separatamente se possibile
}
```

DNS: due record A verso l'IP della VM per i due (sub)domini sopra.

## 4. Opzione B — PaaS a container (cenni)

Backend/worker/scheduler/frontend sono le stesse quattro immagini Docker;
sostituire `db`→Postgres gestito (con estensione PostGIS abilitata),
`redis`→Redis gestito, `minio`→bucket S3 reale (AWS S3, Cloudflare R2,
ecc., impostando `REMIP_S3_ENDPOINT_URL`/`_BUCKET`/`_ACCESS_KEY`/`_SECRET_KEY`).
Ogni PaaS ha la propria sintassi per definire più servizi da un
monorepo — non riprodotta qui perché dipende dal provider scelto e non è
verificabile in questo ambiente.

## 5. Health check, monitoring e superficie esposta

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

## 6. Backup e restore

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

## 7. Scalabilità

Il backend è stateless (JWT, nessuna sessione server-side) quindi più
repliche dietro un load balancer funzionano senza modifiche architetturali,
con due eccezioni da tenere presenti:

- **Rate limiting** (`core/rate_limit.py`, M6): con Redis raggiungibile è
  già correttamente distribuito tra repliche; senza Redis degrada a un
  contatore in-memory per processo (limita ogni replica singolarmente, non
  il totale) — in produzione multi-replica, Redis è quindi da considerare
  un prerequisito, non solo un'ottimizzazione.
- **Metriche** (§5): per-processo, serve scraping per-istanza.

`worker`/`scheduler` possono scalare orizzontalmente sul numero di worker
RQ; lo scheduler APScheduler va tenuto a una singola replica attiva per
evitare doppie esecuzioni schedulate (nessun lock distribuito implementato
in M6 — gap noto, vedi `docs/PLAN.md`).

## 8. Cosa manca prima di un rilascio con utenti reali

Elenco esplicito, non un "tutto pronto":

1. Migrazioni Alembic al posto di `create_all` (§2).
2. Un vero provider OAuth configurato (`REMIP_OAUTH_GOOGLE_CLIENT_ID/SECRET`,
   M6) se si vuole offrire il login social — oggi nessun provider è
   configurato di default, vedi `services/oauth.py`.
3. SMTP reale configurato (§2) — senza, verifica email e reset password
   restano funzionalmente "silenziose" (solo log).
4. Lock distribuito per lo scheduler se si scala a più repliche (§7).
5. Rotazione/backup automatico schedulato (oggi solo on-demand via
   `POST /admin/backup`, §6).
6. Un vero WAF/rate limiting a livello di reverse proxy come difesa
   aggiuntiva — `core/rate_limit.py` protegge gli endpoint auth applicativi,
   non sostituisce una protezione perimetrale.
