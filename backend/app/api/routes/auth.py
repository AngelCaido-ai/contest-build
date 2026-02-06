import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_db
from app.core.security import create_access_token, verify_init_data
from app.models.user import User
from app.schemas.auth import AuthRequest, AuthResponse, BotAuthRequest
from app.schemas.user import UserOut

logger = logging.getLogger(__name__)
router = APIRouter()


def _normalize_tg_username(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("@"):
        value = value[1:]
    value = value.lower()
    return value or None


def _sync_tg_username(db: Session, user: User, username: str | None) -> bool:
    if not username:
        return False
    changed = False
    existing = db.query(User).filter(User.tg_username == username, User.id != user.id).first()
    if existing:
        existing.tg_username = None
        changed = True
    if user.tg_username != username:
        user.tg_username = username
        changed = True
    return changed


@router.post("/miniapp", response_model=AuthResponse)
def auth_miniapp(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user_data = verify_init_data(payload.init_data)
    if not user_data:
        logger.warning("miniapp auth: invalid init_data")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    tg_user_id = user_data.get("id")
    if not tg_user_id:
        logger.warning("miniapp auth: missing tg_user_id in init_data")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    try:
        tg_username = _normalize_tg_username(user_data.get("username"))
        user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
        if not user:
            user = User(tg_user_id=tg_user_id, roles=payload.roles or ["advertiser"])
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("miniapp auth: created user tg_user_id=%s", tg_user_id)
        if _sync_tg_username(db, user, tg_username):
            db.commit()
            db.refresh(user)
        token = create_access_token(user.id)
        logger.info("miniapp auth: success user_id=%s tg_user_id=%s", user.id, tg_user_id)
        return AuthResponse(token=token, user=UserOut.model_validate(user))
    except HTTPException:
        raise
    except Exception:
        logger.exception("miniapp auth: error tg_user_id=%s", tg_user_id)
        raise


@router.post("/bot", response_model=AuthResponse, dependencies=[Depends(get_bot_secret)])
def auth_bot(payload: BotAuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user = db.query(User).filter(User.tg_user_id == payload.tg_user_id).first()
        if not user:
            user = User(tg_user_id=payload.tg_user_id, roles=payload.roles or ["advertiser"])
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("bot auth: created user tg_user_id=%s", payload.tg_user_id)
        token = create_access_token(user.id)
        logger.info("bot auth: success user_id=%s tg_user_id=%s", user.id, payload.tg_user_id)
        return AuthResponse(token=token, user=UserOut.model_validate(user))
    except HTTPException:
        raise
    except Exception:
        logger.exception("bot auth: error tg_user_id=%s", payload.tg_user_id)
        raise
