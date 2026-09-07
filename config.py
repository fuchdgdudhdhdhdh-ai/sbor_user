import os

# ==== Обязательные переменные окружения ====
# API_ID и API_HASH берутся на https://my.telegram.org -> API development tools
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")

# Токен управляющего бота, полученный у @BotFather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Через запятую ID пользователей, которым разрешено управлять ботом
# Узнать свой ID можно у @userinfobot
OWNER_IDS = [int(x) for x in os.environ.get("OWNER_IDS", "").split(",") if x.strip()]

# ==== Необязательные переменные ====
# Строка сессии Telethon. Пустая при первом запуске.
# После первого логина бот пришлёт вам эту строку — сохраните её
# в переменные окружения Render, чтобы не логиниться заново после рестарта.
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Путь к файлу базы SQLite.
# ВНИМАНИЕ: на бесплатном Render диск эфемерный и обнуляется при редеплое/рестарте.
# Если нужна база, которая переживает рестарты — подключите Render Persistent Disk
# и укажите путь на него, например /var/data/employees.db
DB_PATH = os.environ.get("DB_PATH", "employees.db")

# Порт для HTTP health-check (Render сам подставит переменную PORT)
PORT = int(os.environ.get("PORT", "10000"))

if not API_ID or not API_HASH or not BOT_TOKEN or not OWNER_IDS:
    raise RuntimeError(
        "Не заданы обязательные переменные окружения: "
        "API_ID, API_HASH, BOT_TOKEN, OWNER_IDS"
    )
