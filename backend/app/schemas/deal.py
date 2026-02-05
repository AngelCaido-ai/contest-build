from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DealStatus


class DealCreate(BaseModel):
    listing_id: int | None = None
    request_id: int | None = None
    channel_id: int | None = None
    price: float | None = None
    format: str | None = None
    brief: str | None = None
    publish_at: datetime | None = None
    verification_window: int | None = None


class DealTermsUpdate(BaseModel):
    actor_tg_user_id: int | None = None
    price: float | None = None
    format: str | None = None
    publish_at: datetime | None = None
    verification_window: int | None = None


class DealPublishAtUpdate(BaseModel):
    actor_tg_user_id: int | None = None
    publish_at: datetime | None = None


class DealStatusUpdate(BaseModel):
    actor_tg_user_id: int | None = None
    status: DealStatus


class DealOut(BaseModel):
    id: int
    listing_id: int | None
    request_id: int | None
    advertiser_id: int
    channel_id: int
    price: float | None
    format: str | None
    brief: str | None
    publish_at: datetime | None
    verification_window: int | None
    status: DealStatus
    posted_message_id: int | None
    posted_at: datetime | None
    verification_started_at: datetime | None
    tampered: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
