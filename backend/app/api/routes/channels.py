import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.channel_stats import ChannelStats
from app.models.deal import Deal
from app.models.listing import Listing
from app.models.user import User
from app.services.deal_actions import FINAL_DEAL_STATUSES
from app.schemas.channel_stats import ChannelStatsOut
from app.schemas.channel import (
    ChannelCreate,
    ChannelManagerCreate,
    ChannelManagerOut,
    ChannelOut,
    ChannelUpdate,
    TgAdminOut,
)
from app.services import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _can_access_channel(db: Session, channel: Channel, user: User) -> bool:
    if channel.owner_user_id == user.id:
        return True
    return (
        db.query(ChannelManager)
        .filter(ChannelManager.channel_id == channel.id, ChannelManager.user_id == user.id)
        .first()
    ) is not None


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
    tg_chat_id = payload.tg_chat_id
    username = _normalize_tg_username(payload.username)
    title = payload.title

    if tg_chat_id is None and username:
        chat_info = telegram_service.get_chat(username)
        if not chat_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found by username. Make sure the bot is added to the channel as admin.",
            )
        tg_chat_id = chat_info.get("id")
        if not tg_chat_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to resolve channel ID from Telegram",
            )
        if not username:
            username = chat_info.get("username")
        if not title:
            title = chat_info.get("title")

    existing = db.query(Channel).filter(Channel.tg_chat_id == tg_chat_id).first()
    if existing:
        logger.warning("create_channel: conflict tg_chat_id=%s user_id=%s", tg_chat_id, user.id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    try:
        channel = Channel(
            tg_chat_id=tg_chat_id,
            username=username,
            title=title,
            owner_user_id=user.id,
            bot_admin_status=bool(payload.bot_admin_status),
            rights_snapshot=payload.rights_snapshot,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        logger.info("create_channel: success channel_id=%s tg_chat_id=%s user_id=%s", channel.id, tg_chat_id, user.id)
        return ChannelOut.model_validate(channel)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_channel: error tg_chat_id=%s user_id=%s", tg_chat_id, user.id)
        raise


@router.get("/", response_model=list[ChannelOut])
def list_channels(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[ChannelOut]:
    managed_ids = db.query(ChannelManager.channel_id).filter(ChannelManager.user_id == user.id)
    items = (
        db.query(Channel)
        .filter(
            or_(
                Channel.owner_user_id == user.id,
                Channel.id.in_(managed_ids),
            )
        )
        .all()
    )
    channel_ids = [c.id for c in items]
    stats_rows = db.query(ChannelStats).filter(ChannelStats.channel_id.in_(channel_ids)).all() if channel_ids else []
    stats_by_channel_id = {s.channel_id: s for s in stats_rows}
    result = []
    for item in items:
        out = ChannelOut.model_validate(item)
        stats = stats_by_channel_id.get(item.id)
        result.append(out.model_copy(update={"stats": ChannelStatsOut.model_validate(stats) if stats else None}))
    return result


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelOut:
    channel = db.get(Channel, channel_id)
    if not channel or not _can_access_channel(db, channel, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    stats = db.query(ChannelStats).filter(ChannelStats.channel_id == channel.id).first()
    out = ChannelOut.model_validate(channel)
    return out.model_copy(update={"stats": ChannelStatsOut.model_validate(stats) if stats else None})


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


@router.delete("/{channel_id}")
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    active_deals_count = (
        db.query(Deal)
        .filter(Deal.channel_id == channel_id, ~Deal.status.in_(FINAL_DEAL_STATUSES))
        .count()
    )
    if active_deals_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Channel has {active_deals_count} active deal(s). Complete or cancel them first.",
        )
    try:
        db.query(Listing).filter(Listing.channel_id == channel_id).update(
            {"active": False}, synchronize_session="fetch"
        )
        db.query(ChannelManager).filter(ChannelManager.channel_id == channel_id).delete(
            synchronize_session="fetch"
        )
        db.query(ChannelStats).filter(ChannelStats.channel_id == channel_id).delete(
            synchronize_session="fetch"
        )
        db.delete(channel)
        db.commit()
        logger.info("delete_channel: success channel_id=%s user_id=%s", channel_id, user.id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("delete_channel: error channel_id=%s user_id=%s", channel_id, user.id)
        raise


@router.get("/{channel_id}/tg-admins", response_model=list[TgAdminOut])
def list_tg_admins(
    channel_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[TgAdminOut]:
    channel = db.get(Channel, channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    admins = telegram_service.get_chat_administrators(channel.tg_chat_id)
    if admins is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to get admin list from Telegram",
        )
    result = []
    for admin in admins:
        tg_user = admin.get("user", {})
        if tg_user.get("is_bot"):
            continue
        result.append(
            TgAdminOut(
                tg_user_id=tg_user.get("id", 0),
                tg_username=tg_user.get("username"),
                first_name=tg_user.get("first_name", ""),
                status=admin.get("status", "administrator"),
            )
        )
    return result


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
    target_user: User | None = None
    if payload.tg_user_id:
        target_user = db.query(User).filter(User.tg_user_id == payload.tg_user_id).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Ask them to send /start to the bot.",
            )
    elif payload.user_id:
        target_user = db.get(User, payload.user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    elif payload.tg_username:
        username = _normalize_tg_username(payload.tg_username)
        if not username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        target_user = db.query(User).filter(User.tg_username == username).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Ask them to send /start to the bot.",
            )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if not telegram_service.is_chat_admin(channel.tg_chat_id, target_user.tg_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an admin of this channel",
        )
    existing = (
        db.query(ChannelManager)
        .filter(ChannelManager.channel_id == channel_id, ChannelManager.user_id == target_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    try:
        manager = ChannelManager(
            channel_id=channel_id,
            user_id=target_user.id,
            permissions=payload.permissions,
        )
        db.add(manager)
        db.commit()
        logger.info("add_manager: success channel_id=%s target_user_id=%s", channel_id, target_user.id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("add_manager: error channel_id=%s target_user_id=%s", channel_id, target_user.id)
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
