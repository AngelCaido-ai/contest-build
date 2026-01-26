import asyncio
from typing import Any

import requests
from telethon import TelegramClient
from telethon.tl.functions.stats import GetBroadcastStatsRequest

from app.core.config import settings


async def _fetch_stats(chat_id: int) -> dict[str, Any] | None:
    if not settings.telethon_api_id or not settings.telethon_api_hash or not settings.telethon_session:
        return None
    client = TelegramClient(settings.telethon_session, settings.telethon_api_id, settings.telethon_api_hash)
    await client.start()
    entity = await client.get_entity(chat_id)
    result = await client(GetBroadcastStatsRequest(channel=entity))
    await client.disconnect()
    return result.to_dict()


def fetch_stats(chat_id: int) -> dict[str, Any] | None:
    try:
        return asyncio.run(_fetch_stats(chat_id))
    except RuntimeError:
        return None


def fetch_bot_api_subscribers(chat_id: int) -> int | None:
    if not settings.bot_token:
        return None
    url = f"https://api.telegram.org/bot{settings.bot_token}/getChatMemberCount"
    resp = requests.post(url, json={"chat_id": chat_id})
    if not resp.ok:
        return None
    data = resp.json()
    if not data.get("ok"):
        return None
    return data.get("result")
