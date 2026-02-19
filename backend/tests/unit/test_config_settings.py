"""Unit tests for application settings configuration."""

from pathlib import Path

from app.config import Settings


def test_settings_uses_backend_env_file_independent_of_cwd():
    """Settings should always include backend/.env as an env source."""
    env_files = Settings.model_config.get("env_file")
    assert env_files is not None

    normalized = {str(Path(item)) for item in env_files}
    expected_backend_env = str(Path(__file__).resolve().parents[2] / ".env")

    assert expected_backend_env in normalized
    assert str(Path(".env")) in normalized

