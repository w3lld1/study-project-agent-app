"""Настройка GigaChat LLM."""

import inspect
import os

from dotenv import load_dotenv
from langchain_gigachat import GigaChat

load_dotenv()

_llm_instance: GigaChat | None = None


def get_llm() -> GigaChat:
    """Возвращает singleton-экземпляр GigaChat LLM."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = GigaChat(
            credentials=os.getenv("GIGACHAT_CREDENTIALS"),
            verify_ssl_certs=False,
            model="GigaChat-2-Max",
            scope="GIGACHAT_API_B2B",
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
