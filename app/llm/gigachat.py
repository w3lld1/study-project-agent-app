"""Настройка GigaChat LLM."""

import inspect

from langchain_gigachat import GigaChat

from app.config import get_settings, require_gigachat_credentials

_llm_instance: GigaChat | None = None


def get_llm() -> GigaChat:
    """Возвращает singleton-экземпляр GigaChat LLM."""
    global _llm_instance
    if _llm_instance is None:
        settings = get_settings()
        _llm_instance = GigaChat(
            credentials=require_gigachat_credentials(settings),
            verify_ssl_certs=settings.gigachat_verify_ssl_certs,
            model=settings.gigachat_model,
            scope=settings.gigachat_scope,
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
