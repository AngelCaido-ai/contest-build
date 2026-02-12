from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


def get_user_id_key(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return get_remote_address(request)
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        return get_remote_address(request)
    user_id = payload.get("sub")
    if not user_id:
        return get_remote_address(request)
    return f"user:{user_id}"
