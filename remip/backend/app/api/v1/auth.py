from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AuditLog, User, Watchlist
from app.schemas.auth import (
    LoginRequest,
    OnboardingRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbDep) -> User:
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
    db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbDep) -> TokenResponse:
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
