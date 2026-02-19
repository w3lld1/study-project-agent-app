"""Настройка GigaChat LLM."""

import inspect

from langchain_gigachat import GigaChat

from app.config import get_settings

_llm_instance: GigaChat | None = None
SETTINGS = get_settings()


def get_llm() -> GigaChat:
    """Возвращает singleton-экземпляр GigaChat LLM."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = GigaChat(
            credentials=SETTINGS.gigachat_credentials,
            verify_ssl_certs=SETTINGS.gigachat_verify_ssl_certs,
            model=SETTINGS.gigachat_model,
            scope=SETTINGS.gigachat_scope,
        )
    return _llm_instance


async def close_llm() -> None:
    """Закрывает сетевые ресурсы LLM-клиента."""
    global _llm_instance
    if _llm_instance is None:
        return

    close_target = getattr(_llm_instance, "_client", _llm_instance)
    aclose = getattr(close_target, "aclose", None)
    close = getattr(close_target, "close", None)

    if callable(aclose):
        maybe_awaitable = aclose()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable
    elif callable(close):
        close()

    _llm_instance = None
