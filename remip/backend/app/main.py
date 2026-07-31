from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.db.base import Base, SessionLocal, engine
from app.db.seed import seed_database

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "demo_mode": settings.demo_mode}
