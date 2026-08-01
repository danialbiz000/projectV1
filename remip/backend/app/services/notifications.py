"""In-app notifications for users watching a listing.

Deduplication: the (user_id, dedup_key) unique constraint plus an existence
check guarantee that the same event never notifies the same user twice.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    NotificationPreference,
    PropertyListing,
    Watchlist,
    WatchlistItem,
)

EVENT_TITLES = {
    "price_drop": "Prezzo ridotto",
    "price_increase": "Prezzo aumentato",
    "listing_removed": "Annuncio rimosso",
    "listing_relisted": "Annuncio ripubblicato",
    "possible_sale": "Possibile vendita",
    "status_change": "Stato annuncio cambiato",
    "photos_change": "Fotografie aggiornate",
    "listing_update": "Annuncio aggiornato",
}


def _describe(event_type: str, listing: PropertyListing, diff: dict[str, Any]) -> str:
    if event_type in ("price_drop", "price_increase") and "price" in diff:
        old, new = diff["price"]["old"], diff["price"]["new"]
        pct = (new - old) / old * 100 if old else 0.0
        return (
            f"{listing.title}: prezzo da {old:,.0f} a {new:,.0f} {listing.currency} "
            f"({pct:+.1f}%)"
        )
    return f"{listing.title}: {', '.join(diff.keys())}"


def watching_user_ids(db: Session, listing_id: str) -> list[str]:
    rows = db.execute(
        select(Watchlist.user_id)
        .join(WatchlistItem, WatchlistItem.watchlist_id == Watchlist.id)
        .where(WatchlistItem.listing_id == listing_id, WatchlistItem.notify.is_(True))
        .distinct()
    )
    return [r[0] for r in rows]


def _is_muted(db: Session, user_id: str, event_type: str) -> bool:
    pref = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    return pref is not None and event_type in pref.muted_types


def notify_listing_event(
    db: Session,
    listing: PropertyListing,
    event_type: str,
    diff: dict[str, Any],
    version_number: int,
) -> list[Notification]:
    dedup_key = f"listing:{listing.id}:v{version_number}:{event_type}"
    created: list[Notification] = []
    for user_id in watching_user_ids(db, listing.id):
        if _is_muted(db, user_id, event_type):
            continue
        exists = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id, Notification.dedup_key == dedup_key
            )
        )
        if exists:
            continue
        notification = Notification(
            user_id=user_id,
            type=event_type,
            title=EVENT_TITLES.get(event_type, "Aggiornamento"),
            body=_describe(event_type, listing, diff),
            payload={"listing_id": listing.id, "diff": diff, "version": version_number},
            dedup_key=dedup_key,
        )
        db.add(notification)
        created.append(notification)
    db.flush()
    return created
