import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request as FastAPIRequest, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_bot_secret, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
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
    BotDealMessageCreate,
    BotChannelCreate,
    BotDealCreate,
    BotAdvertiserBrief,
    BotEscrowDepositRequest,
    BotListingCreate,
    BotRequestCreate,
    BotUserUpsert,
    TamperRequest,
)
from app.schemas.channel import ChannelOut
from app.schemas.creative import CreativeCreate, CreativeOut, CreativeStatusUpdate
from app.schemas.deal import DealOut, DealPublishAtUpdate, DealStatusUpdate, DealTermsUpdate
from app.schemas.escrow import EscrowOut
from app.schemas.event import DealEventCreate, DealEventOut
from app.schemas.listing import ListingOut
from app.schemas.request import RequestOut
from app.schemas.user import UserOut, UserWalletUpdate
from app.services.deal_actions import (
    FINAL_DEAL_STATUSES,
    ROLE_ADVERTISER,
    ROLE_OWNER,
    do_add_advertiser_brief,
    do_create_creative,
    do_get_creative,
    do_update_creative_status,
    do_update_publish_at,
    do_update_status,
    do_update_terms,
    format_deal_terms,
    get_deal_role,
    get_deal_role_flags,
    notify_deal_parties,
)
from app.services.deal_service import InvalidTransitionError, log_event
from app.services.escrow_service import create_deposit
from app.services.telegram_service import send_media, send_message

router = APIRouter()

_ERROR_MAP = {
    "deal_not_found": (status.HTTP_404_NOT_FOUND, None),
    "channel_not_found": (status.HTTP_404_NOT_FOUND, None),
    "creative_not_found": (status.HTTP_404_NOT_FOUND, None),
    "not_deal_participant": (status.HTTP_403_FORBIDDEN, None),
    "forbidden": (status.HTTP_403_FORBIDDEN, None),
    "invalid_status": (status.HTTP_400_BAD_REQUEST, None),
    "empty_creative": (status.HTTP_400_BAD_REQUEST, None),
    "empty_brief": (status.HTTP_400_BAD_REQUEST, None),
    "comment_required": (status.HTTP_400_BAD_REQUEST, "Comment is required for draft"),
    "publish_at_required": (status.HTTP_400_BAD_REQUEST, "publish_at is required for approval"),
}


def _handle_domain_error(exc: ValueError) -> HTTPException:
    key = str(exc)
    code, detail = _ERROR_MAP.get(key, (status.HTTP_400_BAD_REQUEST, key))
    return HTTPException(status_code=code, detail=detail)


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


def _resolve_user_id(db: Session, tg_user_id: int) -> int:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return user.id


def _message_action_keyboard(deal_id: int) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "Open deal", "callback_data": f"deal:{deal_id}"}],
            [
                {"text": "Reply", "callback_data": f"deal_msg:{deal_id}"},
                {"text": "History", "callback_data": f"deal_msg_history:{deal_id}"},
            ],
        ]
    }


def _notify_message_counterparty(
    db: Session,
    deal: Deal,
    sender_role: str,
    text: str | None,
    media_file_ids: list[dict] | None,
) -> None:
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    advertiser = db.get(User, deal.advertiser_id)
    if sender_role == ROLE_ADVERTISER:
        target = owner
        sender_label = "advertiser"
    else:
        target = advertiser
        sender_label = "owner"
    if not target or not target.tg_user_id:
        return
    preview = (text or "").strip()
    header = f"Deal #{deal.id}: new message from {sender_label}."
    if preview:
        if len(preview) > 180:
            preview = f"{preview[:177]}..."
        header = f"{header}\n{preview}"
    elif media_file_ids:
        header = f"{header}\nMedia attached."
    send_message(int(target.tg_user_id), header, reply_markup=_message_action_keyboard(deal.id))
    if media_file_ids:
        send_media(int(target.tg_user_id), text, media_file_ids)


