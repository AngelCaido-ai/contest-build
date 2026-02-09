import logging

import requests

from bot.app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> dict:
    return {"X-Bot-Secret": settings.bot_secret}


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _url(path: str) -> str:
    return f"{settings.api_base_url}{path}"


def get_deal(deal_id: int) -> dict:
    logger.info("get_deal: deal_id=%s", deal_id)
    try:
        resp = requests.get(_url(f"/bot/deals/{deal_id}"), headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_deal: error deal_id=%s", deal_id)
        raise


def auth_bot(tg_user_id: int) -> dict:
    logger.info("auth_bot: tg_user_id=%s", tg_user_id)
    try:
        resp = requests.post(_url("/auth/bot"), json={"tg_user_id": tg_user_id}, headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("auth_bot: error tg_user_id=%s", tg_user_id)
        raise


def upsert_user(tg_user_id: int, tg_username: str | None) -> dict:
    logger.info("upsert_user: tg_user_id=%s", tg_user_id)
    try:
        resp = requests.post(
            _url("/bot/users/upsert"),
            json={"tg_user_id": tg_user_id, "tg_username": tg_username},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("upsert_user: error tg_user_id=%s", tg_user_id)
        raise


def update_terms(deal_id: int, payload: dict) -> dict:
    logger.info("update_terms: deal_id=%s", deal_id)
    try:
        resp = requests.post(_url(f"/bot/deals/{deal_id}/terms"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("update_terms: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_terms: error deal_id=%s", deal_id)
        raise


def update_publish_at(deal_id: int, payload: dict) -> dict:
    logger.info("update_publish_at: deal_id=%s", deal_id)
    try:
        resp = requests.post(_url(f"/bot/deals/{deal_id}/publish_at"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("update_publish_at: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_publish_at: error deal_id=%s", deal_id)
        raise


def update_wallet(tg_user_id: int, payload: dict) -> dict:
    logger.info("update_wallet: tg_user_id=%s", tg_user_id)
    try:
        resp = requests.post(_url(f"/bot/users/{tg_user_id}/wallet"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("update_wallet: success tg_user_id=%s", tg_user_id)
        return resp.json()
    except Exception:
        logger.exception("update_wallet: error tg_user_id=%s", tg_user_id)
        raise


def update_status(deal_id: int, payload: dict) -> dict:
    logger.info("update_status: deal_id=%s status=%s", deal_id, payload.get("status"))
    try:
        resp = requests.post(
            _url(f"/bot/deals/{deal_id}/status"),
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("update_status: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_status: error deal_id=%s", deal_id)
        raise


def create_creative(deal_id: int, payload: dict) -> dict:
    logger.info("create_creative: deal_id=%s", deal_id)
    try:
        resp = requests.post(_url(f"/bot/deals/{deal_id}/creative"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("create_creative: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_creative: error deal_id=%s", deal_id)
        raise


def get_creative(deal_id: int, tg_user_id: int, version: int | None = None) -> dict:
    params = {"tg_user_id": tg_user_id}
    if version is not None:
        params["version"] = version
    try:
        resp = requests.get(
            _url(f"/bot/deals/{deal_id}/creative"),
            params=params,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_creative: error deal_id=%s", deal_id)
        raise


def update_creative_status(deal_id: int, payload: dict) -> dict:
    logger.info("update_creative_status: deal_id=%s status=%s", deal_id, payload.get("status"))
    try:
        resp = requests.post(
            _url(f"/bot/deals/{deal_id}/creative/status"),
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("update_creative_status: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("update_creative_status: error deal_id=%s", deal_id)
        raise


def create_deposit(deal_id: int, payload: dict) -> dict:
    logger.info("create_deposit: deal_id=%s", deal_id)
    try:
        resp = requests.post(_url(f"/bot/deals/{deal_id}/deposit"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("create_deposit: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_deposit: error deal_id=%s", deal_id)
        raise


def add_event(deal_id: int, event_type: str, payload: dict | None = None) -> dict:
    logger.info("add_event: deal_id=%s type=%s", deal_id, event_type)
    try:
        resp = requests.post(
            _url(f"/bot/deals/{deal_id}/events"),
            json={"type": event_type, "payload": payload},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("add_event: error deal_id=%s type=%s", deal_id, event_type)
        raise


def create_advertiser_brief(deal_id: int, payload: dict) -> dict:
    logger.info("create_advertiser_brief: deal_id=%s", deal_id)
    try:
        resp = requests.post(
            _url(f"/bot/deals/{deal_id}/advertiser_brief"),
            json=payload,
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("create_advertiser_brief: success deal_id=%s", deal_id)
        return resp.json()
    except Exception:
        logger.exception("create_advertiser_brief: error deal_id=%s", deal_id)
        raise


def mark_tamper(channel_tg_chat_id: int, message_id: int) -> None:
    logger.info("mark_tamper: channel=%s message=%s", channel_tg_chat_id, message_id)
    try:
        resp = requests.post(
            _url("/bot/tamper"),
            json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("mark_tamper: success channel=%s message=%s", channel_tg_chat_id, message_id)
    except Exception:
        logger.exception("mark_tamper: error channel=%s message=%s", channel_tg_chat_id, message_id)
        raise


def mark_deleted(channel_tg_chat_id: int, message_id: int) -> None:
    logger.info("mark_deleted: channel=%s message=%s", channel_tg_chat_id, message_id)
    try:
        resp = requests.post(
            _url("/bot/deleted"),
            json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("mark_deleted: success channel=%s message=%s", channel_tg_chat_id, message_id)
    except Exception:
        logger.exception("mark_deleted: error channel=%s message=%s", channel_tg_chat_id, message_id)
        raise


def create_channel(payload: dict) -> dict:
    logger.info("create_channel: tg_chat_id=%s", payload.get("tg_chat_id"))
    try:
        resp = requests.post(_url("/bot/channels"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("create_channel: success tg_chat_id=%s", payload.get("tg_chat_id"))
        return resp.json()
    except Exception:
        logger.exception("create_channel: error tg_chat_id=%s", payload.get("tg_chat_id"))
        raise


def list_deals(
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
        resp = requests.get(_url("/bot/deals"), params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_deals: error tg_user_id=%s", tg_user_id)
        raise


def list_channels(tg_user_id: int) -> list[dict]:
    try:
        resp = requests.get(_url("/bot/channels"), params={"tg_user_id": tg_user_id}, headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_channels: error tg_user_id=%s", tg_user_id)
        raise


def list_channel_managers(tg_user_id: int, channel_id: int) -> list[dict]:
    try:
        token = auth_bot(tg_user_id).get("token")
        resp = requests.get(
            _url(f"/channels/{channel_id}/managers"),
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_channel_managers: error tg_user_id=%s channel_id=%s", tg_user_id, channel_id)
        raise


def add_channel_manager(tg_user_id: int, channel_id: int, tg_username: str) -> dict:
    logger.info("add_channel_manager: channel_id=%s username=%s", channel_id, tg_username)
    try:
        token = auth_bot(tg_user_id).get("token")
        resp = requests.post(
            _url(f"/channels/{channel_id}/managers"),
            json={"tg_username": tg_username},
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        logger.info("add_channel_manager: success channel_id=%s username=%s", channel_id, tg_username)
        return resp.json()
    except Exception:
        logger.exception("add_channel_manager: error channel_id=%s username=%s", channel_id, tg_username)
        raise


def remove_channel_manager(tg_user_id: int, channel_id: int, manager_id: int) -> dict:
    logger.info("remove_channel_manager: channel_id=%s manager_id=%s", channel_id, manager_id)
    try:
        token = auth_bot(tg_user_id).get("token")
        resp = requests.delete(
            _url(f"/channels/{channel_id}/managers/{manager_id}"),
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        logger.info("remove_channel_manager: success channel_id=%s manager_id=%s", channel_id, manager_id)
        return resp.json()
    except Exception:
        logger.exception("remove_channel_manager: error channel_id=%s manager_id=%s", channel_id, manager_id)
        raise


def list_listings() -> list[dict]:
    try:
        resp = requests.get(_url("/listings"), headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_listings: error")
        raise


def get_listing(listing_id: int) -> dict:
    try:
        resp = requests.get(_url(f"/listings/{listing_id}"), headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_listing: error listing_id=%s", listing_id)
        raise


def list_requests() -> list[dict]:
    try:
        resp = requests.get(_url("/requests"), headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("list_requests: error")
        raise


def get_request(request_id: int) -> dict:
    try:
        resp = requests.get(_url(f"/requests/{request_id}"), headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception:
        logger.exception("get_request: error request_id=%s", request_id)
        raise


def create_listing(payload: dict) -> dict:
    logger.info("create_listing: channel_id=%s", payload.get("channel_id"))
    try:
        resp = requests.post(_url("/bot/listings"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("create_listing: success channel_id=%s", payload.get("channel_id"))
        return resp.json()
    except Exception:
        logger.exception("create_listing: error channel_id=%s", payload.get("channel_id"))
        raise


def create_request(payload: dict) -> dict:
    logger.info("create_request: tg_user_id=%s", payload.get("advertiser_tg_user_id"))
    try:
        resp = requests.post(_url("/bot/requests"), json=payload, headers=_headers())
        resp.raise_for_status()
        logger.info("create_request: success")
        return resp.json()
    except Exception:
        logger.exception("create_request: error")
        raise


def create_deal(payload: dict) -> dict:
    logger.info("create_deal: tg_user_id=%s", payload.get("owner_tg_user_id"))
    try:
        resp = requests.post(_url("/bot/deals"), json=payload, headers=_headers())
        resp.raise_for_status()
        result = resp.json()
        logger.info("create_deal: success deal_id=%s", result.get("id"))
        return result
    except Exception:
        logger.exception("create_deal: error")
        raise


def create_test_deal(tg_user_id: int) -> dict:
    logger.info("create_test_deal: tg_user_id=%s", tg_user_id)
    try:
        resp = requests.post(
            _url("/bot/test-deal"),
            params={"tg_user_id": tg_user_id},
            headers=_headers(),
        )
        resp.raise_for_status()
        result = resp.json()
        logger.info("create_test_deal: success deal_id=%s", result.get("deal_id"))
        return result
    except Exception:
        logger.exception("create_test_deal: error tg_user_id=%s", tg_user_id)
        raise
