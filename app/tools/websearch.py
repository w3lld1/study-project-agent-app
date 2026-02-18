"""DuckDuckGo Search — веб-поиск."""

import asyncio

from ddgs import DDGS


def _search_sync(query: str, max_results: int) -> list[dict]:
    """Синхронный поиск, исполняется в отдельном потоке."""
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Поиск в интернете через DuckDuckGo."""
    results = await asyncio.to_thread(_search_sync, query, max_results)

    return [
        {
            "title": r.get("title", ""),
            "body": r.get("body", ""),
            "url": r.get("href", ""),
        }
        for r in results
    ]
