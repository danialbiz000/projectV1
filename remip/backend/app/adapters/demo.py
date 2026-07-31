"""DemoAdapter: deterministic synthetic Italian residential data.

All data is invented (no real people, agencies or addresses) and every API
response built on it carries ``is_demo_data=True``. The generator is seeded so
repeated runs produce identical datasets.
"""
from __future__ import annotations

import random
from typing import Any

from app.adapters.base import BaseAdapter, RawListing, SourceInfo
from app.db.base import utcnow

# base €/sqm sale price, rent €/sqm/month, annual trend %
CITIES: dict[str, dict[str, Any]] = {
    "Milano": {
        "region": "Lombardia",
        "province": "Milano",
        "lat": 45.4642,
        "lon": 9.1900,
        "population": 1372000,
        "base_sqm": 5300.0,
        "rent_sqm": 22.0,
        "trend": 4.0,
        "neighborhoods": {
            "Isola": 1.25,
            "Navigli": 1.15,
            "Città Studi": 0.92,
            "Bicocca": 0.78,
        },
    },
    "Roma": {
        "region": "Lazio",
        "province": "Roma",
        "lat": 41.9028,
        "lon": 12.4964,
        "population": 2761000,
        "base_sqm": 3400.0,
        "rent_sqm": 16.0,
        "trend": 1.5,
        "neighborhoods": {
            "Trastevere": 1.35,
            "Prati": 1.28,
            "San Giovanni": 0.95,
        },
    },
    "Bologna": {
        "region": "Emilia-Romagna",
        "province": "Bologna",
        "lat": 44.4949,
        "lon": 11.3426,
        "population": 392000,
        "base_sqm": 3200.0,
        "rent_sqm": 15.0,
        "trend": 3.0,
        "neighborhoods": {
            "Bolognina": 0.85,
            "Santo Stefano": 1.2,
        },
    },
}

PROPERTY_TYPES = ["apartment", "apartment", "apartment", "studio", "penthouse", "detached_house"]
ENERGY_CLASSES = ["A", "B", "C", "D", "E", "F", "G"]
AGENCY_NAMES = [
    "Demo Immobiliare Nord",
    "Casa Demo SRL",
    "Agenzia Esempio",
    "Demo Real Estate Group",
]
STREET_NAMES = [
    "Via dei Sicomori",
    "Via delle Betulle",
    "Corso Immaginario",
    "Piazza Inventata",
    "Via del Campione",
    "Largo Sintetico",
]
LISTINGS_PER_NEIGHBORHOOD = 12
METRIC_MONTHS = 36


class DemoAdapter(BaseAdapter):
    """Generates synthetic listings; stands in for a licensed source."""

    def __init__(self, seed: int = 42, listings_per_neighborhood: int = LISTINGS_PER_NEIGHBORHOOD):
        super().__init__(enabled=True)
        self.seed = seed
        self.listings_per_neighborhood = listings_per_neighborhood

    def source_info(self) -> SourceInfo:
        return SourceInfo(
            code="demo_it",
            name="REMIP Demo Data (Italia)",
            kind="demo",
            tos_compliant=True,
            is_demo=True,
            quality_score=0.99,
            notes="Dataset sintetico deterministico. Nessun dato reale.",
        )

    def fetch_raw(self) -> list[dict[str, Any]]:
        rng = random.Random(self.seed)
        records: list[dict[str, Any]] = []
        counter = 0
        for city, cfg in CITIES.items():
            for neighborhood, multiplier in cfg["neighborhoods"].items():
                for _ in range(self.listings_per_neighborhood):
                    counter += 1
                    ptype = rng.choice(PROPERTY_TYPES)
                    size = {
                        "studio": rng.uniform(28, 45),
                        "penthouse": rng.uniform(90, 180),
                        "detached_house": rng.uniform(120, 260),
                    }.get(ptype, rng.uniform(50, 130))
                    rooms = max(1, round(size / 32))
                    sqm_price = cfg["base_sqm"] * multiplier * rng.uniform(0.82, 1.22)
                    listing_type = "rent" if rng.random() < 0.25 else "sale"
                    price = (
                        round(size * cfg["rent_sqm"] * multiplier * rng.uniform(0.85, 1.2), -1)
                        if listing_type == "rent"
                        else round(size * sqm_price, -3)
                    )
                    records.append(
                        {
                            "external_id": f"DEMO-{counter:05d}",
                            "city": city,
                            "neighborhood": neighborhood,
                            "listing_type": listing_type,
                            "property_type": ptype,
                            "size_sqm": round(size, 1),
                            "rooms": rooms,
                            "bathrooms": 1 + (rooms > 3),
                            "floor": rng.randint(0, 7),
                            "year_built": rng.randint(1930, 2024),
                            "energy_class": rng.choice(ENERGY_CLASSES),
                            "price": price,
                            "currency": "EUR",
                            "lat": cfg["lat"] + rng.uniform(-0.03, 0.03),
                            "lon": cfg["lon"] + rng.uniform(-0.03, 0.03),
                            "address_text": f"{rng.choice(STREET_NAMES)} "
                            f"{rng.randint(1, 120)}, {neighborhood}, {city}",
                            "agency": rng.choice(AGENCY_NAMES),
                            "days_on_market": rng.randint(3, 220),
                            "photos_count": rng.randint(4, 25),
                            "features": {
                                "elevator": rng.random() < 0.6,
                                "balcony": rng.random() < 0.55,
                                "garage": rng.random() < 0.3,
                                "garden": ptype == "detached_house",
                            },
                        }
                    )
        return records

    def validate(self, record: dict[str, Any]) -> bool:
        return record.get("price", 0) > 0 and record.get("size_sqm", 0) > 0

    def normalize(self, record: dict[str, Any]) -> RawListing:
        return RawListing(
            source_code="demo_it",
            external_id=record["external_id"],
            fetched_at=utcnow(),
            source_updated_at=utcnow(),
            payload=record,
        )
