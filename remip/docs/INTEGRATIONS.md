# REMIP — Integrazioni esterne: stato e autorizzazioni necessarie

Da M4 esistono due adapter reali con caratteristiche diverse:

- **OMI** (`omi_it`): pipeline genuina — fetch, validazione, normalizzazione,
  risoluzione geografica, dedup/upsert — ma i *valori* provengono da una
  fixture locale versionata, non da un endpoint verificato (`is_demo=true`).
- **Eurostat House Price Index** (`eurostat_hpi`): **dato genuinamente live**.
  L'adapter fa una vera chiamata HTTP all'API pubblica Eurostat a ogni
  esecuzione, senza alcun fallback a valori sintetici — se la chiamata
  fallisce, l'ingestion fallisce visibilmente (`is_demo=false`, righe scritte
  solo da una risposta reale riuscita). Provato manualmente in questo
  ambiente: la richiesta viene bloccata dalla policy di rete del sandbox
  (`403 Forbidden`, stesso comportamento verificato anche verso host generici
  come `example.com`) e il job risultante mostra onestamente
  `status="failed"` con l'errore reale — non è stato possibile verificare una
  risposta 200 da qui. In un ambiente con accesso a internet normale (incluso
  probabilmente `docker compose up` su una macchina reale, o la CI di GitHub
  Actions) dovrebbe funzionare: vedi `tests/test_eurostat_adapter.py::test_live_fetch_or_skip`,
  che esegue la chiamata reale e verifica per davvero quando la rete lo
  consente.

Ogni altra fonte in questo registro resta **candidata**, non integrata: i
dati restano sintetici o illustrativi (`is_demo=true`) finché non viene
costruito un adapter dedicato. **Le disponibilità indicate sono da
verificare con i provider: non sono state confermate.**

| Fonte | Tipo | Stato | Prerequisito per l'attivazione |
|---|---|---|---|
| OMI — Agenzia delle Entrate (quotazioni immobiliari) | Open data | **Adapter costruito (M4), non verificato live** | `adapters/omi.py` riproduce la struttura reale (comune/zona/tipologia/stato, bande €/m² per semestre) ma legge da fixture locale versionata, non da un endpoint verificato: questo ambiente non ha potuto testare una connessione live, e OMI distribuisce comunque CSV/Excel semestrali anziché una API REST convenzionale. Prima di uno switch a dati live serve verificare licenza di riuso, formato di download effettivo e granularità/ritardo di pubblicazione |
| Eurostat — House Price Index (`prc_hpi_q`) | Open data | **Adapter live costruito (M4)** | `adapters/eurostat.py`, chiamata HTTP reale, nessuna chiave. Non verificato con una risposta 200 da questo sandbox (rete bloccata per policy — vedi sopra); verificabile subito in un ambiente con internet reale |
| ISTAT (popolazione, redditi, occupazione) | Open data | Candidata M5 | Dataset distinto da Eurostat HPI sopra. Verifica licenza (tip. CC-BY) e API/SDMX |
| Eurostat — altri indicatori (BCE, inflazione, tassi) | Open data | Candidata M5 | Stesso pattern dell'adapter Eurostat HPI, dataset diverso; verifica termini API specifici |
| OpenStreetMap tile raster (`tile.openstreetmap.org`) | Open data | **Attiva in demo, solo basso volume** | Basemap della mappa (M3). Uso pubblico soggetto alla [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/): non idoneo a traffico di produzione. Prima della scala reale serve un provider a licenza (es. MapTiler, Mapbox, Stadia) — vedi anche voce Overpass sotto |
| MapLibre demo glyphs (`demotiles.maplibre.org`) | Servizio pubblico | **Attiva in demo** | Font per le etichette dei cluster sulla mappa (M3). Da sostituire con font self-hosted prima della produzione |
| OpenStreetMap / Overpass (POI, trasporti) | Open data | Candidata M5 | Rispetto ODbL e rate limit; layer opzionali (scuole, trasporti, servizi) non ancora implementati |
| Geoboundaries / ISTAT confini amministrativi | Open data | Candidata M5 | Licenza confini; la mappa M3 mostra solo marker/cluster/heatmap di annunci, non poligoni di confine amministrativo reali |
| Portali annunci (Immobiliare.it, Idealista, Casa.it, …) | Commerciale | **Solo interfaccia adapter** | Accordo commerciale/API autorizzata. Nessuno scraping: vietato da ToS e escluso by design |
| Dati catastali | Pubblico con vincoli | Da valutare | Analisi legale accesso e riuso |
| Provider geocoding (Nominatim/commerciale) | Misto | Candidata M5 | Ricerca per indirizzo libero non ancora implementata (M3 usa i centroidi delle aree già in DB); ToS Nominatim o contratto commerciale |
| Email provider (notifiche) | Commerciale | Candidata M6 | Contratto + DPA GDPR |
| Push provider | Commerciale | Candidata M6 | Contratto + DPA |

Regole vincolanti per ogni adapter (implementate in `backend/app/adapters/base.py`):
identificazione fonte, timestamp acquisizione/aggiornamento, validazione,
normalizzazione, deduplicazione, gestione errori, retry, rate limiting, logging,
versionamento, qualità e provenienza del dato, flag `tos_compliant` e
disattivazione (`enabled=false`). Un adapter con `tos_compliant=false` non può
essere abilitato.
