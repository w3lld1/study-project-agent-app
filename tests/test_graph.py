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
