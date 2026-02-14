import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from watcher.app.config import settings
from watcher.app.handlers import close_client, init_client, router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Watcher bot token length: %d", len(settings.watcher_bot_token))
    logger.info("API base URL: %s", settings.api_base_url)

    try:
        bot = Bot(token=settings.watcher_bot_token)
        bot_info = await bot.get_me()
        logger.info("Watcher bot connected: @%s (%s)", bot_info.username, bot_info.first_name)

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(router)

        await bot.delete_webhook(drop_pending_updates=True)
        allowed_updates = ["edited_channel_post", "edited_message", "channel_post"]
        logger.info("Watcher allowed updates: %s", allowed_updates)

        init_client()
        logger.info("Watcher httpx AsyncClient initialized")

        try:
            logger.info("Starting watcher polling...")
            await dp.start_polling(bot, allowed_updates=allowed_updates)
        finally:
            await close_client()
            logger.info("Watcher httpx AsyncClient closed")
    except Exception as e:
        logger.error("Watcher error: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
