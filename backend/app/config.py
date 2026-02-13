from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_title: str = "Knowledge Base API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    database_url: str = "sqlite:///./knowledge_base.db"
    cors_origins: list[str] = ["http://localhost:3020"]

    # OpenRouter configuration
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "Knowledge Base"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — reads .env once."""
    return Settings()
