import json
import logging
from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache

_config_logger = logging.getLogger(__name__)

_SETTINGS_FILE = Path("data/settings.json")
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_FILES = (
    _BACKEND_DIR / ".env",
    ".env",
)
_MODEL_KEYS = frozenset({
    "classification_model",
    "extraction_model",
    "pdf_processing_model",
    "ontology_assistant_model",
})


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_title: str = "Knowledge Base API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    database_url: str = "postgresql://kb_user:kb_secret_2026@localhost:5432/knowledge_base"
    cors_origins: list[str] = ["http://localhost:3020"]

    # OpenRouter configuration
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "Knowledge Base"

    # Ontology paths (relative to backend directory)
    ontology_l1_dir: str = "data/l1"
    ontology_l2_dir: str = "data/l2"
    embedded_types_file: str = "data/embedded-types.yaml"

    # File upload & storage
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50

    # LLM models via OpenRouter
    classification_model: str = "google/gemini-3-flash-preview"
    extraction_model: str = "anthropic/claude-sonnet-4.5"
    pdf_processing_model: str = "google/gemini-3-flash-preview"
    ontology_assistant_model: str = "openrouter/auto"

    # Logging — per-category log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_level: str = "INFO"                  # Root / app-wide
    log_level_sql: str = "WARNING"           # sqlalchemy.engine — SQL queries
    log_level_http: str = "WARNING"          # httpx / httpcore — outbound HTTP
    log_level_uvicorn: str = "INFO"          # uvicorn.access / uvicorn.error
    log_level_pipeline: str = "INFO"         # FileProcessingService pipeline
    log_level_openrouter: str = "INFO"       # OpenRouter LLM client

    # Website capture (Playwright)
    website_capture_viewport_width: int = 1280
    website_capture_viewport_height: int = 800
    website_capture_timeout: int = 30

    model_config = {
        "env_file": _ENV_FILES,
        "env_file_encoding": "utf-8",
    }

    def model_post_init(self, __context: object) -> None:
        """Merge runtime overrides from data/settings.json into model settings."""
        if _SETTINGS_FILE.exists():
            try:
                overrides = json.loads(_SETTINGS_FILE.read_text("utf-8"))
                for key in _MODEL_KEYS:
                    if key in overrides and isinstance(overrides[key], str):
                        object.__setattr__(self, key, overrides[key])
            except Exception as exc:
                _config_logger.warning("Could not load settings overrides: %s", exc)


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — reads .env once."""
    return Settings()
