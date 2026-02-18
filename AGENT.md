# AGENT.md

## Назначение
Этот проект реализует ИИ-агента "Крипто-консультант" на базе `GigaChat + LangGraph`.
Агент принимает запросы пользователя, выбирает ветку обработки по intent, обращается к внешним инструментам и формирует ответ.

## Что делает агент
- Определяет intent запроса: `price`, `news`, `analytics`, `chat`.
- Получает данные из внешних API:
  - `CoinGecko` (цены и рыночные данные).
  - `NewsAPI` (новости).
  - `DuckDuckGo` (веб-поиск).
- Поддерживает ветвление графа в LangGraph, включая вложенный роутинг для аналитики.
- Сохраняет состояние диалога через `thread_id` и checkpointer `MemorySaver`.

## Архитектура
Основные модули:
- `app/main.py` — FastAPI API (`/chat`, `/health`).
- `app/agent/graph.py` — сборка графа LangGraph.
- `app/agent/router.py` — классификация и роутинг.
- `app/agent/nodes.py` — узлы графа и форматирование данных.
- `app/tools/*.py` — интеграции с внешними сервисами.
- `app/bot/telegram.py` — Telegram-бот.

Маршруты графа:
- `classify_intent -> get_price -> generate_response`
- `classify_intent -> get_news -> generate_response`
- `classify_intent -> web_search -> generate_response`
- `classify_intent -> get_analytics_data -> (analytics_search|analyze) -> analyze/end`

## Требования окружения
- Python `3.11+`
- Переменные в `.env`:
  - `GIGACHAT_CREDENTIALS`
  - `NEWS_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `FASTAPI_URL` (например, `http://localhost:8000`)

## Запуск
- Установка зависимостей:
  - `pip install -r requirements.txt`
- API:
  - `uvicorn app.main:app --reload`
- Telegram-бот:
  - `python -m app.bot.telegram`

## Тесты
- Полный прогон:
  - `./scripts/run-tests.sh`
- Прогон выбранных тестов:
  - `./scripts/run-tests.sh tests/test_router.py`
- Таймауты (опционально):
  - `TEST_RUN_TIMEOUT=240 TEST_CASE_TIMEOUT=60 ./scripts/run-tests.sh`
- Ключевые файлы тестов:
  - `tests/test_api.py`
  - `tests/test_graph.py`
  - `tests/test_router.py`
  - `tests/test_nodes.py`
  - `tests/test_tools.py`

## Инженерные правила
- Не менять публичный контракт API без обновления тестов и README.
- Любая новая ветка/логика роутинга должна иметь тесты.
- Тесты запускать только через `./scripts/run-tests.sh` (репозиторный lock от параллельных инстансов).
- Форматирование числовых полей должно быть безопасным для `None`.
- Роутинг yes/no должен быть строгим, без подстрочных совпадений.
- Не хардкодить даты и годы в пользовательских/поисковых запросах.

## Definition of Done
- Проходит `./scripts/run-tests.sh`.
- Обязательные критерии проекта выполняются:
  - GigaChat.
  - LangGraph.
  - >=2 внешних tools.
  - сохранение состояния диалога.
  - сложный роутинг (>=3 пути).
  - запуск через API.
