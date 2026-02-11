import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.models.channel import Channel
from app.models.channel_stats import ChannelStats
from app.models.listing import Listing
from app.schemas.channel_stats import ChannelStatsOut
from app.schemas.listing import (
    ChannelBriefOut,
    ListingCreate,
    ListingDetailOut,
    ListingOut,
    ListingUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ListingOut)
def create_listing(
    payload: ListingCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ListingOut:
    channel = db.get(Channel, payload.channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
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
        logger.info("create_listing: success listing_id=%s channel_id=%s user_id=%s", listing.id, payload.channel_id, user.id)
        return ListingOut.model_validate(listing)
    except HTTPException:
        raise
    except Exception:
        logger.exception("create_listing: error channel_id=%s user_id=%s", payload.channel_id, user.id)
        raise


@router.get("/", response_model=list[ListingOut])
def list_listings(
    price_min: float | None = Query(default=None),
    price_max: float | None = Query(default=None),
    active: bool | None = Query(default=None),
    channel_id: int | None = Query(default=None),
    exclude_own: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_optional_current_user),
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
    if exclude_own:
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        own_channel_ids = db.query(Channel.id).filter(Channel.owner_user_id == user.id)
        query = query.filter(~Listing.channel_id.in_(own_channel_ids))
    items = query.all()
    return [ListingOut.model_validate(item) for item in items]


@router.get("/{listing_id}", response_model=ListingDetailOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)) -> ListingDetailOut:
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    channel = db.get(Channel, listing.channel_id)
    channel_brief = None
    if channel:
        stats = db.query(ChannelStats).filter(ChannelStats.channel_id == channel.id).first()
        channel_brief = ChannelBriefOut(
            id=channel.id,
            username=channel.username,
            title=channel.title,
            stats=ChannelStatsOut.model_validate(stats) if stats else None,
        )
    result = ListingDetailOut.model_validate(listing)
    return result.model_copy(update={"channel": channel_brief})


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> ListingOut:
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    channel = db.get(Channel, listing.channel_id)
    if not channel or channel.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    try:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(listing, key, value)
        db.commit()
        db.refresh(listing)
        logger.info("update_listing: success listing_id=%s user_id=%s", listing_id, user.id)
        return ListingOut.model_validate(listing)
    except HTTPException:
        raise
    except Exception:
        logger.exception("update_listing: error listing_id=%s user_id=%s", listing_id, user.id)
        raise
