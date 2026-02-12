import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def _post(method: str, payload: dict) -> dict | None:
    if not settings.bot_token:
        logger.warning("telegram _post: bot_token not configured, skip %s", method)
        return None
    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    try:
        resp = requests.post(url, json=payload)
        if not resp.ok:
            logger.warning("telegram %s: http %s body=%s", method, resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        if not data.get("ok"):
            logger.warning("telegram %s: api error %s", method, data.get("description"))
            return None
        return data.get("result")
    except Exception:
        logger.exception("telegram %s: request error", method)
        return None


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> int | None:
    logger.info("send_message: chat_id=%s", chat_id)
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _post("sendMessage", payload)
    if not result:
        logger.warning("send_message: failed chat_id=%s", chat_id)
        return None
    message_id = result.get("message_id")
    logger.info("send_message: success chat_id=%s message_id=%s", chat_id, message_id)
    return message_id


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


def _detect_upload_media_type(filename: str | None, content_type: str | None) -> str:
    ctype = (content_type or "").lower()
    name = (filename or "").lower()
    if ctype.startswith("video/"):
        return "video"
    if ctype == "image/gif" or name.endswith(".gif"):
        return "animation"
    if ctype.startswith("image/"):
        return "photo"
    return "document"


def upload_media_for_user(chat_id: int, filename: str, content: bytes, content_type: str | None = None) -> dict | None:
    if not settings.bot_token:
        logger.warning("upload_media_for_user: bot_token not configured")
        return None
    media_type = _detect_upload_media_type(filename, content_type)
    method_map = {
        "photo": ("sendPhoto", "photo"),
        "video": ("sendVideo", "video"),
        "animation": ("sendAnimation", "animation"),
        "document": ("sendDocument", "document"),
    }
    method, file_field = method_map.get(media_type, ("sendDocument", "document"))
    url = f"https://api.telegram.org/bot{settings.bot_token}/{method}"
    try:
        resp = requests.post(
            url,
            data={"chat_id": chat_id},
            files={file_field: (filename, content, content_type or "application/octet-stream")},
        )
        if not resp.ok:
            logger.warning("upload_media_for_user: http %s body=%s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        if not data.get("ok"):
            logger.warning("upload_media_for_user: api error %s", data.get("description"))
            return None
        result = data.get("result") or {}
        file_id = None
        if media_type == "photo":
            photos = result.get("photo") or []
            if photos:
                file_id = photos[-1].get("file_id")
        elif media_type == "video":
            file_id = (result.get("video") or {}).get("file_id")
        elif media_type == "animation":
            file_id = (result.get("animation") or {}).get("file_id")
        else:
            file_id = (result.get("document") or {}).get("file_id")
        if not file_id:
            logger.warning("upload_media_for_user: file_id missing")
            return None
        return {
            "type": media_type,
            "file_id": file_id,
            "message_id": result.get("message_id"),
        }
    except Exception:
        logger.exception("upload_media_for_user: request error")
        return None


def get_chat_administrators(chat_id: int) -> list[dict] | None:
    if not settings.bot_token:
        logger.warning("get_chat_administrators: bot_token not configured")
        return None
    result = _post("getChatAdministrators", {"chat_id": chat_id})
    if not result or not isinstance(result, list):
        logger.warning("get_chat_administrators: failed chat_id=%s", chat_id)
        return None
    logger.info("get_chat_administrators: chat_id=%s count=%s", chat_id, len(result))
    return result


def is_chat_admin(chat_id: int, tg_user_id: int) -> bool:
    admins = get_chat_administrators(chat_id)
    if admins is None:
        return False
    return any(a.get("user", {}).get("id") == tg_user_id for a in admins)


def copy_message(from_chat_id: int, message_id: int, to_chat_id: int) -> bool:
    if not settings.bot_token:
        logger.warning("copy_message: bot_token not configured")
        return False
    url = f"https://api.telegram.org/bot{settings.bot_token}/copyMessage"
    try:
        resp = requests.post(
            url,
            json={"from_chat_id": from_chat_id, "message_id": message_id, "chat_id": to_chat_id},
        )
        if not resp.ok:
            logger.warning("copy_message: http %s from=%s msg=%s", resp.status_code, from_chat_id, message_id)
            return False
        data = resp.json()
        ok = bool(data.get("ok"))
        if ok:
            logger.info("copy_message: success from=%s msg=%s to=%s", from_chat_id, message_id, to_chat_id)
        return ok
    except Exception:
        logger.exception("copy_message: error from=%s msg=%s", from_chat_id, message_id)
        return False
