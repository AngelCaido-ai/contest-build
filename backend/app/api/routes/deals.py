import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.channel_manager import ChannelManager
from app.models.channel_stats import ChannelStats
from app.models.deal import Deal
from app.models.deal_event import DealEvent
from app.models.enums import DealStatus
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
from app.services.deal_actions import (
    FINAL_DEAL_STATUSES,
    do_add_advertiser_brief,
    do_create_creative,
    do_get_creative,
    do_update_creative_status,
    do_update_publish_at,
    do_update_status,
    do_update_terms,
    format_deal_terms,
    get_deal_role_flags,
    notify_deal_parties,
)
from app.services.deal_service import InvalidTransitionError, log_event
from app.services.telegram_service import upload_media_for_user

logger = logging.getLogger(__name__)
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


@router.post("/", response_model=DealOut)
def create_deal(
    payload: DealCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    if not payload.listing_id and not payload.request_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    if payload.listing_id:
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
                detail={"message": "Active deal already exists for this listing", "deal_id": active_deal.id},
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
        active_deal = (
            db.query(Deal)
            .filter(
                Deal.request_id == request_item.id,
                Deal.channel_id == channel.id,
                ~Deal.status.in_(FINAL_DEAL_STATUSES),
            )
            .first()
        )
        if active_deal:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Active deal already exists for this request and channel", "deal_id": active_deal.id},
            )
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
        logger.exception("create_deal: error user_id=%s", user.id)
        raise


@router.get("/", response_model=list[DealOut])
def list_deals(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[DealOut]:
    owner_channel_ids = [c.id for c in db.query(Channel).filter(Channel.owner_user_id == user.id).all()]
    manager_channel_ids = [c.channel_id for c in db.query(ChannelManager).filter(ChannelManager.user_id == user.id).all()]
    channel_ids = list(set(owner_channel_ids + manager_channel_ids))
    items = (
        db.query(Deal)
        .filter(or_(Deal.advertiser_id == user.id, Deal.channel_id.in_(channel_ids)))
        .order_by(Deal.updated_at.desc())
        .offset(offset)
        .limit(limit)
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
    try:
        get_deal_role_flags(db, deal, user.id)
    except ValueError as exc:
        raise _handle_domain_error(exc)
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


@router.get("/{deal_id}/events", response_model=list[DealEventOut])
def list_deal_events(
    deal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> list[DealEventOut]:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        get_deal_role_flags(db, deal, user.id)
    except ValueError as exc:
        raise _handle_domain_error(exc)
    events = (
        db.query(DealEvent)
        .filter(DealEvent.deal_id == deal.id)
        .order_by(DealEvent.created_at.desc())
        .all()
    )
    return [DealEventOut.model_validate(e) for e in events]


@router.post("/{deal_id}/terms", response_model=DealOut)
def update_terms(
    deal_id: int,
    payload: DealTermsUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    fields = payload.model_dump(exclude_unset=True)
    fields.pop("actor_tg_user_id", None)
    try:
        deal = do_update_terms(db, deal_id, user.id, fields)
        return DealOut.model_validate(deal)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/{deal_id}/publish_at", response_model=DealOut)
def update_publish_at(
    deal_id: int,
    payload: DealPublishAtUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    if payload.publish_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="publish_at is required")
    try:
        deal = do_update_publish_at(db, deal_id, user.id, payload.publish_at)
        return DealOut.model_validate(deal)
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/{deal_id}/status", response_model=DealOut)
def update_status(
    deal_id: int,
    payload: DealStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    try:
        deal = do_update_status(db, deal_id, user.id, payload.status)
        return DealOut.model_validate(deal)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/{deal_id}/creative", response_model=CreativeOut)
def create_creative(
    deal_id: int,
    payload: CreativeCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CreativeOut:
    try:
        creative = do_create_creative(db, deal_id, user.id, payload.text, payload.media_file_ids)
        return CreativeOut.model_validate(creative)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.get("/{deal_id}/creative", response_model=CreativeOut)
def get_creative(
    deal_id: int,
    version: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CreativeOut:
    try:
        creative = do_get_creative(db, deal_id, user.id, version)
        return CreativeOut.model_validate(creative)
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/{deal_id}/creative/status", response_model=CreativeOut)
def update_creative_status(
    deal_id: int,
    payload: CreativeStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> CreativeOut:
    try:
        creative = do_update_creative_status(
            db, deal_id, user.id, payload.status, payload.comment, payload.publish_at,
        )
        return CreativeOut.model_validate(creative)
    except InvalidTransitionError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status transition")
    except ValueError as exc:
        raise _handle_domain_error(exc)


@router.post("/{deal_id}/advertiser_brief", response_model=DealEventOut)
def add_advertiser_brief(
    deal_id: int,
    payload: DealAdvertiserBriefCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealEventOut:
    try:
        event = do_add_advertiser_brief(
            db, deal_id, user.id, payload.text, payload.media_file_ids, payload.publish_at,
        )
        return DealEventOut.model_validate(event)
    except ValueError as exc:
        raise _handle_domain_error(exc)


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
