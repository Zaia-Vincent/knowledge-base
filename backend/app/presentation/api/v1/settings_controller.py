"""Settings API controller — manage runtime model configuration."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.application.services.settings_service import (
    MODEL_KEYS,
    MODEL_LABELS,
    get_model_settings,
    update_model_settings,
    fetch_available_models,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ── Schemas ──────────────────────────────────────────────────────────

class ModelSettingsResponse(BaseModel):
    """Current model settings with labels."""
    models: dict[str, str]           # key → current model id
    labels: dict[str, str]           # key → human-friendly label


class ModelSettingsUpdate(BaseModel):
    """Payload for updating model selections."""
    models: dict[str, str]           # key → new model id


class AvailableModel(BaseModel):
    """Simplified model entry from OpenRouter."""
    id: str
    name: str


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/models", response_model=ModelSettingsResponse)
async def get_models():
    """Return the current model settings for each processing type."""
    return ModelSettingsResponse(
        models=get_model_settings(),
        labels=MODEL_LABELS,
    )


@router.put("/models", response_model=ModelSettingsResponse)
async def put_models(body: ModelSettingsUpdate):
    """Update model settings. Only known keys are accepted."""
    # Validate that all provided keys are known
    unknown = set(body.models.keys()) - set(MODEL_KEYS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown model keys: {', '.join(unknown)}",
        )

    updated = update_model_settings(body.models)
    return ModelSettingsResponse(
        models=updated,
        labels=MODEL_LABELS,
    )


@router.get("/available-models", response_model=list[AvailableModel])
async def get_available_models():
    """Fetch the list of available models from OpenRouter."""
    try:
        models = await fetch_available_models()
        return [AvailableModel(**m) for m in models]
    except Exception as exc:
        logger.exception("Failed to fetch OpenRouter models")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch models from OpenRouter: {exc}",
        )