@router.post("/users/upsert", dependencies=[Depends(get_bot_secret)])
def bot_upsert_user(payload: BotUserUpsert, db: Session = Depends(get_db)) -> dict:
    try:
        username = _normalize_tg_username(payload.tg_username)
        user = db.query(User).filter(User.tg_user_id == payload.tg_user_id).first()
        if not user:
            user = User(tg_user_id=payload.tg_user_id, roles=["advertiser"])
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("bot_upsert_user: created user tg_user_id=%s", payload.tg_user_id)
        if _sync_tg_username(db, user, username):
            db.commit()
            db.refresh(user)
        return {"status": "ok", "user_id": user.id}
    except Exception:
        logger.exception("bot_upsert_user: error tg_user_id=%s", payload.tg_user_id)
        raise


@router.get("/deals/{deal_id}", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_get_deal(deal_id: int, db: Session = Depends(get_db)) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return DealOut.model_validate(deal)


@router.get("/deals", response_model=list[DealOut], dependencies=[Depends(get_bot_secret)])
def bot_list_deals(
    tg_user_id: int,
    statuses: list[DealStatus] | None = Query(None),
    role: str | None = None,
    channel_id: int | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    order_by: str | None = None,
    db: Session = Depends(get_db),
) -> list[DealOut]:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        return []
    channel_ids = [c.id for c in db.query(Channel).filter(Channel.owner_user_id == user.id).all()]
    query = db.query(Deal)
    if role:
        role_value = role.lower()
        if role_value == ROLE_OWNER:
            if not channel_ids:
                return []
            query = query.filter(Deal.channel_id.in_(channel_ids))
        elif role_value == ROLE_ADVERTISER:
            query = query.filter(Deal.advertiser_id == user.id)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    else:
        if channel_ids:
            query = query.filter(or_(Deal.advertiser_id == user.id, Deal.channel_id.in_(channel_ids)))
        else:
            query = query.filter(Deal.advertiser_id == user.id)
    if channel_id is not None:
        query = query.filter(Deal.channel_id == channel_id)
    if statuses:
        query = query.filter(Deal.status.in_(statuses))
    order_value = (order_by or "updated_at_desc").lower()
    if order_value == "updated_at_asc":
        query = query.order_by(Deal.updated_at.asc())
    elif order_value == "created_at_asc":
        query = query.order_by(Deal.created_at.asc())
    elif order_value == "created_at_desc":
        query = query.order_by(Deal.created_at.desc())
    else:
        query = query.order_by(Deal.updated_at.desc())
    items = query.offset(offset).limit(limit).all()
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
    if not user.linked_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet is required to create a listing",
        )
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


@router.get("/listings", response_model=list[ListingOut], dependencies=[Depends(get_bot_secret)])
def bot_list_listings(
    price_min: float | None = Query(default=None),
    price_max: float | None = Query(default=None),
    active: bool | None = Query(default=None),
    channel_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ListingOut]:
    query = db.query(Listing)
    if active is not None:
        query = query.filter(Listing.active == active)
    if channel_id is not None:
        query = query.filter(Listing.channel_id == channel_id)
    if price_min is not None:
        query = query.filter(Listing.price_usd >= price_min)
    if price_max is not None:
        query = query.filter(Listing.price_usd <= price_max)
    items = query.all()
    return [ListingOut.model_validate(item) for item in items]


@router.get("/listings/{listing_id}", response_model=ListingOut, dependencies=[Depends(get_bot_secret)])
def bot_get_listing(listing_id: int, db: Session = Depends(get_db)) -> ListingOut:
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ListingOut.model_validate(listing)


@router.get("/requests", response_model=list[RequestOut], dependencies=[Depends(get_bot_secret)])
def bot_list_requests(
    budget_min: float | None = Query(default=None),
    budget_max: float | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RequestOut]:
    query = db.query(Request)
    if budget_min is not None:
        query = query.filter(Request.budget >= budget_min)
    if budget_max is not None:
        query = query.filter(Request.budget <= budget_max)
    items = query.all()
    return [RequestOut.model_validate(item) for item in items]


