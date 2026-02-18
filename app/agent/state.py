"""Определение State для LangGraph графа."""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Состояние агента, передаваемое между узлами графа."""

    messages: Annotated[list, add_messages]
    user_query: str
    intent: str
    coin: str
    api_data: dict
    response: str
