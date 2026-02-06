import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("add_channel"))
async def add_channel(message: Message, bot: Bot) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /add_channel @channel or /add_channel -1001234567890")
        return
    ref = parts[1]
    try:
        chat = await bot.get_chat(ref)
    except Exception:
        logger.warning("add_channel: channel not found ref=%s tg_user_id=%s", ref, message.from_user.id)
        await message.answer("Channel not found")
        return
    try:
        user_member = await bot.get_chat_member(chat.id, message.from_user.id)
        bot_member = await bot.get_chat_member(chat.id, (await bot.me()).id)
    except TelegramBadRequest:
        logger.warning("add_channel: cannot access member list chat_id=%s", chat.id)
        await message.answer("Cannot access member list. Make bot admin or use a public channel.")
        return
    user_admin = user_member.status in {"administrator", "creator"}
    bot_admin = bot_member.status in {"administrator", "creator"}
    if not user_admin:
        logger.warning("add_channel: user not admin chat_id=%s tg_user_id=%s", chat.id, message.from_user.id)
        await message.answer("You are not channel admin")
        return
    payload = {
        "owner_tg_user_id": message.from_user.id,
        "tg_chat_id": chat.id,
        "username": chat.username,
        "title": chat.title,
        "bot_admin_status": bot_admin,
        "rights_snapshot": {
            "user_status": user_member.status,
            "bot_status": bot_member.status,
        },
    }
    try:
        result = api_client.create_channel(payload)
        logger.info("add_channel: success chat_id=%s result=%s", chat.id, result.get("status"))
        await message.answer(f"Channel linked: {result.get('status')}")
    except Exception:
        logger.exception("add_channel: error chat_id=%s tg_user_id=%s", chat.id, message.from_user.id)
        await message.answer("Failed to link channel.")
