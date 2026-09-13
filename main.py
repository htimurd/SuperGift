import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

import config
import handlers_admin
import handlers_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_commands(bot: Bot):
    """Список команд, который Telegram показывает при вводе '/'."""
    default_commands = [
        BotCommand(command="start", description="Открыть меню"),
    ]
    admin_commands = default_commands + [
        BotCommand(command="admin", description="Админ-панель"),
    ]

    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    try:
        await bot.set_my_commands(
            admin_commands,
            scope=BotCommandScopeChat(chat_id=config.ADMIN_ID),
        )
    except Exception:
        # Если админ ещё ни разу не писал боту, Telegram может отказать
        # в установке персональных команд для этого chat_id — это не критично,
        # команда /admin всё равно работает, просто не будет в подсказке до /start.
        logger.warning("Не удалось установить персональные команды для админа")


async def on_startup(bot: Bot):
    await setup_commands(bot)
    if config.WEBHOOK_URL:
        await bot.set_webhook(
            config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET or None,
        )
        logger.info("Webhook set to %s", config.WEBHOOK_URL)
    else:
        logger.warning(
            "WEBHOOK_HOST/RENDER_EXTERNAL_URL не задан — webhook не установлен. "
            "На Render это должно проставляться автоматически."
        )


def create_app() -> web.Application:
    if not config.BOT_TOKEN:
        raise RuntimeError("Переменная окружения BOT_TOKEN не задана")

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_user.router)
    dp.startup.register(on_startup)

    app = web.Application()

    async def health(request):
        return web.Response(text="OK")

    app.router.add_get("/", health)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.WEBHOOK_SECRET or None,
    ).register(app, path=config.WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host=config.WEB_SERVER_HOST, port=config.PORT)
    
