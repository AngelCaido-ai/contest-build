import logging

import httpx
from telethon import events

from watcher.app.config import settings

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def init_client() -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.api_base_url,
        headers={"X-Bot-Secret": settings.bot_secret},
        timeout=httpx.Timeout(10.0, connect=5.0),
    )


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("httpx client not initialized, call init_client() first")
    return _client


async def _call_api(endpoint: str, channel_tg_chat_id: int, message_id: int) -> None:
    try:
        client = _get_client()
        resp = await client.post(
            endpoint,
            json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
        )
        resp.raise_for_status()
        logger.info("%s: ok channel=%s message=%s", endpoint, channel_tg_chat_id, message_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.debug("%s: not found channel=%s message=%s (not tracked)", endpoint, channel_tg_chat_id, message_id)
        else:
            logger.exception("%s: http error channel=%s message=%s", endpoint, channel_tg_chat_id, message_id)
    except Exception:
        logger.exception("%s: error channel=%s message=%s", endpoint, channel_tg_chat_id, message_id)


async def on_message_edited(event: events.MessageEdited.Event) -> None:
    if not event.is_channel:
        return
    chat_id = event.chat_id
    message_id = event.message.id
    logger.info("edit detected: chat_id=%s message_id=%s", chat_id, message_id)
    await _call_api("/bot/tamper", chat_id, message_id)


async def on_message_deleted(event: events.MessageDeleted.Event) -> None:
    chat_id = event.chat_id
    if not chat_id:
        return
    for msg_id in event.deleted_ids:
        logger.info("delete detected: chat_id=%s message_id=%s", chat_id, msg_id)
        await _call_api("/bot/deleted", chat_id, msg_id)
