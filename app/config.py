"""Централизованная конфигурация приложения."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из .env и переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gigachat_credentials: str | None = Field(default=None, alias="GIGACHAT_CREDENTIALS")
    gigachat_model: str = Field(default="GigaChat-2-Max", alias="GIGACHAT_MODEL")
    gigachat_scope: str = Field(default="GIGACHAT_API_B2B", alias="GIGACHAT_SCOPE")
    gigachat_verify_ssl_certs: bool = Field(
        default=False, alias="GIGACHAT_VERIFY_SSL_CERTS"
    )

    news_api_key: str | None = Field(default=None, alias="NEWS_API_KEY")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    fastapi_url: str = Field(default="http://localhost:8000", alias="FASTAPI_URL")

    graph_timeout_seconds: float = Field(default=30.0, alias="GRAPH_TIMEOUT_SECONDS")
    graph_debug_nodes: bool = Field(default=False, alias="GRAPH_DEBUG_NODES")


def _require_non_empty(value: str | None, env_name: str) -> str:
    """Проверяет, что обязательный env задан непустым значением."""

    normalized = (value or "").strip()
    if not normalized:
        raise RuntimeError(f"Не задан обязательный параметр окружения: {env_name}")
    return normalized


def require_gigachat_credentials(settings: Settings | None = None) -> str:
    """Возвращает GigaChat credentials или бросает понятную ошибку."""

    cfg = settings or get_settings()
    return _require_non_empty(cfg.gigachat_credentials, "GIGACHAT_CREDENTIALS")


def require_telegram_bot_token(settings: Settings | None = None) -> str:
    """Возвращает Telegram bot token или бросает понятную ошибку."""

    cfg = settings or get_settings()
    return _require_non_empty(cfg.telegram_bot_token, "TELEGRAM_BOT_TOKEN")


@lru_cache
def get_settings() -> Settings:
    """Возвращает кэшированный экземпляр настроек."""

    return Settings()
