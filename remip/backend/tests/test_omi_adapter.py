from datetime import date

from app.adapters.omi import ZONES, OmiAdapter, _current_semester, _previous_semester


def test_semester_helpers():
    assert _current_semester(date(2026, 3, 15)) == "2026-1"
    assert _current_semester(date(2026, 9, 1)) == "2026-2"
    assert _previous_semester("2026-1") == "2025-2"
    assert _previous_semester("2026-2") == "2026-1"


def test_source_info_declares_illustrative_values():
    info = OmiAdapter().source_info()
    assert info.code == "omi_it"
    assert info.is_demo is True
    assert info.tos_compliant is True
    assert "fixture" in info.notes.lower() or "locale" in info.notes.lower()


def test_fetch_raw_covers_all_zones_states_semesters_and_types():
    records = OmiAdapter().fetch_raw()
    # 9 zones x 1 property type x 3 conservation states x 2 semesters x 2 listing types
    assert len(records) == len(ZONES) * 1 * 3 * 2 * 2
    assert all(r["price_sqm_max"] >= r["price_sqm_min"] > 0 for r in records)
    listing_types = {r["listing_type"] for r in records}
    assert listing_types == {"sale", "rent"}


def test_run_is_deterministic_and_deduplicated():
    a = OmiAdapter().run()
    b = OmiAdapter().run()
    assert [x.external_id for x in a] == [x.external_id for x in b]
    assert len({x.external_id for x in a}) == len(a)


def test_conservation_state_ordering_affects_price():
    records = OmiAdapter().fetch_raw()
    by_state = {
        r["stato"]: r
        for r in records
        if r["zona_code"] == "B12" and r["listing_type"] == "sale"
    }
    assert by_state["Scadente"]["price_sqm_max"] < by_state["Normale"]["price_sqm_max"]
    assert by_state["Normale"]["price_sqm_max"] < by_state["Ottimo"]["price_sqm_max"]
