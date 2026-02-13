"""Pydantic DTOs (Data Transfer Objects) for the ClientRecord feature."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ClientRecordCreate(BaseModel):
    """Schema for creating a new client record."""

    module_name: str = Field(
        ..., min_length=1, max_length=100, examples=["setup"],
    )
    entity_type: str = Field(
        ..., min_length=1, max_length=100, examples=["theme-colors"],
    )
    data: dict[str, Any] = Field(
        ..., examples=[{"background": "#C03232", "foreground": "#0A0A0A"}],
    )
    parent_id: str | None = Field(None, max_length=36)
    user_id: str | None = Field(None, max_length=255)


class ClientRecordUpdate(BaseModel):
    """Schema for updating an existing client record — all fields optional."""

    data: dict[str, Any] | None = None
    parent_id: str | None = None


class ClientRecordResponse(BaseModel):
    """Schema returned to the client."""

    id: str
    module_name: str
    entity_type: str
    data: dict[str, Any]
    parent_id: str | None
    user_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
