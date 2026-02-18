"""Тесты для сборки и выполнения графа."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph


# ─── build_graph ───


def test_build_graph_returns_compiled_graph():
    from app.agent.graph import build_graph

    graph = build_graph()
    assert isinstance(graph, CompiledStateGraph)


# ─── Интеграционный тест: price-ветка с моками ───


@pytest.mark.asyncio
async def test_price_flow_integration():
    """Полный прогон price-ветки: classify -> get_price -> generate_response."""
    mock_llm = MagicMock()

    # Первый вызов — classify_intent
    # Второй вызов — generate_response_node
    mock_llm.ainvoke = AsyncMock(
        side_effect=[
            MagicMock(content='{"intent": "price", "coin": "bitcoin"}'),
            MagicMock(content="Bitcoin стоит $50,000"),
        ]
    )

    mock_price_data = {
        "name": "Bitcoin",
        "symbol": "BTC",
        "price_usd": 50000.0,
        "price_change_24h_pct": 2.5,
        "market_cap_usd": 1_000_000_000_000,
        "total_volume_usd": 30_000_000_000,
    }

    with (
        patch("app.agent.router.get_llm", return_value=mock_llm),
        patch("app.agent.nodes.get_llm", return_value=mock_llm),
        patch(
            "app.agent.nodes.get_price",
            new_callable=AsyncMock,
            return_value=mock_price_data,
        ),
    ):
        from app.agent.graph import build_graph

        graph = build_graph()
        result = await graph.ainvoke(
            {
                "messages": [],
                "user_query": "Сколько стоит биткоин?",
                "intent": "",
                "coin": "",
                "api_data": {},
                "response": "",
            },
            config={"configurable": {"thread_id": "test-thread"}},
        )

    # LangGraph может оставлять фоновые asyncio-задачи в тестовом event loop.
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    assert result["intent"] == "price"
    assert result["coin"] == "bitcoin"
    assert "50,000" in result["response"]


@pytest.mark.asyncio
async def test_multiturn_coreference_reuses_previous_coin():
    """Во втором запросе местоимение должно резолвиться в монету из прошлого хода."""
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
        from app.agent.graph import build_graph

        graph = build_graph()
        config = {"configurable": {"thread_id": "test-thread-coref"}}

        await graph.ainvoke(
            {
                "messages": [],
                "user_query": "сколько стоит биток?",
                "intent": "",
                "coin": "",
                "api_data": {},
                "response": "",
            },
            config=config,
        )

        result = await graph.ainvoke(
            {
                "messages": [],
                "user_query": "если он так дешево сейчас стоит, может, закупиться?",
            },
            config=config,
        )

    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    assert result["intent"] == "analytics"
    assert result["coin"] == "bitcoin"
    assert "Аналитика" in result["response"]
    assert mock_market.await_args.args[0] == "bitcoin"
