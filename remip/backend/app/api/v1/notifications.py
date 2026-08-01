from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbDep
from app.db.base import utcnow
from app.models import Notification, NotificationPreference
from app.schemas.listing import (
    NotificationOut,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
)
from app.services.notifications import EVENT_TITLES

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    user: CurrentUser,
    db: DbDep,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    ).all()
    unread = (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        )
        or 0
    )
    return {
        "items": [NotificationOut.model_validate(n).model_dump() for n in rows],
        "total": total,
        "unread": unread,
        "limit": limit,
        "offset": offset,
    }


@router.get("/digest")
def notification_digest(user: CurrentUser, db: DbDep) -> dict:
    """Grouped summary of unread notifications: by event type and by
    listing, so a user (or a future email digest — see docs/PLAN.md M6) sees
    the shape of what changed without scrolling a flat list. In-app only for
    now; batched email/push digests are M6 scope."""
    unread = db.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    ).all()

    by_type: dict[str, int] = {}
    by_listing: dict[str, dict] = {}
    for n in unread:
        by_type[n.type] = by_type.get(n.type, 0) + 1
        listing_id = n.payload.get("listing_id") if isinstance(n.payload, dict) else None
        if listing_id:
            entry = by_listing.setdefault(
                listing_id, {"listing_id": listing_id, "count": 0, "latest_title": n.title}
            )
            entry["count"] += 1

    return {
        "unread_total": len(unread),
        "by_type": [
            {"type": t, "label": EVENT_TITLES.get(t, "Aggiornamento"), "count": c}
            for t, c in sorted(by_type.items(), key=lambda kv: -kv[1])
        ],
        "by_listing": sorted(by_listing.values(), key=lambda e: -e["count"]),
        "generated_at": utcnow().isoformat(),
    }


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: str, user: CurrentUser, db: DbDep) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification.is_read = True
    db.commit()
    return notification


@router.post("/read-all")
def mark_all_read(user: CurrentUser, db: DbDep) -> dict:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return {"detail": "ok"}


@router.get("/preferences", response_model=NotificationPreferenceOut)
def get_preferences(user: CurrentUser, db: DbDep) -> NotificationPreferenceOut:
    pref = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    if pref is None:
        return NotificationPreferenceOut(frequency="instant", muted_types=[], updated_at=None)
    return NotificationPreferenceOut(
        frequency=pref.frequency, muted_types=pref.muted_types, updated_at=pref.updated_at
    )


@router.put("/preferences", response_model=NotificationPreferenceOut)
def update_preferences(
    body: NotificationPreferenceIn, user: CurrentUser, db: DbDep
) -> NotificationPreferenceOut:
    unknown = sorted(set(body.muted_types) - set(EVENT_TITLES))
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unknown notification type(s): {unknown}. Valid: {sorted(EVENT_TITLES)}",
        )
    pref = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    if pref is None:
        pref = NotificationPreference(user_id=user.id)
        db.add(pref)
    pref.frequency = body.frequency
    pref.muted_types = body.muted_types
    db.commit()
    db.refresh(pref)
    return NotificationPreferenceOut(
        frequency=pref.frequency, muted_types=pref.muted_types, updated_at=pref.updated_at
    )
