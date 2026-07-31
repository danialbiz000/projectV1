"""Deterministic demo seed for Italy (see adapters/demo.py).

Creates: country config, administrative hierarchy, providers, agencies,
listings with version history (price cuts, removals, relistings), 36 months of
market metrics per area, baseline forecasts, demo users and a demo watchlist.
"""
from __future__ import annotations

import logging
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.demo import CITIES, METRIC_MONTHS, DemoAdapter
from app.core.security import hash_password
from app.db.base import utcnow
from app.models import (
    AdministrativeArea,
    Agency,
    Country,
    DataProvider,
    MarketForecast,
    MarketMetric,
    PhysicalProperty,
    PropertyListing,
    User,
    Watchlist,
    WatchlistItem,
)
from app.services import forecast as forecast_service
from app.services import market as market_service
from app.services.versioning import apply_listing_update, create_initial_version

logger = logging.getLogger("remip.seed")

DEMO_USER_EMAIL = "demo@example.com"
DEMO_ADMIN_EMAIL = "admin@example.com"
DEMO_PASSWORD = "demo1234"  # demo-only credentials, documented in README


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace("à", "a").replace("è", "e")


def _month_start(d: date, months_back: int) -> date:
    total = d.year * 12 + (d.month - 1) - months_back
    return date(total // 12, total % 12 + 1, 1)


def seed_database(db: Session, listings_per_neighborhood: int = 12, seed: int = 42) -> None:
    if db.scalar(select(Country.code).limit(1)):
        return  # already seeded
    rng = random.Random(seed)
    logger.info("seeding demo database…")

    italy = Country(
        code="IT",
        name="Italia",
        currency="EUR",
        locale="it",
        unit_system="metric",
        admin_levels=["region", "province", "city", "neighborhood"],
    )
    db.add(italy)

    provider = DataProvider(
        code="demo_it",
        name="REMIP Demo Data (Italia)",
        kind="demo",
        tos_compliant=True,
        enabled=True,
        is_demo=True,
        quality_score=0.99,
        last_ingested_at=utcnow(),
        notes="Dataset sintetico deterministico. Nessun dato reale.",
    )
    # Real-source placeholders: interface only, disabled until an agreement exists.
    db.add_all(
        [
            provider,
            DataProvider(
                code="omi_it",
                name="OMI - Agenzia delle Entrate (quotazioni)",
                kind="open_data",
                tos_compliant=True,
                enabled=False,
                is_demo=False,
                quality_score=0.0,
                notes="Adapter previsto in M4. Licenza e granularità da verificare.",
            ),
            DataProvider(
                code="portal_generic",
                name="Portale annunci (da autorizzare)",
                kind="portal",
                tos_compliant=False,
                enabled=False,
                is_demo=False,
                quality_score=0.0,
                notes="Solo interfaccia: richiede accordo commerciale/API autorizzata.",
            ),
        ]
    )
    db.flush()

    agencies: dict[str, Agency] = {}
    areas: dict[tuple[str, str], AdministrativeArea] = {}
    for city, cfg in CITIES.items():
        region_key = ("region", cfg["region"])
        if region_key not in areas:
            areas[region_key] = AdministrativeArea(
                country_code="IT",
                level="region",
                name=cfg["region"],
                slug=_slug(cfg["region"]),
                centroid_lat=cfg["lat"],
                centroid_lon=cfg["lon"],
            )
            db.add(areas[region_key])
            db.flush()
        province_key = ("province", cfg["province"])
        if province_key not in areas:
            areas[province_key] = AdministrativeArea(
                country_code="IT",
                level="province",
                name=cfg["province"],
                slug=_slug(cfg["province"]) + "-provincia",
                parent_id=areas[region_key].id,
                centroid_lat=cfg["lat"],
                centroid_lon=cfg["lon"],
            )
            db.add(areas[province_key])
            db.flush()
        city_area = AdministrativeArea(
            country_code="IT",
            level="city",
            name=city,
            slug=_slug(city),
            parent_id=areas[province_key].id,
            centroid_lat=cfg["lat"],
            centroid_lon=cfg["lon"],
            population=cfg["population"],
        )
        areas[("city", city)] = city_area
        db.add(city_area)
        db.flush()
        for neighborhood in cfg["neighborhoods"]:
            n_area = AdministrativeArea(
                country_code="IT",
                level="neighborhood",
                name=neighborhood,
                slug=f"{_slug(city)}-{_slug(neighborhood)}",
                parent_id=city_area.id,
                centroid_lat=cfg["lat"] + rng.uniform(-0.02, 0.02),
                centroid_lon=cfg["lon"] + rng.uniform(-0.02, 0.02),
            )
            areas[("neighborhood", f"{city}/{neighborhood}")] = n_area
            db.add(n_area)
    db.flush()

    adapter = DemoAdapter(seed=seed, listings_per_neighborhood=listings_per_neighborhood)
    listings: list[PropertyListing] = []
    for raw in adapter.run():
        p = raw.payload
        if p["agency"] not in agencies:
            agencies[p["agency"]] = Agency(name=p["agency"], provider_id=provider.id)
            db.add(agencies[p["agency"]])
            db.flush()
        area = areas[("neighborhood", f"{p['city']}/{p['neighborhood']}")]
        prop = PhysicalProperty(
            area_id=area.id,
            address_text=p["address_text"],
            lat=p["lat"],
            lon=p["lon"],
            property_type=p["property_type"],
            size_sqm=p["size_sqm"],
            rooms=p["rooms"],
            bathrooms=p["bathrooms"],
            floor=p["floor"],
            year_built=p["year_built"],
            energy_class=p["energy_class"],
            features=p["features"],
        )
        db.add(prop)
        db.flush()
        published = utcnow() - timedelta(days=p["days_on_market"])
        listing = PropertyListing(
            property_id=prop.id,
            provider_id=provider.id,
            agency_id=agencies[p["agency"]].id,
            source_external_id=p["external_id"],
            listing_type=p["listing_type"],
            status="active",
            title=f"{p['property_type'].replace('_', ' ').title()} "
            f"{p['rooms']} locali - {p['neighborhood']}, {p['city']}",
            description=f"[DATI DEMO] Immobile sintetico di {p['size_sqm']} m² "
            f"in zona {p['neighborhood']}.",
            current_price=p["price"],
            currency=p["currency"],
            photos_count=p["photos_count"],
            published_at=published,
            first_seen_at=published,
            last_seen_at=utcnow(),
        )
        db.add(listing)
        db.flush()
        create_initial_version(db, listing)
        listings.append(listing)

    # Version history: ~30% got a price cut, some were removed or relisted.
    for listing in listings:
        roll = rng.random()
        if roll < 0.30:
            cut = rng.uniform(0.03, 0.12)
            apply_listing_update(
                db, listing, {"price": round(listing.current_price * (1 - cut), -2)}
            )
        elif roll < 0.38:
            apply_listing_update(db, listing, {"status": "removed"})
        elif roll < 0.42:
            apply_listing_update(db, listing, {"status": "removed"})
            apply_listing_update(db, listing, {"status": "relisted"})

    # 36 months of metrics per city and neighborhood, coherent with city trends.
    today = date.today()
    for (level, key), area in areas.items():
        if level in ("region", "province"):
            continue
        city = key.split("/")[0] if level == "neighborhood" else key
        cfg = CITIES[city]
        multiplier = (
            cfg["neighborhoods"][key.split("/")[1]] if level == "neighborhood" else 1.0
        )
        base_sqm = cfg["base_sqm"] * multiplier
        monthly_trend = (1 + cfg["trend"] / 100) ** (1 / 12) - 1
        sample = max(20, listings_per_neighborhood * (4 if level == "city" else 1))
        for back in range(METRIC_MONTHS - 1, -1, -1):
            noise = rng.uniform(-0.015, 0.015)
            sqm = base_sqm * ((1 + monthly_trend) ** (-back)) * (1 + noise)
            avg_size = 85.0
            rent_sqm = cfg["rent_sqm"] * multiplier * ((1 + monthly_trend * 0.6) ** (-back))
            db.add(
                MarketMetric(
                    area_id=area.id,
                    period=_month_start(today, back),
                    listing_type="sale",
                    avg_price=round(sqm * avg_size, 0),
                    median_price=round(sqm * avg_size * 0.93, 0),
                    avg_price_sqm=round(sqm, 0),
                    median_price_sqm=round(sqm * 0.95, 0),
                    active_listings=int(sample * rng.uniform(0.8, 1.2)),
                    new_listings=int(sample * rng.uniform(0.08, 0.2)),
                    removed_listings=int(sample * rng.uniform(0.05, 0.15)),
                    avg_days_on_market=round(rng.uniform(45, 130), 0),
                    price_reduction_share=round(rng.uniform(0.15, 0.4), 2),
                    avg_discount_pct=round(rng.uniform(2.0, 8.0), 1),
                    rent_avg_sqm=round(rent_sqm, 1),
                    gross_yield_pct=round(rent_sqm * 12 / sqm * 100, 2),
                    sample_size=sample,
                    data_quality=0.99,
                    source_code="demo_it",
                )
            )
        db.flush()
        series = market_service.get_series(db, area.id)
        for fc in forecast_service.compute_forecasts(series):
            db.add(MarketForecast(area_id=area.id, listing_type="sale", **fc))

    demo_user = User(
        email=DEMO_USER_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="Utente Demo",
        role="user",
        onboarding_completed=True,
    )
    admin_user = User(
        email=DEMO_ADMIN_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="Admin Demo",
        role="admin",
        onboarding_completed=True,
    )
    db.add_all([demo_user, admin_user])
    db.flush()

    watchlist = Watchlist(user_id=demo_user.id, name="Osservati")
    db.add(watchlist)
    db.flush()
    first_active = next(li for li in listings if li.status == "active")
    db.add(
        WatchlistItem(
            watchlist_id=watchlist.id,
            kind="listing",
            listing_id=first_active.id,
            initial_price=first_active.current_price,
            thresholds={"price_drop_pct": 3},
        )
    )
    db.commit()
    logger.info("demo seed completed: %d listings", len(listings))
