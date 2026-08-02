"""OAuth2 login endpoints (M6). See services/oauth.py for why every
provider is "not configured" in this deployment by default, and for the
mock-provider testing approach.

Known limitation: the ``state`` parameter is generated for standards
compliance but not persisted server-side for verification on callback —
this stateless JWT-only backend has no session store to tie it to. A
production deployment should bind ``state`` to a short-lived server-side
session (or a signed, time-boxed cookie) before trusting it as CSRF
protection; documented in docs/PLAN.md's M6 exit notes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbDep
from app.core.config import get_settings
from app.core.security import create_access_token, generate_token, hash_password
from app.models import AuditLog, OAuthAccount, User, Watchlist
from app.schemas.auth import TokenResponse
from app.services.oauth import OAuthError, build_authorize_url, configured_providers, exchange_code

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


@router.get("/providers")
def list_providers() -> dict:
    return {"providers": sorted(configured_providers().keys())}


@router.get("/{provider}/authorize")
def authorize(provider: str) -> dict:
    providers = configured_providers()
    if provider not in providers:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"'{provider}' is not configured on this deployment (no client credentials set).",
        )
    settings = get_settings()
    redirect_uri = f"{settings.oauth_redirect_base_url}/login/oauth/{provider}/callback"
    state = generate_token()
    return {
        "authorize_url": build_authorize_url(providers[provider], redirect_uri, state),
        "state": state,
    }


@router.get("/{provider}/callback", response_model=TokenResponse)
def callback(provider: str, code: str, db: DbDep) -> TokenResponse:
    providers = configured_providers()
    if provider not in providers:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"'{provider}' is not configured")
    settings = get_settings()
    redirect_uri = f"{settings.oauth_redirect_base_url}/login/oauth/{provider}/callback"
    try:
        identity = exchange_code(providers[provider], code, redirect_uri)
    except OAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    account = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == identity.provider_account_id,
        )
    )
    if account is not None:
        user = db.get(User, account.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    else:
        # The provider vouches for this email address, so linking to an
        # existing local account (if any) is safe; otherwise provision one.
        user = db.scalar(select(User).where(User.email == identity.email.lower()))
        if user is None:
            user = User(
                email=identity.email.lower(),
                password_hash=hash_password(generate_token()),  # unusable until a reset is done
                full_name=identity.full_name,
                email_verified=True,  # the provider already verified it
            )
            db.add(user)
            db.flush()
            db.add(Watchlist(user_id=user.id))
            db.add(
                AuditLog(
                    user_id=user.id,
                    action="user.register_oauth",
                    entity="user",
                    entity_id=user.id,
                    meta={"provider": provider},
                )
            )
        db.add(
            OAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_account_id=identity.provider_account_id,
            )
        )

    db.add(
        AuditLog(
            user_id=user.id,
            action="user.login_oauth",
            entity="user",
            entity_id=user.id,
            meta={"provider": provider},
        )
    )
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role))
