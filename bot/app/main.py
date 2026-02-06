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

        import requests as sync_requests
        import json

        diag_url = f"https://api.telegram.org/bot{settings.bot_token}/getUpdates"
        diag_resp = sync_requests.post(
            diag_url,
            json={"allowed_updates": allowed_updates, "limit": 100, "timeout": 3},
            timeout=10,
        )
        diag_data = diag_resp.json()
        diag_results = diag_data.get("result", [])
        logger.info("DIAG getUpdates: ok=%s count=%s", diag_data.get("ok"), len(diag_results))
        for upd in diag_results:
            upd_type = "unknown"
            for t in ["edited_channel_post", "channel_post", "edited_message", "message", "callback_query"]:
                if t in upd:
                    upd_type = t
                    break
            chat_id = None
            msg_id = None
            obj = upd.get(upd_type)
            if isinstance(obj, dict):
                chat_obj = obj.get("chat")
                if isinstance(chat_obj, dict):
                    chat_id = chat_obj.get("id")
                msg_id = obj.get("message_id")
            logger.info(
                "DIAG update: id=%s type=%s chat_id=%s message_id=%s",
                upd.get("update_id"),
                upd_type,
                chat_id,
                msg_id,
            )

        try:
            channels_resp = sync_requests.get(
                f"{settings.api_base_url}/bot/channels",
                params={"tg_user_id": 0},
                headers={"X-Bot-Secret": settings.bot_secret},
                timeout=5,
            )
            if channels_resp.ok:
                for ch in channels_resp.json():
                    tg_chat_id = ch.get("tg_chat_id")
                    if not tg_chat_id:
                        continue
                    try:
                        member = await bot.get_chat_member(tg_chat_id, bot_info.id)
                        logger.info(
                            "DIAG bot in channel %s: status=%s can_post=%s can_edit=%s can_delete=%s",
                            tg_chat_id,
                            member.status,
                            getattr(member, "can_post_messages", None),
                            getattr(member, "can_edit_messages", None),
                            getattr(member, "can_delete_messages", None),
                        )
                    except Exception as ch_err:
                        logger.error("DIAG bot in channel %s: error=%s", tg_chat_id, ch_err)
        except Exception as ch_list_err:
            logger.warning("DIAG channels check failed: %s", ch_list_err)

        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
