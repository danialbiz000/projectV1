from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditLog, User, Watchlist
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OnboardingRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyEmailRequest,
)
from app.services import auth_tokens
from app.services.email import EmailMessage, send_email

router = APIRouter(prefix="/auth", tags=["auth"])


def _send_verification_email(db, user: User) -> str:
    settings = get_settings()
    raw_token = auth_tokens.issue_token(
        db, user.id, "email_verify", settings.email_verify_token_expire_minutes
    )
    link = f"{settings.oauth_redirect_base_url}/verify-email?token={raw_token}"
    send_email(
        EmailMessage(
            to=user.email,
            subject="Conferma il tuo indirizzo email — REMIP",
            body=f"Conferma il tuo indirizzo email: {link}\n\nIl link scade tra "
            f"{settings.email_verify_token_expire_minutes} minuti.",
        )
    )
    return raw_token


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, request: Request, db: DbDep) -> User:
    enforce_rate_limit("register", request, get_settings().rate_limit_register_per_minute)
    existing = db.scalar(select(User).where(User.email == body.email.lower()))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    db.flush()
    db.add(Watchlist(user_id=user.id))  # default watchlist
    db.add(AuditLog(user_id=user.id, action="user.register", entity="user", entity_id=user.id))
    _send_verification_email(db, user)
    db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DbDep) -> TokenResponse:
    enforce_rate_limit("login", request, get_settings().rate_limit_login_per_minute)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    db.add(AuditLog(user_id=user.id, action="user.login", entity="user", entity_id=user.id))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/onboarding", response_model=UserOut)
def complete_onboarding(body: OnboardingRequest, user: CurrentUser, db: DbDep) -> User:
    user.onboarding_completed = True
    db.add(
        AuditLog(
            user_id=user.id,
            action="user.onboarding",
            entity="user",
            entity_id=user.id,
            meta={"goal": body.goal, "preferred_country": body.preferred_country},
        )
    )
    db.commit()
    return user


@router.post("/verify-email/request", response_model=MessageResponse)
def request_email_verification(user: CurrentUser, db: DbDep) -> MessageResponse:
    if user.email_verified:
        return MessageResponse(detail="Email già verificata")
    raw_token = _send_verification_email(db, user)
    db.commit()
    settings = get_settings()
    return MessageResponse(
        detail="Email di verifica inviata",
        dev_token=raw_token if settings.demo_mode else None,
    )


@router.post("/verify-email/confirm", response_model=MessageResponse)
def confirm_email_verification(body: VerifyEmailRequest, db: DbDep) -> MessageResponse:
    record = auth_tokens.consume_token(db, body.token, "email_verify")
    if record is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token non valido o scaduto")
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.email_verified = True
    db.add(
        AuditLog(user_id=user.id, action="user.verify_email", entity="user", entity_id=user.id)
    )
    db.commit()
    return MessageResponse(detail="Email verificata")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: DbDep) -> MessageResponse:
    settings = get_settings()
    enforce_rate_limit("password_reset", request, settings.rate_limit_password_reset_per_minute)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    generic = MessageResponse(
        detail="Se l'indirizzo esiste, riceverai un'email con le istruzioni per reimpostare "
        "la password."
    )
    if user is None or not user.is_active:
        # Same response whether or not the account exists — otherwise this
        # endpoint would let anyone enumerate registered emails.
        return generic
    raw_token = auth_tokens.issue_token(
        db, user.id, "password_reset", settings.password_reset_token_expire_minutes
    )
    link = f"{settings.oauth_redirect_base_url}/reset-password?token={raw_token}"
    send_email(
        EmailMessage(
            to=user.email,
            subject="Reimposta la tua password — REMIP",
            body=f"Reimposta la password: {link}\n\nIl link scade tra "
            f"{settings.password_reset_token_expire_minutes} minuti. Se non hai richiesto "
            "questo reset, ignora questa email.",
        )
    )
    db.add(
        AuditLog(user_id=user.id, action="user.forgot_password", entity="user", entity_id=user.id)
    )
    db.commit()
    if settings.demo_mode:
        return MessageResponse(detail=generic.detail, dev_token=raw_token)
    return generic


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, db: DbDep) -> MessageResponse:
    record = auth_tokens.consume_token(db, body.token, "password_reset")
    if record is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token non valido o scaduto")
    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.password_hash = hash_password(body.new_password)
    db.add(
        AuditLog(user_id=user.id, action="user.reset_password", entity="user", entity_id=user.id)
    )
    db.commit()
    return MessageResponse(detail="Password aggiornata")
