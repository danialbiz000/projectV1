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


@lru_cache
def get_settings() -> Settings:
    return Settings()
