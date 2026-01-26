import requests

from app.core.config import settings


def send_message(chat_id: int, text: str) -> int | None:
    if not settings.bot_token:
        return None
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    resp = requests.post(url, json={"chat_id": chat_id, "text": text})
    if not resp.ok:
        return None
    data = resp.json()
    if not data.get("ok"):
        return None
    return data["result"]["message_id"]


def copy_message(from_chat_id: int, message_id: int, to_chat_id: int) -> bool:
    if not settings.bot_token:
        return False
    url = f"https://api.telegram.org/bot{settings.bot_token}/copyMessage"
    resp = requests.post(
        url,
        json={"from_chat_id": from_chat_id, "message_id": message_id, "chat_id": to_chat_id},
    )
    if not resp.ok:
        return False
    data = resp.json()
    return bool(data.get("ok"))
