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


def check_message_tampered(
    chat_id: int, message_id: int, original_text: str | None, has_media: bool
) -> bool | None:
    if not settings.bot_token:
        return None
    url_base = f"https://api.telegram.org/bot{settings.bot_token}"
    if has_media:
        method = "editMessageCaption"
        payload: dict = {
            "chat_id": chat_id,
            "message_id": message_id,
            "caption": original_text or "",
        }
    else:
        if not original_text:
            return None
        method = "editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": original_text,
        }
    try:
        resp = requests.post(f"{url_base}/{method}", json=payload)
        data = resp.json()
        if data.get("ok"):
            logger.info(
                "check_message_tampered: TAMPERED chat_id=%s message_id=%s",
                chat_id,
                message_id,
            )
            return True
        description = (data.get("description") or "").lower()
        if "not modified" in description:
            return False
        if "message to edit not found" in description or "message can't be edited" in description:
            logger.warning(
                "check_message_tampered: message gone chat_id=%s message_id=%s desc=%s",
                chat_id,
                message_id,
                description,
            )
            return None
        logger.warning(
            "check_message_tampered: unexpected response chat_id=%s message_id=%s resp=%s",
            chat_id,
            message_id,
            data,
        )
        return None
    except Exception:
        logger.exception(
            "check_message_tampered: error chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )
        return None


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
