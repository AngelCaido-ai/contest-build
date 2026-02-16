from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChannelStatsOut(BaseModel):
    id: int
    channel_id: int
    subscribers: int | None
    views_per_post: float | None
    shares_per_post: float | None = None
    reactions_per_post: float | None = None
    enabled_notifications: float | None = None

    subscribers_prev: int | None = None
    views_per_post_prev: float | None = None
    shares_per_post_prev: float | None = None
    reactions_per_post_prev: float | None = None

    languages_json: dict | None
    premium_json: dict | None
    updated_at: datetime
    source: str | None

    model_config = ConfigDict(from_attributes=True)
