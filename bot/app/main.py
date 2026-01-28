import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.app.config import settings
from bot.app.handlers import channel_posts, deals, marketplace, onboarding, start

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info(f"Bot token length: {len(settings.bot_token)}")
    logger.info(f"API base URL: {settings.api_base_url}")
    logger.info(f"Bot secret length: {len(settings.bot_secret)}")
    
    try:
        bot = Bot(token=settings.bot_token)
        logger.info("Bot instance created")
        
        bot_info = await bot.get_me()
        logger.info(f"Bot connected: @{bot_info.username} ({bot_info.first_name})")
        
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(start.router)
        dp.include_router(onboarding.router)
        dp.include_router(marketplace.router)
        dp.include_router(deals.router)
        dp.include_router(channel_posts.router)
        logger.info("Routers registered")
        
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
