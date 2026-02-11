from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.channel_stats import ChannelStatsOut


class ListingCreate(BaseModel):
    channel_id: int
    price_ton: float | None = None
    price_usd: float | None = None
    format: str | None = "post"
    categories: list[str] | None = None
    constraints: dict | None = None
    active: bool | None = True


class ListingUpdate(BaseModel):
    price_ton: float | None = None
    price_usd: float | None = None
    format: str | None = None
    categories: list[str] | None = None
    constraints: dict | None = None
    active: bool | None = None


class ListingOut(BaseModel):
    id: int
    channel_id: int
    price_ton: float | None
    price_usd: float | None
    format: str
    categories: list[str] | None
    constraints: dict | None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChannelBriefOut(BaseModel):
    id: int
    username: str | None
    title: str | None
    stats: ChannelStatsOut | None = None

    model_config = ConfigDict(from_attributes=True)


class ListingDetailOut(ListingOut):
    channel: ChannelBriefOut | None = None
