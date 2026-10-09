"""Tests del módulo app.config (Settings y sync_env_to_dotenv)."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import ENV_VARS_TO_SYNC, sync_env_to_dotenv


def test_sync_env_to_dotenv_appends_only_missing_vars(tmp_path):
    """sync_env_to_dotenv añade al .env solo las variables del sistema que no están ya en el archivo."""
    env_file = tmp_path / ".env"
    env_file.write_text("PYTHON_VERSION=3.12\nMANCER_API_KEY=mcr-secret-in-file\n", encoding="utf-8")
    with patch("app.config._PROJECT_ROOT", tmp_path), patch.dict(
        os.environ,
        {"OPENAI_PROJECT_ID": "proj_new", "MANCER_API_KEY": "mcr-from-system"},
        clear=False,
    ):
        sync_env_to_dotenv(skip_if_pytest=False)
    content = env_file.read_text(encoding="utf-8")
    assert "PYTHON_VERSION=3.12" in content
    assert "MANCER_API_KEY=mcr-secret-in-file" in content  # no se sobrescribe
    assert "OPENAI_PROJECT_ID=proj_new" in content  # sí se añade (no estaba)


def test_sync_env_to_dotenv_skipped_under_pytest(monkeypatch, tmp_path):
    """Bajo pytest (PYTEST_CURRENT_TEST definido) no se escribe .env."""
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_config.py::test_foo")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "proj_should_not_appear")
    with patch("app.config._PROJECT_ROOT", tmp_path):
        sync_env_to_dotenv()
    assert env_file.read_text(encoding="utf-8") == ""


def test_env_vars_to_sync_contains_expected():
    """ENV_VARS_TO_SYNC incluye las variables usadas por la aplicación."""
    expected = {
        "OPENAI_API_KEY",
        "OPENAI_PROJECT_ID",
        "OLLAMA_HOST",
        "MANCER_API_KEY",
        "ABLIT_KEY",
        "NAN_API_KEY",
        "NAN_BASE_URL",
        "PYTHON_VERSION",
        "FORGE_BASE_URL",
        "FORGE_DATA_PATH",
        "FORGE_STYLE_INIT_DIR",
        "FORGE_TIMEOUT_SECONDS",
    }
    assert expected.issubset(set(ENV_VARS_TO_SYNC))


def test_forge_settings_defaults():
    """Settings Forge tienen defaults seguros sin FORGE_* en el entorno."""
    from app.config import Settings

    s = Settings(
        _env_file=None,
        FORGE_BASE_URL="http://127.0.0.1:7860",
        FORGE_DATA_PATH="",
        FORGE_STYLE_INIT_DIR="",
        FORGE_TIMEOUT_SECONDS=600,
    )
    assert s.forge_base_url == "http://127.0.0.1:7860"
    assert s.forge_data_path == ""
    assert s.forge_style_init_dir == ""
    assert s.forge_timeout_seconds == 600.0


def test_forge_settings_from_env(monkeypatch):
    """Settings lee FORGE_* desde el entorno."""
    from app.config import Settings

    monkeypatch.setenv("FORGE_BASE_URL", "http://forge.local:7860")
    monkeypatch.setenv("FORGE_DATA_PATH", "/tmp/forge-data")
    monkeypatch.setenv("FORGE_STYLE_INIT_DIR", "/tmp/forge-init")
    monkeypatch.setenv("FORGE_TIMEOUT_SECONDS", "120.5")
    s = Settings(_env_file=None)
    assert s.forge_base_url == "http://forge.local:7860"
    assert s.forge_data_path == "/tmp/forge-data"
    assert s.forge_style_init_dir == "/tmp/forge-init"
    assert s.forge_timeout_seconds == 120.5
