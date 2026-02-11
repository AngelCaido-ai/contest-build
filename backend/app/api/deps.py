from typing import Generator

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def get_optional_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def get_bot_secret(x_bot_secret: str | None = Header(default=None)) -> None:
    if not x_bot_secret or x_bot_secret != settings.bot_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
