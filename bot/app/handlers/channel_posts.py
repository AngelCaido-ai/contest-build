import logging

from aiogram import Router
from aiogram.types import Message

from bot.app.services import api_client

logger = logging.getLogger(__name__)
router = Router()


async def _handle_edit(message: Message) -> None:
    if not message.chat or not message.message_id:
        logger.info('handle edit by not message.chat', message)
        return
    if message.chat.type not in {"channel", "supergroup", "group"}:
        logger.info('handle edit by message.chat.type not in', message)
        return
    logger.info(
        "edit detected: chat_id=%s message_id=%s chat_type=%s",
        message.chat.id,
        message.message_id,
        message.chat.type,
    )
    try:
        api_client.mark_tamper(message.chat.id, message.message_id)
    except Exception as exc:
        logger.error(
            "mark_tamper failed: chat_id=%s message_id=%s error=%s",
            message.chat.id,
            message.message_id,
            exc,
        )
        return
    logger.info(
        "mark_tamper ok: chat_id=%s message_id=%s",
        message.chat.id,
        message.message_id,
    )


@router.edited_channel_post()
async def on_edited_channel_post(message: Message) -> None:
    await _handle_edit(message)


@router.edited_message()
async def on_edited_message(message: Message) -> None:
    await _handle_edit(message)
