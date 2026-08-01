"""OMI-shaped open-data adapter.

OMI (Osservatorio del Mercato Immobiliare, Agenzia delle Entrate) publishes
semestral price bands per "zona OMI" within each comune — min/max €/m² for
sales and rents, by property type and conservation state. This is
*aggregated zone-level* data, not per-listing data (see docs/PLAN.md
assumption A2), which is exactly the shape this adapter produces.

**Honesty note**: `fetch_raw()` reads a local, versioned fixture rather than
a live endpoint. Agenzia delle Entrate distributes OMI data as downloadable
semestral CSV/Excel files rather than a conventional REST API, and this
sandbox cannot verify a live source end-to-end (see docs/INTEGRATIONS.md).
The fixture mirrors OMI's real column shape so the ingestion pipeline
(validate → normalize → resolve-to-area → dedup → persist) is genuine and
testable; only the *values* are illustrative. Swapping `fetch_raw()` for a
real download once a source is verified does not require touching anything
downstream.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.adapters.base import BaseAdapter, RawListing, SourceInfo
from app.db.base import utcnow

# (comune, zona_descrizione, zona_code, base €/sqm sale, base €/sqm rent/month)
# Base figures deliberately below adapters/demo.py's asking-price averages:
# OMI valuations are a conservative reference basis, not asking prices.
ZONES: list[tuple[str, str, str, float, float]] = [
    ("Milano", "Isola", "B12", 4200.0, 18.0),
    ("Milano", "Navigli", "B13", 3900.0, 16.5),
    ("Milano", "Città Studi", "B21", 3300.0, 14.0),
    ("Milano", "Bicocca", "D12", 2650.0, 11.5),
    ("Roma", "Trastevere", "B9", 2900.0, 13.5),
    ("Roma", "Prati", "B4", 2750.0, 13.0),
    ("Roma", "San Giovanni", "C7", 2100.0, 10.0),
    ("Bologna", "Bolognina", "D3", 1900.0, 9.0),
    ("Bologna", "Santo Stefano", "B2", 2650.0, 12.5),
]
PROPERTY_TYPES = ["apartment"]  # OMI covers many; MVP scope stays residential
CONSERVATION_STATES = ["Normale", "Ottimo", "Scadente"]
STATE_MULTIPLIER = {"Ottimo": 1.12, "Normale": 1.0, "Scadente": 0.82}
BAND_WIDTH = 0.18  # OMI publishes a range, not a point estimate


def _current_semester(today: date) -> str:
    return f"{today.year}-{1 if today.month <= 6 else 2}"


def _previous_semester(current: str) -> str:
    year, half = (int(x) for x in current.split("-"))
    return f"{year - 1}-2" if half == 1 else f"{year}-1"


class OmiAdapter(BaseAdapter):
    def source_info(self) -> SourceInfo:
        return SourceInfo(
            code="omi_it",
            name="OMI - Agenzia delle Entrate (quotazioni, struttura dimostrativa)",
            kind="open_data",
            tos_compliant=True,
            is_demo=True,
            quality_score=0.4,
            notes=(
                "Struttura fedele alle quotazioni OMI reali (comune/zona/tipologia/stato, "
                "range compravendite e locazioni €/m² per semestre); valori illustrativi da "
                "fixture locale, non da endpoint live verificato. Vedi docs/INTEGRATIONS.md."
            ),
        )

    def fetch_raw(self) -> list[dict[str, Any]]:
        current = _current_semester(date.today())
        semesters = [_previous_semester(current), current]
        records: list[dict[str, Any]] = []
        for semester_index, semester in enumerate(semesters):
            drift = 1.0 - 0.015 * (len(semesters) - 1 - semester_index)  # slight past discount
            for comune, zona_desc, zona_code, base_sale, base_rent in ZONES:
                for ptype in PROPERTY_TYPES:
                    for state in CONSERVATION_STATES:
                        mult = STATE_MULTIPLIER[state] * drift
                        for listing_type, base, decimals in (
                            ("sale", base_sale, 0),
                            ("rent", base_rent, 2),
                        ):
                            mid = base * mult
                            records.append(
                                {
                                    "comune": comune,
                                    "zona_descrizione": zona_desc,
                                    "zona_code": zona_code,
                                    "tipologia": ptype,
                                    "stato": state,
                                    "semestre": semester,
                                    "listing_type": listing_type,
                                    "price_sqm_min": round(mid * (1 - BAND_WIDTH / 2), decimals),
                                    "price_sqm_max": round(mid * (1 + BAND_WIDTH / 2), decimals),
                                }
                            )
        return records

    def validate(self, record: dict[str, Any]) -> bool:
        return record.get("price_sqm_max", 0) >= record.get("price_sqm_min", 0) > 0

    def normalize(self, record: dict[str, Any]) -> RawListing:
        external_id = (
            f"{record['comune']}-{record['zona_code']}-{record['tipologia']}-"
            f"{record['stato']}-{record['semestre']}-{record['listing_type']}"
        )
        now = utcnow()
        return RawListing(
            source_code="omi_it",
            external_id=external_id,
            fetched_at=now,
            source_updated_at=now,
            payload=record,
        )
