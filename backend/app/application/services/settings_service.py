"""Application service for runtime model settings management.

Reads/writes model configuration to a JSON file so settings persist
across restarts without requiring a database migration.
"""

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path("data/settings.json")

# The 4 model setting keys used throughout the application.
MODEL_KEYS = [
    "classification_model",
    "extraction_model",
    "pdf_processing_model",
    "ontology_assistant_model",
]

# Human-friendly labels for each model setting.
MODEL_LABELS = {
    "classification_model": "Classification",
    "extraction_model": "Metadata Extraction",
    "pdf_processing_model": "PDF Processing",
    "ontology_assistant_model": "Ontology Assistant",
}


def _read_overrides() -> dict[str, Any]:
    """Read the JSON overrides file, returning {} if missing or corrupt."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text("utf-8"))
    except Exception:
        logger.warning("Could not read %s — using defaults", SETTINGS_FILE)
        return {}


def _write_overrides(data: dict[str, Any]) -> None:
    """Persist overrides to the JSON file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_model_settings() -> dict[str, str]:
    """Return the effective model setting for each processing type.

    Merges .env defaults with any overrides from settings.json.
    """
    defaults = get_settings()
    overrides = _read_overrides()
    return {
        key: overrides.get(key, getattr(defaults, key))
        for key in MODEL_KEYS
    }


def update_model_settings(updates: dict[str, str]) -> dict[str, str]:
    """Persist model setting overrides and return the new effective values.

    Only known keys in MODEL_KEYS are accepted; unknown keys are ignored.
    After writing, the Settings LRU cache is cleared so subsequent service
    instantiations pick up the new values.
    """
    overrides = _read_overrides()
    for key in MODEL_KEYS:
        if key in updates:
            overrides[key] = updates[key]
    _write_overrides(overrides)

    # Clear the cached Settings so get_settings() re-reads from env + overrides
    from app.config import get_settings as _gs
    _gs.cache_clear()

    logger.info("Model settings updated: %s", {k: overrides.get(k) for k in MODEL_KEYS})
    return get_model_settings()


async def fetch_available_models() -> list[dict[str, str]]:
    """Fetch all available models from the OpenRouter API.

    Returns a simplified list of {id, name} dicts, sorted by name.
    """
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "http://localhost",
        "X-Title": settings.openrouter_app_name,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"{settings.openrouter_base_url}/models",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    models = []
    for model in data.get("data", []):
        model_id = model.get("id", "")
        model_name = model.get("name", model_id)
        models.append({"id": model_id, "name": model_name})

    models.sort(key=lambda m: m["name"].lower())
    return models
