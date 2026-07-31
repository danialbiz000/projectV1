"""Data-source adapter contract.

Every external source (portal, open data, commercial feed) is integrated through
a subclass of BaseAdapter. The contract enforces the requirements from
docs/INTEGRATIONS.md: source identity, timestamps, validation, normalization,
error handling with retry, rate limiting, logging, ToS compliance and a
kill-switch. Sources without an authorized API get ONLY an adapter interface
(``tos_compliant=False`` → cannot be enabled); no scraping is implemented.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.db.base import utcnow

logger = logging.getLogger("remip.ingestion")


@dataclass
class SourceInfo:
    code: str
    name: str
    kind: str  # demo | open_data | commercial | portal
    tos_compliant: bool
    is_demo: bool = False
    quality_score: float = 0.0
    notes: str = ""


@dataclass
class RawListing:
    """Normalized payload every adapter must emit."""

    source_code: str
    external_id: str
    fetched_at: datetime
    source_updated_at: datetime | None
    payload: dict[str, Any] = field(default_factory=dict)


class AdapterError(Exception):
    pass


class BaseAdapter(ABC):
    """Template-method base: subclasses implement fetching and validation,
    the base class provides retry, rate limiting and logging."""

    max_retries = 3
    retry_backoff_seconds = 1.0
    min_seconds_between_requests = 0.0

    def __init__(self, enabled: bool = True) -> None:
        info = self.source_info()
        if enabled and not info.tos_compliant:
            raise AdapterError(
                f"Adapter '{info.code}' cannot be enabled: source terms of service "
                "do not allow automated access. Awaiting a licensed API/agreement."
            )
        self.enabled = enabled
        self._last_request_at = 0.0

    @abstractmethod
    def source_info(self) -> SourceInfo: ...

    @abstractmethod
    def fetch_raw(self) -> list[dict[str, Any]]:
        """Fetch raw records from the source (one network/page unit)."""

    @abstractmethod
    def validate(self, record: dict[str, Any]) -> bool: ...

    @abstractmethod
    def normalize(self, record: dict[str, Any]) -> RawListing: ...

    def dedup_key(self, listing: RawListing) -> str:
        return f"{listing.source_code}:{listing.external_id}"

    def _throttle(self) -> None:
        if self.min_seconds_between_requests <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_seconds_between_requests:
            time.sleep(self.min_seconds_between_requests - elapsed)
        self._last_request_at = time.monotonic()

    def run(self) -> list[RawListing]:
        info = self.source_info()
        if not self.enabled:
            logger.info("adapter %s disabled, skipping", info.code)
            return []
        attempt = 0
        while True:
            try:
                self._throttle()
                raw = self.fetch_raw()
                break
            except Exception as exc:  # noqa: BLE001 - retry any fetch failure
                attempt += 1
                if attempt >= self.max_retries:
                    logger.error("adapter %s failed after %d attempts: %s", info.code, attempt, exc)
                    raise AdapterError(str(exc)) from exc
                sleep_for = self.retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "adapter %s attempt %d failed, retrying in %.1fs",
                    info.code,
                    attempt,
                    sleep_for,
                )
                time.sleep(sleep_for)

        results: list[RawListing] = []
        seen: set[str] = set()
        for record in raw:
            if not self.validate(record):
                logger.warning("adapter %s: invalid record skipped", info.code)
                continue
            normalized = self.normalize(record)
            key = self.dedup_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            results.append(normalized)
        logger.info("adapter %s: %d records at %s", info.code, len(results), utcnow().isoformat())
        return results
