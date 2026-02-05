from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_bot_secret, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.escrow_payment import EscrowPayment
from app.models.listing import Listing
from app.models.request import Request
from app.models.enums import CreativeStatus, DealStatus
from app.models.user import User
from app.schemas.bot import (
    BotChannelCreate,
    BotDealCreate,
    BotEscrowDepositRequest,
    BotListingCreate,
    BotRequestCreate,
    TamperRequest,
)
from app.schemas.channel import ChannelOut
from app.schemas.creative import CreativeCreate, CreativeOut, CreativeStatusUpdate
from app.schemas.deal import DealOut, DealStatusUpdate, DealTermsUpdate
from app.schemas.escrow import EscrowOut
from app.schemas.event import DealEventCreate, DealEventOut
from app.schemas.listing import ListingOut
from app.schemas.request import RequestOut
from app.services.deal_service import can_transition, log_event, set_status
from app.services.escrow_service import create_deposit
from app.services.telegram_service import send_media, send_message

router = APIRouter()
ROLE_OWNER = "owner"
ROLE_ADVERTISER = "advertiser"

ROLE_ALLOWED_STATUSES: dict[str, set[DealStatus]] = {
    ROLE_OWNER: {
        DealStatus.TERMS_LOCKED,
        DealStatus.CANCELED,
        DealStatus.SCHEDULED,
        DealStatus.POSTED,
        DealStatus.VERIFYING,
        DealStatus.RELEASED,
        DealStatus.REFUNDED,
    },
    ROLE_ADVERTISER: {
        DealStatus.AWAITING_PAYMENT,
        DealStatus.FUNDED,
        DealStatus.CANCELED,
    },
}


def _get_or_create_user(db: Session, tg_user_id: int, roles: list[str]) -> User:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        user = User(tg_user_id=tg_user_id, roles=roles)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    if roles:
        existing_roles = set(user.roles or [])
        new_roles = set(roles)
        if not new_roles.issubset(existing_roles):
            user.roles = sorted(existing_roles | new_roles)
            db.commit()
            db.refresh(user)
    return user


def _get_actor_user(db: Session, tg_user_id: int) -> User:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user


