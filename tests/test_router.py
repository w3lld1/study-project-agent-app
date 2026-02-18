"""Тесты для router: classify_intent, route_by_intent, route_needs_search."""

from unittest.mock import MagicMock, patch

import pytest

from app.agent.router import classify_intent, route_by_intent, route_needs_search


# ─── classify_intent ───


@pytest.mark.asyncio
async def test_classify_intent_price(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"intent": "price", "coin": "bitcoin"}'
    )
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await classify_intent({"user_query": "Сколько стоит биткоин?"})

    assert result["intent"] == "price"
    assert result["coin"] == "bitcoin"


@pytest.mark.asyncio
async def test_classify_intent_news(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(
        content='{"intent": "news", "coin": "ethereum"}'
    )
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await classify_intent({"user_query": "Новости по Ethereum"})

    assert result["intent"] == "news"
    assert result["coin"] == "ethereum"


@pytest.mark.asyncio
async def test_classify_intent_with_markdown_wrapper(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(
        content='```json\n{"intent": "analytics", "coin": "solana"}\n```'
    )
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await classify_intent({"user_query": "Аналитика по солане"})

    assert result["intent"] == "analytics"
    assert result["coin"] == "solana"


@pytest.mark.asyncio
async def test_classify_intent_invalid_json(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content="not valid json at all")
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await classify_intent({"user_query": "что-то непонятное"})

    assert result["intent"] == "chat"
    assert result["coin"] == ""


# ─── route_by_intent ───


@pytest.mark.parametrize(
    "intent,coin,expected",
    [
        ("price", "bitcoin", "price"),
        ("price", "", "clarify_coin"),
        ("news", "ethereum", "news"),
        ("news", "", "clarify_coin"),
        ("analytics", "solana", "analytics"),
        ("analytics", "", "clarify_coin"),
        ("chat", "", "chat"),
        ("unknown", "", "chat"),
        ("", "", "chat"),
    ],
)
@pytest.mark.asyncio
async def test_route_by_intent(intent, coin, expected):
    assert await route_by_intent({"intent": intent, "coin": coin}) == expected


@pytest.mark.asyncio
async def test_classify_intent_uses_previous_coin_for_analytics(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content='{"intent": "analytics", "coin": ""}')
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await classify_intent(
            {
                "user_query": "если он сейчас дешево стоит, брать?",
                "coin": "bitcoin",
                "messages": [],
            }
        )

    assert result["intent"] == "analytics"
    assert result["coin"] == "bitcoin"


# ─── route_needs_search ───


@pytest.mark.asyncio
async def test_route_needs_search_yes(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content="yes")
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await route_needs_search(
            {"user_query": "Прогноз BTC", "api_data": {"market": {}}}
        )

    assert result == "needs_search"


@pytest.mark.asyncio
async def test_route_needs_search_no(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content="no")
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await route_needs_search(
            {"user_query": "Прогноз BTC", "api_data": {"market": {}}}
        )

    assert result == "no_search"


@pytest.mark.asyncio
async def test_route_needs_search_yesterday_not_yes(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content="yesterday")
    with patch("app.agent.router.get_llm", return_value=mock_llm):
        result = await route_needs_search(
            {"user_query": "Прогноз BTC", "api_data": {"market": {}}}
        )

    assert result == "no_search"
