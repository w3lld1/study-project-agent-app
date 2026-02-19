"""Тесты для tools: coingecko, news, websearch."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.tools.coingecko import get_market_data, get_price, resolve_coin_id
from app.tools.news import get_crypto_news
from app.tools.websearch import _search_sync, search_web


# ─── resolve_coin_id ───


def test_resolve_coin_id_known_ticker():
    assert resolve_coin_id("btc") == "bitcoin"
    assert resolve_coin_id("ETH") == "ethereum"
    assert resolve_coin_id("Sol") == "solana"


def test_resolve_coin_id_unknown_coin():
    assert resolve_coin_id("unknowncoin") == "unknowncoin"
    assert resolve_coin_id("  BTC  ") == "bitcoin"


# ─── get_price ───


@pytest.mark.asyncio
async def test_get_price_success(mock_httpx_response):
    response_data = [
        {
            "name": "Bitcoin",
            "symbol": "btc",
            "current_price": 50000.0,
            "price_change_percentage_24h": 2.5,
            "market_cap": 1_000_000_000_000,
            "total_volume": 30_000_000_000,
        }
    ]
    mock_resp = mock_httpx_response(200, response_data)
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tools.coingecko.httpx.AsyncClient", return_value=mock_client):
        result = await get_price("btc")

    assert result["name"] == "Bitcoin"
    assert result["symbol"] == "BTC"
    assert result["price_usd"] == 50000.0


@pytest.mark.asyncio
async def test_get_price_coin_not_found(mock_httpx_response):
    mock_resp = mock_httpx_response(200, [])
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tools.coingecko.httpx.AsyncClient", return_value=mock_client):
        result = await get_price("nonexistent")

    assert "error" in result


@pytest.mark.asyncio
async def test_get_price_http_error(mock_httpx_response):
    mock_resp = mock_httpx_response(500)
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tools.coingecko.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await get_price("btc")


# ─── get_market_data ───


@pytest.mark.asyncio
async def test_get_market_data_success(mock_httpx_response):
    response_data = {
        "name": "Bitcoin",
        "symbol": "btc",
        "market_data": {
            "current_price": {"usd": 50000.0},
            "price_change_percentage_24h": 2.5,
            "price_change_percentage_7d": 5.0,
            "price_change_percentage_30d": 10.0,
            "market_cap": {"usd": 1_000_000_000_000},
            "total_volume": {"usd": 30_000_000_000},
            "ath": {"usd": 69000.0},
            "ath_change_percentage": {"usd": -27.5},
        },
    }
    mock_resp = mock_httpx_response(200, response_data)
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tools.coingecko.httpx.AsyncClient", return_value=mock_client):
        result = await get_market_data("btc")

    assert result["name"] == "Bitcoin"
    assert result["price_usd"] == 50000.0
    assert result["ath_usd"] == 69000.0


# ─── get_crypto_news ───


@pytest.mark.asyncio
async def test_get_crypto_news_success(mock_httpx_response):
    response_data = {
        "articles": [
            {
                "title": "Bitcoin hits new high",
                "description": "BTC surges past 50k",
                "url": "https://example.com/news",
                "publishedAt": "2025-01-01T00:00:00Z",
                "source": {"name": "CryptoNews"},
            }
        ]
    }
    mock_resp = mock_httpx_response(200, response_data)
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tools.news.httpx.AsyncClient", return_value=mock_client),
        patch("app.tools.news.get_settings", return_value=SimpleNamespace(news_api_key="fake-api-key")),
    ):
        result = await get_crypto_news("bitcoin")

    assert len(result) == 1
    assert result[0]["title"] == "Bitcoin hits new high"
    assert result[0]["source"] == "CryptoNews"
    kwargs = mock_client.get.await_args.kwargs
    assert kwargs["headers"] == {"X-Api-Key": "fake-api-key"}
    assert kwargs["params"]["q"] == "(bitcoin) AND (crypto OR cryptocurrency)"
    assert kwargs["params"]["pageSize"] == 5


@pytest.mark.asyncio
async def test_get_crypto_news_clamps_page_size(mock_httpx_response):
    mock_resp = mock_httpx_response(200, {"articles": []})
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tools.news.httpx.AsyncClient", return_value=mock_client),
        patch("app.tools.news.get_settings", return_value=SimpleNamespace(news_api_key="fake-api-key")),
    ):
        await get_crypto_news("bitcoin", max_results=999)
        high_kwargs = mock_client.get.await_args.kwargs
        await get_crypto_news("bitcoin", max_results=0)
        low_kwargs = mock_client.get.await_args.kwargs

    assert high_kwargs["params"]["pageSize"] == 100
    assert low_kwargs["params"]["pageSize"] == 1


@pytest.mark.asyncio
async def test_get_crypto_news_http_error_message(mock_httpx_response):
    mock_resp = mock_httpx_response(
        401,
        {"code": "apiKeyInvalid", "message": "Your API key is invalid or incorrect."},
    )
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tools.news.httpx.AsyncClient", return_value=mock_client),
        patch("app.tools.news.get_settings", return_value=SimpleNamespace(news_api_key="fake-api-key")),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            await get_crypto_news("bitcoin")

    assert "NewsAPI error 401" in str(exc_info.value)
    assert "apiKeyInvalid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_crypto_news_no_api_key():
    with patch("app.tools.news.get_settings", return_value=SimpleNamespace(news_api_key=None)):
        result = await get_crypto_news("bitcoin")

    assert len(result) == 1
    assert "error" in result[0]


# ─── search_web ───


@pytest.mark.asyncio
async def test_search_web_success():
    mock_results = [
        {"title": "Result 1", "body": "Body 1", "href": "https://example.com/1"},
        {"title": "Result 2", "body": "Body 2", "href": "https://example.com/2"},
    ]
    to_thread_mock = AsyncMock(return_value=mock_results)
    with patch("app.tools.websearch.asyncio.to_thread", to_thread_mock):
        result = await search_web("bitcoin", max_results=2)

    to_thread_mock.assert_awaited_once()
    assert len(result) == 2
    assert result[0]["title"] == "Result 1"
    assert result[0]["url"] == "https://example.com/1"


@pytest.mark.asyncio
async def test_search_web_uses_to_thread():
    to_thread_results = [
        {"title": "Result 1", "body": "Body 1", "href": "https://example.com/1"},
        {"title": "Result 2", "body": "Body 2", "href": "https://example.com/2"},
    ]
    to_thread_mock = AsyncMock(return_value=to_thread_results)

    with patch("app.tools.websearch.asyncio.to_thread", to_thread_mock):
        result = await search_web("bitcoin", max_results=2)

    to_thread_mock.assert_awaited_once()
    args = to_thread_mock.await_args.args
    assert args[1] == "bitcoin"
    assert args[2] == 2
    assert len(result) == 2


def test_search_sync_success():
    mock_results = [
        {"title": "Result 1", "body": "Body 1", "href": "https://example.com/1"},
        {"title": "Result 2", "body": "Body 2", "href": "https://example.com/2"},
    ]
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=False)
    mock_ddgs.text.return_value = mock_results

    with patch("app.tools.websearch.DDGS", return_value=mock_ddgs):
        result = _search_sync("bitcoin", max_results=2)

    assert len(result) == 2
    assert result[0]["href"] == "https://example.com/1"
