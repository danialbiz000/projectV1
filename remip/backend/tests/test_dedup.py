"""Unit tests for cross-agency duplicate detection (services/dedup.py) and an
integration check that the demo seed actually exercises it end-to-end."""
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.seed import DUPLICATE_AGENCY_NAMES
from app.models import Agency, PhysicalProperty, PropertyListing
from app.services.dedup import MATCH_THRESHOLD, find_duplicate_property, score_candidate


def _property(**overrides):
    defaults = dict(
        area_id="area-x",
        address_text="Via Roma 10",
        lat=45.0,
        lon=9.0,
        property_type="apartment",
        size_sqm=80.0,
        rooms=3,
    )
    defaults.update(overrides)
    return PhysicalProperty(**defaults)


def test_score_candidate_high_for_near_identical():
    subject = _property()
    scored = score_candidate(
        lat=45.0001, lon=9.0001, size_sqm=81, rooms=3, address_text="Via Roma 10", candidate=subject
    )
    assert scored.confidence >= MATCH_THRESHOLD
    assert scored.reasons  # explains why it matched


def test_score_candidate_low_for_distant_and_different_property():
    subject = _property()
    scored = score_candidate(
        lat=41.9, lon=12.5, size_sqm=40, rooms=1, address_text="Corso Napoli 99", candidate=subject
    )
    assert scored.confidence < MATCH_THRESHOLD


def test_score_candidate_low_for_same_spot_but_different_size():
    subject = _property()
    scored = score_candidate(
        lat=45.0001,
        lon=9.0001,
        size_sqm=200,
        rooms=6,
        address_text="Via Roma 10",
        candidate=subject,
    )
    assert scored.confidence < MATCH_THRESHOLD


def test_find_duplicate_property_no_match_returns_none():
    with SessionLocal() as db:
        result = find_duplicate_property(
            db,
            area_id="area-does-not-exist",
            property_type="apartment",
            lat=45.0,
            lon=9.0,
            size_sqm=80,
            rooms=3,
            address_text="Via Roma 10",
        )
        assert result is None


def test_seeded_duplicates_share_physical_property_with_high_confidence():
    with SessionLocal() as db:
        duplicate_agency_ids = [
            a.id for a in db.scalars(select(Agency).where(Agency.name.in_(DUPLICATE_AGENCY_NAMES)))
        ]
        assert duplicate_agency_ids, "seed should create the duplicate-testing agencies"

        duplicate_listings = db.scalars(
            select(PropertyListing).where(PropertyListing.agency_id.in_(duplicate_agency_ids))
        ).all()
        assert duplicate_listings, "seed should generate at least one republished listing"

        for dup in duplicate_listings:
            siblings = db.scalars(
                select(PropertyListing).where(
                    PropertyListing.property_id == dup.property_id,
                    PropertyListing.id != dup.id,
                )
            ).all()
            assert siblings, f"{dup.id} should share its physical property with another listing"
            assert dup.dedup_confidence >= MATCH_THRESHOLD


def test_listing_detail_exposes_duplicate_listings(client):
    with SessionLocal() as db:
        duplicate_agency_ids = [
            a.id for a in db.scalars(select(Agency).where(Agency.name.in_(DUPLICATE_AGENCY_NAMES)))
        ]
        dup = db.scalars(
            select(PropertyListing).where(PropertyListing.agency_id.in_(duplicate_agency_ids))
        ).first()
        assert dup is not None
        listing_id = dup.id

    detail = client.get(f"/api/v1/listings/{listing_id}").json()
    assert detail["duplicate_listings"], "detail should list sibling listings for the same property"
    sibling = detail["duplicate_listings"][0]
    assert sibling["agency_name"]
    assert 0 <= sibling["dedup_confidence"] <= 1
