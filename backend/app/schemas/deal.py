from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DealStatus
from app.schemas.event import DealEventOut


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


class DealAdvertiserBriefCreate(BaseModel):
    text: str | None = None
    publish_at: datetime | None = None
    media_file_ids: list[dict] | list[str] | None = None


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


class DealChannelBrief(BaseModel):
    id: int
    username: str | None
    title: str | None
    subscribers: int | None = None
    views_per_post: float | None = None
    shares_per_post: float | None = None
    reactions_per_post: float | None = None
    enabled_notifications: float | None = None
    subscribers_prev: int | None = None
    views_per_post_prev: float | None = None
    shares_per_post_prev: float | None = None
    reactions_per_post_prev: float | None = None

    model_config = ConfigDict(from_attributes=True)


class DealAdvertiserBrief(BaseModel):
    id: int
    tg_username: str | None

    model_config = ConfigDict(from_attributes=True)


class DealDetailOut(DealOut):
    channel_info: DealChannelBrief | None = None
    advertiser_info: DealAdvertiserBrief | None = None
    events: list[DealEventOut] = []
