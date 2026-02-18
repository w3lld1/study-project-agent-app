"""Telegram-бот для крипто-консультанта."""

import os

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    await update.message.reply_text(
        "Привет! Я крипто-консультант на базе GigaChat.\n\n"
        "Я могу:\n"
        "- Показать курс криптовалюты (напр. «Сколько стоит Bitcoin?»)\n"
        "- Найти новости (напр. «Новости по Ethereum»)\n"
        "- Дать аналитику (напр. «Стоит ли покупать BTC?»)\n"
        "- Ответить на общие вопросы (напр. «Что такое DeFi?»)\n\n"
        "Просто напишите свой вопрос!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений — пересылает в FastAPI."""
    user_id = str(update.effective_user.id)
    message_text = update.message.text

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(
                f"{FASTAPI_URL}/chat",
                json={"message": message_text, "thread_id": user_id},
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

    # Telegram ограничивает длину сообщения 4096 символами
    if len(answer) > 4096:
        for i in range(0, len(answer), 4096):
            await update.message.reply_text(answer[i : i + 4096])
    else:
        await update.message.reply_text(answer)


def main() -> None:
    """Запуск Telegram-бота."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не задан в .env")
        return

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram-бот запущен...")
    application.run_polling()


if __name__ == "__main__":
    main()
