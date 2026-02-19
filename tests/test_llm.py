"""Тесты для lifecycle LLM-клиента."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm import gigachat


@pytest.fixture(autouse=True)
def reset_llm_singleton():
    """Изолирует singleton LLM между тестами."""
    gigachat._llm_instance = None
    yield
    gigachat._llm_instance = None


def test_get_llm_returns_singleton(monkeypatch):
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-credentials")

    llm_instance = MagicMock()
    with patch("app.llm.gigachat.GigaChat", return_value=llm_instance) as mock_ctor:
        first = gigachat.get_llm()
        second = gigachat.get_llm()

    assert first is llm_instance
    assert second is llm_instance
    mock_ctor.assert_called_once()


@pytest.mark.asyncio
async def test_close_llm_uses_aclose():
    close_target = MagicMock()
    close_target.aclose = AsyncMock()

    llm_instance = MagicMock()
    llm_instance._client = close_target
    gigachat._llm_instance = llm_instance

    await gigachat.close_llm()

    close_target.aclose.assert_awaited_once()
    assert gigachat._llm_instance is None


@pytest.mark.asyncio
async def test_close_llm_uses_close_when_only_sync_close():
    class SyncClient:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    close_target = SyncClient()
    llm_instance = MagicMock()
    llm_instance._client = close_target
    gigachat._llm_instance = llm_instance

    await gigachat.close_llm()

    assert close_target.closed is True
    assert gigachat._llm_instance is None
