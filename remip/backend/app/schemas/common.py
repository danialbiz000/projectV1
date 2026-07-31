from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class DataContext(BaseModel):
    """Transparency block attached to every analytical response."""

    sources: list[str]
    period: str | None = None
    observations: int | None = None
    updated_at: datetime | None = None
    quality: float | None = None
    aggregation_level: str | None = None
    methodology: str | None = None
    limitations: str | None = None
    is_demo_data: bool = True


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Message(BaseModel):
    detail: str


class ApiEnvelope(BaseModel):
    """Analytical payload + mandatory transparency context."""

    data: dict[str, Any] | list[Any]
    data_context: DataContext
