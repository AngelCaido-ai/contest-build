import requests

from app.core.config import settings


def _post(method: str, payload: dict) -> dict | None:
    if not settings.bot_token:
        return None
    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    resp = requests.post(url, json=payload)
    if not resp.ok:
        return None
    data = resp.json()
    if not data.get("ok"):
        return None
    return data.get("result")


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> int | None:
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _post("sendMessage", payload)
    if not result:
        return None
    return result.get("message_id")


def send_media(chat_id: int, text: str | None, media_items: list[dict] | list[str] | None) -> int | None:
    if not media_items:
        if not text:
            return None
        return send_message(chat_id, text)
    normalized: list[dict] = []
    for item in media_items:
        if isinstance(item, dict):
            file_id = item.get("file_id")
            media_type = item.get("type") or "document"
        elif isinstance(item, str):
            file_id = item
            media_type = "photo"
        else:
            continue
        if not file_id:
            continue
        if media_type not in {"photo", "document", "video", "animation"}:
            media_type = "document"
        normalized.append({"type": media_type, "media": file_id})
    if not normalized:
        if not text:
            return None
        return send_message(chat_id, text)
    if len(normalized) == 1:
        media = normalized[0]
        method = {
            "photo": "sendPhoto",
            "document": "sendDocument",
            "video": "sendVideo",
            "animation": "sendAnimation",
        }.get(media["type"], "sendDocument")
        payload = {"chat_id": chat_id, media["type"]: media["media"]}
        if text:
            payload["caption"] = text
        result = _post(method, payload)
        if not result and media["type"] == "photo":
            fallback = {"chat_id": chat_id, "document": media["media"]}
            if text:
                fallback["caption"] = text
            result = _post("sendDocument", fallback)
        if not result:
            return None
        return result.get("message_id")
    group: list[dict] = []
    for index, media in enumerate(normalized):
        entry = {"type": media["type"], "media": media["media"]}
        if index == 0 and text:
            entry["caption"] = text
        group.append(entry)
    result = _post("sendMediaGroup", {"chat_id": chat_id, "media": group})
    if not result:
        return None
    first = result[0] if isinstance(result, list) and result else None
    if not first:
        return None
    return first.get("message_id")


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
