"""Issue and redeem single-use hashed tokens for email verification and
password reset (M6). Only ``token_hash`` is ever persisted — see
models/auth.py::AuthToken — so a leaked database row cannot be replayed as
the token itself."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_token, hash_token
from app.db.base import ensure_aware, utcnow
from app.models import AuthToken


def issue_token(db: Session, user_id: str, kind: str, expire_minutes: int) -> str:
    raw = generate_token()
    db.add(
        AuthToken(
            user_id=user_id,
            kind=kind,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(minutes=expire_minutes),
        )
    )
    return raw


def consume_token(db: Session, raw_token: str, kind: str) -> AuthToken | None:
    """Marks the token used and returns it, or ``None`` if it doesn't exist,
    was already used, or has expired."""
    record = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == hash_token(raw_token), AuthToken.kind == kind
        )
    )
    if record is None or record.used_at is not None or ensure_aware(record.expires_at) < utcnow():
        return None
    record.used_at = utcnow()
    return record
