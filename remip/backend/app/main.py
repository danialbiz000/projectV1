from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.metrics import record_request, render_prometheus
from app.db.base import Base, SessionLocal, engine, ensure_postgis
from app.db.seed import seed_database

logging.basicConfig(level=logging.INFO)
settings = get_settings()
access_logger = logging.getLogger("remip.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_postgis()
    # M1 runs schema creation directly; Alembic migrations arrive with M2+.
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed_database(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "API della Real Estate Market Intelligence Platform. "
        "**Tutti i dati sono sintetici (demo)**: nessuna fonte reale è ancora integrata "
        "(vedi `/api/v1/sources` e docs/INTEGRATIONS.md)."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Structured access log line + in-process Prometheus counters (M6) for
    every request. Uses the matched route's path *template*
    (``/listings/{listing_id}``), not the raw URL, so per-entity IDs don't
    blow up metric cardinality — see core/metrics.py."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    route = request.scope.get("route")
    path_template = route.path if route is not None else request.url.path
    record_request(request.method, path_template, response.status_code, duration)
    access_logger.info(
        "method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        path_template,
        response.status_code,
        duration * 1000,
    )
    return response


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "demo_mode": settings.demo_mode}


@app.get("/metrics", tags=["health"])
def metrics() -> Response:
    """Prometheus-scrapeable request metrics. Process-local (see
    core/metrics.py); no auth by design — Prometheus itself has none in a
    typical local scrape setup — so a production deployment should restrict
    network access to this path rather than expose it publicly (see
    docs/DEPLOYMENT.md)."""
    return Response(render_prometheus(), media_type="text/plain; version=0.0.4")
