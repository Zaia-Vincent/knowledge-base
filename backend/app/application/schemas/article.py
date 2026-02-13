"""Pydantic DTOs (Data Transfer Objects) for the Article feature."""

from datetime import datetime

from pydantic import BaseModel, Field


class ArticleCreate(BaseModel):
    """Schema for creating a new article."""

    title: str = Field(..., min_length=1, max_length=255, examples=["Getting Started"])
    content: str = Field(..., min_length=1, examples=["This is a knowledge base article."])


class ArticleUpdate(BaseModel):
    """Schema for updating an existing article — all fields optional."""

    title: str | None = Field(None, min_length=1, max_length=255)
    content: str | None = Field(None, min_length=1)


class ArticleResponse(BaseModel):
    """Schema returned to the client."""

    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
