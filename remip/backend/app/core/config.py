from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REMIP_", env_file=".env", extra="ignore")

    app_name: str = "REMIP - Real Estate Market Intelligence Platform"
    environment: str = "development"
    # SQLite by default so the API runs with zero external services;
    # docker-compose overrides this with the PostgreSQL/PostGIS DSN.
    database_url: str = "sqlite:///./remip.db"
    # Dev-only fallback. Any non-development environment must set REMIP_SECRET_KEY.
    secret_key: str = "dev-only-secret-change-me-0123456789abcdef"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:3000"]
    demo_mode: bool = True
    seed_on_startup: bool = True

    # Job queue (M4). Ingestion still works with no Redis at all: the admin
    # trigger and seed-time bootstrap call run_ingestion() inline when the
    # queue is unreachable — see jobs/ingestion.py.
    redis_url: str = "redis://localhost:6379/0"
    ingestion_queue_name: str = "remip-ingestion"
    ingestion_interval_minutes: int = 360

    # Object storage for listing-version snapshots (M4). Falls back to local
    # disk under `snapshot_local_dir` when unset, so this never blocks the
    # zero-external-services dev flow described in the README.
    s3_endpoint_url: str | None = None
    s3_bucket: str = "remip-snapshots"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    snapshot_local_dir: str = "./data/snapshots"


@lru_cache
def get_settings() -> Settings:
    return Settings()
