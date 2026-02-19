"""E2E-тесты памяти диалога: multi-turn и restart-сценарии."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.agent.graph import build_graph
from app.main import app


@pytest.mark.asyncio
async def test_e2e_multiturn_same_thread_keeps_coin_context(monkeypatch):
    """В одном thread_id вторая реплика с местоимением должна взять прошлую монету."""
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-credentials")

    graph = build_graph()
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            MagicMock(content='{"intent": "price", "coin": "bitcoin"}'),
            MagicMock(content="Bitcoin стоит $50,000"),
            MagicMock(content='{"intent": "analytics", "coin": ""}'),
            MagicMock(content="no"),
            MagicMock(content="Аналитика по BTC"),
        ]
    )

    original_graph = main_module.agent_graph
    main_module.agent_graph = graph
    try:
        with (
            patch("app.agent.router.get_llm", return_value=mock_llm),
            patch("app.agent.nodes.get_llm", return_value=mock_llm),
            patch(
                "app.agent.nodes.get_price",
                new_callable=AsyncMock,
                return_value={
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "price_usd": 50000.0,
                    "price_change_24h_pct": 2.5,
                    "market_cap_usd": 1_000_000_000_000,
                    "total_volume_usd": 30_000_000_000,
                },
            ),
            patch(
                "app.agent.nodes.get_market_data",
                new_callable=AsyncMock,
                return_value={"price_usd": 49000.0},
            ) as mock_market,
            patch(
                "app.agent.nodes.get_crypto_news",
                new_callable=AsyncMock,
                return_value=[{"title": "BTC news"}],
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                first = await client.post(
                    "/chat",
                    json={"message": "какой щас курс битка?", "thread_id": "e2e-memory-1"},
                )
                second = await client.post(
                    "/chat",
                    json={
                        "message": "ему щас совсем плохо, думаю закупиться на низах, что думаешь?",
                        "thread_id": "e2e-memory-1",
                    },
                )
    finally:
        main_module.agent_graph = original_graph

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["intent"] == "analytics"
    assert "Аналитика" in second.json()["response"]
    assert mock_market.await_args.args[0] == "bitcoin"


@pytest.mark.asyncio
async def test_e2e_restart_with_memorysaver_loses_coin_context(monkeypatch):
    """После имитации рестарта process-level память теряется и агент просит уточнить монету."""
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "test-credentials")

    first_graph = build_graph()
    second_graph = build_graph()
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            MagicMock(content='{"intent": "price", "coin": "bitcoin"}'),
            MagicMock(content="Bitcoin стоит $50,000"),
            MagicMock(content='{"intent": "analytics", "coin": ""}'),
        ]
    )

    original_graph = main_module.agent_graph
    try:
        with (
            patch("app.agent.router.get_llm", return_value=mock_llm),
            patch("app.agent.nodes.get_llm", return_value=mock_llm),
            patch(
                "app.agent.nodes.get_price",
                new_callable=AsyncMock,
                return_value={
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "price_usd": 50000.0,
                    "price_change_24h_pct": 2.5,
                    "market_cap_usd": 1_000_000_000_000,
                    "total_volume_usd": 30_000_000_000,
                },
            ),
            patch("app.agent.nodes.get_market_data", new_callable=AsyncMock) as mock_market,
            patch("app.agent.nodes.get_crypto_news", new_callable=AsyncMock) as mock_news,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                main_module.agent_graph = first_graph
                first = await client.post(
                    "/chat",
                    json={"message": "какой щас курс битка?", "thread_id": "e2e-memory-2"},
                )

                main_module.agent_graph = second_graph
                second = await client.post(
                    "/chat",
                    json={
                        "message": "ему щас совсем плохо, думаю закупиться на низах, что думаешь?",
                        "thread_id": "e2e-memory-2",
                    },
                )
    finally:
        main_module.agent_graph = original_graph

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["intent"] == "analytics"
    assert "Уточните" in second.json()["response"]
    assert mock_market.await_count == 0
    assert mock_news.await_count == 0