@router.get("/requests/{request_id}", response_model=RequestOut, dependencies=[Depends(get_bot_secret)])
def bot_get_request(request_id: int, db: Session = Depends(get_db)) -> RequestOut:
    item = db.get(Request, request_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
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
        active_deal = (
            db.query(Deal)
            .filter(Deal.listing_id == listing.id, ~Deal.status.in_(FINAL_DEAL_STATUSES))
            .first()
        )
        if active_deal:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Active deal already exists for this listing",
            )
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
    try:
        db.add(deal)
        db.commit()
        db.refresh(deal)
        log_event(db, deal.id, "DEAL_CREATED")
        db.commit()
        logger.info("bot_create_deal: success deal_id=%s", deal.id)
        terms_text = format_deal_terms(deal)
        if deal.request_id:
            notify_text = f"Deal #{deal.id}: new response to request #{deal.request_id}.\n\n{terms_text}"
        else:
            notify_text = f"Deal #{deal.id}: new response to listing #{deal.listing_id}.\n\n{terms_text}"
        notify_deal_parties(db, deal, notify_text)
        return DealOut.model_validate(deal)
    except HTTPException:
        raise
    except Exception:
        logger.exception("bot_create_deal: error")
        raise


@router.post("/deals/{deal_id}/deposit", response_model=EscrowOut, dependencies=[Depends(get_bot_secret)])
@limiter.limit(settings.rate_limit_escrow_bot)
def bot_create_deposit(
    request: FastAPIRequest,
    deal_id: int,
    payload: BotEscrowDepositRequest,
    db: Session = Depends(get_db),
) -> EscrowOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        _, is_advertiser = get_deal_role_flags(db, deal, user_id)
    except ValueError as exc:
        raise _handle_domain_error(exc)
    if not is_advertiser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    existing = db.query(EscrowPayment).filter(EscrowPayment.deal_id == deal_id).first()
    if existing:
        return EscrowOut.model_validate(existing)
    if deal.status not in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    try:
        expected_amount = payload.expected_amount or deal.price
        payment = create_deposit(db, deal, expected_amount)
        logger.info("bot_create_deposit: success deal_id=%s", deal_id)
        return EscrowOut.model_validate(payment)
    except HTTPException:
        raise
    except Exception:
        logger.exception("bot_create_deposit: error deal_id=%s", deal_id)
        raise


@router.post("/deals/{deal_id}/terms", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_update_terms(
    deal_id: int,
    payload: DealTermsUpdate,
    db: Session = Depends(get_db),
) -> DealOut:
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    fields = payload.model_dump(exclude_unset=True)
    fields.pop("actor_tg_user_id", None)
    try:
        deal = do_update_terms(db, deal_id, user_id, fields)
        return DealOut.model_validate(deal)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/deals/{deal_id}/publish_at", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_update_publish_at(
    deal_id: int,
    payload: DealPublishAtUpdate,
    db: Session = Depends(get_db),
) -> DealOut:
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.publish_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="publish_at is required")
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        deal = do_update_publish_at(db, deal_id, user_id, payload.publish_at)
        return DealOut.model_validate(deal)
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/users/{tg_user_id}/wallet", response_model=UserOut, dependencies=[Depends(get_bot_secret)])
def bot_update_wallet(
    tg_user_id: int,
    payload: UserWalletUpdate,
    db: Session = Depends(get_db),
) -> UserOut:
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.actor_tg_user_id != tg_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    user = _get_or_create_user(db, tg_user_id, [])
    wallet = (payload.linked_wallet or "").strip()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="linked_wallet is required")
    user.linked_wallet = wallet
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/deals/{deal_id}/status", response_model=DealOut, dependencies=[Depends(get_bot_secret)])
def bot_update_status(
    deal_id: int,
    payload: DealStatusUpdate,
    db: Session = Depends(get_db),
) -> DealOut:
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        deal = do_update_status(db, deal_id, user_id, payload.status)
        return DealOut.model_validate(deal)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/deals/{deal_id}/creative", response_model=CreativeOut, dependencies=[Depends(get_bot_secret)])
