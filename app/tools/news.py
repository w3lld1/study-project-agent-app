"""NewsAPI — получение новостей по криптовалютам."""

import httpx

from app.config import get_settings

NEWSAPI_BASE_URL = "https://newsapi.org/v2"
NEWSAPI_MAX_PAGE_SIZE = 100
SETTINGS = get_settings()


def _clamp_page_size(max_results: int) -> int:
    """Ограничивает pageSize в допустимых для NewsAPI границах."""
    if max_results < 1:
        return 1
    return min(max_results, NEWSAPI_MAX_PAGE_SIZE)


def _build_news_query(query: str) -> str:
    """Формирует поисковый запрос с более точной фильтрацией."""
    clean_query = " ".join(query.strip().split())
    if not clean_query:
        return "crypto OR cryptocurrency"
    return f"({clean_query}) AND (crypto OR cryptocurrency)"


async def get_crypto_news(query: str, max_results: int = 5) -> list[dict]:
    """Получает последние новости по запросу через NewsAPI."""
    api_key = SETTINGS.news_api_key
    if not api_key:
        return [{"error": "NEWS_API_KEY не задан в .env"}]

    url = f"{NEWSAPI_BASE_URL}/everything"
    params = {
        "q": _build_news_query(query),
        "sortBy": "publishedAt",
        "pageSize": _clamp_page_size(max_results),
        "language": "en",
    }
    headers = {"X-Api-Key": api_key}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                payload = resp.json()
                code = payload.get("code")
                message = payload.get("message")
                parts = [part for part in (code, message) if part]
                if parts:
                    detail = f": {' | '.join(parts)}"
            except Exception:
                detail = ""
            raise RuntimeError(f"NewsAPI error {resp.status_code}{detail}") from exc
        data = resp.json()

    articles = data.get("articles", [])
    return [
        {
            "title": a["title"],
            "description": a.get("description", ""),
            "url": a["url"],
            "published_at": a["publishedAt"],
            "source": a.get("source", {}).get("name", ""),
        }
        for a in articles
    ]
