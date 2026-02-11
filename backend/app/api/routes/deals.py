import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.deal import Deal
from app.models.listing import Listing
from app.models.request import Request
from app.models.enums import DealStatus
from app.schemas.deal import DealCreate, DealOut
from app.services.deal_service import log_event

logger = logging.getLogger(__name__)
router = APIRouter()


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
    channel_ids = [c.id for c in db.query(Channel).filter(Channel.owner_user_id == user.id).all()]
    items = (
        db.query(Deal)
        .filter(or_(Deal.advertiser_id == user.id, Deal.channel_id.in_(channel_ids)))
        .all()
    )
    return [DealOut.model_validate(item) for item in items]


@router.get("/{deal_id}", response_model=DealOut)
def get_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> DealOut:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    channel = db.get(Channel, deal.channel_id)
    if deal.advertiser_id != user.id and (not channel or channel.owner_user_id != user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return DealOut.model_validate(deal)
