import os

# Токен бота — задаётся в переменных окружения Render (Environment -> BOT_TOKEN)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ID администратора (жёстко задан по требованию)
ADMIN_ID = 8080874290

# Render автоматически даёт переменную RENDER_EXTERNAL_URL для web service
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL") or ""
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") or RENDER_EXTERNAL_URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

# Необязательный секрет для проверки, что запросы идут от Telegram
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

WEB_SERVER_HOST = "0.0.0.0"
PORT = int(os.getenv("PORT") or "10000")

DATA_FILE = os.getenv("DATA_FILE", "data.json")
