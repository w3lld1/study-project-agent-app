"""Telegram-бот для крипто-консультанта."""

import uuid

import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import get_settings

SETTINGS = get_settings()
FASTAPI_URL = SETTINGS.fastapi_url


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Привет! Я крипто-консультант на базе GigaChat.\n\n"
        "Можно просто писать вопрос обычным текстом: команды не обязательны.\n\n"
        "Я могу:\n"
        "- Показать курс криптовалюты (напр. «Сколько стоит Bitcoin?»)\n"
        "- Найти новости (напр. «Новости по Ethereum»)\n"
        "- Дать аналитику (напр. «Стоит ли покупать BTC?»)\n"
        "- Ответить на общие вопросы (напр. «Что такое DeFi?»)\n\n"
        "Команды:\n"
        "/help — справка\n"
        "/price <coin> — цена монеты\n"
        "/news <coin> — новости по монете\n"
        "/analyze <coin> — аналитика по монете\n"
        "/reset — сбросить контекст диалога"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Справка по использованию бота."""

    await update.message.reply_text(
        "Доступны два режима:\n"
        "1) Просто пишите вопрос в свободной форме (без команд).\n"
        "2) Используйте команды для явного сценария.\n\n"
        "Команды:\n"
        "/price <coin> — узнать цену (пример: /price bitcoin)\n"
        "/news <coin> — последние новости (пример: /news eth)\n"
        "/analyze <coin> — аналитика (пример: /analyze solana)\n"
        "/reset — начать диалог заново (сброс контекста)"
    )


def _get_thread_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Возвращает thread_id для текущего пользователя."""

    user_id = str(update.effective_user.id)
    return str(context.user_data.get("thread_id") or user_id)


async def _reply_text(update: Update, text: str) -> None:
    """Отправляет ответ, разбивая длинные сообщения на части."""

    # Telegram ограничивает длину сообщения 4096 символами
    if len(text) > 4096:
        for i in range(0, len(text), 4096):
            await update.message.reply_text(text[i : i + 4096])
    else:
        await update.message.reply_text(text)


async def _forward_to_api(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str
) -> None:
    """Пересылает запрос в FastAPI и отправляет ответ в Telegram."""

    thread_id = _get_thread_id(update, context)

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{FASTAPI_URL}/chat",
                json={"message": message_text, "thread_id": thread_id},
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("response", "Не удалось получить ответ.")
        except httpx.HTTPStatusError as e:
            answer = f"Ошибка сервера: {e.response.status_code}"
        except httpx.ConnectError:
            answer = "Сервер недоступен. Убедитесь, что FastAPI запущен."
        except Exception as e:
            answer = f"Произошла ошибка: {e}"

    await _reply_text(update, answer)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений — пересылает в FastAPI."""

    await _forward_to_api(update, context, update.message.text)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /price."""

    coin = " ".join(context.args).strip()
    if not coin:
        await update.message.reply_text("Укажите монету: /price <coin>")
        return
    await _forward_to_api(update, context, f"Сколько стоит {coin}?")


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /news."""

    coin = " ".join(context.args).strip()
    if not coin:
        await update.message.reply_text("Укажите монету: /news <coin>")
        return
    await _forward_to_api(update, context, f"Какие последние новости по {coin}?")


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /analyze."""

    coin = " ".join(context.args).strip()
    if not coin:
        await update.message.reply_text("Укажите монету: /analyze <coin>")
        return
    await _forward_to_api(update, context, f"Сделай аналитику по {coin}.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает контекст диалога пользователя."""

    user_id = str(update.effective_user.id)
    context.user_data["thread_id"] = f"{user_id}:{uuid.uuid4()}"
    await update.message.reply_text("Контекст диалога сброшен. Можете начать новый запрос.")


def main() -> None:
    """Запуск Telegram-бота."""
    token = SETTINGS.telegram_bot_token
    if not token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не задан в .env")
        return

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram-бот запущен...")
    application.run_polling()


if __name__ == "__main__":
    main()
