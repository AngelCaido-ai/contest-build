from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_db
from app.models.channel import Channel
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.enums import CreativeStatus, DealStatus
from app.models.user import User
from app.schemas.bot import BotChannelCreate, TamperRequest
from app.schemas.creative import CreativeCreate, CreativeOut, CreativeStatusUpdate
from app.schemas.deal import DealOut, DealStatusUpdate, DealTermsUpdate
from app.schemas.event import DealEventCreate, DealEventOut
from app.services.deal_service import can_transition, log_event, set_status

router = APIRouter()


@router.get("/deals/{deal_id}", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_get_deal(deal_id: int, db: Session = Depends(get_db)) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return DealOut.model_validate(deal)


@router.post("/deals/{deal_id}/terms", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_update_terms(
    deal_id: int,
    payload: DealTermsUpdate,
    db: Session = Depends(get_db),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(deal, key, value)
    set_status(deal, DealStatus.TERMS_LOCKED)
    log_event(db, deal.id, "TERMS_LOCKED", update_data)
    db.commit()
    db.refresh(deal)
    return DealOut.model_validate(deal)


@router.post("/deals/{deal_id}/status", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_update_status(
    deal_id: int,
    payload: DealStatusUpdate,
    db: Session = Depends(get_db),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not can_transition(deal.status, payload.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    set_status(deal, payload.status)
    log_event(db, deal.id, "STATUS_UPDATED", {"status": payload.status})
    db.commit()
    db.refresh(deal)
    return DealOut.model_validate(deal)


@router.post("/deals/{deal_id}/creative", response_model=CreativeOut, dependencies=[Depends(get_bot_secret)])
def bot_create_creative(
    deal_id: int,
    payload: CreativeCreate,
    db: Session = Depends(get_db),
) -> CreativeOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    existing = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    version = 1
    if existing:
        version = existing.version + 1
    creative = Creative(
        deal_id=deal_id,
        text=payload.text,
        media_file_ids=payload.media_file_ids,
        version=version,
        status=CreativeStatus.DRAFT,
    )
    db.add(creative)
    set_status(deal, DealStatus.CREATIVE_DRAFT)
    log_event(db, deal.id, "CREATIVE_DRAFTED", {"version": version})
    db.commit()
    db.refresh(creative)
    return CreativeOut.model_validate(creative)


@router.post(
    "/deals/{deal_id}/creative/status",
    response_model=CreativeOut,
    dependencies=[Depends(get_bot_secret)],
)
def bot_update_creative_status(
    deal_id: int,
    payload: CreativeStatusUpdate,
    db: Session = Depends(get_db),
) -> CreativeOut:
    creative = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    creative.status = payload.status
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if payload.status == CreativeStatus.REVIEW:
        set_status(deal, DealStatus.CREATIVE_REVIEW)
    if payload.status == CreativeStatus.APPROVED:
        set_status(deal, DealStatus.APPROVED)
    log_event(db, deal.id, "CREATIVE_STATUS", {"status": payload.status})
    db.commit()
    db.refresh(creative)
    return CreativeOut.model_validate(creative)


@router.post("/deals/{deal_id}/events", response_model=DealEventOut, dependencies=[Depends(get_bot_secret)])
def bot_add_event(
    deal_id: int,
    payload: DealEventCreate,
    db: Session = Depends(get_db),
) -> DealEventOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    event = DealEvent(deal_id=deal_id, type=payload.type, payload=payload.payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    return DealEventOut.model_validate(event)


@router.post("/tamper", dependencies=[Depends(get_bot_secret)])
def bot_mark_tamper(payload: TamperRequest, db: Session = Depends(get_db)) -> dict:
    channel = db.query(Channel).filter(Channel.tg_chat_id == payload.channel_tg_chat_id).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal = db.query(Deal).filter(Deal.channel_id == channel.id, Deal.posted_message_id == payload.message_id).first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal.tampered = True
    log_event(db, deal.id, "POST_TAMPERED", {"message_id": payload.message_id})
    db.commit()
    return {"status": "ok"}


@router.post("/deleted", dependencies=[Depends(get_bot_secret)])
def bot_mark_deleted(payload: TamperRequest, db: Session = Depends(get_db)) -> dict:
    channel = db.query(Channel).filter(Channel.tg_chat_id == payload.channel_tg_chat_id).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal = db.query(Deal).filter(Deal.channel_id == channel.id, Deal.posted_message_id == payload.message_id).first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal.deleted = True
    log_event(db, deal.id, "POST_DELETED", {"message_id": payload.message_id})
    db.commit()
    return {"status": "ok"}


@router.post("/channels", dependencies=[Depends(get_bot_secret)])
def bot_create_channel(payload: BotChannelCreate, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.tg_user_id == payload.owner_tg_user_id).first()
    if not user:
        user = User(tg_user_id=payload.owner_tg_user_id, roles=["owner"])
        db.add(user)
        db.commit()
        db.refresh(user)
    existing = db.query(Channel).filter(Channel.tg_chat_id == payload.tg_chat_id).first()
    if existing:
        existing.username = payload.username
        existing.title = payload.title
        existing.bot_admin_status = bool(payload.bot_admin_status)
        existing.rights_snapshot = payload.rights_snapshot
        db.commit()
        return {"status": "updated", "channel_id": existing.id}
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
    return {"status": "created", "channel_id": channel.id}
