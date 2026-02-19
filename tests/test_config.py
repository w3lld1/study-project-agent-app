"""Тесты централизованного config-layer."""

import pytest

from app.config import (
    Settings,
    get_settings,
    require_gigachat_credentials,
    require_telegram_bot_token,
)


def test_settings_defaults_without_env(monkeypatch):
    monkeypatch.delenv("FASTAPI_URL", raising=False)
    monkeypatch.delenv("GRAPH_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("GRAPH_DEBUG_NODES", raising=False)

    settings = Settings()

    assert settings.fastapi_url == "http://localhost:8000"
    assert settings.graph_timeout_seconds == 30.0
    assert settings.graph_debug_nodes is False


def test_settings_bool_parsing_from_env(monkeypatch):
    monkeypatch.setenv("GRAPH_DEBUG_NODES", "true")
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL_CERTS", "1")

    settings = Settings()

    assert settings.graph_debug_nodes is True
    assert settings.gigachat_verify_ssl_certs is True


def test_require_gigachat_credentials_raises_on_missing():
    settings = Settings(gigachat_credentials="")

    with pytest.raises(RuntimeError, match="GIGACHAT_CREDENTIALS"):
        require_gigachat_credentials(settings)


def test_require_telegram_bot_token_raises_on_missing():
    settings = Settings(telegram_bot_token="   ")

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        require_telegram_bot_token(settings)


def test_get_settings_respects_env_override_after_cache_clear(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("FASTAPI_URL", "http://api.internal:9000")

    settings = get_settings()

    assert settings.fastapi_url == "http://api.internal:9000"

    get_settings.cache_clear()
