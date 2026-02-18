"""Функции узлов графа LangGraph."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from numbers import Real

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.llm.gigachat import get_llm
from app.tools.coingecko import get_market_data, get_price
from app.tools.news import get_crypto_news
from app.tools.websearch import search_web

LOGGER = logging.getLogger(__name__)

# ─── Узел: получение цены ───


async def get_price_node(state: dict) -> dict:
    """Получает цену криптовалюты через CoinGecko."""
    coin = state.get("coin", "bitcoin")
    api_call = "coingecko:/coins/markets"
    try:
        data = await get_price(coin)
    except Exception as e:
        _log_node_error("get_price", state, e)
        data = {"error": str(e)}
    if isinstance(data, dict):
        data["_api_calls"] = [api_call]
    return {"api_data": data}


# ─── Узел: получение новостей ───


async def get_news_node(state: dict) -> dict:
    """Получает новости через NewsAPI."""
    coin = state.get("coin", "crypto")
    api_call = "newsapi:/v2/everything"
    try:
        articles = await get_crypto_news(coin)
    except Exception as e:
        _log_node_error("get_news", state, e)
        articles = [{"error": str(e)}]
    return {"api_data": {"articles": articles, "_api_calls": [api_call]}}


# ─── Узел: сбор данных для аналитики ───


async def get_analytics_data_node(state: dict) -> dict:
    """Собирает рыночные данные и новости для аналитики."""
    coin = state.get("coin", "bitcoin")
    api_calls = ["coingecko:/coins/{id}", "newsapi:/v2/everything"]
    market_result, news_result = await asyncio.gather(
        get_market_data(coin),
        get_crypto_news(coin, max_results=3),
        return_exceptions=True,
    )

    if isinstance(market_result, Exception):
        _log_node_error("get_analytics_data.market", state, market_result)
        market = {"error": str(market_result)}
    else:
        market = market_result

    if isinstance(news_result, Exception):
        _log_node_error("get_analytics_data.news", state, news_result)
        news = [{"error": str(news_result)}]
    else:
        news = news_result

    return {"api_data": {"market": market, "news": news, "_api_calls": api_calls}}


# ─── Узел: дополнительный веб-поиск для аналитики ───


async def analytics_search_node(state: dict) -> dict:
    """Доп. веб-поиск для обогащения аналитики."""
    coin = state.get("coin", "crypto")
    query = _build_analytics_search_query(coin)
    try:
        results = await search_web(query, max_results=3)
    except Exception as e:
        _log_node_error("analytics_search", state, e)
        results = [{"error": str(e)}]

    api_data = state.get("api_data", {})
    api_data["web_search"] = results
    api_calls = list(api_data.get("_api_calls", []))
    api_calls.append("ddgs:text")
    api_data["_api_calls"] = api_calls
    return {"api_data": api_data}


# ─── Узел: аналитика (отдельный промпт) ───


async def analyze_node(state: dict) -> dict:
    """LLM-анализ с аналитическим системным промптом."""
    llm = get_llm()
    api_data = state.get("api_data", {})

    system_prompt = """Ты — опытный криптоаналитик. Проанализируй предоставленные данные и дай \
развёрнутый аналитический ответ на русском языке.

Структура ответа:
1. **Текущее состояние** — цена, динамика, объёмы
2. **Тренд** — краткосрочный и среднесрочный (на основе изменений за 24ч, 7д, 30д)
3. **Новостной фон** — краткий обзор последних новостей и их влияние
4. **Оценка рисков** — основные риски для инвестора
5. **Рекомендация** — общая оценка (осторожно / нейтрально / позитивно) с обоснованием

ВАЖНО: Это не финансовый совет. Всегда добавляй дисклеймер об этом в конце."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Запрос пользователя: {state['user_query']}\n\n"
                f"Собранные данные:\n{json.dumps(api_data, ensure_ascii=False, indent=2, default=str)}"
            )
        ),
    ]
    result = await llm.ainvoke(messages)
    return {
        "response": result.content,
        "messages": [AIMessage(content=result.content)],
    }


# ─── Узел: веб-поиск (для chat intent) ───


async def web_search_node(state: dict) -> dict:
    """Веб-поиск через DuckDuckGo для общих вопросов."""
    query = state.get("user_query", "")
    try:
        results = await search_web(query, max_results=5)
    except Exception as e:
        _log_node_error("web_search", state, e)
        results = [{"error": str(e)}]
    return {"api_data": {"web_results": results, "_api_calls": ["ddgs:text"]}}


