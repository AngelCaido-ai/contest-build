import logging

import httpx

from bot.app.config import settings

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


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def get_deal(deal_id: int) -> dict:
    logger.info("get_deal: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.get(f"/bot/deals/{deal_id}")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_deal: error deal_id=%s", deal_id)
        raise


async def auth_bot(tg_user_id: int) -> dict:
    logger.info("auth_bot: tg_user_id=%s", tg_user_id)
    try:
        client = _get_client()
        resp = await client.post("/auth/bot", json={"tg_user_id": tg_user_id})
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("auth_bot: error tg_user_id=%s", tg_user_id)
        raise


async def upsert_user(tg_user_id: int, tg_username: str | None) -> dict:
    logger.info("upsert_user: tg_user_id=%s", tg_user_id)
    try:
        client = _get_client()
        resp = await client.post(
            "/bot/users/upsert",
            json={"tg_user_id": tg_user_id, "tg_username": tg_username},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("upsert_user: error tg_user_id=%s", tg_user_id)
        raise


async def update_terms(deal_id: int, payload: dict) -> dict:
    logger.info("update_terms: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.post(f"/bot/deals/{deal_id}/terms", json=payload)
        resp.raise_for_status()
        logger.info("update_terms: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_terms: error deal_id=%s", deal_id)
        raise


async def update_publish_at(deal_id: int, payload: dict) -> dict:
    logger.info("update_publish_at: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.post(f"/bot/deals/{deal_id}/publish_at", json=payload)
        resp.raise_for_status()
        logger.info("update_publish_at: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_publish_at: error deal_id=%s", deal_id)
        raise


async def update_wallet(tg_user_id: int, payload: dict) -> dict:
    logger.info("update_wallet: tg_user_id=%s", tg_user_id)
    try:
        client = _get_client()
        resp = await client.post(f"/bot/users/{tg_user_id}/wallet", json=payload)
        resp.raise_for_status()
        logger.info("update_wallet: success tg_user_id=%s", tg_user_id)
        return resp.json()
    except Exception:
        logger.exception("update_wallet: error tg_user_id=%s", tg_user_id)
        raise


async def update_status(deal_id: int, payload: dict) -> dict:
    logger.info("update_status: deal_id=%s status=%s", deal_id, payload.get("status"))
    try:
        client = _get_client()
        resp = await client.post(
            f"/bot/deals/{deal_id}/status",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("update_status: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_status: error deal_id=%s", deal_id)
        raise


async def create_creative(deal_id: int, payload: dict) -> dict:
    logger.info("create_creative: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.post(f"/bot/deals/{deal_id}/creative", json=payload)
        resp.raise_for_status()
        logger.info("create_creative: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_creative: error deal_id=%s", deal_id)
        raise


async def get_creative(deal_id: int, tg_user_id: int, version: int | None = None) -> dict:
    params = {"tg_user_id": tg_user_id}
    if version is not None:
        params["version"] = version
    try:
        client = _get_client()
        resp = await client.get(
            f"/bot/deals/{deal_id}/creative",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_creative: error deal_id=%s", deal_id)
        raise


async def update_creative_status(deal_id: int, payload: dict) -> dict:
    logger.info("update_creative_status: deal_id=%s status=%s", deal_id, payload.get("status"))
    try:
        client = _get_client()
        resp = await client.post(
            f"/bot/deals/{deal_id}/creative/status",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("update_creative_status: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_creative_status: error deal_id=%s", deal_id)
        raise


async def create_deposit(deal_id: int, payload: dict) -> dict:
    logger.info("create_deposit: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.post(f"/bot/deals/{deal_id}/deposit", json=payload)
        resp.raise_for_status()
        logger.info("create_deposit: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_deposit: error deal_id=%s", deal_id)
        raise


async def add_event(deal_id: int, event_type: str, payload: dict | None = None) -> dict:
    logger.info("add_event: deal_id=%s type=%s", deal_id, event_type)
    try:
        client = _get_client()
        resp = await client.post(
            f"/bot/deals/{deal_id}/events",
            json={"type": event_type, "payload": payload},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("add_event: error deal_id=%s type=%s", deal_id, event_type)
        raise


async def create_advertiser_brief(deal_id: int, payload: dict) -> dict:
    logger.info("create_advertiser_brief: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.post(
            f"/bot/deals/{deal_id}/advertiser_brief",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("create_advertiser_brief: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_advertiser_brief: error deal_id=%s", deal_id)
        raise


async def create_deal_message(deal_id: int, payload: dict) -> dict:
    logger.info("create_deal_message: deal_id=%s", deal_id)
    try:
        client = _get_client()
        resp = await client.post(
            f"/bot/deals/{deal_id}/messages",
            json=payload,
        )
        resp.raise_for_status()
        logger.info("create_deal_message: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_deal_message: error deal_id=%s", deal_id)
        raise


async def list_deal_messages(
    deal_id: int,
    tg_user_id: int,
    *,
    limit: int = 10,
    before_id: int | None = None,
) -> list[dict]:
    logger.info("list_deal_messages: deal_id=%s tg_user_id=%s", deal_id, tg_user_id)
    params: dict[str, object] = {"tg_user_id": tg_user_id, "limit": limit}
    if before_id is not None:
        params["before_id"] = before_id
    try:
        client = _get_client()
        resp = await client.get(
            f"/bot/deals/{deal_id}/messages",
            params=params,
        )
        resp.raise_for_status()
        logger.info("list_deal_messages: success deal_id=%s count=%s", deal_id, len(resp.json()))
        return resp.json()
    except Exception:
        logger.exception("list_deal_messages: error deal_id=%s", deal_id)
        raise


async def mark_tamper(channel_tg_chat_id: int, message_id: int) -> None:
    logger.info("mark_tamper: channel=%s message=%s", channel_tg_chat_id, message_id)
    try:
        client = _get_client()
        resp = await client.post(
            "/bot/tamper",
            json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
        )
        resp.raise_for_status()
        logger.info("mark_tamper: success channel=%s message=%s", channel_tg_chat_id, message_id)
    except Exception:
        logger.exception("mark_tamper: error channel=%s message=%s", channel_tg_chat_id, message_id)
        raise


async def mark_deleted(channel_tg_chat_id: int, message_id: int) -> None:
    logger.info("mark_deleted: channel=%s message=%s", channel_tg_chat_id, message_id)
    try:
        client = _get_client()
        resp = await client.post(
            "/bot/deleted",
            json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
        )
        resp.raise_for_status()
        logger.info("mark_deleted: success channel=%s message=%s", channel_tg_chat_id, message_id)
    except Exception:
        logger.exception("mark_deleted: error channel=%s message=%s", channel_tg_chat_id, message_id)
        raise


async def create_channel(payload: dict) -> dict:
    logger.info("create_channel: tg_chat_id=%s", payload.get("tg_chat_id"))
    try:
        client = _get_client()
        resp = await client.post("/bot/channels", json=payload)
        resp.raise_for_status()
        logger.info("create_channel: success tg_chat_id=%s", payload.get("tg_chat_id"))
        return resp.json()
    except Exception:
        logger.exception("create_channel: error tg_chat_id=%s", payload.get("tg_chat_id"))
        raise


async def list_deals(
    tg_user_id: int,
    *,
    statuses: list[str] | None = None,
    role: str | None = None,
    channel_id: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
) -> list[dict]:
    params: dict[str, object] = {"tg_user_id": tg_user_id}
    if statuses:
        params["statuses"] = statuses
    if role:
        params["role"] = role
    if channel_id is not None:
        params["channel_id"] = channel_id
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    if order_by:
        params["order_by"] = order_by
    try:
        client = _get_client()
        resp = await client.get("/bot/deals", params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_deals: error tg_user_id=%s", tg_user_id)
        raise


async def list_channels(tg_user_id: int) -> list[dict]:
    try:
        client = _get_client()
        resp = await client.get("/bot/channels", params={"tg_user_id": tg_user_id})
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_channels: error tg_user_id=%s", tg_user_id)
        raise


async def list_channel_managers(tg_user_id: int, channel_id: int) -> list[dict]:
    try:
        token = (await auth_bot(tg_user_id)).get("token")
        client = _get_client()
        resp = await client.get(
            f"/channels/{channel_id}/managers",
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_channel_managers: error tg_user_id=%s channel_id=%s", tg_user_id, channel_id)
        raise


async def add_channel_manager(tg_user_id: int, channel_id: int, tg_username: str) -> dict:
    logger.info("add_channel_manager: channel_id=%s username=%s", channel_id, tg_username)
    try:
        token = (await auth_bot(tg_user_id)).get("token")
        client = _get_client()
        resp = await client.post(
            f"/channels/{channel_id}/managers",
            json={"tg_username": tg_username},
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        logger.info("add_channel_manager: success channel_id=%s username=%s", channel_id, tg_username)
        return resp.json()
    except Exception:
        logger.exception("add_channel_manager: error channel_id=%s username=%s", channel_id, tg_username)
        raise


async def remove_channel_manager(tg_user_id: int, channel_id: int, manager_id: int) -> dict:
    logger.info("remove_channel_manager: channel_id=%s manager_id=%s", channel_id, manager_id)
    try:
        token = (await auth_bot(tg_user_id)).get("token")
        client = _get_client()
        resp = await client.delete(
            f"/channels/{channel_id}/managers/{manager_id}",
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        logger.info("remove_channel_manager: success channel_id=%s manager_id=%s", channel_id, manager_id)
        return resp.json()
    except Exception:
        logger.exception("remove_channel_manager: error channel_id=%s manager_id=%s", channel_id, manager_id)
        raise


async def list_listings(
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    params: dict[str, object] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    try:
        client = _get_client()
        resp = await client.get("/bot/listings", params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_listings: error")
        raise


async def get_listing(listing_id: int) -> dict:
    try:
        client = _get_client()
        resp = await client.get(f"/bot/listings/{listing_id}")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_listing: error listing_id=%s", listing_id)
        raise


async def list_requests(
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    params: dict[str, object] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    try:
        client = _get_client()
        resp = await client.get("/bot/requests", params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_requests: error")
        raise


async def get_request(request_id: int) -> dict:
    try:
        client = _get_client()
        resp = await client.get(f"/bot/requests/{request_id}")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_request: error request_id=%s", request_id)
        raise


async def create_listing(payload: dict) -> dict:
    logger.info("create_listing: channel_id=%s", payload.get("channel_id"))
    try:
        client = _get_client()
        resp = await client.post("/bot/listings", json=payload)
        resp.raise_for_status()
        logger.info("create_listing: success channel_id=%s", payload.get("channel_id"))
        return resp.json()
    except Exception:
        logger.exception("create_listing: error channel_id=%s", payload.get("channel_id"))
        raise


async def create_request(payload: dict) -> dict:
    logger.info("create_request: tg_user_id=%s", payload.get("advertiser_tg_user_id"))
    try:
        client = _get_client()
        resp = await client.post("/bot/requests", json=payload)
        resp.raise_for_status()
        logger.info("create_request: success")
        return resp.json()
    except Exception:
        logger.exception("create_request: error")
        raise


async def create_deal(payload: dict) -> dict:
    logger.info("create_deal: tg_user_id=%s", payload.get("owner_tg_user_id"))
    try:
        client = _get_client()
        resp = await client.post("/bot/deals", json=payload)
        resp.raise_for_status()
        result = resp.json()
        logger.info("create_deal: success deal_id=%s", result.get("id"))
        return result
    except Exception:
        logger.exception("create_deal: error")
        raise


async def create_test_deal(tg_user_id: int) -> dict:
    logger.info("create_test_deal: tg_user_id=%s", tg_user_id)
    try:
        client = _get_client()
        resp = await client.post(
            "/bot/test-deal",
            params={"tg_user_id": tg_user_id},
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("create_test_deal: success deal_id=%s", result.get("deal_id"))
        return result
    except Exception:
        logger.exception("create_test_deal: error tg_user_id=%s", tg_user_id)
        raise
