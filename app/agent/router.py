"""Роутинг: классификация intent и маршрутизация."""

import json
import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

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
    previous_coin = str(state.get("coin", "") or "").strip()
    history = _format_recent_history(state.get("messages", []))

    messages = [
        SystemMessage(content=CLASSIFY_PROMPT),
        HumanMessage(
            content=(
                f"История диалога (последние сообщения):\n{history}\n\n"
                f"Текущий вопрос пользователя: {user_query}\n\n"
                "Если в текущем вопросе используются местоимения ('он', 'она', "
                "'эта монета', 'она сейчас дешёвая') и явная монета не названа, "
                "используй монету из истории диалога."
            )
        ),
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
        coin = str(parsed.get("coin", "") or "").strip()
    except (json.JSONDecodeError, KeyError):
        intent = "chat"
        coin = ""

    if not coin and intent in {"price", "news", "analytics"} and previous_coin:
        coin = previous_coin

    return {"intent": intent, "coin": coin}


async def route_by_intent(state: dict) -> str:
    """Роутер: направляет по intent."""
    intent = state.get("intent", "chat")
    coin = str(state.get("coin", "") or "").strip()
    if intent in {"price", "news", "analytics"} and not coin:
        return "clarify_coin"
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


def _format_recent_history(messages: list[object], limit: int = 6) -> str:
    """Форматирует последние сообщения диалога для контекстной классификации."""

    if not messages:
        return "(история пуста)"

    lines: list[str] = []
    for msg in messages[-limit:]:
        if isinstance(msg, BaseMessage):
            role = _message_role(msg)
            raw_content = msg.content
        elif isinstance(msg, dict):
            role = str(msg.get("type", "message"))
            raw_content = msg.get("content", "")
        else:
            continue

        content = raw_content if isinstance(raw_content, str) else str(raw_content)
        compact_content = " ".join(content.split())
        if not compact_content:
            continue
        lines.append(f"{role}: {compact_content}")

    return "\n".join(lines) if lines else "(история пуста)"


def _message_role(msg: BaseMessage) -> str:
    """Преобразует тип сообщения в читаемую роль для промпта."""

    msg_type = getattr(msg, "type", "")
    if msg_type == "human":
        return "user"
    if msg_type == "ai":
        return "assistant"
    return msg_type or "message"