async def clarify_coin_node(state: dict) -> dict:
    """Просит пользователя уточнить монету, если intent требует coin."""

    intent = state.get("intent", "")
    topic_by_intent = {
        "price": "цену",
        "news": "новости",
        "analytics": "аналитику",
    }
    topic = topic_by_intent.get(intent, "информацию")
    response = (
        f"Уточните, пожалуйста, о какой криптовалюте речь, чтобы я мог дать {topic}. "
        "Например: Bitcoin, ETH, SOL."
    )
    return {
        "response": response,
        "messages": [AIMessage(content=response)],
    }


# ─── Узел: генерация ответа (для price, news, chat) ───


async def generate_response_node(state: dict) -> dict:
    """GigaChat формирует финальный ответ."""
    llm = get_llm()
    intent = state.get("intent", "chat")
    api_data = state.get("api_data", {})

    system_prompt = """Ты — дружелюбный крипто-консультант. Отвечай на русском языке, \
кратко и по делу. Используй предоставленные данные для формирования ответа.

Если данные содержат ошибку, сообщи пользователю об этом вежливо и предложи \
уточнить запрос."""

    if intent == "price":
        data_text = _format_price_data(api_data)
    elif intent == "news":
        data_text = _format_news_data(api_data)
    else:
        data_text = _format_search_data(api_data)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Запрос пользователя: {state['user_query']}\n\n"
                f"Данные:\n{data_text}"
            )
        ),
    ]
    result = await llm.ainvoke(messages)
    return {
        "response": result.content,
        "messages": [AIMessage(content=result.content)],
    }


# ─── Форматирование данных ───


def _format_price_data(data: dict) -> str:
    """Форматирует рыночные данные в текстовый блок для ответа о цене."""

    if "error" in data:
        return f"Ошибка: {data['error']}"
    price = _format_number_or_na(data.get("price_usd"), ",.2f")
    change_24h = _format_number_or_na(data.get("price_change_24h_pct"), ".2f")
    market_cap = _format_number_or_na(data.get("market_cap_usd"), ",.0f")
    volume = _format_number_or_na(data.get("total_volume_usd"), ",.0f")
    change_display = f"{change_24h}%" if change_24h != "n/a" else "n/a"
    return (
        f"Монета: {data.get('name') or '?'} ({data.get('symbol') or '?'})\n"
        f"Цена: ${price}\n"
        f"Изменение за 24ч: {change_display}\n"
        f"Капитализация: ${market_cap}\n"
        f"Объём торгов 24ч: ${volume}"
    )


def _format_news_data(data: dict) -> str:
    """Форматирует список новостей в читаемый текст для LLM."""

    articles = data.get("articles", [])
    if not articles:
        return "Новости не найдены."
    if "error" in articles[0]:
        return f"Ошибка: {articles[0]['error']}"
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(
            f"{i}. {a['title']}\n"
            f"   Источник: {a.get('source', '?')} | {a.get('published_at', '?')}\n"
            f"   {a.get('description', '')}\n"
            f"   Ссылка: {a.get('url', '')}"
        )
    return "\n\n".join(lines)


def _format_search_data(data: dict) -> str:
    """Форматирует результаты веб-поиска в текстовый блок."""

    results = data.get("web_results", [])
    if not results:
        return "Результаты поиска не найдены."
    if "error" in results[0]:
        return f"Ошибка: {results[0]['error']}"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   {r.get('body', '')}")
    return "\n\n".join(lines)


def _format_number_or_na(value: object, fmt: str) -> str:
    """Форматирует число или возвращает 'n/a', если значение отсутствует."""

    if value is None or isinstance(value, bool):
        return "n/a"
    if isinstance(value, Real):
        return format(value, fmt)
    return "n/a"


def _build_analytics_search_query(coin: str) -> str:
    """Формирует аналитический поисковый запрос с актуальным годом."""

    current_year = datetime.now(timezone.utc).year
    return f"{coin} crypto analysis forecast {current_year}"


def _log_node_error(node_name: str, state: dict, error: Exception) -> None:
    """Логирует ошибку узла с контекстом запроса."""

    query = " ".join(str(state.get("user_query", "")).split())
    query_preview = query if len(query) <= 160 else f"{query[:157]}..."
    LOGGER.error(
        "[node:%s] external call failed | thread_id=%r intent=%r coin=%r query=%r error=%s",
        node_name,
        state.get("thread_id", ""),
        state.get("intent", ""),
        state.get("coin", ""),
        query_preview,
        error,
        exc_info=error,
    )
