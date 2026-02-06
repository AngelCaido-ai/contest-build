import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

from bot.app.config import settings
from bot.app.handlers import channel_posts, deals, marketplace, onboarding, start

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UpdateLogMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        update_type = event.event_type
        chat_id = None
        message_id = None
        obj = (
            event.edited_channel_post
            or event.edited_message
            or event.channel_post
            or event.message
        )
        if obj:
            chat_id = obj.chat.id if obj.chat else None
            message_id = obj.message_id
        logger.info(
            "RAW UPDATE id=%s type=%s chat_id=%s message_id=%s",
            event.update_id,
            update_type,
            chat_id,
            message_id,
        )
        return await handler(event, data)


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
        dp.update.outer_middleware(UpdateLogMiddleware())
        dp.include_router(start.router)
        dp.include_router(onboarding.router)
        dp.include_router(marketplace.router)
        dp.include_router(deals.router)
        dp.include_router(channel_posts.router)
        logger.info("Routers registered")

        await bot.delete_webhook(drop_pending_updates=True)
        allowed_updates = dp.resolve_used_update_types()
        allowed_updates = sorted(set(allowed_updates) | {"edited_channel_post", "edited_message", "channel_post"})
        logger.info(f"Allowed updates: {allowed_updates}")
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
