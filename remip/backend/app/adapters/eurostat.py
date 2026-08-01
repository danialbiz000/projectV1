"""Eurostat House Price Index adapter — a genuinely live source, unlike
adapters/omi.py.

`fetch_raw()` makes a real HTTP call to Eurostat's public dissemination API
(no API key required — it's free, open, institutional data). There is no
synthetic fallback: if the request fails, BaseAdapter's retry/backoff
exhausts and raises AdapterError, which jobs/ingestion.py turns into a
DataIngestionJob with status="failed" and the real error message. No
fabricated values are ever stored.

**Honesty note**: this sandbox's egress proxy blocks arbitrary external
hosts (verified — even example.com returns a 403 policy denial), so this
adapter's live HTTP round-trip has not been exercised successfully from
here. The endpoint and dataset code (`prc_hpi_q` — House Price Index,
quarterly, Eurostat's standard code) are correct per Eurostat's documented
API structure, but were not confirmed against a live response in this
environment. The SDMX-JSON parser below is deliberately generic — it derives
dimension order and category codes from the response's own `id`/`size`/
`dimension` fields rather than hardcoding positions, so it stays correct
even if exact filter/unit codes drift. See docs/INTEGRATIONS.md and
tests/test_eurostat_adapter.py::test_live_fetch_or_skip, which makes the
real call and skips (not fails) only when the network is unreachable — so it
verifies for real in any environment with actual internet access (e.g. CI).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import BaseAdapter, RawListing, SourceInfo
from app.db.base import utcnow

EUROSTAT_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
DATASET_CODE = "prc_hpi_q"  # House Price Index, quarterly
COUNTRY = "IT"
UNITS = ["I15_Q", "RCH_A"]  # index (2015=100) and year-on-year % change
UNIT_LABELS = {"I15_Q": "index_2015q1_100", "RCH_A": "pct_change_yoy"}
INDICATOR_NAME = "House Price Index"
REQUEST_TIMEOUT_SECONDS = 15.0


def decode_flat_index(flat_index: int, sizes: list[int]) -> list[int]:
    """Row-major decode of an SDMX-JSON `value` key into per-dimension
    category indices, given the `size` array (parallel to `id`)."""
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    indices = []
    remaining = flat_index
    for stride in strides:
        indices.append(remaining // stride)
        remaining %= stride
    return indices


def parse_sdmx_json(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Generic SDMX-JSON dataset parser: reads dimension order/sizes/category
    labels from the payload itself rather than assuming a fixed shape."""
    try:
        dim_ids: list[str] = payload["id"]
        sizes: list[int] = payload["size"]
        dimensions: dict[str, Any] = payload["dimension"]
        values: dict[str, float] = payload.get("value", {})
    except KeyError as exc:
        raise ValueError(f"Unexpected Eurostat SDMX-JSON shape: missing {exc}") from exc

    index_to_code: dict[str, dict[int, str]] = {}
    for dim_id in dim_ids:
        category_index = dimensions[dim_id]["category"]["index"]
        index_to_code[dim_id] = {v: k for k, v in category_index.items()}

    records: list[dict[str, Any]] = []
    for flat_key, value in values.items():
        per_dim_indices = decode_flat_index(int(flat_key), sizes)
        codes = {
            dim_id: index_to_code[dim_id][idx]
            for dim_id, idx in zip(dim_ids, per_dim_indices, strict=True)
        }
        records.append({**codes, "value": value})
    return records


class EurostatHpiAdapter(BaseAdapter):
    def source_info(self) -> SourceInfo:
        return SourceInfo(
            code="eurostat_hpi",
            name="Eurostat - House Price Index (prc_hpi_q)",
            kind="open_data",
            tos_compliant=True,
            is_demo=False,
            quality_score=0.85,
            notes=(
                "Chiamata HTTP reale all'API pubblica Eurostat, nessuna chiave richiesta. "
                "Non fatto un fallback a valori sintetici: se la richiesta fallisce "
                "l'ingestion fallisce visibilmente. Endpoint non verificato end-to-end da "
                "questo ambiente (rete esterna bloccata in sandbox) — vedi "
                "docs/INTEGRATIONS.md."
            ),
        )

    def fetch_raw(self) -> list[dict[str, Any]]:
        params: dict[str, str | list[str]] = {
            "format": "JSON",
            "lang": "EN",
            "geo": COUNTRY,
            "purchase": "TOTAL",
            "unit": UNITS,  # httpx repeats the param per list item: unit=I15_Q&unit=RCH_A
        }
        response = httpx.get(
            f"{EUROSTAT_BASE_URL}/{DATASET_CODE}", params=params, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return parse_sdmx_json(response.json())

    def validate(self, record: dict[str, Any]) -> bool:
        return bool(
            record.get("geo") == COUNTRY
            and record.get("unit") in UNITS
            and record.get("time")
            and record.get("value") is not None
        )

    def normalize(self, record: dict[str, Any]) -> RawListing:
        now = utcnow()
        return RawListing(
            source_code="eurostat_hpi",
            external_id=f"eurostat-{DATASET_CODE}-{record['geo']}-{record['unit']}-{record['time']}",
            fetched_at=now,
            source_updated_at=now,
            payload={
                "country_code": record["geo"],
                "indicator_code": f"house_price_index_{record['unit'].lower()}",
                "indicator_name": INDICATOR_NAME,
                "period": record["time"],
                "value": float(record["value"]),
                "unit": UNIT_LABELS.get(record["unit"], record["unit"]),
            },
        )
