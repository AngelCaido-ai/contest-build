import logging

from aiogram import Router
from aiogram.types import Message

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()


async def _handle_edit(message: Message) -> None:
    if not message.chat or not message.message_id:
        return
    if message.chat.type not in {"channel", "supergroup", "group"}:
        return
    channel_id = message.chat.id
    if message.sender_chat and message.sender_chat.id:
        channel_id = message.sender_chat.id
    logger.info(
        "edit detected: chat_id=%s sender_chat_id=%s message_id=%s chat_type=%s",
        message.chat.id,
        message.sender_chat.id if message.sender_chat else None,
        message.message_id,
        message.chat.type,
    )
    try:
        api_client.mark_tamper(channel_id, message.message_id)
    except Exception as exc:
        logger.error(
            "mark_tamper failed: chat_id=%s message_id=%s error=%s",
            channel_id,
            message.message_id,
            exc,
        )
        return
    logger.info(
        "mark_tamper ok: chat_id=%s message_id=%s",
        channel_id,
        message.message_id,
    )


@router.edited_channel_post()
async def on_edited_channel_post(message: Message) -> None:
    await _handle_edit(message)


@router.edited_message()
async def on_edited_message(message: Message) -> None:
    await _handle_edit(message)


@router.channel_post()
async def on_channel_post(message: Message) -> None:
    if not message.edit_date:
        return
    await _handle_edit(message)
