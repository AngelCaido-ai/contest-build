from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.channel import Channel
from app.models.listing import Listing
from app.schemas.listing import ListingCreate, ListingOut, ListingUpdate

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


@router.get("/", response_model=list[ListingOut])
def list_listings(
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


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)) -> ListingOut:
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return ListingOut.model_validate(listing)


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
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(listing, key, value)
    db.commit()
    db.refresh(listing)
    return ListingOut.model_validate(listing)
