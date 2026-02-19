"""Сборка LangGraph графа с MemorySaver."""

import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    analyze_node,
    analytics_search_node,
    clarify_coin_node,
    generate_response_node,
    get_analytics_data_node,
    get_news_node,
    get_price_node,
    web_search_node,
)
from app.agent.router import classify_intent, route_by_intent, route_needs_search
from app.agent.state import AgentState
from app.config import get_settings

LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()


def _is_debug_enabled() -> bool:
    """Возвращает признак включённого логирования шагов графа."""

    return SETTINGS.graph_debug_nodes


def _ensure_debug_logger() -> None:
    """Подключает stream handler, если логирование ещё не настроено извне."""

    if LOGGER.hasHandlers():
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    LOGGER.addHandler(handler)
    LOGGER.propagate = False


def _format_state_preview(state: Any) -> str:
    """Краткий срез состояния для логов без избыточного шума."""
    if not isinstance(state, dict):
        return "state=<non-dict>"
    query = str(state.get("user_query", ""))
    query_preview = query if len(query) <= 80 else f"{query[:77]}..."
    return (
        f"intent={state.get('intent', '')!r}, "
        f"coin={state.get('coin', '')!r}, "
        f"query={query_preview!r}"
    )


def _format_result_preview(result: Any) -> str:
    """Кратко описывает результат шага графа для логов."""
    if isinstance(result, dict):
        keys = ", ".join(sorted(result.keys()))
        preview = f"dict_keys=[{keys}]"
        api_data = result.get("api_data")
        if isinstance(api_data, dict):
            api_calls = api_data.get("_api_calls")
            if isinstance(api_calls, list) and api_calls:
                preview += f", api_calls={api_calls}"
        return preview
    return type(result).__name__


def _wrap_step(name: str, step: Callable[..., Any], debug: bool) -> Callable[..., Any]:
    """Оборачивает шаг графа логами при включённом debug-режиме."""
    if not debug:
        return step

    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        state = args[0] if args else None
        start = time.perf_counter()
        LOGGER.info("[graph] -> %s | %s", name, _format_state_preview(state))
        try:
            result = step(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            LOGGER.exception("[graph] !! %s failed", name)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        LOGGER.info(
            "[graph] <- %s | %.1f ms | %s",
            name,
            elapsed_ms,
            _format_result_preview(result),
        )
        return result

    return wrapped


def build_graph() -> StateGraph:
    """Собирает и компилирует граф агента."""
    debug_enabled = _is_debug_enabled()
    if debug_enabled:
        _ensure_debug_logger()
        LOGGER.setLevel(logging.INFO)
        LOGGER.info("[graph] debug mode enabled (GRAPH_DEBUG_NODES)")

    graph = StateGraph(AgentState)

    # Добавляем узлы
    graph.add_node(
        "classify_intent", _wrap_step("classify_intent", classify_intent, debug_enabled)
    )
    graph.add_node("get_price", _wrap_step("get_price", get_price_node, debug_enabled))
    graph.add_node("get_news", _wrap_step("get_news", get_news_node, debug_enabled))
    graph.add_node(
        "get_analytics_data",
        _wrap_step("get_analytics_data", get_analytics_data_node, debug_enabled),
    )
    graph.add_node(
        "analytics_search",
        _wrap_step("analytics_search", analytics_search_node, debug_enabled),
    )
    graph.add_node("analyze", _wrap_step("analyze", analyze_node, debug_enabled))
    graph.add_node("web_search", _wrap_step("web_search", web_search_node, debug_enabled))
    graph.add_node(
        "clarify_coin", _wrap_step("clarify_coin", clarify_coin_node, debug_enabled)
    )
    graph.add_node(
        "generate_response",
        _wrap_step("generate_response", generate_response_node, debug_enabled),
    )

    # Точка входа
    graph.set_entry_point("classify_intent")

    # Основной роутер: 4 пути
    graph.add_conditional_edges(
        "classify_intent",
        _wrap_step("route_by_intent", route_by_intent, debug_enabled),
        {
            "price": "get_price",
            "news": "get_news",
            "analytics": "get_analytics_data",
            "chat": "web_search",
            "clarify_coin": "clarify_coin",
        },
    )

    # price -> generate_response -> END
    graph.add_edge("get_price", "generate_response")

    # news -> generate_response -> END
    graph.add_edge("get_news", "generate_response")

    # chat (web_search) -> generate_response -> END
    graph.add_edge("web_search", "generate_response")

    # clarify_coin -> END
    graph.add_edge("clarify_coin", END)

    # generate_response -> END
    graph.add_edge("generate_response", END)

    # Ветка аналитики: вложенный роутер
    graph.add_conditional_edges(
        "get_analytics_data",
        _wrap_step("route_needs_search", route_needs_search, debug_enabled),
        {
            "needs_search": "analytics_search",
            "no_search": "analyze",
        },
    )

    # analytics_search -> analyze -> END
    graph.add_edge("analytics_search", "analyze")
    graph.add_edge("analyze", END)

    # Компиляция с MemorySaver
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Синглтон графа
agent_graph = build_graph()