def bot_create_creative(
    deal_id: int,
    payload: CreativeCreate,
    db: Session = Depends(get_db),
) -> CreativeOut:
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        creative = do_create_creative(db, deal_id, user_id, payload.text, payload.media_file_ids)
        return CreativeOut.model_validate(creative)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


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
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        creative = do_update_creative_status(
            db, deal_id, user_id, payload.status, payload.comment, payload.publish_at,
        )
        return CreativeOut.model_validate(creative)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post(
    "/deals/{deal_id}/advertiser_brief",
    response_model=DealEventOut,
    dependencies=[Depends(get_bot_secret)],
)
def bot_add_advertiser_brief(
    deal_id: int,
    payload: BotAdvertiserBrief,
    db: Session = Depends(get_db),
) -> DealEventOut:
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        event = do_add_advertiser_brief(
            db, deal_id, user_id, payload.text, payload.media_file_ids, payload.publish_at,
        )
        return DealEventOut.model_validate(event)
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post(
    "/deals/{deal_id}/messages",
    response_model=DealEventOut,
    dependencies=[Depends(get_bot_secret)],
)
def bot_create_deal_message(
    deal_id: int,
    payload: BotDealMessageCreate,
    db: Session = Depends(get_db),
) -> DealEventOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not payload.actor_tg_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if deal.status in FINAL_DEAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deal is already closed")
    user_id = _resolve_user_id(db, payload.actor_tg_user_id)
    try:
        sender_role = get_deal_role(db, deal, user_id)
    except ValueError as exc:
        raise _handle_domain_error(exc)
    text = (payload.text or "").strip() or None
    media_file_ids = payload.media_file_ids or None
    if not text and not media_file_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="text or media_file_ids is required")
    event_payload: dict = {
        "text": text,
        "media_file_ids": media_file_ids,
        "sender_role": sender_role,
    }
    if payload.reply_to_event_id is not None:
        event_payload["reply_to_event_id"] = payload.reply_to_event_id
    event = DealEvent(deal_id=deal_id, type="MESSAGE", payload=event_payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    _notify_message_counterparty(db, deal, sender_role, text, media_file_ids)
    return DealEventOut.model_validate(event)


@router.get(
    "/deals/{deal_id}/messages",
    response_model=list[DealEventOut],
    dependencies=[Depends(get_bot_secret)],
)
def bot_list_deal_messages(
    deal_id: int,
    tg_user_id: int,
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[DealEventOut]:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user_id = _resolve_user_id(db, tg_user_id)
    try:
        get_deal_role_flags(db, deal, user_id)
    except ValueError as exc:
        raise _handle_domain_error(exc)
    query = db.query(DealEvent).filter(DealEvent.deal_id == deal_id, DealEvent.type == "MESSAGE")
    if before_id is not None:
        query = query.filter(DealEvent.id < before_id)
    items = query.order_by(DealEvent.id.desc()).limit(limit).all()
    items.reverse()
    return [DealEventOut.model_validate(item) for item in items]


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
    user_id = _resolve_user_id(db, tg_user_id)
    try:
        creative = do_get_creative(db, deal_id, user_id, version)
        return CreativeOut.model_validate(creative)
    except ValueError as exc:
        raise _handle_domain_error(exc)


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
    logger.info("tamper request: channel_tg_chat_id=%s message_id=%s", payload.channel_tg_chat_id, payload.message_id)
    channel = db.query(Channel).filter(Channel.tg_chat_id == payload.channel_tg_chat_id).first()
    if not channel:
        logger.warning("tamper: channel not found for tg_chat_id=%s", payload.channel_tg_chat_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal = db.query(Deal).filter(Deal.channel_id == channel.id, Deal.posted_message_id == payload.message_id).first()
    if not deal:
        logger.warning("tamper: deal not found for channel_id=%s message_id=%s", channel.id, payload.message_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal.tampered = True
    log_event(db, deal.id, "POST_TAMPERED", {"message_id": payload.message_id})
    db.commit()
    logger.info("tamper: deal_id=%s marked as tampered", deal.id)
    return {"status": "ok"}


@router.post("/deleted", dependencies=[Depends(get_bot_secret)])
def bot_mark_deleted(payload: TamperRequest, db: Session = Depends(get_db)) -> dict:
    logger.info("deleted request: channel_tg_chat_id=%s message_id=%s", payload.channel_tg_chat_id, payload.message_id)
    channel = db.query(Channel).filter(Channel.tg_chat_id == payload.channel_tg_chat_id).first()
    if not channel:
        logger.warning("deleted: channel not found for tg_chat_id=%s", payload.channel_tg_chat_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal = db.query(Deal).filter(Deal.channel_id == channel.id, Deal.posted_message_id == payload.message_id).first()
    if not deal:
        logger.warning("deleted: deal not found for channel_id=%s message_id=%s", channel.id, payload.message_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        deal.deleted = True
        log_event(db, deal.id, "POST_DELETED", {"message_id": payload.message_id})
        db.commit()
        logger.info("deleted: deal_id=%s marked as deleted", deal.id)
        return {"status": "ok"}
    except Exception:
        logger.exception("deleted: error deal_id=%s", deal.id)
        raise


@router.post("/test-deal", dependencies=[Depends(get_bot_secret)])
def bot_create_test_deal(
    tg_user_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    channel = db.query(Channel).filter(Channel.owner_user_id == user.id).first()
    if not channel:
        channel = Channel(
            tg_chat_id=tg_user_id,
            username=None,
            title="Test Channel",
            owner_user_id=user.id,
            bot_admin_status=False,
        )
        db.add(channel)
        db.flush()
        logger.info("bot_create_test_deal: created test channel_id=%s for user_id=%s", channel.id, user.id)
    channel_id = channel.id
    listing = Listing(
        channel_id=channel_id,
        price_ton=0.01,
        format="post",
        active=True,
    )
    db.add(listing)
    db.flush()
    now = datetime.utcnow()
    deal = Deal(
        listing_id=listing.id,
        advertiser_id=user.id,
        channel_id=channel_id,
        price=0.01,
        format="post",
        brief="test deal",
        publish_at=now + timedelta(minutes=2),
        verification_window=10,
        status=DealStatus.SCHEDULED,
    )
    db.add(deal)
    db.flush()
    creative = Creative(
        deal_id=deal.id,
        text="testtest",
        version=1,
        status=CreativeStatus.APPROVED,
    )
    db.add(creative)
    log_event(db, deal.id, "TEST_DEAL_CREATED")
    db.commit()
    db.refresh(deal)
    logger.info("bot_create_test_deal: deal_id=%s publish_at=%s", deal.id, deal.publish_at)
    return {
        "status": "ok",
        "deal_id": deal.id,
        "listing_id": listing.id,
        "publish_at": deal.publish_at.isoformat(),
        "verification_window": deal.verification_window,
    }


@router.post("/channels", dependencies=[Depends(get_bot_secret)])
def bot_create_channel(payload: BotChannelCreate, db: Session = Depends(get_db)) -> dict:
    try:
        user = db.query(User).filter(User.tg_user_id == payload.owner_tg_user_id).first()
        if not user:
            user = User(tg_user_id=payload.owner_tg_user_id, roles=["owner"])
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("bot_create_channel: created user tg_user_id=%s", payload.owner_tg_user_id)
        existing = db.query(Channel).filter(Channel.tg_chat_id == payload.tg_chat_id).first()
        if existing:
            existing.username = payload.username
            existing.title = payload.title
            existing.bot_admin_status = bool(payload.bot_admin_status)
            existing.rights_snapshot = payload.rights_snapshot
            db.commit()
            logger.info("bot_create_channel: updated channel_id=%s tg_chat_id=%s", existing.id, payload.tg_chat_id)
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
        logger.info("bot_create_channel: created channel_id=%s tg_chat_id=%s", channel.id, payload.tg_chat_id)
        return {"status": "created", "channel_id": channel.id}
    except Exception:
        logger.exception("bot_create_channel: error tg_chat_id=%s", payload.tg_chat_id)
        raise
