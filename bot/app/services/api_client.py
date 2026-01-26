import requests

from bot.app.config import settings


def _headers() -> dict:
    return {"X-Bot-Secret": settings.bot_secret}


def _url(path: str) -> str:
    return f"{settings.api_base_url}{path}"


def get_deal(deal_id: int) -> dict:
    resp = requests.get(_url(f"/bot/deals/{deal_id}"), headers=_headers())
    resp.raise_for_status()
    return resp.json()


def update_terms(deal_id: int, payload: dict) -> dict:
    resp = requests.post(_url(f"/bot/deals/{deal_id}/terms"), json=payload, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def update_status(deal_id: int, status: str) -> dict:
    resp = requests.post(
        _url(f"/bot/deals/{deal_id}/status"),
        json={"status": status},
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def create_creative(deal_id: int, payload: dict) -> dict:
    resp = requests.post(_url(f"/bot/deals/{deal_id}/creative"), json=payload, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def update_creative_status(deal_id: int, status: str) -> dict:
    resp = requests.post(
        _url(f"/bot/deals/{deal_id}/creative/status"),
        json={"status": status},
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def add_event(deal_id: int, event_type: str, payload: dict | None = None) -> dict:
    resp = requests.post(
        _url(f"/bot/deals/{deal_id}/events"),
        json={"type": event_type, "payload": payload},
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def mark_tamper(channel_tg_chat_id: int, message_id: int) -> None:
    resp = requests.post(
        _url("/bot/tamper"),
        json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
        headers=_headers(),
    )
    resp.raise_for_status()


def mark_deleted(channel_tg_chat_id: int, message_id: int) -> None:
    resp = requests.post(
        _url("/bot/deleted"),
        json={"channel_tg_chat_id": channel_tg_chat_id, "message_id": message_id},
        headers=_headers(),
    )
    resp.raise_for_status()


def create_channel(payload: dict) -> dict:
    resp = requests.post(_url("/bot/channels"), json=payload, headers=_headers())
    resp.raise_for_status()
    return resp.json()
