"""GDPR self-service endpoints (M6): export and erasure of one's own data.
Scoped to CurrentUser only — there is no admin-triggered export/erasure of
another user's data, by design."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.security import generate_token, hash_password
from app.db.base import utcnow
from app.models import (
    AuditLog,
    AuthToken,
    Notification,
    NotificationPreference,
    OAuthAccount,
    Watchlist,
)
from app.schemas.auth import MessageResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/export")
def export_my_data(user: CurrentUser, db: DbDep) -> dict:
    """Everything stored about the current account, as a single JSON
    document — Art. 20 GDPR data portability. Valuations are intentionally
    absent: they are point-in-time snapshots on a *listing*, not attributed
    to the user who requested them (see models/valuation.py)."""
    watchlists = db.scalars(select(Watchlist).where(Watchlist.user_id == user.id)).all()
    notifications = db.scalars(
        select(Notification).where(Notification.user_id == user.id)
    ).all()
    preference = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    oauth_accounts = db.scalars(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id)
    ).all()
    audit_log = db.scalars(
        select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.at)
    ).all()

    return {
        "exported_at": utcnow().isoformat(),
        "profile": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "email_verified": user.email_verified,
            "onboarding_completed": user.onboarding_completed,
            "created_at": user.created_at.isoformat(),
        },
        "watchlists": [
            {
                "id": w.id,
                "name": w.name,
                "created_at": w.created_at.isoformat(),
                "items": [
                    {
                        "id": i.id,
                        "kind": i.kind,
                        "listing_id": i.listing_id,
                        "area_id": i.area_id,
                        "note": i.note,
                        "initial_price": i.initial_price,
                        "notify": i.notify,
                        "created_at": i.created_at.isoformat(),
                    }
                    for i in w.items
                ],
            }
            for w in watchlists
        ],
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "notification_preference": (
            {
                "frequency": preference.frequency,
                "muted_types": preference.muted_types,
                "updated_at": preference.updated_at.isoformat(),
            }
            if preference
            else None
        ),
        "oauth_accounts": [
            {"provider": a.provider, "provider_account_id": a.provider_account_id}
            for a in oauth_accounts
        ],
        "audit_log": [
            {
                "action": a.action,
                "entity": a.entity,
                "entity_id": a.entity_id,
                "at": a.at.isoformat(),
            }
            for a in audit_log
        ],
    }


@router.delete("/me", response_model=MessageResponse)
def delete_my_account(user: CurrentUser, db: DbDep) -> MessageResponse:
    """Right to erasure (Art. 17 GDPR). The user row is anonymized rather
    than hard-deleted — AuditLog.user_id has no foreign key and audit trails
    are routinely kept post-erasure for security/legal accountability, a
    recognized GDPR exception — but every other table that can hold
    user-authored content (watchlists, notifications, preferences, linked
    OAuth identities, pending tokens) is deleted outright."""
    user_id = user.id
    for watchlist in db.scalars(select(Watchlist).where(Watchlist.user_id == user_id)).all():
        db.delete(watchlist)  # cascades to WatchlistItem
    for notification in db.scalars(
        select(Notification).where(Notification.user_id == user_id)
    ).all():
        db.delete(notification)
    preference = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if preference is not None:
        db.delete(preference)
    for account in db.scalars(select(OAuthAccount).where(OAuthAccount.user_id == user_id)).all():
        db.delete(account)
    for token in db.scalars(select(AuthToken).where(AuthToken.user_id == user_id)).all():
        db.delete(token)

    user.email = f"deleted-{user.id}@deleted.remip.invalid"
    user.full_name = ""
    user.password_hash = hash_password(generate_token())  # unusable, never shared with the user
    user.is_active = False
    user.email_verified = False
    db.add(
        AuditLog(user_id=user_id, action="user.self_delete", entity="user", entity_id=user_id)
    )
    db.commit()
    return MessageResponse(detail="Account eliminato")
