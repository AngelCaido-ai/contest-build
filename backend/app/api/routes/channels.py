import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.user import User
from app.schemas.channel import (
    ChannelCreate,
    ChannelManagerCreate,
    ChannelManagerOut,
    ChannelOut,
    ChannelUpdate,
)

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


@router.post("/", response_model=ChannelOut)
def create_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelOut:
    existing = db.query(Channel).filter(Channel.tg_chat_id == payload.tg_chat_id).first()
    if existing:
        logger.warning("create_channel: conflict tg_chat_id=%s user_id=%s", payload.tg_chat_id, user.id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    try:
        channel = Channel(
            tg_chat_id=payload.tg_chat_id,
            username=payload.username,
            title=payload.title,
            owner_user_id=user.id,
            bot_admin_status=bool(payload.bot_admin_status),
            rights_snapshot=payload.rights_snapshot,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        logger.info("create_channel: success channel_id=%s tg_chat_id=%s user_id=%s", channel.id, payload.tg_chat_id, user.id)
        return ChannelOut.model_validate(channel)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_channel: error tg_chat_id=%s user_id=%s", payload.tg_chat_id, user.id)
        raise


@router.get("/", response_model=list[ChannelOut])
def list_channels(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[ChannelOut]:
    items = db.query(Channel).filter(Channel.owner_user_id == user.id).all()
    return [ChannelOut.model_validate(item) for item in items]


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelOut:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ChannelOut.model_validate(channel)


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelOut:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(channel, key, value)
        db.commit()
        db.refresh(channel)
        logger.info("update_channel: success channel_id=%s user_id=%s", channel_id, user.id)
        return ChannelOut.model_validate(channel)
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_channel: error channel_id=%s user_id=%s", channel_id, user.id)
        raise


@router.post("/{channel_id}/managers")
def add_manager(
    channel_id: int,
    payload: ChannelManagerCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    target_user_id = payload.user_id
    if not target_user_id:
        username = _normalize_tg_username(payload.tg_username)
        if not username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        target_user = db.query(User).filter(User.tg_username == username).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Ask them to /start bot.",
            )
        target_user_id = target_user.id
    else:
        target_user = db.get(User, target_user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    existing = (
        db.query(ChannelManager)
        .filter(ChannelManager.channel_id == channel_id, ChannelManager.user_id == target_user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    try:
        manager = ChannelManager(
            channel_id=channel_id,
            user_id=target_user_id,
            permissions=payload.permissions,
        )
        db.add(manager)
        db.commit()
        logger.info("add_manager: success channel_id=%s target_user_id=%s", channel_id, target_user_id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("add_manager: error channel_id=%s target_user_id=%s", channel_id, target_user_id)
        raise


@router.get("/{channel_id}/managers", response_model=list[ChannelManagerOut])
def list_managers(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[ChannelManagerOut]:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    rows = (
        db.query(ChannelManager, User)
        .join(User, User.id == ChannelManager.user_id)
        .filter(ChannelManager.channel_id == channel_id)
        .all()
    )
    items = []
    for manager, manager_user in rows:
        items.append(
            ChannelManagerOut(
                id=manager.id,
                channel_id=manager.channel_id,
                user_id=manager.user_id,
                tg_user_id=manager_user.tg_user_id,
                tg_username=manager_user.tg_username,
                permissions=manager.permissions,
            )
        )
    return items


@router.delete("/{channel_id}/managers/{manager_id}")
def delete_manager(
    channel_id: int,
    manager_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    manager = (
        db.query(ChannelManager)
        .filter(ChannelManager.channel_id == channel_id, ChannelManager.id == manager_id)
        .first()
    )
    if not manager:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        db.delete(manager)
        db.commit()
        logger.info("delete_manager: success channel_id=%s manager_id=%s", channel_id, manager_id)
        return {"status": "ok"}
    except Exception:
        logger.exception("delete_manager: error channel_id=%s manager_id=%s", channel_id, manager_id)
        raise
