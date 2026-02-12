import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.channel_stats import ChannelStats
from app.models.creative import Creative
from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.escrow_payment import EscrowPayment
from app.models.enums import CreativeStatus, DealStatus
from app.models.listing import Listing
from app.models.request import Request
from app.models.user import User
from app.schemas.creative import CreativeCreate, CreativeOut, CreativeStatusUpdate
from app.schemas.deal import (
    DealAdvertiserBrief,
    DealAdvertiserBriefCreate,
    DealChannelBrief,
    DealCreate,
    DealDetailOut,
    DealOut,
    DealPublishAtUpdate,
    DealStatusUpdate,
    DealTermsUpdate,
)
from app.schemas.event import DealEventOut
from app.services.deal_service import can_transition, log_event, set_status
from app.services.escrow_service import create_deposit
from app.services.telegram_service import send_media, send_message, upload_media_for_user

logger = logging.getLogger(__name__)
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


def _get_deal_role_flags(db: Session, deal: Deal, user: User) -> tuple[bool, bool]:
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


def _get_deal_role(db: Session, deal: Deal, user: User) -> str:
    is_owner, _ = _get_deal_role_flags(db, deal, user)
    if is_owner:
        return ROLE_OWNER
    return ROLE_ADVERTISER


def _next_step_for_role(status_value: DealStatus, role: str) -> str | None:
    if status_value == DealStatus.NEGOTIATING:
        return "Lock terms or cancel the deal." if role == ROLE_OWNER else "Wait for owner to lock terms."
    if status_value == DealStatus.TERMS_LOCKED:
        return "Wait for payment." if role == ROLE_OWNER else "Pay escrow (open Payment details)."
    if status_value == DealStatus.AWAITING_PAYMENT:
        return "Wait for payment." if role == ROLE_OWNER else "Send payment to escrow."
    if status_value == DealStatus.FUNDED:
        return "Create and submit creative." if role == ROLE_OWNER else "Wait for creative."
    if status_value == DealStatus.CREATIVE_DRAFT:
        return "Update creative and submit for review." if role == ROLE_OWNER else "Wait for creative."
    if status_value == DealStatus.CREATIVE_REVIEW:
        return "Review creative and approve/request edits." if role == ROLE_ADVERTISER else "Waiting for review."
    if status_value == DealStatus.APPROVED:
        return "Schedule the post." if role == ROLE_OWNER else "Waiting for schedule."
    if status_value == DealStatus.SCHEDULED:
        return "Post at scheduled time." if role == ROLE_OWNER else "Waiting for post."
    if status_value == DealStatus.POSTED:
        return "Start verification." if role == ROLE_OWNER else "Waiting for verification."
    if status_value == DealStatus.VERIFYING:
        return "Release or refund after verification window." if role == ROLE_OWNER else "Waiting for release/refund."
    return None


def _deal_action_keyboard(deal: Deal, role: str) -> dict | None:
    buttons = [[{"text": "Open deal", "callback_data": f"deal:{deal.id}"}]]
    if role == ROLE_ADVERTISER and deal.status in {DealStatus.TERMS_LOCKED, DealStatus.AWAITING_PAYMENT}:
        buttons.append([{"text": "Payment details", "callback_data": f"deal_payment:{deal.id}"}])
    return {"inline_keyboard": buttons}


def _send_deal_notification(deal: Deal, user: User, role: str, text: str) -> None:
    if not user.tg_user_id:
        return
    next_step = _next_step_for_role(deal.status, role)
    message = text
    if next_step:
        message = f"{message}\nNext step: {next_step}"
    reply_markup = _deal_action_keyboard(deal, role)
    send_message(int(user.tg_user_id), message, reply_markup=reply_markup)


def _notify_deal_parties(db: Session, deal: Deal, text: str) -> None:
    advertiser = db.get(User, deal.advertiser_id)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if advertiser:
        _send_deal_notification(deal, advertiser, ROLE_ADVERTISER, text)
    if owner:
        _send_deal_notification(deal, owner, ROLE_OWNER, text)


def _send_creative_to_advertiser(deal: Deal, creative: Creative, advertiser: User | None) -> None:
    if not advertiser or not advertiser.tg_user_id:
        return
    send_media(int(advertiser.tg_user_id), creative.text, creative.media_file_ids)


