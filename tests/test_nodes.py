"""Тесты для узлов графа (nodes)."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes import (
    analyze_node,
    analytics_search_node,
    clarify_coin_node,
    generate_response_node,
    get_analytics_data_node,
    get_news_node,
    get_price_node,
    web_search_node,
    _format_news_data,
    _format_price_data,
    _format_search_data,
)


# ─── get_price_node ───


@pytest.mark.asyncio
async def test_get_price_node_success():
    mock_data = {"name": "Bitcoin", "symbol": "BTC", "price_usd": 50000.0}
    with patch("app.agent.nodes.get_price", new_callable=AsyncMock, return_value=mock_data):
        result = await get_price_node({"coin": "bitcoin"})

    assert result["api_data"]["name"] == "Bitcoin"
    assert result["api_data"]["_api_calls"] == ["coingecko:/coins/markets"]


@pytest.mark.asyncio
async def test_get_price_node_error():
    with patch(
        "app.agent.nodes.get_price",
        new_callable=AsyncMock,
        side_effect=Exception("connection error"),
    ):
        result = await get_price_node({"coin": "bitcoin"})

    assert "error" in result["api_data"]


# ─── get_news_node ───


@pytest.mark.asyncio
async def test_get_news_node_success():
    mock_articles = [{"title": "News 1"}]
    with patch(
        "app.agent.nodes.get_crypto_news",
        new_callable=AsyncMock,
        return_value=mock_articles,
    ):
        result = await get_news_node({"coin": "bitcoin"})

    assert result["api_data"]["articles"] == mock_articles
    assert result["api_data"]["_api_calls"] == ["newsapi:/v2/everything"]


# ─── get_analytics_data_node ───


@pytest.mark.asyncio
async def test_get_analytics_data_node_success():
    mock_market = {"price_usd": 50000.0}
    mock_news = [{"title": "News 1"}]
    with (
        patch(
            "app.agent.nodes.get_market_data",
            new_callable=AsyncMock,
            return_value=mock_market,
        ),
        patch(
            "app.agent.nodes.get_crypto_news",
            new_callable=AsyncMock,
            return_value=mock_news,
        ),
    ):
        result = await get_analytics_data_node({"coin": "bitcoin"})

    assert result["api_data"]["market"] == mock_market
    assert result["api_data"]["news"] == mock_news
    assert result["api_data"]["_api_calls"] == [
        "coingecko:/coins/{id}",
        "newsapi:/v2/everything",
    ]


@pytest.mark.asyncio
async def test_get_analytics_data_node_uses_parallel_gather():
    mock_market = {"price_usd": 50000.0}
    mock_news = [{"title": "News 1"}]
    with (
        patch(
            "app.agent.nodes.get_market_data",
            new_callable=AsyncMock,
            return_value=mock_market,
        ),
        patch(
            "app.agent.nodes.get_crypto_news",
            new_callable=AsyncMock,
            return_value=mock_news,
        ),
        patch("app.agent.nodes.asyncio.gather", wraps=asyncio.gather) as gather_spy,
    ):
        result = await get_analytics_data_node({"coin": "bitcoin"})

    assert result["api_data"]["market"] == mock_market
    assert result["api_data"]["news"] == mock_news
    gather_spy.assert_called_once()
    assert gather_spy.call_args.kwargs.get("return_exceptions") is True


@pytest.mark.asyncio
async def test_get_analytics_data_node_runs_market_and_news_in_parallel():
    started = {"market": False, "news": False}
    both_started = asyncio.Event()
    release = asyncio.Event()

    async def fake_market(_coin):
        started["market"] = True
        if started["news"]:
            both_started.set()
        await both_started.wait()
        await release.wait()
        return {"price_usd": 50000.0}

    async def fake_news(_coin, max_results=3):
        assert max_results == 3
        started["news"] = True
        if started["market"]:
            both_started.set()
        await both_started.wait()
        await release.wait()
        return [{"title": "News 1"}]

    with (
        patch("app.agent.nodes.get_market_data", side_effect=fake_market),
        patch("app.agent.nodes.get_crypto_news", side_effect=fake_news),
    ):
        task = asyncio.create_task(get_analytics_data_node({"coin": "bitcoin"}))
        await asyncio.wait_for(both_started.wait(), timeout=0.2)
        release.set()
        result = await task

    assert result["api_data"]["market"]["price_usd"] == 50000.0
    assert result["api_data"]["news"][0]["title"] == "News 1"


# ─── analytics_search_node ───


@pytest.mark.asyncio
async def test_analytics_search_node_success():
    mock_results = [{"title": "Analysis 1", "body": "...", "url": "https://example.com"}]
    with patch(
        "app.agent.nodes.search_web",
        new_callable=AsyncMock,
        return_value=mock_results,
    ):
        result = await analytics_search_node(
            {"coin": "bitcoin", "api_data": {"market": {}}}
        )

    assert result["api_data"]["web_search"] == mock_results
    assert result["api_data"]["_api_calls"][-1] == "ddgs:text"


@pytest.mark.asyncio
async def test_analytics_search_node_uses_current_year_query():
    mock_results = [{"title": "Analysis 1", "body": "...", "url": "https://example.com"}]
    current_year = datetime.now(timezone.utc).year
    with patch(
        "app.agent.nodes.search_web",
        new_callable=AsyncMock,
        return_value=mock_results,
    ) as mock_search:
        await analytics_search_node({"coin": "bitcoin", "api_data": {}})

    query = mock_search.await_args.args[0]
    assert f"forecast {current_year}" in query
    if current_year != 2025:
        assert "2025" not in query


# ─── analyze_node ───


@pytest.mark.asyncio
async def test_analyze_node(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content="Аналитический ответ")
    with patch("app.agent.nodes.get_llm", return_value=mock_llm):
        result = await analyze_node(
            {"user_query": "Прогноз BTC", "api_data": {"market": {}}}
        )

    assert result["response"] == "Аналитический ответ"
    assert len(result["messages"]) == 1


# ─── web_search_node ───


@pytest.mark.asyncio
async def test_web_search_node_success():
    mock_results = [{"title": "Result 1", "body": "...", "url": "https://example.com"}]
    with patch(
        "app.agent.nodes.search_web",
        new_callable=AsyncMock,
        return_value=mock_results,
    ):
        result = await web_search_node({"user_query": "Что такое DeFi?"})

    assert result["api_data"]["web_results"] == mock_results
    assert result["api_data"]["_api_calls"] == ["ddgs:text"]


# ─── generate_response_node ───


@pytest.mark.asyncio
async def test_clarify_coin_node():
    result = await clarify_coin_node({"intent": "analytics"})
    assert "Уточните" in result["response"]
    assert len(result["messages"]) == 1


@pytest.mark.asyncio
async def test_generate_response_node(mock_llm):
    mock_llm.ainvoke.return_value = MagicMock(content="Ответ бота")
    with patch("app.agent.nodes.get_llm", return_value=mock_llm):
        result = await generate_response_node(
            {
                "user_query": "Сколько стоит BTC?",
                "intent": "price",
                "api_data": {
                    "name": "Bitcoin",
                    "symbol": "BTC",
                    "price_usd": 50000.0,
                    "price_change_24h_pct": 2.5,
                    "market_cap_usd": 1_000_000_000_000,
                    "total_volume_usd": 30_000_000_000,
                },
            }
        )

    assert result["response"] == "Ответ бота"
    assert len(result["messages"]) == 1


# ─── Форматирование ───


def test_format_price_data_success():
    data = {
        "name": "Bitcoin",
        "symbol": "BTC",
        "price_usd": 50000.0,
        "price_change_24h_pct": 2.5,
        "market_cap_usd": 1_000_000_000_000,
        "total_volume_usd": 30_000_000_000,
    }
    result = _format_price_data(data)
    assert "Bitcoin" in result
    assert "50,000.00" in result


def test_format_price_data_error():
    data = {"error": "Монета не найдена"}
    result = _format_price_data(data)
    assert "Ошибка" in result


def test_format_price_data_none_values():
    data = {
        "name": "Bitcoin",
        "symbol": "BTC",
        "price_usd": None,
        "price_change_24h_pct": None,
        "market_cap_usd": None,
        "total_volume_usd": None,
    }
    result = _format_price_data(data)
    assert "Цена: $n/a" in result
    assert "Изменение за 24ч: n/a" in result
    assert "Капитализация: $n/a" in result
    assert "Объём торгов 24ч: $n/a" in result


def test_format_news_data_success():
    data = {
        "articles": [
            {
                "title": "Bitcoin News",
                "source": "CryptoNews",
                "published_at": "2025-01-01",
                "description": "Description",
                "url": "https://example.com",
            }
        ]
    }
    result = _format_news_data(data)
    assert "Bitcoin News" in result
    assert "CryptoNews" in result


def test_format_news_data_empty():
    assert _format_news_data({"articles": []}) == "Новости не найдены."


def test_format_search_data_success():
    data = {
        "web_results": [
            {"title": "Result 1", "body": "Body 1"},
        ]
    }
    result = _format_search_data(data)
    assert "Result 1" in result


def test_format_search_data_empty():
    assert _format_search_data({}) == "Результаты поиска не найдены."
