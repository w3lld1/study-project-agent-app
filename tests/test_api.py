"""Тесты для FastAPI эндпоинтов."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def mock_graph():
    """Мок графа агента."""
    mock = AsyncMock()
    mock.ainvoke.return_value = {
        "response": "Bitcoin стоит $50,000",
        "intent": "price",
    }
    return mock


# ─── GET /health ───


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ─── POST /chat ───


@pytest.mark.asyncio
async def test_chat_success(mock_graph, monkeypatch):
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-credentials")
    with patch("app.main.agent_graph", mock_graph):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/chat",
                json={"message": "Сколько стоит BTC?", "thread_id": "test-123"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Bitcoin стоит $50,000"
    assert data["thread_id"] == "test-123"
    assert data["intent"] == "price"


@pytest.mark.asyncio
async def test_chat_auto_thread_id(mock_graph, monkeypatch):
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-credentials")
    with patch("app.main.agent_graph", mock_graph):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/chat",
                json={"message": "Что такое DeFi?"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["thread_id"]
    assert len(data["thread_id"]) > 0


@pytest.mark.asyncio
async def test_chat_timeout(mock_graph, monkeypatch):
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-credentials")

    async def slow_ainvoke(*_args, **_kwargs):
        await asyncio.sleep(1)

    mock_graph.ainvoke = AsyncMock(side_effect=slow_ainvoke)
    with (
        patch("app.main.agent_graph", mock_graph),
        patch("app.main.get_settings", return_value=SimpleNamespace(graph_timeout_seconds=0.01)),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/chat",
                json={"message": "Сколько стоит BTC?", "thread_id": "test-123"},
            )

    assert resp.status_code == 504
    assert resp.json()["detail"] == "Таймаут обработки запроса. Попробуйте повторить запрос."
