from aiogram import Router
from aiogram.types import Message

from bot.app.services import api_client

router = Router()


async def _handle_edit(message: Message) -> None:
    if not message.chat or not message.message_id:
        return
    if message.chat.type not in {"channel", "supergroup", "group"}:
        return
    try:
        api_client.mark_tamper(message.chat.id, message.message_id)
    except Exception:
        return


@router.edited_channel_post()
async def on_edited_channel_post(message: Message) -> None:
    await _handle_edit(message)


@router.edited_message()
async def on_edited_message(message: Message) -> None:
    await _handle_edit(message)
