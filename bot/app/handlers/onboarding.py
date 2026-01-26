from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.app.services import api_client

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
        await message.answer("Channel not found")
        return
    user_member = await bot.get_chat_member(chat.id, message.from_user.id)
    bot_member = await bot.get_chat_member(chat.id, (await bot.me()).id)
    user_admin = user_member.status in {"administrator", "creator"}
    bot_admin = bot_member.status in {"administrator", "creator"}
    if not user_admin:
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
    result = api_client.create_channel(payload)
    await message.answer(f"Channel linked: {result.get('status')}")
