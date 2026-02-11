import asyncio
import logging
from typing import Any

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stats import GetBroadcastStatsRequest

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _fetch_stats(chat_id: int, username: str | None = None) -> dict[str, Any] | None:
    if not settings.telethon_api_id or not settings.telethon_api_hash or not settings.telethon_session:
        logger.warning("fetch_stats: telethon credentials not configured")
        return None
    client = TelegramClient(StringSession(settings.telethon_session), settings.telethon_api_id, settings.telethon_api_hash)
    await client.start()
    try:
        target = username if username else chat_id
        logger.info("fetch_stats: requesting broadcast stats for %s", target)
        entity = await client.get_entity(target)
        result = await client(GetBroadcastStatsRequest(channel=entity))
        data = result.to_dict()
        raw_followers = data.get("followers", {})
        raw_views = data.get("views_per_post", {})
        logger.info(
            "fetch_stats: mtproto raw — followers=%s views_per_post=%s",
            raw_followers, raw_views,
        )

        views_val = raw_views.get("current") if isinstance(raw_views, dict) else None
        if not views_val:
            logger.info("fetch_stats: broadcast stats views=0, calculating from recent posts")
            avg = await _avg_views_from_posts(client, entity)
            if avg is not None:
                data["_views_from_posts"] = avg
                logger.info("fetch_stats: avg views from recent posts = %s", avg)

        return data
    finally:
        await client.disconnect()


async def _avg_views_from_posts(client: TelegramClient, entity: Any, limit: int = 20) -> int | None:
    try:
        messages = await client.get_messages(entity, limit=limit)
        views = [m.views for m in messages if m.views is not None and m.views > 0]
        if not views:
            return None
        return sum(views) // len(views)
    except Exception:
        logger.exception("_avg_views_from_posts: failed")
        return None


def fetch_stats(chat_id: int, username: str | None = None) -> dict[str, Any] | None:
    try:
        return asyncio.run(_fetch_stats(chat_id, username))
    except Exception:
        logger.exception("fetch_stats: mtproto failed for chat_id=%s username=%s", chat_id, username)
        return None


def fetch_bot_api_subscribers(chat_id: int) -> int | None:
    if not settings.bot_token:
        logger.warning("fetch_bot_api_subscribers: bot_token not configured")
        return None
    url = f"https://api.telegram.org/bot{settings.bot_token}/getChatMemberCount"
    resp = requests.post(url, json={"chat_id": chat_id})
    if not resp.ok:
        logger.warning("fetch_bot_api_subscribers: bot API error status=%s body=%s", resp.status_code, resp.text)
        return None
    data = resp.json()
    if not data.get("ok"):
        logger.warning("fetch_bot_api_subscribers: bot API response not ok: %s", data)
        return None
    count = data.get("result")
    logger.info("fetch_bot_api_subscribers: chat_id=%s subscribers=%s", chat_id, count)
    return count
