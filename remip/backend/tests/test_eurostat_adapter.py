"""adapters/eurostat.py: the SDMX-JSON parser is tested against a
hand-built, structurally-accurate sample (deterministic, no network) so its
correctness doesn't depend on this sandbox's blocked egress. The one test
that makes a real HTTP call self-skips when the network is unreachable
rather than failing — see test_live_fetch_or_skip below."""
import pytest

from app.adapters.base import AdapterError
from app.adapters.eurostat import EurostatHpiAdapter, decode_flat_index, parse_sdmx_json

# Hand-built, structurally accurate Eurostat SDMX-JSON sample:
# dimensions freq(1) x unit(2: I15_Q, RCH_A) x purchase(1) x geo(1) x time(3),
# row-major flat index = unit_idx*3 + time_idx (other dims fixed at 0).
SAMPLE_PAYLOAD = {
    "version": "2.0",
    "class": "dataset",
    "id": ["freq", "unit", "purchase", "geo", "time"],
    "size": [1, 2, 1, 1, 3],
    "dimension": {
        "freq": {"category": {"index": {"Q": 0}}},
        "unit": {"category": {"index": {"I15_Q": 0, "RCH_A": 1}}},
        "purchase": {"category": {"index": {"TOTAL": 0}}},
        "geo": {"category": {"index": {"IT": 0}}},
        "time": {"category": {"index": {"2024-Q4": 0, "2025-Q1": 1, "2025-Q2": 2}}},
    },
    "value": {
        "0": 118.5,
        "1": 119.0,
        "2": 119.8,
        "3": 3.2,
        "4": 3.5,
        "5": 3.9,
    },
}


def test_decode_flat_index_matches_hand_computed_positions():
    sizes = [1, 2, 1, 1, 3]
    assert decode_flat_index(0, sizes) == [0, 0, 0, 0, 0]  # I15_Q, 2024-Q4
    assert decode_flat_index(3, sizes) == [0, 1, 0, 0, 0]  # RCH_A, 2024-Q4
    assert decode_flat_index(5, sizes) == [0, 1, 0, 0, 2]  # RCH_A, 2025-Q2


def test_parse_sdmx_json_decodes_all_records():
    records = parse_sdmx_json(SAMPLE_PAYLOAD)
    assert len(records) == 6
    by_key = {(r["unit"], r["time"]): r["value"] for r in records}
    assert by_key[("I15_Q", "2024-Q4")] == 118.5
    assert by_key[("I15_Q", "2025-Q2")] == 119.8
    assert by_key[("RCH_A", "2025-Q1")] == 3.5
    assert all(r["geo"] == "IT" and r["purchase"] == "TOTAL" and r["freq"] == "Q" for r in records)


def test_parse_sdmx_json_raises_clear_error_on_malformed_payload():
    with pytest.raises(ValueError, match="Unexpected Eurostat SDMX-JSON shape"):
        parse_sdmx_json({"not": "the expected shape"})


def test_validate_accepts_only_italy_and_known_units():
    adapter = EurostatHpiAdapter()
    valid = {"geo": "IT", "unit": "I15_Q", "time": "2025-Q2", "value": 119.8}
    assert adapter.validate(valid) is True
    assert adapter.validate({**valid, "geo": "FR"}) is False
    assert adapter.validate({**valid, "unit": "UNKNOWN"}) is False
    assert adapter.validate({**valid, "value": None}) is False


def test_normalize_produces_economic_indicator_shaped_payload():
    adapter = EurostatHpiAdapter()
    record = {"geo": "IT", "unit": "I15_Q", "time": "2025-Q2", "value": 119.8}
    raw = adapter.normalize(record)
    assert raw.source_code == "eurostat_hpi"
    assert raw.external_id == "eurostat-prc_hpi_q-IT-I15_Q-2025-Q2"
    assert raw.payload == {
        "country_code": "IT",
        "indicator_code": "house_price_index_i15_q",
        "indicator_name": "House Price Index",
        "period": "2025-Q2",
        "value": 119.8,
        "unit": "index_2015q1_100",
    }


def test_source_info_declares_live_not_demo():
    info = EurostatHpiAdapter().source_info()
    assert info.code == "eurostat_hpi"
    assert info.is_demo is False
    assert info.tos_compliant is True


def test_live_fetch_or_skip():
    """Makes a real HTTP call to Eurostat's public API. In network-restricted
    environments (this sandbox's egress proxy blocks arbitrary hosts) it
    skips rather than fails; in any environment with real internet access
    (e.g. CI) it verifies the live round-trip and response shape for real."""
    try:
        raw_records = EurostatHpiAdapter().run()
    except AdapterError as exc:
        pytest.skip(f"Eurostat unreachable from this environment: {exc}")
    assert len(raw_records) > 0
    assert all(r.payload["country_code"] == "IT" for r in raw_records)
    assert all(r.payload["indicator_code"].startswith("house_price_index_") for r in raw_records)
