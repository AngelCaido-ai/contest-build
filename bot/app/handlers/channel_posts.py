from aiogram import Router
from aiogram.types import Message

from bot.app.services import api_client

router = Router()


@router.edited_channel_post()
async def on_edited_channel_post(message: Message) -> None:
    if message.chat and message.message_id:
        api_client.mark_tamper(message.chat.id, message.message_id)
