from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChannelStatsOut(BaseModel):
    id: int
    channel_id: int
    subscribers: int | None
    views_per_post: int | None
    languages_json: dict | None
    premium_json: dict | None
    updated_at: datetime
    source: str | None

    model_config = ConfigDict(from_attributes=True)