def _format_deal_terms(deal: Deal) -> str:
    lines = []
    if deal.price is not None:
        lines.append(f"price: {deal.price}")
    if deal.format:
        lines.append(f"format: {deal.format}")
    if deal.publish_at:
        lines.append(f"publish_at: {deal.publish_at.isoformat()}")
    if deal.verification_window:
        lines.append(f"verification_window: {deal.verification_window}")
    if deal.brief:
        lines.append(f"brief: {deal.brief}")
    if not lines:
        return "terms: -"
    return "terms:\n" + "\n".join(lines)


@router.post("/", response_model=DealOut)
def create_deal(
    payload: DealCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    if not payload.listing_id and not payload.request_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    FINAL_STATUSES = {DealStatus.CANCELED, DealStatus.RELEASED, DealStatus.REFUNDED}
    if payload.listing_id:
        listing = db.get(Listing, payload.listing_id)
        if not listing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        active_deal = (
            db.query(Deal)
            .filter(Deal.listing_id == listing.id, ~Deal.status.in_(FINAL_STATUSES))
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
        advertiser_id = user.id
        channel_id = channel.id
    else:
        request_item = db.get(Request, payload.request_id)
        if not request_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if not payload.channel_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        channel = db.get(Channel, payload.channel_id)
        if not channel or channel.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        advertiser_id = request_item.advertiser_id
        channel_id = channel.id
    try:
        deal = Deal(
            listing_id=payload.listing_id,
            request_id=payload.request_id,
            advertiser_id=advertiser_id,
            channel_id=channel_id,
            price=payload.price,
            format=payload.format,
            brief=payload.brief,
            publish_at=payload.publish_at,
            verification_window=payload.verification_window,
            status=DealStatus.NEGOTIATING,
        )
        db.add(deal)
        db.commit()
        db.refresh(deal)
        log_event(db, deal.id, "DEAL_CREATED")
        db.commit()
        logger.info("create_deal: success deal_id=%s user_id=%s", deal.id, user.id)
        return DealOut.model_validate(deal)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_deal: error user_id=%s", user.id)
        raise


@router.get("/", response_model=list[DealOut])
def list_deals(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[DealOut]:
    owner_channel_ids = [c.id for c in db.query(Channel).filter(Channel.owner_user_id == user.id).all()]
    manager_channel_ids = [c.channel_id for c in db.query(ChannelManager).filter(ChannelManager.user_id == user.id).all()]
    channel_ids = list(set(owner_channel_ids + manager_channel_ids))
    items = (
        db.query(Deal)
        .filter(or_(Deal.advertiser_id == user.id, Deal.channel_id.in_(channel_ids)))
        .all()
    )
    return [DealOut.model_validate(item) for item in items]


@router.get("/{deal_id}", response_model=DealDetailOut)
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealDetailOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _get_deal_role_flags(db, deal, user)
    channel = db.get(Channel, deal.channel_id)

    stats = db.query(ChannelStats).filter(ChannelStats.channel_id == deal.channel_id).first()
    advertiser = db.get(User, deal.advertiser_id)
    events = (
        db.query(DealEvent)
        .filter(DealEvent.deal_id == deal.id)
        .order_by(DealEvent.created_at.asc())
        .all()
    )

    channel_info = None
    if channel:
        channel_info = DealChannelBrief(
            id=channel.id,
            username=channel.username,
            title=channel.title,
            subscribers=stats.subscribers if stats else None,
            views_per_post=stats.views_per_post if stats else None,
        )

    advertiser_info = None
    if advertiser:
        advertiser_info = DealAdvertiserBrief(id=advertiser.id, tg_username=advertiser.tg_username)

    base = DealOut.model_validate(deal)
    return DealDetailOut(
        **base.model_dump(),
        channel_info=channel_info,
        advertiser_info=advertiser_info,
        events=[DealEventOut.model_validate(e) for e in events],
    )


@router.post("/{deal_id}/terms", response_model=DealOut)
def update_terms(
    deal_id: int,
    payload: DealTermsUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    role = _get_deal_role(db, deal, user)
    if role != ROLE_OWNER:
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
    advertiser = db.get(User, deal.advertiser_id)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if owner:
        _send_deal_notification(deal, owner, ROLE_OWNER, f"Deal #{deal.id}: terms locked.")
    if advertiser:
        terms_text = _format_deal_terms(deal)
        _send_deal_notification(
            deal,
            advertiser,
            ROLE_ADVERTISER,
            f"Deal #{deal.id}: terms locked.\n\n{terms_text}",
        )
    return DealOut.model_validate(deal)


@router.post("/{deal_id}/publish_at", response_model=DealOut)
def update_publish_at(
    deal_id: int,
    payload: DealPublishAtUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    role = _get_deal_role(db, deal, user)
    if role != ROLE_OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if deal.status in {
        DealStatus.POSTED,
        DealStatus.VERIFYING,
        DealStatus.RELEASED,
        DealStatus.REFUNDED,
        DealStatus.CANCELED,
    }:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.publish_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="publish_at is required")
    deal.publish_at = payload.publish_at
    log_event(db, deal.id, "PUBLISH_AT_UPDATED", {"publish_at": payload.publish_at.isoformat()})
    db.commit()
    db.refresh(deal)
    _notify_deal_parties(db, deal, f"Deal #{deal.id}: publish_at -> {payload.publish_at.isoformat()}.")
    return DealOut.model_validate(deal)


@router.post("/{deal_id}/status", response_model=DealOut)
def update_status(
    deal_id: int,
    payload: DealStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    role = _get_deal_role(db, deal, user)
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


@router.post("/{deal_id}/creative", response_model=CreativeOut)
def create_creative(
    deal_id: int,
    payload: CreativeCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CreativeOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    is_owner, _ = _get_deal_role_flags(db, deal, user)
    if not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if deal.status not in {DealStatus.FUNDED, DealStatus.CREATIVE_DRAFT}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if not payload.text and not payload.media_file_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    existing = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    version = 1 if not existing else existing.version + 1
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


@router.get("/{deal_id}/creative", response_model=CreativeOut)
def get_creative(
    deal_id: int,
    version: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CreativeOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _get_deal_role_flags(db, deal, user)
    query = db.query(Creative).filter(Creative.deal_id == deal_id)
    if version is not None:
        creative = query.filter(Creative.version == version).first()
    else:
        creative = query.order_by(Creative.version.desc()).first()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return CreativeOut.model_validate(creative)


@router.post("/{deal_id}/creative/status", response_model=CreativeOut)
def update_creative_status(
    deal_id: int,
    payload: CreativeStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CreativeOut:
    creative = db.query(Creative).filter(Creative.deal_id == deal_id).order_by(Creative.version.desc()).first()
    if not creative:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _, is_advertiser = _get_deal_role_flags(db, deal, user)
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
                deal,
                owner,
                ROLE_OWNER,
                f"Deal #{deal.id}: edits requested. Comment: {comment}",
            )
    return CreativeOut.model_validate(creative)


@router.post("/{deal_id}/advertiser_brief", response_model=DealEventOut)
def add_advertiser_brief(
    deal_id: int,
    payload: DealAdvertiserBriefCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealEventOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    _, is_advertiser = _get_deal_role_flags(db, deal, user)
    if not is_advertiser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if not payload.text and not payload.media_file_ids and payload.publish_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.publish_at is not None:
        if deal.status in {
            DealStatus.POSTED,
            DealStatus.VERIFYING,
            DealStatus.RELEASED,
            DealStatus.REFUNDED,
            DealStatus.CANCELED,
        }:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        deal.publish_at = payload.publish_at
        log_event(db, deal.id, "PUBLISH_AT_REQUESTED", {"publish_at": payload.publish_at.isoformat()})
    event_payload: dict = {
        "text": payload.text,
        "media_file_ids": payload.media_file_ids,
    }
    if payload.publish_at is not None:
        event_payload["publish_at"] = payload.publish_at.isoformat()
    event = DealEvent(deal_id=deal_id, type="ADVERTISER_BRIEF", payload=event_payload)
    db.add(event)
    db.commit()
    db.refresh(event)
    channel = db.get(Channel, deal.channel_id)
    owner = db.get(User, channel.owner_user_id) if channel else None
    if owner and owner.tg_user_id:
        lines = [f"Deal #{deal.id}: advertiser brief received."]
        if payload.text:
            lines.append(f"brief: {payload.text}")
        if payload.publish_at is not None:
            lines.append(f"publish_at: {payload.publish_at.isoformat()}")
        send_media(int(owner.tg_user_id), "\n".join(lines), payload.media_file_ids)
        _send_deal_notification(deal, owner, ROLE_OWNER, f"Deal #{deal.id}: advertiser brief received.")
    return DealEventOut.model_validate(event)


@router.post("/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
) -> dict:
    tg_user_id = int(user.tg_user_id or 0)
    if tg_user_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tg_user_id is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file is empty")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file is too large")
    uploaded = upload_media_for_user(
        tg_user_id,
        file.filename or "upload.bin",
        content,
        file.content_type,
    )
    if not uploaded:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="failed to upload media to telegram")
    return {"status": "ok", **uploaded}
