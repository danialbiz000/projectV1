"""Alembic migrations (M6+). `alembic upgrade head` must produce exactly
the schema SQLAlchemy's models describe via Base.metadata — this is the
regression check that would catch the two drifting (e.g. a new/changed
model added without a matching migration). Runs against its own temporary
SQLite file, independent of the shared in-memory test database used by
every other test in this suite."""
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

import app.core.config as app_config
from alembic import command
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_matches_model_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_migration_test.db"
    fake_settings = app_config.get_settings().model_copy(
        update={"database_url": f"sqlite:///{db_path}"}
    )
    monkeypatch.setattr(app_config, "get_settings", lambda: fake_settings)

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        db_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        model_tables = set(Base.metadata.tables.keys())
        assert db_tables == model_tables
    finally:
        engine.dispose()


def test_alembic_downgrade_to_base_removes_everything(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_downgrade_test.db"
    fake_settings = app_config.get_settings().model_copy(
        update={"database_url": f"sqlite:///{db_path}"}
    )
    monkeypatch.setattr(app_config, "get_settings", lambda: fake_settings)

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
        assert remaining == set()
    finally:
        engine.dispose()