def _get_deal_role_flags(db: Session, deal: Deal, actor_tg_user_id: int) -> tuple[bool, bool]:
    user = _get_actor_user(db, actor_tg_user_id)
    channel = db.get(Channel, deal.channel_id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    is_owner = channel.owner_user_id == user.id
    if not is_owner:
        manager = (
            db.query(ChannelManager)
            .filter(ChannelManager.channel_id == channel.id, ChannelManager.user_id == user.id)
            .first()
        )
        is_owner = bool(manager)
    is_advertiser = deal.advertiser_id == user.id
    if not is_owner and not is_advertiser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return is_owner, is_advertiser


def _get_deal_role(db: Session, deal: Deal, actor_tg_user_id: int) -> str:
    is_owner, is_advertiser = _get_deal_role_flags(db, deal, actor_tg_user_id)
    if is_owner:
        return ROLE_OWNER
    return ROLE_ADVERTISER


def _notify_deal_parties(db: Session, deal: Deal, text: str) -> None:
    advertiser = db.get(User, deal.advertiser_id)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if advertiser:
        _send_deal_notification(db, deal, advertiser, ROLE_ADVERTISER, text)
    if owner:
        _send_deal_notification(db, deal, owner, ROLE_OWNER, text)


def _send_creative_to_advertiser(deal: Deal, creative: Creative, advertiser: User | None) -> None:
    if not advertiser or not advertiser.tg_user_id:
        return
    send_media(int(advertiser.tg_user_id), creative.text, creative.media_file_ids)


def _next_step_for_role(status: DealStatus, role: str) -> str | None:
    if status == DealStatus.NEGOTIATING:
        return "Lock terms or cancel the deal." if role == ROLE_OWNER else "Wait for owner to lock terms."
    if status == DealStatus.TERMS_LOCKED:
        return "Wait for payment." if role == ROLE_OWNER else "Pay escrow (open Payment details)."
    if status == DealStatus.AWAITING_PAYMENT:
        return "Wait for payment." if role == ROLE_OWNER else "Send payment to escrow."
    if status == DealStatus.FUNDED:
        return "Create and submit creative." if role == ROLE_OWNER else "Wait for creative."
    if status == DealStatus.CREATIVE_DRAFT:
        return "Update creative and submit for review." if role == ROLE_OWNER else "Wait for creative."
    if status == DealStatus.CREATIVE_REVIEW:
        return "Review creative and approve/request edits." if role == ROLE_ADVERTISER else "Waiting for review."
    if status == DealStatus.APPROVED:
        return "Schedule the post." if role == ROLE_OWNER else "Waiting for schedule."
    if status == DealStatus.SCHEDULED:
        return "Post at scheduled time." if role == ROLE_OWNER else "Waiting for post."
    if status == DealStatus.POSTED:
        return "Start verification." if role == ROLE_OWNER else "Waiting for verification."
    if status == DealStatus.VERIFYING:
        return "Release or refund after verification window." if role == ROLE_OWNER else "Waiting for release/refund."
    return None


def _deal_action_keyboard(deal: Deal, role: str) -> dict | None:
    buttons = [[{"text": "Open deal", "callback_data": f"deal:{deal.id}"}]]
    if role == ROLE_ADVERTISER and deal.status in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        buttons.append([{"text": "Payment details", "callback_data": f"deal_payment:{deal.id}"}])
    return {"inline_keyboard": buttons}


def _send_deal_notification(db: Session, deal: Deal, user: User, role: str, text: str) -> None:
    next_step = _next_step_for_role(deal.status, role)
    message = text
    if next_step:
        message = f"{message}\nNext step: {next_step}"
    reply_markup = _deal_action_keyboard(deal, role)
    send_message(int(user.tg_user_id), message, reply_markup=reply_markup)


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
    if payload.listing_id and payload.request_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if not payload.listing_id and not payload.request_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.listing_id:
        advertiser = _get_or_create_user(db, payload.owner_tg_user_id, ["advertiser"])
        listing = db.get(Listing, payload.listing_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        channel = db.get(Channel, listing.channel_id)
        if not channel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if channel.owner_user_id == advertiser.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot respond to own listing")
        manager = (
            db.query(ChannelManager)
            .filter(ChannelManager.channel_id == channel.id, ChannelManager.user_id == advertiser.id)
            .first()
        )
        if manager:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot respond to own listing")
        deal = Deal(
            listing_id=listing.id,
            request_id=None,
            advertiser_id=advertiser.id,
            channel_id=channel.id,
            price=payload.price,
            format=payload.format,
            brief=payload.brief,
            publish_at=payload.publish_at,
            verification_window=payload.verification_window,
            status=DealStatus.NEGOTIATING,
        )
    else:
        owner = _get_or_create_user(db, payload.owner_tg_user_id, ["owner"])
        request_item = db.get(Request, payload.request_id)
        if not request_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if not payload.channel_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
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
            brief=payload.brief or request_item.brief,
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


@router.post("/deals/{deal_id}/deposit", response_model=EscrowOut, dependencies=[Depends(get_bot_secret)])
def bot_create_deposit(deal_id: int, payload: BotEscrowDepositRequest, db: Session = Depends(get_db)) -> EscrowOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    is_owner, is_advertiser = _get_deal_role_flags(db, deal, payload.actor_tg_user_id)
    if not is_advertiser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    existing = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
    if existing:
        return EscrowOut.model_validate(existing)
    if deal.status not in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    expected_amount = payload.expected_amount or deal.price
    payment = create_deposit(db, deal, expected_amount)
    return EscrowOut.model_validate(payment)


@router.post("/deals/{deal_id}/terms", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_update_terms(
    deal_id: int,
    payload: DealTermsUpdate,
    db: Session = Depends(get_db),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    role = _get_deal_role(db, deal, payload.actor_tg_user_id)
    if role != ROLE_ADVERTISER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if deal.status not in {DealStatus.NEGOTIATING, DealStatus.TERMS_LOCKED}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("actor_tg_user_id", None)
    log_payload = payload.model_dump(exclude_unset=True, mode="json")
    log_payload.pop("actor_tg_user_id", None)
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
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    role = _get_deal_role(db, deal, payload.actor_tg_user_id)
    allowed_for_role = ROLE_ALLOWED_STATUSES.get(role, set())
    if payload.status not in allowed_for_role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if not can_transition(deal.status, payload.status):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.status == DealStatus.AWAITING_PAYMENT:
        existing = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
        if not existing:
            create_deposit(db, deal, deal.price)
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
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    is_owner, is_advertiser = _get_deal_role_flags(db, deal, payload.actor_tg_user_id)
    if not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if deal.status not in {DealStatus.FUNDED, DealStatus.CREATIVE_DRAFT}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    existing = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    version = 1
    if existing:
        version = existing.version + 1
    creative = Creative(
        deal_id=deal_id,
        text=payload.text,
        media_file_ids=payload.media_file_ids,
        version=version,
        status=CreativeStatus.REVIEW,
    )
    db.add(creative)
    set_status(deal, DealStatus.CREATIVE_REVIEW)
    log_event(db, deal.id, "CREATIVE_SUBMITTED", {"version": version})
    db.commit()
    db.refresh(creative)
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: creative drafted v{version}.")
    _send_creative_to_advertiser(deal, creative, db.get(User, deal.advertiser_id))
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
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    is_owner, is_advertiser = _get_deal_role_flags(db, deal, payload.actor_tg_user_id)
    if not is_advertiser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if deal.status != DealStatus.CREATIVE_REVIEW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    comment = (payload.comment or "").strip() or None
    if payload.status == CreativeStatus.DRAFT and not comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required for draft")
    if payload.publish_at is not None:
        deal.publish_at = payload.publish_at
    if payload.status == CreativeStatus.APPROVED and deal.publish_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="publish_at is required for approval")
    creative.status = payload.status
    if payload.status == CreativeStatus.APPROVED:
        set_status(deal, DealStatus.APPROVED)
    elif payload.status == CreativeStatus.DRAFT:
        set_status(deal, DealStatus.CREATIVE_DRAFT)
    elif payload.status == CreativeStatus.REVIEW:
        set_status(deal, DealStatus.CREATIVE_REVIEW)
    log_payload: dict = {"status": payload.status}
    if comment:
        log_payload["comment"] = comment
    if payload.publish_at is not None:
        log_payload["publish_at"] = payload.publish_at.isoformat()
    log_event(db, deal.id, "CREATIVE_STATUS", log_payload)
    db.commit()
    db.refresh(creative)
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: creative status -> {payload.status.value}.")
    if payload.status == CreativeStatus.DRAFT and comment:
        channel = db.get(Channel, deal.channel_id)
        owner = db.get(User, channel.owner_user_id) if channel else None
        if owner:
            _send_deal_notification(
                db,
                deal,
                owner,
                ROLE_OWNER,
                f"Deal #{deal.id}: edits requested. Comment: {comment}",
            )
    return CreativeOut.model_validate(creative)


@router.get(
    "/deals/{deal_id}/creative",
    response_model=CreativeOut,
    dependencies=[Depends(get_bot_secret)],
)
def bot_get_creative(
    deal_id: int,
    tg_user_id: int,
    version: int | None = None,
    db: Session = Depends(get_db),
) -> CreativeOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _get_deal_role_flags(db, deal, tg_user_id)
    query = db.query(Creative).filter(Creative.deal_id == deal_id)
    if version is not None:
        creative = query.filter(Creative.version == version).first()
    else:
        creative = query.order_by(Creative.version.desc()).first()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
