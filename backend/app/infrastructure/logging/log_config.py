"""Centralized logging configuration.

Applies per-category log levels from Settings so that noisy loggers
(e.g. SQLAlchemy SQL statements, httpx/httpcore) can be silenced without
affecting other parts of the application.

Usage:
    from app.infrastructure.logging.log_config import setup_logging
    setup_logging()   # Call once at startup (in main.py or lifespan)
"""

import logging
import sys

from app.config import get_settings


# ── Logger-name → Settings-field mapping ────────────────────────────
#
# Each entry maps one or more Python logger names to a Settings field.
# When setup_logging() runs, it sets the level of each listed logger
# to the value of the corresponding setting.

_CATEGORY_MAP: dict[str, list[str]] = {
    "log_level_sql": [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "aiosqlite",
    ],
    "log_level_http": [
        "httpx",
        "httpcore",
    ],
    "log_level_uvicorn": [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
    ],
    "log_level_pipeline": [
        "FileProcessingService",
    ],
    "log_level_openrouter": [
        "app.infrastructure.openrouter",
        "app.infrastructure.llm",
    ],
}


def setup_logging() -> None:
    """Configure Python logging levels from application settings.

    Call this once during startup (e.g. in the FastAPI lifespan).
    """
    settings = get_settings()
    root_level = _parse_level(settings.log_level)

    # ── Root logger ────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(root_level)

    # Ensure at least one handler exists (uvicorn usually adds one,
    # but when running tests or scripts it may not).
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)-8s %(name)s — %(message)s",
            )
        )
        root.addHandler(handler)

    # ── Per-category loggers ───────────────────────────────────────
    for settings_field, logger_names in _CATEGORY_MAP.items():
        raw_level: str = getattr(settings, settings_field, "INFO")
        level = _parse_level(raw_level)

        for name in logger_names:
            logging.getLogger(name).setLevel(level)

    logging.getLogger(__name__).debug(
        "Logging configured — root=%s, sql=%s, http=%s, uvicorn=%s, pipeline=%s, openrouter=%s",
        settings.log_level,
        settings.log_level_sql,
        settings.log_level_http,
        settings.log_level_uvicorn,
        settings.log_level_pipeline,
        settings.log_level_openrouter,
    )


def _parse_level(raw: str) -> int:
    """Convert a level name string to a logging constant, defaulting to INFO."""
    numeric = getattr(logging, raw.upper(), None)
    if isinstance(numeric, int):
        return numeric
    return logging.INFO
