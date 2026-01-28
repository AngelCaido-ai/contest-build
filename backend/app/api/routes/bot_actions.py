from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.listing import Listing
from app.models.request import Request
from app.models.enums import CreativeStatus, DealStatus
from app.models.user import User
from app.schemas.bot import BotChannelCreate, BotDealCreate, BotListingCreate, BotRequestCreate, TamperRequest
from app.schemas.channel import ChannelOut
from app.schemas.creative import CreativeCreate, CreativeOut, CreativeStatusUpdate
from app.schemas.deal import DealOut, DealStatusUpdate, DealTermsUpdate
from app.schemas.event import DealEventCreate, DealEventOut
from app.schemas.listing import ListingOut
from app.schemas.request import RequestOut
from app.services.deal_service import can_transition, log_event, set_status
from app.services.telegram_service import send_message

router = APIRouter()


def _get_or_create_user(db: Session, tg_user_id: int, roles: list[str]) -> User:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        user = User(tg_user_id=tg_user_id, roles=roles)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _notify_deal_parties(db: Session, deal: Deal, text: str) -> None:
    chat_ids: list[int] = []
    advertiser = db.get(User, deal.advertiser_id)
    if advertiser:
        chat_ids.append(int(advertiser.tg_user_id))
    channel = db.get(Channel, deal.channel_id)
    if channel:
        owner = db.get(User, channel.owner_user_id)
        if owner:
            chat_ids.append(int(owner.tg_user_id))
    sent: set[int] = set()
    for chat_id in chat_ids:
        if chat_id in sent:
            continue
        sent.add(chat_id)
        send_message(chat_id, text)


@router.get("/deals/{deal_id}", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_get_deal(deal_id: int, db: Session = Depends(get_db)) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return DealOut.model_validate(deal)


@router.get("/deals", response_model=list[DealOut], dependencies=[Depends(get_bot_secret)])
def bot_list_deals(tg_user_id: int, db: Session = Depends(get_db)) -> list[DealOut]:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        return []
    channel_ids = [c.id for c in db.query(Channel).filter(Channel.owner_user_id == user.id).all()]
    items = (
        db.query(Deal)
        .filter(or_(Deal.advertiser_id == user.id, Deal.channel_id.in_(channel_ids)))
        .all()
    )
    return [DealOut.model_validate(item) for item in items]


@router.get("/channels", response_model=list[ChannelOut], dependencies=[Depends(get_bot_secret)])
def bot_list_channels(tg_user_id: int, db: Session = Depends(get_db)) -> list[ChannelOut]:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        return []
    owner_channels = db.query(Channel.id).filter(Channel.owner_user_id == user.id)
    manager_channels = db.query(ChannelManager.channel_id).filter(ChannelManager.user_id == user.id)
    channel_ids = {row[0] for row in owner_channels.union(manager_channels).all()}
    if not channel_ids:
        return []
    items = db.query(Channel).filter(Channel.id.in_(channel_ids)).all()
    return [ChannelOut.model_validate(item) for item in items]


@router.post("/listings", response_model=ListingOut, dependencies=[Depends(get_bot_secret)])
def bot_create_listing(payload: BotListingCreate, db: Session = Depends(get_db)) -> ListingOut:
    user = _get_or_create_user(db, payload.owner_tg_user_id, ["owner"])
    channel = db.get(Channel, payload.channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if channel.owner_user_id != user.id:
        manager = (
            db.query(ChannelManager)
            .filter(ChannelManager.channel_id == channel.id, ChannelManager.user_id == user.id)
            .first()
        )
        if not manager:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    listing = Listing(
        channel_id=payload.channel_id,
        price_ton=payload.price_ton,
        price_usd=payload.price_usd,
        format=payload.format or "post",
        categories=payload.categories,
        constraints=payload.constraints,
        active=payload.active if payload.active is not None else True,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return ListingOut.model_validate(listing)


@router.post("/requests", response_model=RequestOut, dependencies=[Depends(get_bot_secret)])
def bot_create_request(payload: BotRequestCreate, db: Session = Depends(get_db)) -> RequestOut:
    user = _get_or_create_user(db, payload.advertiser_tg_user_id, ["advertiser"])
    item = Request(
        advertiser_id=user.id,
        budget=payload.budget,
        niche=payload.niche,
        languages=payload.languages,
        min_subs=payload.min_subs,
        min_views=payload.min_views,
        dates=payload.dates,
        brief=payload.brief,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return RequestOut.model_validate(item)


@router.post("/deals", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_create_deal(payload: BotDealCreate, db: Session = Depends(get_db)) -> DealOut:
    owner = _get_or_create_user(db, payload.owner_tg_user_id, ["owner"])
    request_item = db.get(Request, payload.request_id)
    if not request_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    channel = db.get(Channel, payload.channel_id)
    if not channel:
        channel = db.query(Channel).filter(Channel.tg_chat_id == payload.channel_id).first()
    if not channel or channel.owner_user_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    deal = Deal(
        listing_id=None,
        request_id=payload.request_id,
        advertiser_id=request_item.advertiser_id,
        channel_id=channel.id,
        price=payload.price,
        format=payload.format,
        publish_at=payload.publish_at,
        verification_window=payload.verification_window,
        status=DealStatus.NEGOTIATING,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    log_event(db, deal.id, "DEAL_CREATED")
    db.commit()
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
    log_payload = payload.model_dump(exclude_unset=True, mode="json")
    for key, value in update_data.items():
        setattr(deal, key, value)
    set_status(deal, DealStatus.TERMS_LOCKED)
    log_event(db, deal.id, "TERMS_LOCKED", log_payload)
    db.commit()
    db.refresh(deal)
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: terms locked.")
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
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: status -> {payload.status.value}.")
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
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: creative drafted v{version}.")
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
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: creative status -> {payload.status.value}.")
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
