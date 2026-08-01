# REMIP — Integrazioni esterne: stato e autorizzazioni necessarie

Nessuna fonte esterna è integrata nell'MVP: tutti i dati sono **sintetici**
(DemoAdapter, `is_demo=true`, segnalato in ogni risposta API tramite
`data_context.is_demo_data`). Questo registro elenca le integrazioni candidate,
cosa va verificato e cosa serve per attivarle. **Le disponibilità indicate sono
da verificare con i provider: non sono state confermate.**

| Fonte | Tipo | Stato | Prerequisito per l'attivazione |
|---|---|---|---|
| OMI — Agenzia delle Entrate (quotazioni immobiliari) | Open data | Candidata M4 | Verifica licenza riuso e granularità/ritardo pubblicazione |
| ISTAT (popolazione, redditi, occupazione) | Open data | Candidata M4 | Verifica licenza (tip. CC-BY) e API/SDMX |
| Eurostat / BCE (tassi, inflazione) | Open data | Candidata M4 | Verifica termini API |
| OpenStreetMap tile raster (`tile.openstreetmap.org`) | Open data | **Attiva in demo, solo basso volume** | Basemap della mappa (M3). Uso pubblico soggetto alla [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/): non idoneo a traffico di produzione. Prima della scala reale serve un provider a licenza (es. MapTiler, Mapbox, Stadia) — vedi anche voce Overpass sotto |
| MapLibre demo glyphs (`demotiles.maplibre.org`) | Servizio pubblico | **Attiva in demo** | Font per le etichette dei cluster sulla mappa (M3). Da sostituire con font self-hosted prima della produzione |
| OpenStreetMap / Overpass (POI, trasporti) | Open data | Candidata M4-M5 | Rispetto ODbL e rate limit; layer opzionali (scuole, trasporti, servizi) non ancora implementati |
| Geoboundaries / ISTAT confini amministrativi | Open data | Candidata M4 | Licenza confini; la mappa M3 mostra solo marker/cluster/heatmap di annunci, non poligoni di confine amministrativo reali |
| Portali annunci (Immobiliare.it, Idealista, Casa.it, …) | Commerciale | **Solo interfaccia adapter** | Accordo commerciale/API autorizzata. Nessuno scraping: vietato da ToS e escluso by design |
| Dati catastali | Pubblico con vincoli | Da valutare | Analisi legale accesso e riuso |
| Provider geocoding (Nominatim/commerciale) | Misto | Candidata M4 | Ricerca per indirizzo libero non ancora implementata (M3 usa i centroidi delle aree già in DB); ToS Nominatim o contratto commerciale |
| Email provider (notifiche) | Commerciale | Candidata M6 | Contratto + DPA GDPR |
| Push provider | Commerciale | Candidata M6 | Contratto + DPA |

Regole vincolanti per ogni adapter (implementate in `backend/app/adapters/base.py`):
identificazione fonte, timestamp acquisizione/aggiornamento, validazione,
normalizzazione, deduplicazione, gestione errori, retry, rate limiting, logging,
versionamento, qualità e provenienza del dato, flag `tos_compliant` e
disattivazione (`enabled=false`). Un adapter con `tos_compliant=false` non può
essere abilitato.
