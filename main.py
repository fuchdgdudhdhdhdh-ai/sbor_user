import asyncio
import logging
import threading

from flask import Flask

import config
from userbot import userbot_manager
from bot import build_application

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("main")

flask_app = Flask(__name__)


@flask_app.route("/")
def health():
    return "OK", 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=config.PORT)


async def main():
    application = build_application()

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Управляющий бот запущен")

    # Если ранее уже логинились и сохранили SESSION_STRING в переменные окружения —
    # подключаемся сразу, чтобы можно было нажать "Запустить мониторинг" без повторного входа
    if config.SESSION_STRING:
        try:
            await userbot_manager.ensure_connected()
            if await userbot_manager.is_authorized():
                logger.info("Юзербот авторизован по сохранённой сессии")
            else:
                logger.warning("SESSION_STRING задан, но сессия не авторизована — потребуется повторный вход")
        except Exception as e:
            logger.warning("Не удалось подключить юзербота по сохранённой сессии: %s", e)

    stop_event = asyncio.Event()
    await stop_event.wait()


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
