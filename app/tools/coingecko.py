"""CoinGecko API — получение курса криптовалют."""

import httpx

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Маппинг популярных тикеров на CoinGecko ID
TICKER_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "xrp": "ripple",
    "sol": "solana",
    "ada": "cardano",
    "doge": "dogecoin",
    "dot": "polkadot",
    "matic": "polygon-ecosystem-token",
    "avax": "avalanche-2",
    "link": "chainlink",
    "bnb": "binancecoin",
    "ltc": "litecoin",
    "ton": "the-open-network",
    "trx": "tron",
    "shib": "shiba-inu",
    "usdt": "tether",
    "usdc": "usd-coin",
}


def resolve_coin_id(name: str) -> str:
    """Преобразует название/тикер в CoinGecko ID."""
    name_lower = name.lower().strip()
    if name_lower in TICKER_MAP:
        return TICKER_MAP[name_lower]
    return name_lower


async def get_price(coin: str) -> dict:
    """Получает текущую цену, изменение за 24ч и капитализацию."""
    coin_id = resolve_coin_id(coin)
    url = f"{COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": coin_id,
        "order": "market_cap_desc",
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return {"error": f"Криптовалюта '{coin}' не найдена на CoinGecko."}

    item = data[0]
    return {
        "name": item["name"],
        "symbol": item["symbol"].upper(),
        "price_usd": item["current_price"],
        "price_change_24h_pct": item.get("price_change_percentage_24h"),
        "market_cap_usd": item.get("market_cap"),
        "total_volume_usd": item.get("total_volume"),
    }


async def get_market_data(coin: str) -> dict:
    """Расширенные рыночные данные для аналитики."""
    coin_id = resolve_coin_id(coin)
    url = f"{COINGECKO_BASE_URL}/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "community_data": "false",
        "developer_data": "false",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    market = data.get("market_data", {})
    return {
        "name": data.get("name"),
        "symbol": data.get("symbol", "").upper(),
        "price_usd": market.get("current_price", {}).get("usd"),
        "price_change_24h_pct": market.get("price_change_percentage_24h"),
        "price_change_7d_pct": market.get("price_change_percentage_7d"),
        "price_change_30d_pct": market.get("price_change_percentage_30d"),
        "market_cap_usd": market.get("market_cap", {}).get("usd"),
        "total_volume_usd": market.get("total_volume", {}).get("usd"),
        "ath_usd": market.get("ath", {}).get("usd"),
        "ath_change_pct": market.get("ath_change_percentage", {}).get("usd"),
    }
