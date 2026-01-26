from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.schemas.channel import ChannelCreate, ChannelManagerCreate, ChannelOut, ChannelUpdate

router = APIRouter()


@router.post("/", response_model=ChannelOut)
def create_channel(
    payload: ChannelCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ChannelOut:
    existing = db.query(Channel).filter(Channel.tg_chat_id == payload.tg_chat_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
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
    return ChannelOut.model_validate(channel)


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
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(channel, key, value)
    db.commit()
    db.refresh(channel)
    return ChannelOut.model_validate(channel)


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
    manager = ChannelManager(
        channel_id=channel_id,
        user_id=payload.user_id,
        permissions=payload.permissions,
    )
    db.add(manager)
    db.commit()
    return {"status": "ok"}
