from __future__ import annotations

import logging
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

logger = logging.getLogger("remip.db")


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_aware(dt: datetime) -> datetime:
    """SQLite silently drops tzinfo on read for ``DateTime(timezone=True)``
    columns; PostgreSQL does not. Comparing a value read back from either
    dialect against ``utcnow()`` needs this normalization first."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_postgis() -> None:
    """Enable the PostGIS extension when running on PostgreSQL.

    M3's spatial filters (radius/polygon) run in Python for SQLite/Postgres
    portability (see services/geo.py); this only readies the schema for
    indexed PostGIS geometry columns (ST_DWithin/ST_Contains) once listing
    volume justifies them (M4+). A missing CREATE EXTENSION privilege is
    logged, not fatal — the platform still runs without it.
    """
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    except DBAPIError:
        logger.warning("Could not enable PostGIS extension (missing privilege?)", exc_info=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
