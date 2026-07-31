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
    onboarding_completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OnboardingRequest(BaseModel):
    goal: str = Field(default="", max_length=50)  # buy | sell | rent | invest | monitor
    preferred_country: str = Field(default="IT", max_length=2)
