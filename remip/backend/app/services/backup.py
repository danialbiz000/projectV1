"""Database backup (M6): dumps the database and stores it through the
existing object-storage abstraction — S3-compatible when configured, local
disk otherwise, see services/storage.py. SQLite: copy the file bytes
directly. PostgreSQL: shell out to ``pg_dump`` if it's on PATH.

No automated restore endpoint exists. Restoring a database is destructive
enough that it belongs in an operator runbook (docs/DEPLOYMENT.md), not
behind an API call an admin token could trigger by mistake.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.db.base import utcnow
from app.services.storage import save_snapshot


class BackupError(Exception):
    pass


def create_backup() -> dict:
    settings = get_settings()
    url = settings.database_url
    timestamp = utcnow().strftime("%Y%m%dT%H%M%SZ")

    if url.startswith("sqlite"):
        data, extension = _dump_sqlite(url), "db"
    elif url.startswith("postgresql"):
        data, extension = _dump_postgres(url), "sql"
    else:
        raise BackupError(f"No backup strategy for this database URL scheme: '{url}'")

    key = f"backups/remip-{timestamp}.{extension}"
    storage_key = save_snapshot(key, data, content_type="application/octet-stream")
    return {"storage_key": storage_key, "size_bytes": len(data), "created_at": timestamp}


def _dump_sqlite(url: str) -> bytes:
    path = url.removeprefix("sqlite:///")
    if path == ":memory:":
        raise BackupError(
            "Cannot back up an in-memory SQLite database (no file exists to copy)."
        )
    file_path = Path(path)
    if not file_path.exists():
        raise BackupError(f"SQLite database file not found: {file_path}")
    return file_path.read_bytes()


def _dump_postgres(url: str) -> bytes:
    if shutil.which("pg_dump") is None:
        raise BackupError(
            "pg_dump is not available on PATH; cannot back up PostgreSQL (install the "
            "postgresql-client package on the backend/worker image)."
        )
    result = subprocess.run(
        ["pg_dump", "--format=plain", "--no-owner", "--dbname", url],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise BackupError(f"pg_dump failed: {result.stderr.decode(errors='replace')}")
    return result.stdout
