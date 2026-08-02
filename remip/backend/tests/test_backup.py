"""Database backup (M6). The test suite runs against an in-memory SQLite
database (see conftest.py), which has no file to copy — that's exercised
directly as the honest 400 case. The real file-copy path is proven against
a temporary on-disk SQLite file instead, and the object-storage round trip
through services/storage.py is verified end-to-end."""
import sqlite3

import pytest

import app.services.backup as backup_service
import app.services.storage as storage_service
from app.core.config import get_settings
from app.services.storage import get_snapshot


def test_backup_requires_admin(client, user_headers):
    assert client.post("/api/v1/admin/backup", headers=user_headers).status_code == 403


def test_backup_in_memory_sqlite_returns_honest_400(client, admin_headers):
    response = client.post("/api/v1/admin/backup", headers=admin_headers)
    assert response.status_code == 400
    assert "in-memory" in response.json()["detail"]


def test_create_backup_copies_sqlite_file_bytes_and_round_trips(tmp_path, monkeypatch):
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()
    original_bytes = db_path.read_bytes()

    fake_settings = get_settings().model_copy(
        update={
            "database_url": f"sqlite:///{db_path}",
            "s3_endpoint_url": None,
            "snapshot_local_dir": str(tmp_path / "snapshots"),
        }
    )
    monkeypatch.setattr(backup_service, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(storage_service, "get_settings", lambda: fake_settings)

    result = backup_service.create_backup()
    assert result["size_bytes"] == len(original_bytes)
    assert result["storage_key"].startswith("file://")
    assert get_snapshot(result["storage_key"]) == original_bytes


def test_dump_sqlite_missing_file_raises(tmp_path):
    with pytest.raises(backup_service.BackupError, match="not found"):
        backup_service._dump_sqlite(f"sqlite:///{tmp_path / 'nope.db'}")


def test_dump_postgres_without_pg_dump_raises(monkeypatch):
    monkeypatch.setattr(backup_service.shutil, "which", lambda name: None)
    with pytest.raises(backup_service.BackupError, match="pg_dump"):
        backup_service._dump_postgres("postgresql://user:pass@localhost/db")


def test_create_backup_unknown_scheme_raises(monkeypatch):
    fake_settings = get_settings().model_copy(update={"database_url": "mysql://user@host/db"})
    monkeypatch.setattr(backup_service, "get_settings", lambda: fake_settings)
    with pytest.raises(backup_service.BackupError, match="No backup strategy"):
        backup_service.create_backup()
