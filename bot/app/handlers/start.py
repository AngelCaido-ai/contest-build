import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    try:
        api_client.upsert_user(message.from_user.id, message.from_user.username)
        logger.info("start: upsert user tg_user_id=%s", message.from_user.id)
    except Exception:
        logger.exception("start: upsert_user failed tg_user_id=%s", message.from_user.id)
    await message.answer(
        "Bot is running. Use /menu, /add_channel, /channels, /assigned_channels, /listings, /requests, "
        "/create_listing, /create_request, /respond_request, /deals, /deal, /terms, /status, /creative, "
        "/creative_status, /add_manager, /list_managers, /remove_manager, /cancel"
    )
