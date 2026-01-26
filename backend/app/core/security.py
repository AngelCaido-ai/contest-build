import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from jose import jwt

from app.core.config import settings


def build_data_check_string(init_data: str) -> tuple[str, str]:
    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = parsed.pop("hash", "")
    pairs = []
    for key in sorted(parsed.keys()):
        pairs.append(f"{key}={parsed[key]}")
    data_check_string = "\n".join(pairs)
    return data_check_string, received_hash


def verify_init_data(init_data: str) -> dict:
    if not settings.bot_token:
        return {}
    data_check_string, received_hash = build_data_check_string(init_data)
    secret = hmac.new(
        b"WebAppData",
        settings.bot_token.encode(),
        hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        secret,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if computed_hash != received_hash:
        return {}
    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    user_raw = parsed.get("user")
    if not user_raw:
        return {}
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return {}
    return user


def create_access_token(user_id: int) -> str:
    now = int(time.time())
    exp = now + settings.jwt_ttl_minutes * 60
    payload = {"sub": str(user_id), "iat": now, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
