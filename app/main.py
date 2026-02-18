"""FastAPI-приложение: эндпоинты крипто-консультанта."""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agent.graph import agent_graph
from app.llm.gigachat import close_llm

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        await close_llm()


app = FastAPI(
    title="Крипто-консультант",
    description="ИИ-агент на GigaChat + LangGraph для консультаций по криптовалютам",
    version="1.0.0",
    lifespan=lifespan,
)

GRAPH_TIMEOUT_SECONDS = float(os.getenv("GRAPH_TIMEOUT_SECONDS", "30"))


class ChatRequest(BaseModel):
    """Тело запроса к эндпоинту чата."""

    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """Модель ответа эндпоинта чата."""

    response: str
    thread_id: str
    intent: str


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Основной эндпоинт чата с крипто-консультантом."""
    thread_id = request.thread_id or str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    input_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_query": request.message,
        "thread_id": thread_id,
    }

    try:
        result = await asyncio.wait_for(
            agent_graph.ainvoke(input_state, config=config),
            timeout=GRAPH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Таймаут обработки запроса. Попробуйте повторить запрос.",
        ) from exc

    return ChatResponse(
        response=result.get("response", "Не удалось получить ответ."),
        thread_id=thread_id,
        intent=result.get("intent", "unknown"),
    )


@app.get("/health")
async def health():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
