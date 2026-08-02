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

    # Outbound email (M6). No real mailbox is configured in this environment
    # — see services/email.py — so the console adapter (log only) is used
    # whenever smtp_host is unset. Setting it switches to real SMTP delivery.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@remip.local"
    email_verify_token_expire_minutes: int = 60 * 24
    password_reset_token_expire_minutes: int = 30

    # Rate limiting (M6). Redis-backed with an in-memory fallback — see
    # core/rate_limit.py — same reachability pattern as the job queue.
    rate_limit_login_per_minute: int = 10
    rate_limit_register_per_minute: int = 5
    rate_limit_password_reset_per_minute: int = 5

    # OAuth login (M6). Unset by default: no real client credentials are
    # available in this environment, so every provider reports as
    # "not configured" until these are set — see services/oauth.py. The
    # endpoint URLs default to Google's real ones but are overridable so
    # tests can point them at a local mock instead of the live network.
    oauth_google_client_id: str | None = None
    oauth_google_client_secret: str | None = None
    oauth_google_authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    oauth_google_token_url: str = "https://oauth2.googleapis.com/token"
    oauth_google_userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo"
    oauth_redirect_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
