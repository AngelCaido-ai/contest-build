import asyncio
import json
import logging
from typing import Any

import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stats import GetBroadcastStatsRequest, LoadAsyncGraphRequest
from telethon.tl.types import StatsGraph, StatsGraphAsync

from app.core.config import settings

logger = logging.getLogger(__name__)


def _extract_abs_value(data: dict, key: str) -> tuple[float | None, float | None]:
    """Extract current and previous from a StatsAbsValueAndPrev dict.

    MTProto returns these as double (float), e.g. shares_per_post = 2.7.
    We keep the original precision and round only at display time.
    """
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        return None, None
    current = raw.get("current")
    previous = raw.get("previous")
    return (
        float(current) if current is not None else None,
        float(previous) if previous is not None else None,
    )


def _extract_percent_value(data: dict, key: str) -> float | None:
    """Extract a StatsPercentValue (part / total → 0..1)."""
    raw = data.get(key, {})
    if not isinstance(raw, dict):
        return None
    part = raw.get("part")
    total = raw.get("total")
    if part is None or total is None or total == 0:
        return None
    return round(part / total, 4)


async def _resolve_async_graph(client: TelegramClient, graph: Any) -> dict[str, float] | None:
    """Resolve a StatsGraphAsync token into parsed {name: fraction} dict."""
    if isinstance(graph, StatsGraphAsync):
        try:
            resolved = await client(LoadAsyncGraphRequest(token=graph.token))
        except Exception:
            logger.exception("_resolve_async_graph: failed to load async graph")
            return None
        if not isinstance(resolved, StatsGraph):
            return None
        graph = resolved

    if isinstance(graph, StatsGraph) and graph.json:
        return _parse_graph_json(graph.json.data if hasattr(graph.json, "data") else graph.json)
    return None


def _parse_graph_json(raw_json: str | dict) -> dict[str, float] | None:
    """Parse Telegram chart JSON into {name: fraction} dict."""
    try:
        data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
    except (json.JSONDecodeError, TypeError):
        logger.warning("_parse_graph_json: invalid JSON")
        return None

    columns = data.get("columns", [])
    names = data.get("names", {})
    if not columns or not names:
        return None

    totals: dict[str, float] = {}
    for col in columns:
        if not col or len(col) < 2:
            continue
        key = col[0]
        if key == "x":
            continue
        values = [v for v in col[1:] if isinstance(v, (int, float))]
        if values:
            totals[key] = sum(values)

    grand_total = sum(totals.values())
    if grand_total == 0:
        return None

    result: dict[str, float] = {}
    for key, total in totals.items():
        name = names.get(key, key)
        result[name] = round(total / grand_total, 4)

    return result if result else None


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

        logger.info(
            "fetch_stats: mtproto RAW — followers=%s views_per_post=%s shares_per_post=%s reactions_per_post=%s enabled_notifications=%s",
            data.get("followers"), data.get("views_per_post"),
            data.get("shares_per_post"), data.get("reactions_per_post"),
            data.get("enabled_notifications"),
        )

        followers_cur, followers_prev = _extract_abs_value(data, "followers")
        views_cur, views_prev = _extract_abs_value(data, "views_per_post")
        shares_cur, shares_prev = _extract_abs_value(data, "shares_per_post")
        reactions_cur, reactions_prev = _extract_abs_value(data, "reactions_per_post")
        enabled_notifications = _extract_percent_value(data, "enabled_notifications")

        logger.info(
            "fetch_stats: mtproto PARSED — followers=%s/%s views=%s/%s shares=%s/%s reactions=%s/%s notifications=%.2f%%",
            followers_cur, followers_prev, views_cur, views_prev,
            shares_cur, shares_prev, reactions_cur, reactions_prev,
            (enabled_notifications or 0) * 100,
        )

        if not views_cur:
            logger.info("fetch_stats: broadcast stats views=0, calculating from recent posts")
            avg = await _avg_views_from_posts(client, entity)
            if avg is not None:
                data["_views_from_posts"] = avg
                logger.info("fetch_stats: avg views from recent posts = %s", avg)

        languages_parsed = await _resolve_async_graph(client, result.languages_graph)
        logger.info("fetch_stats: languages_parsed=%s", languages_parsed)

        data["_parsed"] = {
            "subscribers": followers_cur,
            "subscribers_prev": followers_prev,
            "views_per_post": views_cur,
            "views_per_post_prev": views_prev,
            "shares_per_post": shares_cur,
            "shares_per_post_prev": shares_prev,
            "reactions_per_post": reactions_cur,
            "reactions_per_post_prev": reactions_prev,
            "enabled_notifications": enabled_notifications,
            "languages": languages_parsed,
        }

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
