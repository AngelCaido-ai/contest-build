import logging

import requests
from aiogram import Router
from aiogram.types import Message

from watcher.app.config import settings

logger = logging.getLogger(__name__)
router = Router()


def _headers() -> dict:
    return {"X-Bot-Secret": settings.bot_secret}


def _mark_tamper(channel_tg_chat_id: int, message_id: int) -> None:
    url = f"{settings.api_base_url}/bot/tamper"
    try:
        resp = requests.post(
            url,
            json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("mark_tamper: ok channel=%s message=%s", channel_tg_chat_id, message_id)
    except Exception:
        logger.exception("mark_tamper: error channel=%s message=%s", channel_tg_chat_id, message_id)


async def _handle_edit(message: Message) -> None:
    if not message.chat or not message.message_id:
        return
    if message.chat.type not in {"channel", "supergroup", "group"}:
        return
    channel_id = message.chat.id
    if message.sender_chat and message.sender_chat.id:
        channel_id = message.sender_chat.id
    logger.info(
        "edit detected: chat_id=%s sender_chat_id=%s message_id=%s",
        message.chat.id,
        message.sender_chat.id if message.sender_chat else None,
        message.message_id,
    )
    _mark_tamper(channel_id, message.message_id)


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
