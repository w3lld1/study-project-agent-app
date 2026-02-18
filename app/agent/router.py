"""Роутинг: классификация intent и маршрутизация."""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.gigachat import get_llm

CLASSIFY_PROMPT = """Ты — классификатор запросов пользователя о криптовалютах.

Определи intent (намерение) пользователя и извлеки название криптовалюты, если оно есть.

Возможные intent:
- "price" — пользователь спрашивает о текущей цене/курсе криптовалюты
- "news" — пользователь хочет узнать новости о криптовалюте
- "analytics" — пользователь просит аналитику, прогноз, рекомендацию по покупке/продаже
- "chat" — общий вопрос о криптовалютах, блокчейне, DeFi и т.д.

Ответь СТРОГО в формате JSON:
{"intent": "<intent>", "coin": "<название монеты или пустая строка>"}

Примеры:
Вопрос: "Сколько стоит Bitcoin?"
{"intent": "price", "coin": "bitcoin"}

Вопрос: "Новости по Ethereum"
{"intent": "news", "coin": "ethereum"}

Вопрос: "Стоит ли покупать BTC сейчас?"
{"intent": "analytics", "coin": "bitcoin"}

Вопрос: "Что такое DeFi?"
{"intent": "chat", "coin": ""}

Вопрос: "Какой курс солана?"
{"intent": "price", "coin": "solana"}
"""


async def classify_intent(state: dict) -> dict:
    """Классифицирует intent пользователя через GigaChat."""
    llm = get_llm()
    user_query = state["user_query"]

    messages = [
        SystemMessage(content=CLASSIFY_PROMPT),
        HumanMessage(content=user_query),
    ]
    result = await llm.ainvoke(messages)

    try:
        # Извлекаем JSON из ответа
        text = result.content.strip()
        # Убираем markdown-обёртку если есть
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        intent = parsed.get("intent", "chat")
        coin = parsed.get("coin", "")
    except (json.JSONDecodeError, KeyError):
        intent = "chat"
        coin = ""

    return {"intent": intent, "coin": coin}


async def route_by_intent(state: dict) -> str:
    """Роутер: направляет по intent."""
    intent = state.get("intent", "chat")
    if intent in ("price", "news", "analytics", "chat"):
        return intent
    return "chat"


async def route_needs_search(state: dict) -> str:
    """Вложенный роутер: решает, нужен ли доп. поиск для аналитики."""
    llm = get_llm()
    api_data = state.get("api_data", {})

    messages = [
        SystemMessage(
            content=(
                "Ты — помощник аналитика. На основе собранных данных определи, "
                "нужен ли дополнительный веб-поиск для качественной аналитики.\n"
                "Ответь ТОЛЬКО одним словом: 'yes' или 'no'.\n"
                "Отвечай 'yes', если данных мало, новости устарели или вопрос "
                "требует дополнительного контекста."
            )
        ),
        HumanMessage(
            content=(
                f"Запрос пользователя: {state['user_query']}\n"
                f"Собранные данные: {json.dumps(api_data, ensure_ascii=False, default=str)}"
            )
        ),
    ]
    result = await llm.ainvoke(messages)
    answer = _parse_yes_no_answer(result.content)

    if answer == "yes":
        return "needs_search"
    return "no_search"


def _parse_yes_no_answer(raw_answer: str) -> str | None:
    """Возвращает строго 'yes' или 'no' из ответа LLM, иначе None."""

    text = raw_answer.strip().lower()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    match = re.fullmatch(r"[`\"'\\s]*([a-z]+)[`\"'\\s]*[.!?,;:]*", text)
    if not match:
        return None
    answer = match.group(1)
    if answer in {"yes", "no"}:
        return answer
    return None
