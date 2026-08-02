from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    email_verified: bool
    onboarding_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardingRequest(BaseModel):
    goal: str = Field(default="", max_length=50)  # buy | sell | rent | invest | monitor
    preferred_country: str = Field(default="IT", max_length=2)


class MessageResponse(BaseModel):
    detail: str
    # Only populated when the server runs with demo_mode=True (see
    # core/config.py) — a deliberate dev/demo convenience so the flow is
    # testable end-to-end without a real mailbox. A production deployment
    # must set REMIP_DEMO_MODE=false, at which point this is always null and
    # the token only ever reaches the user via the configured email adapter.
    dev_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str
