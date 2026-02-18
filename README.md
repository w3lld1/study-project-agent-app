# Крипто-консультант: ИИ-агент на GigaChat + LangGraph

ИИ-агент для консультаций по инвестициям в криптовалюту. Курсовой проект по курсу "Разработка ИИ-агентов" (Сбер Университет).

## Стек

- **LLM**: GigaChat (через langchain-gigachat)
- **Оркестрация**: LangGraph
- **API**: FastAPI
- **Инструменты**: CoinGecko, NewsAPI, DDGS (DuckDuckGo Search)
- **Интерфейс**: Telegram-бот
- **Язык**: Python 3.11+

## Возможности

- **Курс криптовалют** — актуальная цена, изменение за 24ч, капитализация (CoinGecko)
- **Новости** — последние новости по выбранной криптовалюте (NewsAPI)
- **Аналитика** — оценка рисков, трендов, рекомендации (GigaChat + данные)
- **Общие вопросы** — ответы на вопросы о блокчейне, DeFi и т.д. (DDGS/DuckDuckGo)

## Архитектура графа

```
START -> [classify_intent] ---> [get_price]           --> [generate_response] -> END
              (роутер)     |--> [get_news]            --> [generate_response] -> END
                           |--> [get_analytics_data]  --> [needs_search?] -yes-> [analytics_search] -> [analyze] -> END
                           |                              -no-> [analyze] -> END
                           |--> [web_search]          --> [generate_response] -> END
```

- **5+ путей** через граф (основной роутер: 4 пути + вложенный роутер в аналитике: 2 пути)
- **MemorySaver** для сохранения состояния диалога

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

Создайте файл `.env` в корне проекта:

```
GIGACHAT_CREDENTIALS=ваш_ключ_gigachat
NEWS_API_KEY=ваш_ключ_newsapi
TELEGRAM_BOT_TOKEN=ваш_токен_телеграм_бота
FASTAPI_URL=http://localhost:8000
GRAPH_TIMEOUT_SECONDS=30
GRAPH_DEBUG_NODES=false
```

- `GRAPH_TIMEOUT_SECONDS` — таймаут обработки одного запроса графом (в секундах). При превышении API вернёт `504`.
- `GRAPH_DEBUG_NODES=true` включает отладочный режим графа: в логах сервера видны вызовы узлов/роутеров и время выполнения.

## Запуск

### FastAPI-сервер

```bash
uvicorn app.main:app --reload
```

### Telegram-бот (в отдельном терминале)

```bash
python -m app.bot.telegram
```

## Тесты

Рекомендуемый запуск (с защитой от параллельного запуска несколькими инстансами агента):

```bash
./scripts/run-tests.sh
```

Запуск конкретного файла:

```bash
./scripts/run-tests.sh tests/test_router.py
```

Опциональные таймауты:

```bash
TEST_RUN_TIMEOUT=240 TEST_CASE_TIMEOUT=60 ./scripts/run-tests.sh
```

## API

### POST /chat

```json
{
  "message": "Сколько стоит Bitcoin?",
  "thread_id": "user-123"
}
```

Ответ:

```json
{
  "response": "...",
  "thread_id": "user-123",
  "intent": "price"
}
```

### GET /health

Проверка работоспособности.

## Примеры запросов

| Запрос | Intent | Ветка |
|--------|--------|-------|
| "Сколько стоит Bitcoin?" | price | get_price -> generate_response |
| "Новости по Ethereum" | news | get_news -> generate_response |
| "Стоит ли покупать BTC?" | analytics | get_analytics_data -> [search?] -> analyze |
| "Что такое DeFi?" | chat | web_search -> generate_response |
