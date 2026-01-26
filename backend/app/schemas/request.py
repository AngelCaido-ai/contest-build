from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RequestCreate(BaseModel):
    budget: float | None = None
    niche: str | None = None
    languages: list[str] | None = None
    min_subs: int | None = None
    min_views: int | None = None
    dates: dict | None = None
    brief: str | None = None


class RequestUpdate(BaseModel):
    budget: float | None = None
    niche: str | None = None
    languages: list[str] | None = None
    min_subs: int | None = None
    min_views: int | None = None
    dates: dict | None = None
    brief: str | None = None


class RequestOut(BaseModel):
    id: int
    advertiser_id: int
    budget: float | None
    niche: str | None
    languages: list[str] | None
    min_subs: int | None
    min_views: int | None
    dates: dict | None
    brief: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
