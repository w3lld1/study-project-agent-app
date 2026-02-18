"""Общие фикстуры для тестов."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest


@pytest.fixture
def mock_llm():
    """Мок GigaChat LLM с настраиваемым .invoke()/.ainvoke() ответом."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="mocked response")
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="mocked response"))
    return llm


@pytest.fixture
def mock_httpx_response():
    """Фабрика мок-ответов httpx."""

    def _make(status_code: int = 200, json_data=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="error",
                request=MagicMock(),
                response=resp,
            )
        return resp

    return _make
