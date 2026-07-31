from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbDep
from app.models import DataProvider

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources(db: DbDep) -> list[dict]:
    """Public transparency endpoint: which sources feed the platform, their
    status, quality and whether they are demo data."""
    providers = db.scalars(select(DataProvider).order_by(DataProvider.name)).all()
    return [
        {
            "code": p.code,
            "name": p.name,
            "kind": p.kind,
            "enabled": p.enabled,
            "tos_compliant": p.tos_compliant,
            "is_demo": p.is_demo,
            "quality_score": p.quality_score,
            "last_ingested_at": p.last_ingested_at.isoformat() if p.last_ingested_at else None,
            "notes": p.notes,
        }
        for p in providers
    ]
